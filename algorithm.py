import sqlite3
import math
import logging
import time
import threading
from itertools import groupby
from functools import lru_cache
from collections import defaultdict
from data import (
    get_teacher, get_subject, get_student,
    get_subject_teacher, get_subject_student, get_hour_blocker
)
from ortools.sat.python import cp_model
import statistics
import multiprocessing as mp
from multiprocessing import Manager
import copy

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Constants ---
PERIODS_PER_DAY = 10
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
MAX_SOLVER_ITERATIONS = 2000  # Maximum iterations
IMPROVEMENT_THRESHOLD = 200  # How many iterations without improvement before resetting
PROGRESS_INTERVAL = 100  # How often to log progress

# --- Global counters for periodic summary ---
backtrack_calls = 0
cp_start_time = 0.0

def periodic_summary():
    # Runs every 5 seconds, logs summary
    while True:
        time.sleep(5)
        elapsed = time.time() - cp_start_time
        logger.info(f"[Summary] elapsed={elapsed:.1f}s, backtracks={backtrack_calls}")

# --- Data Loading ---
def load_data():
    teachers = {t[0]: t for t in get_teacher()}
    subjects = {s[0]: s for s in get_subject()}
    students_raw = get_student()
    subject_teachers = get_subject_teacher()

    # Fix subject_students loading - handle JSON array of subject IDs
    subj_students = {}
    for row in get_subject_student():
        import json
        subject_ids = json.loads(row[1])  # Load JSON array of subject IDs
        student_id = row[3]
        for sid in subject_ids:
            subj_students.setdefault(sid, set()).add(student_id)

    hb_row = get_hour_blocker()[0]
    hour_blocker = {
        day: [hb_row[i*PERIODS_PER_DAY + p] for p in range(PERIODS_PER_DAY)]
        for i, day in enumerate(DAYS)
    }
    logger.info(f"Loaded {len(teachers)} teachers, {len(subjects)} subjects, {len(students_raw)} students")
    return teachers, subjects, students_raw, subject_teachers, subj_students, hour_blocker

def validate_student_schedules(sessions):
    """Validate that all students can theoretically attend their classes"""
    student_hours = {}
    conflicts = []
    
    # Count total hours per student per day
    for sess in sessions:
        total_slots = len(sess['candidates'])
        slots_per_day = {day: 0 for day in range(len(DAYS))}
        for slot in sess['candidates']:
            day = slot // PERIODS_PER_DAY
            slots_per_day[day] += 1
            
        for student in sess['students']:
            if student not in student_hours:
                student_hours[student] = {day: [] for day in range(len(DAYS))}
            
            # Check if student has enough slots available
            for day, count in slots_per_day.items():
                if count > 0:
                    student_hours[student][day].append(sess['id'])
                    if len(student_hours[student][day]) > PERIODS_PER_DAY:
                        conflicts.append((student, day, student_hours[student][day]))

    if conflicts:
        logger.error("Found student scheduling conflicts:")
        for student, day, sessions in conflicts:
            logger.error(f"Student {student} has too many sessions on {DAYS[day]}: {sessions}")
        return False
    return True

# --- Validation Functions ---
def validate_input_data(teachers, subjects, subject_teachers, subj_students):
    """Validate input data consistency"""
    errors = []
    
    # Check teacher availability
    for tid, teacher in teachers.items():
        available_days = sum(1 for day in range(4) if teacher[4 + day])
        if available_days == 0:
            errors.append(f"Teacher {tid} has no available days")
    
    # Check subject hours vs available slots
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        if sid not in subjects:
            errors.append(f"Subject {sid} not found for teacher {tid}")
            continue
        subject = subjects[sid]
        teacher = teachers.get(tid)
        if not teacher:
            errors.append(f"Teacher {tid} not found for subject {sid}")
            continue
            
        # Calculate available slots
        available_slots = 0
        for day in range(4):
            if teacher[4 + day]:
                available_slots += PERIODS_PER_DAY
                
        required_slots = subject[3]  # number_of_hours_per_week
        if available_slots < required_slots:
            errors.append(f"Subject {sid} needs {required_slots} slots but teacher {tid} only has {available_slots} available")
    
    if errors:
        for error in errors:
            logger.error(f"Validation error: {error}")
        return False
    return True

# --- Session Creation ---
def build_sessions(teachers, subjects, subject_teachers, subj_students, hour_blocker):
    if not validate_input_data(teachers, subjects, subject_teachers, subj_students):
        logger.error("Input data validation failed")
        return []

    # Build subject-teacher-group mapping first
    subject_teacher_groups = {}  # {sid: [(tid, group_count), ...]}
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        group_count = max(1, st[7])
        subject_teacher_groups.setdefault(sid, []).append((tid, group_count))

    sessions = []
    
    for sid, subj in subjects.items():
        hours_per_week = subj[3]
        maxpd = min(subj[4], 2)  # Maximum sessions per day
        is_parallel = subjects[sid][7] == 1  # Check if subject is parallel
        teacher_groups = subject_teacher_groups.get(sid, [])
        all_students = sorted(list(subj_students.get(sid, set())))

        if is_parallel:
            # For parallel subjects, create one session per required hour with all teachers
            teacher_list = [t[0] for t in teacher_groups]
            for hour in range(hours_per_week):
                session = create_session(
                    sid=sid,
                    teachers_list=teacher_list,  # All teachers together
                    hour=hour,
                    students=all_students,  # All students together
                    teacher_info=teachers,  # Pass full teachers dict for availability check
                    maxpd=maxpd,
                    hour_blocker=hour_blocker,
                    parallel_group=None  # No parallel group needed since it's one big session
                )
                sessions.append(session)
        else:
            # Handle regular sessions as before
            for tid, group_count in teacher_groups:
                for hour in range(hours_per_week):
                    session = create_session(
                        sid=sid,
                        teachers_list=[tid],
                        hour=hour,
                        students=all_students,
                        teacher_info=teachers[tid],
                        maxpd=maxpd,
                        hour_blocker=hour_blocker,
                        parallel_group=None
                    )
                    sessions.append(session)

    return sessions

def create_session(sid, teachers_list, hour, students, teacher_info, maxpd, hour_blocker, parallel_group=None):
    """Modified to handle multiple teachers per session"""
    cand = []
    # Find slots where ALL teachers are available
    for di, day in enumerate(DAYS):
        all_available = True
        for tid in teachers_list:
            # For regular sessions, teacher_info is a single teacher's info
            # For parallel sessions, it's the full teachers dictionary
            teacher = teacher_info[tid] if isinstance(teacher_info, dict) else teacher_info
            if not teacher[4 + di]:  # Check day availability (mon=4, tue=5, wed=6, thu=7)
                all_available = False
                break
        
        if all_available:
            for p in range(PERIODS_PER_DAY):
                if hour_blocker[day][p] == 1:
                    cand.append(di * PERIODS_PER_DAY + p)
    
    return {
        'id': f"S{sid}_H{hour}",
        'subject': sid,
        'teachers': teachers_list,  # Now a list of teachers
        'group': 1,
        'students': students,
        'candidates': cand,
        'max_per_day': maxpd,
        'parallel_with': parallel_group,
        'is_parallel': parallel_group is not None
    }

def evaluate_schedule(schedule, all_sessions):
    """Modified evaluation with higher penalties for critical constraints"""
    score = 0
    scheduled = defaultdict(int)
    required = defaultdict(int)
    
    # Count required sessions
    for sess in all_sessions:
        required[sess['subject']] += 1
    
    # Track subject occurrences per day and teacher assignments
    subject_daily = defaultdict(lambda: defaultdict(int))
    teacher_slots = defaultdict(set)
    
    for (day, period), slots in schedule.items():
        slot_num = day * PERIODS_PER_DAY + period
        teachers_this_slot = set()
        students_this_slot = set()
        
        for sess in slots:
            scheduled[sess['subject']] += 1
            
            # Teacher conflicts (increased penalty)
            for tid in sess['teachers']:
                if tid in teachers_this_slot:
                    score += 5000  # Increased from 2000
                teachers_this_slot.add(tid)
                teacher_slots[tid].add(slot_num)
            
            # Student conflicts
            student_set = set(sess['students'])
            if students_this_slot & student_set:
                score += 2000  # Increased from 1500
            students_this_slot |= student_set
            
            # Track daily limits
            subject_daily[sess['subject']][day] += 1
            if subject_daily[sess['subject']][day] > sess['max_per_day']:
                score += 1000  # Increased from 800
    
    # Missing or extra sessions penalty (highest priority)
    for subject, req_count in required.items():
        diff = abs(scheduled[subject] - req_count)
        if diff > 0:
            score += diff * 10000  # Significantly increased from 3000
    
    return score

def greedy_initial(sessions):
    """Improved initial solution generation with strict session count enforcement"""
    # Track required and scheduled sessions per subject
    subject_requirements = defaultdict(int)
    for sess in sessions:
        subject_requirements[sess['subject']] += 1
    
    # Sort sessions prioritizing those with most unmet requirements
    sorted_sessions = sorted(sessions, key=lambda s: (
        subject_requirements[s['subject']],  # Most required sessions first
        -len(s['students']),  # More students = more constraints
        len(s['candidates'])  # Fewer candidates = more constrained
    ), reverse=True)
    
    teacher_schedule = defaultdict(set)  # Track teacher assignments
    subject_daily = defaultdict(lambda: defaultdict(int))
    schedule = {}
    unplaced = []
    
    # First pass - try to place all required sessions
    for sess in sorted_sessions:
        placed = False
        # Sort candidate slots by preference
        sorted_slots = sorted(
            sess['candidates'],
            key=lambda slot: (
                len(schedule.get((slot // PERIODS_PER_DAY, slot % PERIODS_PER_DAY), [])),
                abs((slot % PERIODS_PER_DAY) - PERIODS_PER_DAY//2)  # Prefer middle periods
            )
        )
        
        for slot in sorted_slots:
            day = slot // PERIODS_PER_DAY
            period = slot % PERIODS_PER_DAY
            key = (day, period)
            
            # Skip if exceeds daily limit
            if subject_daily[sess['subject']][day] >= sess['max_per_day']:
                continue
            
            # Check teacher availability
            if any(slot in teacher_schedule[tid] for tid in sess['teachers']):
                continue
                
            # Check slot capacity and conflicts
            current_slot = schedule.get(key, [])
            if len(current_slot) >= 3:
                continue
                
            # Check student conflicts
            if any(set(sess['students']) & set(s['students']) for s in current_slot):
                continue
            
            # Place session
            schedule.setdefault(key, []).append(sess)
            for tid in sess['teachers']:
                teacher_schedule[tid].add(slot)
            subject_daily[sess['subject']][day] += 1
            placed = True
            break
            
        if not placed:
            unplaced.append(sess)
    
    # Second pass - try to place unplaced sessions in any valid slot
    for sess in unplaced:
        best_slot = None
        best_score = float('inf')
        
        for slot in sess['candidates']:
            day = slot // PERIODS_PER_DAY
            period = slot % PERIODS_PER_DAY
            key = (day, period)
            
            if subject_daily[sess['subject']][day] >= sess['max_per_day']:
                continue
                
            current_slot = schedule.get(key, [])
            if len(current_slot) >= 3:
                continue
                
            # Calculate slot score (lower is better)
            score = 0
            # Penalize teacher conflicts
            if any(slot in teacher_schedule[tid] for tid in sess['teachers']):
                score += 1000
            # Penalize student conflicts
            if any(set(sess['students']) & set(s['students']) for s in current_slot):
                score += 500
            # Prefer middle periods
            score += abs(period - PERIODS_PER_DAY//2)
            
            if score < best_score:
                best_score = score
                best_slot = slot
        
        if best_slot is not None:
            day = best_slot // PERIODS_PER_DAY
            period = best_slot % PERIODS_PER_DAY
            key = (day, period)
            schedule.setdefault(key, []).append(sess)
            for tid in sess['teachers']:
                teacher_schedule[tid].add(best_slot)
            subject_daily[sess['subject']][day] += 1
    
    return schedule

# --- Solver Process ---
@lru_cache(maxsize=1024)
def get_parallel_group_requirements(subject_id, group_id):
    """Cache parallel group requirements. Now uses immutable types."""
    return f"P{subject_id}_{group_id}"

def solver_process(sessions, shared_best_score, shared_best_schedule, shared_lock, process_id, time_limit):
    """Modified solver process to handle partial solutions better"""
    start_time = time.time()
    last_log_time = start_time
    last_log_iterations = 0
    iteration_times = []
    iter_start = time.time()  # Initialize first iteration timing
    
    local_best_score = float('inf')
    local_best_schedule = {}
    
    # Pre-compute compatible sessions using frozensets for faster lookups
    compatible = precompute_compatible_slots(sessions)
    session_lookup = {s['id']: i for i, s in enumerate(sessions)}
    
    iterations = 0
    stagnant_iterations = 0
    
    # Initialize with multiple starting points
    schedules = [greedy_initial(sessions) for _ in range(3)]
    current_schedule = min(schedules, key=lambda s: evaluate_schedule(s, sessions))
    
    # Get initial score
    current_score = evaluate_schedule(current_schedule, sessions)
    if current_score < local_best_score:
        local_best_score = current_score
        local_best_schedule = copy.deepcopy(current_schedule)
        with shared_lock:
            if current_score < shared_best_score.value:
                shared_best_score.value = current_score
                shared_best_schedule.clear()
                shared_best_schedule.update(local_best_schedule)
    
    while iterations < MAX_SOLVER_ITERATIONS and time.time() - start_time < time_limit:
        iter_time = time.time() - iter_start  # Calculate previous iteration time
        iteration_times.append(iter_time)
        
        iterations += 1
        iter_start = time.time()  # Start timing new iteration
        
        if iterations % PROGRESS_INTERVAL == 0:
            current_time = time.time()
            elapsed_since_log = current_time - last_log_time
            
            if iteration_times:
                recent_times = iteration_times[-min(100, len(iteration_times)):]
                avg_time = sum(recent_times) / len(recent_times)
                batch_time = elapsed_since_log / min(PROGRESS_INTERVAL, iterations)
                
                logger.info(
                    f"Process {process_id}: "
                    f"Iteration {iterations}/{MAX_SOLVER_ITERATIONS}, "
                    f"score: {local_best_score}, "
                    f"iter time: {avg_time*1000:.1f}ms, "
                    f"batch: {batch_time*1000:.1f}ms/iter"
                )
            
            last_log_time = current_time
            last_log_iterations = iterations

        # Early exit if perfect solution found
        if local_best_score == 0:
            with shared_lock:
                shared_best_score.value = 0
                shared_best_schedule.update(local_best_schedule)
            return

        if stagnant_iterations >= IMPROVEMENT_THRESHOLD:
            current_schedule = greedy_initial(sessions)
            stagnant_iterations = 0
            continue

        # Smart move selection - focus on parallel groups first
        move_candidates = []
        for (day, period), slots in current_schedule.items():
            if not slots:  # Skip empty slots
                continue
            for i, sess in enumerate(slots):
                if i >= len(slots):  # Ensure index is valid
                    continue
                if sess['parallel_with']:  # Prioritize parallel sessions
                    move_candidates.insert(0, (day, period, i))
                else:
                    move_candidates.append((day, period, i))
        
        improved = False
        for day, period, sess_idx in move_candidates[:min(len(move_candidates), 10)]:
            # Validate slot exists and index is in range
            if (day, period) not in current_schedule or \
               sess_idx >= len(current_schedule[(day, period)]):
                continue

            # Try moving this session to different slots
            try:
                original_slot = current_schedule[(day, period)].pop(sess_idx)
            except IndexError:
                # Skip if index becomes invalid (due to concurrent modifications)
                continue

            for new_slot in original_slot['candidates']:
                new_day = new_slot // PERIODS_PER_DAY
                new_period = new_slot % PERIODS_PER_DAY
                new_key = (new_day, new_period)
                
                if new_key == (day, period):
                    continue
                    
                target_slot = current_schedule.get(new_key, [])
                if len(target_slot) >= 3:
                    continue
                    
                # Check if move is valid
                if not any(tid in [s['teachers'] for s in target_slot] for tid in original_slot['teachers']) and \
                   not any(set(s['students']) & set(original_slot['students']) for s in target_slot):
                    
                    # Try the move
                    target_slot.append(original_slot)
                    score = evaluate_schedule(current_schedule, sessions)
                    
                    if score < local_best_score:
                        local_best_score = score
                        local_best_schedule = {k: v[:] for k, v in current_schedule.items()}
                        improved = True
                        stagnant_iterations = 0
                    else:
                        # Undo move
                        target_slot.remove(original_slot)
            
            # Put session back if no better position found
            if not improved:
                try:
                    current_schedule[(day, period)].insert(sess_idx, original_slot)
                except IndexError:
                    # If insertion fails, append to end
                    current_schedule[(day, period)].append(original_slot)

        if not improved:
            stagnant_iterations += 1
        else:
            with shared_lock:
                if local_best_score < shared_best_score.value:
                    shared_best_score.value = local_best_score
                    shared_best_schedule.clear()
                    shared_best_schedule.update(local_best_schedule)
                    logger.info(f"Process {process_id}: New best score: {local_best_score}")

# --- Solver with Parallel Processing ---
def solve_timetable(sessions, time_limit=600):
    """Improved solver with parallel processing and partial solution handling"""
    sessions = sorted(sessions, 
                     key=lambda s: (s['parallel_with'] is not None,
                                  len(s['candidates']),
                                  s['max_per_day']), 
                     reverse=True)
                     
    manager = Manager()
    shared_best_score = manager.Value('d', float('inf'))
    shared_best_schedule = manager.dict()
    shared_lock = manager.Lock()
    
    # Store initial solution as fallback
    initial_schedule = greedy_initial(sessions)
    initial_score = evaluate_schedule(initial_schedule, sessions)
    with shared_lock:
        shared_best_score.value = initial_score
        shared_best_schedule.update(initial_schedule)
    
    # Run parallel processes
    num_processes = max(1, mp.cpu_count() - 1)
    processes = []
    for i in range(num_processes):
        p = mp.Process(
            target=solver_process,
            args=(copy.deepcopy(sessions), shared_best_score, shared_best_schedule, 
                  shared_lock, i, time_limit)
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()
        
    if shared_best_score.value == float('inf'):
        logger.warning("No solution found, returning initial solution")
        return initial_schedule
        
    return dict(shared_best_schedule)

# --- Helper Function for Student Sessions ---
def get_student_sessions(sessions):
    """Map each student to all their sessions."""
    student_sessions = {}
    for i, sess in enumerate(sessions):
        for student in sess['students']:
            student_sessions.setdefault(student, []).append(i)
    return student_sessions

def is_perfect_solution(schedule, subjects, sessions):
    """Check if schedule meets all requirements perfectly"""
    # Check subject hours
    scheduled_counts = {}
    for (day, period), slot_sessions in schedule.items():
        for sess in slot_sessions:
            sid = sess['subject']
            scheduled_counts[sid] = scheduled_counts.get(sid, 0) + 1
    
    # Verify all subjects have exact required hours
    for sid, count in scheduled_counts.items():
        if count != sum(1 for s in sessions if s['subject'] == sid):
            return False
    
    # Check daily limits
    day_counts = {}
    for (day, period), slots in schedule.items():
        # Check no more than 3 sessions per slot
        if len(slots) > 3:
            return False
            
        # Check teacher conflicts
        teachers = set()
        for sess in slots:
            for tid in sess['teachers']:
                if tid in teachers:
                    return False
                teachers.add(tid)
            
        # Check student conflicts
        students = set()
        for sess in slots:
            for student in sess['students']:
                if student in students:
                    return False
                students.add(student)
            
        # Check daily subject limits
        for sess in slots:
            key = (day, sess['subject'], sess['group'])
            day_counts[key] = day_counts.get(key, 0) + 1
            if day_counts[key] > sess['max_per_day']:
                return False
    
    return True

def precompute_compatible_slots(sessions):
    """Pre-compute which sessions can be scheduled together"""
    compatible = {}
    for i, sess1 in enumerate(sessions):
        compatible[i] = set()
        for j, sess2 in enumerate(sessions):
            if i != j and not any(tid in sess2['teachers'] for tid in sess1['teachers']) and \
               not set(sess1['students']) & set(sess2['students']):
                # For parallel sessions, they must be scheduled together
                if sess1['parallel_with'] is not None and sess2['parallel_with'] is not None:
                    if sess1['parallel_with'] == sess2['parallel_with']:
                        compatible[i].add(j)  # Always compatible with other parts of same parallel group
                    else:
                        continue  # Different parallel groups can't be in same slot
                else:
                    compatible[i].add(j)
    return compatible

@lru_cache(maxsize=1024)
def get_slot_score(day, period):
    """Cache slot quality scores"""
    # Prefer middle periods and distribute across days
    period_penalty = abs(period - PERIODS_PER_DAY//2) * 2
    return period_penalty + day * 3

@lru_cache(maxsize=1024)
def get_parallel_groups_for_timeslot(slot_sessions_key):
    """Cache parallel group analysis for a given timeslot"""
    return {s['parallel_with'] for s in slot_sessions_key if s['parallel_with']}

def try_place_parallel_group(schedule, sess, slot, compatible_sessions):
    """Try to place all sessions in a parallel group together"""
    if not sess['parallel_with']:
        return True
        
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    key = (day, period)
    current = schedule.get(key, [])
    
    # Get all parallel sessions for this group
    parallel_sessions = [s for s in current 
                       if s['parallel_with'] == sess['parallel_with']]
    
    # Check if adding this session would exceed daily limit
    daily_count = sum(1/s['total_teachers'] for s in parallel_sessions)
    if daily_count + 1/sess['total_teachers'] > sess['max_per_day']:
        return False
    
    # Check slot capacity
    if len(current) + 1 > 3:
        return False
        
    return True

def has_major_conflicts(schedule):
    """Check for deal-breaking conflicts"""
    for sessions in schedule.values():
        # Check teacher conflicts
        teachers = set()
        for sess in sessions:
            for tid in sess['teachers']:
                if tid in teachers:
                    return True
                teachers.add(tid)
    return False

def analyze_schedule_issues(schedule, sessions):
    """Return list of issues with the schedule"""
    issues = []
    
    # Track sessions per subject and daily distribution
    subject_counts = {}
    day_counts = {}
    
    for (day, period), slots in schedule.items():
        for sess in slots:
            sid = sess['subject']
            subject_counts[sid] = subject_counts.get(sid, 0) + 1
            
            # Track daily counts for all subjects the same way
            key = (day, sid)
            day_counts[key] = day_counts.get(key, 0) + 1
            if day_counts[key] > sess['max_per_day']:
                issues.append(f"Subject {sid} exceeds daily limit on {DAYS[day]}")
    
    # Check missing/extra sessions
    for sid, count in subject_counts.items():
        expected = sum(1 for s in sessions if s['subject'] == sid)
        if count != expected:
            issues.append(f"Subject {sid} has {count} sessions (expected {expected})")
    
    return issues

def validate_schedule_completeness(schedule, subjects, all_sessions):
    """Verify that all subjects have their required number of hours scheduled"""
    scheduled_counts = {}
    
    # Count scheduled sessions per subject
    for (day, period), sessions in schedule.items():
        for sess in sessions:
            sid = sess['subject']
            scheduled_counts[sid] = scheduled_counts.get(sid, 0) + 1
            
    # Compare with required hours from subjects table
    issues = []
    for sid, subj in subjects.items():
        required = subj[3]  # number_of_hours_per_week
        actual = scheduled_counts.get(sid, 0)
        if actual != required:
            issues.append(f"Subject {sid} has {actual} sessions (requires {required})")
    
    # Additional validation for parallel groups
    for (day, period), slot_sessions in schedule.items():
        parallel_groups = {}
        for sess in slot_sessions:
            if sess['parallel_with'] is not None:
                base_group = sess['parallel_with']
                if base_group in parallel_groups:
                    # Parallel groups must be scheduled together
                    logger.warning(f"Parallel group violation: {sess['id']} should be with {parallel_groups[base_group]['id']}")
                    issues.append(f"Parallel groups for subject {sess['subject']} must be scheduled together")
                parallel_groups[base_group] = sess
            
    return issues

def validate_teacher_conflicts(schedule):
    """Verify no teacher is scheduled for multiple sessions simultaneously"""
    issues = []
    
    for (day, period), sessions in schedule.items():
        teachers = {}
        for sess in sessions:
            for tid in sess['teachers']:
                if tid in teachers:
                    issues.append(f"Teacher {tid} has multiple sessions on {DAYS[day]} period {period+1}")
                teachers[tid] = sess['id']
            
    return issues

def validate_student_attendance(schedule, sessions):
    """Verify students can attend all their scheduled sessions"""
    issues = []
    
    # Build student schedule map
    student_schedules = {}
    
    for day_period, slot_sessions in schedule.items():
        if not isinstance(day_period, tuple):
            continue
            
        day, period = day_period
        for sess in slot_sessions:
            for student in sess['students']:
                if student not in student_schedules:
                    student_schedules[student] = {d: set() for d in range(len(DAYS))}
                student_schedules[student][day].add(period)
                
    # Check conflicts
    for student, schedule in student_schedules.items():
        for day, periods in schedule.items():
            # Check total periods per day
            if len(periods) > PERIODS_PER_DAY:
                issues.append(f"Student {student} has too many sessions ({len(periods)}) on {DAYS[day]}")
            
            # Check simultaneous sessions
            slots_this_day = []
            for day_period, slot_sessions in schedule.items():
                if not isinstance(day_period, tuple):
                    continue
                d, p = day_period
                if d == day:
                    student_sessions = [s for s in slot_sessions if student in s['students']]
                    if len(student_sessions) > 1:
                        issues.append(f"Student {student} has conflicting sessions on {DAYS[day]} period {p+1}")
                        
    return issues

# --- Main ---
if __name__ == '__main__':
    teachers, subjects, students_raw, st_map, stud_map, hb = load_data()
    sessions = build_sessions(teachers, subjects, st_map, stud_map, hb)
    
    # Single run with longer time limit
    MAX_SOLVER_ITERATIONS = 3000
    schedule = solve_timetable(sessions, time_limit=1200)  # 20 minutes
    
    if schedule:
        score = evaluate_schedule(schedule, sessions)
        print(f"\nFound solution with score: {score}")
        
        # Collect all validation issues
        all_issues = []
        all_issues.extend(analyze_schedule_issues(schedule, sessions))
        all_issues.extend(validate_schedule_completeness(schedule, subjects, sessions))
        all_issues.extend(validate_teacher_conflicts(schedule))
        all_issues.extend(validate_student_attendance(schedule, sessions))
        
        if all_issues:
            print("\nSchedule Issues Found:")
            for issue in sorted(set(all_issues)):  # Remove duplicates and sort
                print(f"- {issue}")
        else:
            print("\nNo issues found - schedule is valid!")
        
        # Print schedule in readable format with fixed string conversion
        print("\nGenerated Schedule:")
        for day_idx, day in enumerate(DAYS):
            print(f"\n=== {day.upper()} ===")
            for period in range(PERIODS_PER_DAY):
                key = (day_idx, period)
                if key in schedule:
                    sessions_here = schedule[key]
                    sessions_str = ", ".join(f"{s['subject']} (T:{','.join(str(t) for t in s['teachers'])})" 
                                           for s in sessions_here)
                    print(f"Period {period+1}: {sessions_str}")
                else:
                    print(f"Period {period+1}: ---")
    else:
        print("No solution found")
        exit(1)
