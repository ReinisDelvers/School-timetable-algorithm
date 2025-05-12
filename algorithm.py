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
MAX_SOLVER_ITERATIONS = 20  # Maximum iterations
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

# --- Helper Function ---
def group_students_by_subjects(subj_students):
    """Group students that have exactly the same subject selections"""
    # Build student -> subjects mapping
    student_subjects = defaultdict(set)
    for sid, students in subj_students.items():
        for student in students:
            student_subjects[student].add(sid)
    
    # Group students by their subject combinations
    groups = defaultdict(list)
    for student, subjects in student_subjects.items():
        group_key = frozenset(subjects)
        groups[group_key].append(student)
    
    # Create reverse mapping of student to group representative
    student_to_group = {}
    for subjects, students in groups.items():
        group_rep = students[0]  # Use first student as group representative
        for student in students:
            student_to_group[student] = group_rep
    
    # Update subj_students to use group representatives
    grouped_subj_students = defaultdict(set)
    for sid, students in subj_students.items():
        for student in students:
            grouped_subj_students[sid].add(student_to_group[student])
    
    return grouped_subj_students, student_to_group

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

    # Group students with identical subject selections
    grouped_subj_students, student_groups = group_students_by_subjects(subj_students)
    
    hb_row = get_hour_blocker()[0]
    hour_blocker = {
        day: [hb_row[i*PERIODS_PER_DAY + p] for p in range(PERIODS_PER_DAY)]
        for i, day in enumerate(DAYS)
    }
    
    original_student_count = len({s for students in subj_students.values() for s in students})
    grouped_student_count = len({s for students in grouped_subj_students.values() for s in students})
    logger.info(f"Loaded {len(teachers)} teachers, {len(subjects)} subjects")
    logger.info(f"Grouped {original_student_count} students into {grouped_student_count} unique combinations")
    
    return teachers, subjects, students_raw, subject_teachers, grouped_subj_students, hour_blocker, student_groups

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
    
    # Check subject groups vs teacher assignments
    subject_teacher_counts = defaultdict(int)
    subject_group_counts = {}
    
    # Count teachers per subject
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        subject_teacher_counts[sid] += 1
    
    # Get group counts per subject
    for sid, subj in subjects.items():
        # Skip subjects marked as parallel (parallel_subject_groups = 1)
        if subj[7] != 1:  # Check if not a parallel subject
            subject_group_counts[sid] = subj[2]  # group_number from subjects table
    
    # Compare teachers vs groups (only for non-parallel subjects)
    for sid, teacher_count in subject_teacher_counts.items():
        # Only check if subject is in group_counts (non-parallel subjects)
        if sid in subject_group_counts:
            group_count = subject_group_counts[sid]
            if teacher_count > group_count:
                errors.append(f"Subject {sid} has {teacher_count} teachers but only {group_count} groups")
    
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

    # Track required sessions per subject
    subject_session_counts = defaultdict(int)
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

        # Validate we won't exceed required hours
        if subject_session_counts[sid] >= hours_per_week:
            logger.warning(f"Skipping additional sessions for subject {sid} - already at required hours {hours_per_week}")
            continue

        if is_parallel:
            # For parallel subjects, create one session per required hour with all teachers
            teacher_list = [t[0] for t in teacher_groups]
            for hour in range(hours_per_week):
                if subject_session_counts[sid] >= hours_per_week:
                    break
                session = create_session(
                    sid=sid,
                    teachers_list=teacher_list,
                    hour=hour,
                    students=all_students,
                    teacher_info=teachers,
                    maxpd=maxpd,
                    hour_blocker=hour_blocker,
                    parallel_group=None
                )
                sessions.append(session)
                subject_session_counts[sid] += 1
        else:
            # Handle regular sessions as before
            for tid, group_count in teacher_groups:
                remaining_hours = hours_per_week - subject_session_counts[sid]
                for hour in range(min(remaining_hours, hours_per_week)):
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
                    subject_session_counts[sid] += 1

    # Validate final session counts
    for sid, count in subject_session_counts.items():
        required = subjects[sid][3]
        if count != required:
            logger.error(f"Subject {sid} has incorrect number of sessions: {count} (required {required})")

    return sessions

def create_session(sid, teachers_list, hour, students, teacher_info, maxpd, hour_blocker, parallel_group=None):
    """Modified to handle multiple teachers per session and validate hours"""
    # Add validation to prevent over-creation of sessions
    session = {
        'id': f"S{sid}_H{hour}",
        'subject': sid,
        'teachers': teachers_list,
        'group': 1,
        'students': students,
        'candidates': [],  # Will be populated below
        'max_per_day': maxpd,
        'parallel_with': parallel_group,
        'is_parallel': parallel_group is not None,
        'hour': hour  # Add hour tracking
    }
    
    # Find slots where ALL teachers are available
    for di, day in enumerate(DAYS):
        all_available = True
        for tid in teachers_list:
            teacher = teacher_info[tid] if isinstance(teacher_info, dict) else teacher_info
            if not teacher[4 + di]:
                all_available = False
                break
        
        if all_available:
            for p in range(PERIODS_PER_DAY):
                if hour_blocker[day][p] == 1:
                    session['candidates'].append(di * PERIODS_PER_DAY + p)
    
    return session

def evaluate_schedule(schedule, all_sessions):
    """Modified evaluation with focus on shorter days"""
    score = 0
    scheduled = defaultdict(int)
    required = defaultdict(int)
    student_schedule = defaultdict(lambda: defaultdict(set))
    
    # Track last used period for each day
    last_period_by_day = defaultdict(int)
    
    # Count required sessions and track last period used per day
    for sess in all_sessions:
        required[sess['subject']] += 1
    
    for (day, period), slots in schedule.items():
        if slots:  # If there are sessions in this slot
            last_period_by_day[day] = max(last_period_by_day[day], period + 1)
        teachers_this_slot = set()
        
        for sess in slots:
            subject = sess['subject']
            scheduled[subject] += 1
            
            # Existing conflict penalties
            for student in sess['students']:
                if period in student_schedule[student][day]:
                    score += 8000
                student_schedule[student][day].add(period)
            
            for tid in sess['teachers']:
                if tid in teachers_this_slot:
                    score += 10000
                teachers_this_slot.add(tid)
    
    # Add penalties for late periods and using later days
    day_penalties = 0
    for day, last_period in last_period_by_day.items():
        # Exponential penalty for periods after the 6th
        if last_period > 6:
            day_penalties += (last_period - 6) ** 3 * 500
        
        # Penalty for using later days when early days are shorter
        if day > 0 and last_period > last_period_by_day.get(day-1, 0):
            day_penalties += 1000 * (day + 1)
    
    score += day_penalties
    
    # Keep existing penalties for incorrect session counts
    for subject, req_count in required.items():
        actual = scheduled[subject]
        if actual != req_count:
            score += abs(actual - req_count) * 20000
    
    return score

def calculate_strict_score(sess, key, slot, schedule, subject_daily,
                         student_subject_sessions, subject_requirements):
    """Modified scoring to strongly prefer earlier slots"""
    score = 0
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    
    # Exponential penalty for later periods
    score += period ** 3 * 30
    
    # Strong penalty for using later days if earlier days aren't full
    prev_days_usage = [0] * day
    for (d, p), slots in schedule.items():
        if d < day and slots:
            prev_days_usage[d] = max(prev_days_usage[d], p + 1)
    
    # Large penalty if previous days have empty early slots
    for d, usage in enumerate(prev_days_usage):
        if usage < 6:  # If day has less than 6 periods used
            score += (day - d) * 800  # Higher penalty for using later days
    
    return score

def greedy_initial(sessions):
    """Modified to prefer earlier slots"""
    # Map to track subject sessions already scheduled for each student
    student_subject_sessions = defaultdict(lambda: defaultdict(int))
    subject_requirements = defaultdict(int)
    subject_scheduled = defaultdict(int)
    student_schedule = defaultdict(lambda: defaultdict(set))
    
    # Pre-compute requirements
    for sess in sessions:
        sid = sess['subject']
        subject_requirements[sid] += 1
    
    # Sort sessions with improved prioritization
    def session_priority(sess):
        sid = sess['subject']
        required = subject_requirements[sid]
        current = subject_scheduled[sid]
        
        # Prioritize sessions with earlier available slots
        earliest_slot = min(sess['candidates']) if sess['candidates'] else PERIODS_PER_DAY * len(DAYS)
        
        return (
            current == 0,  # First priority: subjects with no sessions
            required - current,  # Second: more remaining sessions needed
            -earliest_slot,  # Third: prefer sessions with earlier available slots
            -len(sess['candidates']),
            len(sess['students'])
        )
    
    sorted_sessions = sorted(sessions, key=session_priority, reverse=True)
    schedule = {}
    teacher_schedule = defaultdict(set)
    subject_daily = defaultdict(lambda: defaultdict(int))
    
    # Place sessions with strict validation
    for sess in sorted_sessions:
        sid = sess['subject']
        
        # Skip if subject requirements are met
        if subject_scheduled[sid] >= subject_requirements[sid]:
            continue
            
        # Skip if any student already has enough sessions for this subject
        skip = False
        for student in sess['students']:
            if student_subject_sessions[student][sid] >= subject_requirements[sid]:
                skip = True
                break
        if skip:
            continue
            
        best_slot = find_best_slot_strict(
            sess, schedule, teacher_schedule,
            subject_daily, student_schedule,
            student_subject_sessions, subject_requirements
        )
        
        if best_slot is not None:
            place_session_strict(
                sess, best_slot, schedule,
                teacher_schedule, subject_daily,
                subject_scheduled, student_schedule,
                student_subject_sessions, subject_requirements
            )
    
    return schedule

def find_best_slot_strict(sess, schedule, teacher_schedule, subject_daily,
                         student_schedule, student_subject_sessions, subject_requirements):
    """Find best slot with strict student and subject validation"""
    best_slot = None
    min_score = float('inf')
    sid = sess['subject']
    
    for slot in sess['candidates']:
        day = slot // PERIODS_PER_DAY
        period = slot % PERIODS_PER_DAY
        key = (day, period)
        
        # Skip if basic constraints are violated
        if (subject_daily[sid][day] >= sess['max_per_day'] or
            len(schedule.get(key, [])) >= 3):
            continue
            
        # Check teacher conflicts
        if any(slot in teacher_schedule[tid] for tid in sess['teachers']):
            continue
            
        # Check student conflicts
        has_student_conflict = False
        if key in schedule:
            for other in schedule[key]:
                if set(sess['students']) & set(other['students']):
                    has_student_conflict = True
                    break
        
        if has_student_conflict:
            continue
            
        # Calculate slot score
        score = calculate_strict_score(
            sess, key, slot,
            schedule, subject_daily,
            student_subject_sessions, subject_requirements
        )
        
        if score < min_score:
            min_score = score
            best_slot = slot
    
    return best_slot

def place_session_strict(sess, slot, schedule, teacher_schedule, subject_daily,
                        subject_scheduled, student_schedule, student_subject_sessions,
                        subject_requirements):
    """Place session with strict validation"""
    sid = sess['subject']
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    key = (day, period)
    
    # Add session to schedule
    schedule.setdefault(key, []).append(sess)
    
    # Update tracking structures
    for tid in sess['teachers']:
        teacher_schedule[tid].add(slot)
    
    for student in sess['students']:
        student_schedule[student][day].add(period)
        student_subject_sessions[student][sid] += 1
    
    subject_daily[sid][day] += 1
    subject_scheduled[sid] += 1

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
    # Get all unique subject IDs from sessions 
    subject_ids = {s['subject'] for s in sessions}
    
    # Build subject info dict
    subjects = {}
    for sid in subject_ids:
        for s in sessions:
            if s['subject'] == sid:
                subjects[sid] = {
                    'id': sid,
                    'hours_per_week': sum(1 for x in sessions if x['subject'] == sid),
                    'max_per_day': s['max_per_day']
                }
                break

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

    final_schedule = dict(shared_best_schedule)
    
    # Run diagnostics on final schedule
    logger.info("Running final schedule diagnostics...")
    
    # Check for teacher conflicts
    teacher_issues = validate_teacher_conflicts(final_schedule)
    if teacher_issues:
        logger.error("Found teacher conflicts:")
        for issue in teacher_issues:
            logger.error(f"  - {issue}")
    else:
        logger.info("No teacher conflicts found")
    
    # Check for student attendance issues
    student_issues = validate_student_attendance(final_schedule, sessions)
    if student_issues:
        logger.error("Found student scheduling issues:")
        for issue in student_issues:
            logger.error(f"  - {issue}")
    else:
        logger.info("No student scheduling issues found")
    
    # Check schedule completeness using subjects dict we created
    completeness_issues = validate_schedule_completeness(final_schedule, subjects, sessions)
    if completeness_issues:
        logger.error("Found schedule completeness issues:")
        for issue in completeness_issues:
            logger.error(f"  - {issue}")
    else:
        logger.info("All required sessions scheduled correctly")
    
    # Run comprehensive constraint check using subjects dict
    if check_schedule_feasibility(final_schedule, sessions, subjects):
        logger.info("Final schedule passed all feasibility checks")
    
    # Get students data before returning
    students_raw = get_student()
    students_dict = {s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()} for s in students_raw}
    
    return final_schedule, students_dict

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
        required = subj['hours_per_week']
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
def verify_schedule_constraints(schedule, sessions, subjects):
    """Perform comprehensive schedule verification"""
    issues = {
        'teacher_conflicts': [],
        'student_conflicts': [],
        'subject_requirements': [],
        'unscheduled': []
    }
    
    # Track teacher assignments
    teacher_schedule = defaultdict(list)
    # Track student assignments
    student_schedule = defaultdict(list)
    # Track subject counts
    subject_counts = defaultdict(int)
    
    for (day, period), slots in schedule.items():
        time_slot = f"{DAYS[day]} period {period+1}"
        
        # Check teacher conflicts
        teachers_this_slot = {}
        for sess in slots:
            for tid in sess['teachers']:
                if tid in teachers_this_slot:
                    issues['teacher_conflicts'].append(
                        f"Teacher {tid} has multiple sessions in {time_slot}: "
                        f"{teachers_this_slot[tid]} and {sess['id']}"
                    )
                teachers_this_slot[tid] = sess['id']
                teacher_schedule[tid].append((day, period))
        
        # Check student conflicts
        students_this_slot = {}
        for sess in slots:
            for student in sess['students']:
                if student in students_this_slot:
                    issues['student_conflicts'].append(
                        f"Student {student} has multiple sessions in {time_slot}: "
                        f"{students_this_slot[student]} and {sess['id']}"
                    )
                students_this_slot[student] = sess['id']
                student_schedule[student].append((day, period))
            
            # Count subject occurrences
            subject_counts[sess['subject']] += 1
    
    # Verify subject requirements are met
    for sid, subj in subjects.items():
        required = subj['hours_per_week']
        actual = subject_counts[sid]
        if actual != required:
            issues['subject_requirements'].append(
                f"Subject {sid} has {actual} sessions (requires {required})"
            )
    
    # Check for completely unscheduled sessions
    scheduled_sessions = {sess['id'] for slots in schedule.values() for sess in slots}
    for sess in sessions:
        if sess['id'] not in scheduled_sessions:
            issues['unscheduled'].append(f"Session {sess['id']} not scheduled")
    
    return issues

def check_schedule_feasibility(schedule, sessions, subjects):
    """Comprehensive check if the schedule is feasible"""
    # Track assignments
    teacher_schedule = defaultdict(list)  # {teacher_id: [(day, period), ...]}
    student_schedule = defaultdict(list)  # {student_id: [(day, period), ...]}
    subject_counts = defaultdict(int)     # {subject_id: count}
    issues = []
    
    # Build schedules and check constraints
    for (day, period), slots in schedule.items():
        slot_teachers = set()
        slot_students = set()
        
        for sess in slots:
            # Check teacher overlap
            for tid in sess['teachers']:
                if tid in slot_teachers:
                    issues.append(f"Teacher {tid} has overlapping sessions on {DAYS[day]} period {period+1}")
                slot_teachers.add(tid)
                teacher_schedule[tid].append((day, period))
            
            # Check student overlap
            for student in sess['students']:
                if student in slot_students:
                    issues.append(f"Student {student} has overlapping sessions on {DAYS[day]} period {period+1}")
                slot_students.add(student)
                student_schedule[student].append((day, period))
            
            # Count subject hours
            subject_counts[sess['subject']] += 1
    
    # Verify each subject has correct number of hours
    for sid, count in subject_counts.items():
        required = subjects[sid]['hours_per_week']
        if count != required:
            issues.append(f"Subject {sid} has {count} sessions (requires exactly {required})")
    
    # Check each teacher's schedule is feasible
    for tid, schedule in teacher_schedule.items():
        daily_counts = defaultdict(int)
        for day, _ in schedule:
            daily_counts[day] += 1
            if daily_counts[day] > PERIODS_PER_DAY:
                issues.append(f"Teacher {tid} has too many sessions ({daily_counts[day]}) on {DAYS[day]}")
    
    # Check each student's schedule is feasible
    for student, schedule in student_schedule.items():
        daily_counts = defaultdict(int)
        for day, _ in schedule:
            daily_counts[day] += 1
            if daily_counts[day] > PERIODS_PER_DAY:
                issues.append(f"Student {student} has too many sessions ({daily_counts[day]}) on {DAYS[day]}")
    
    if issues:
        logger.error("Schedule feasibility check failed:")
        for issue in issues:
            logger.error(f"- {issue}")
        return False
    
    logger.info("Schedule feasibility check passed!")
    return True

def format_schedule_output(schedule, subjects, teachers, students_dict):
    """Format schedule into JSON-friendly structure with split parallel groups"""
    
    # Convert subjects tuple to dict for easier lookup
    subject_dict = {s[0]: {'id': s[0], 'name': s[1], 'group_count': s[2]} for s in subjects.values()}
    
    # Convert teachers tuple to dict for easier lookup  
    teacher_dict = {t[0]: {'id': t[0], 'name': f"{t[1]} {t[2] or ''} {t[3]}".strip()} for t in teachers.values()}

    formatted = {
        'metadata': {
            'num_days': 4,
            'periods_per_day': 10,
            'total_sessions': sum(len(slots) for slots in schedule.values())
        },
        'days': {}
    }

    # Group schedule by days
    for (day, period), sessions in schedule.items():
        if str(day) not in formatted['days']:
            formatted['days'][str(day)] = {}
            
        formatted['days'][str(day)][str(period)] = []
        
        for sess in sessions:
            subject_id = sess['subject']
            subject_info = subject_dict[subject_id]
            
            if len(sess['teachers']) > 1:  # This is a parallel subject
                required_groups = subject_info['group_count']
                student_count = len(sess['students'])
                students_per_group = math.ceil(student_count / required_groups)
                
                # Split students into groups
                student_groups = []
                for i in range(0, student_count, students_per_group):
                    group = sess['students'][i:i + students_per_group]
                    student_groups.append(group)
                
                # Pad with empty groups if needed
                while len(student_groups) < required_groups:
                    student_groups.append([])
                
                # Create a session for each group
                for group_idx, (teacher_id, student_group) in enumerate(zip(sess['teachers'], student_groups)):
                    formatted_session = {
                        'id': f"{sess['id']}_G{group_idx + 1}",
                        'subject_id': subject_id,
                        'subject_name': subject_info['name'],
                        'teachers': [{
                            'id': teacher_id,
                            'name': teacher_dict[teacher_id]['name']
                        }],
                        'students': [{
                            'id': sid,
                            'name': students_dict[sid]['name']
                        } for sid in student_group],
                        'group': group_idx + 1,
                        'is_parallel': True,
                        'parallel_group_id': sess['id']
                    }
                    formatted['days'][str(day)][str(period)].append(formatted_session)
            else:
                # Regular non-parallel session
                formatted_session = {
                    'id': sess['id'],
                    'subject_id': subject_id,
                    'subject_name': subject_info['name'],
                    'teachers': [{
                        'id': tid, 
                        'name': teacher_dict[tid]['name']
                    } for tid in sess['teachers']],
                    'students': [{
                        'id': sid,
                        'name': students_dict[sid]['name']
                    } for sid in sess['students']],
                    'group': sess['group'],
                    'is_parallel': False,
                    'parallel_group_id': None
                }
                formatted['days'][str(day)][str(period)].append(formatted_session)

    return formatted

if __name__ == '__main__':
    teachers, subjects, students_raw, st_map, stud_map, hb, student_groups = load_data()
    sessions = build_sessions(teachers, subjects, st_map, stud_map, hb)
    
    MAX_SOLVER_ITERATIONS = 3000
    schedule, students_dict = solve_timetable(sessions, time_limit=1200)
    
    if schedule:
        # Format schedule for output
        formatted_schedule = format_schedule_output(schedule, subjects, teachers, students_dict)
        
        # Print compact summary
        print("\nSchedule Summary:")
        print(f"Total sessions scheduled: {formatted_schedule['metadata']['total_sessions']}")
        print(f"Days: {formatted_schedule['metadata']['num_days']}")
        print(f"Periods per day: {formatted_schedule['metadata']['periods_per_day']}")
        
        # Return formatted schedule for other programs to use
        import json
        with open('schedule_output.json', 'w') as f:
            json.dump(formatted_schedule, f, indent=2)
        
        print("\nDetailed schedule has been saved to 'schedule_output.json'")
    else:
        print("No solution found")
        exit(1)
