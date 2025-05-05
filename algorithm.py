import sqlite3
import math
import logging
import time
import threading
from itertools import groupby
from functools import lru_cache
from data import (
    get_teacher, get_subject, get_student,
    get_subject_teacher, get_subject_student, get_hour_blocker
)
from ortools.sat.python import cp_model
import statistics

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
    subject_sessions = {}
    
    for sid, subj in subjects.items():
        hours_per_week = subj[3]  # hours required per group
        maxpd = min(subj[4], 2)
        is_parallel = subjects[sid][7] == 1
        
        teacher_groups = subject_teacher_groups.get(sid, [])
        all_students = sorted(list(subj_students.get(sid, set())))
        total_groups = 1 if is_parallel else sum(gc for _, gc in teacher_groups)
        students_per_group = math.ceil(len(all_students) / total_groups) if all_students and total_groups else 0
        
        total_sessions = hours_per_week * (1 if is_parallel else total_groups)
        # Single logging point for all subjects
        logger.info(f"Subject {sid}: {hours_per_week} hours/week, {maxpd} max/day, {total_groups} groups, {len(all_students)} students ({students_per_group} per group) => {total_sessions} total sessions {'(parallel)' if is_parallel else ''}")
        
        if is_parallel:
            # For parallel subjects, treat all groups as one unit
            group_teachers = [tid for tid, _ in teacher_groups]
            students_per_teacher = len(all_students) // len(group_teachers)
            
            # Build combined candidate slots from all teachers
            combined_cand = set()
            for tid in group_teachers:
                teacher = teachers.get(tid)
                if not teacher:
                    continue
                for di, day in enumerate(DAYS):
                    if teacher[4 + di]:
                        for p in range(PERIODS_PER_DAY):
                            if hour_blocker[day][p] == 1:
                                combined_cand.add(di * PERIODS_PER_DAY + p)
            
            # Create sessions with student distribution
            for hour in range(hours_per_week):
                session_groups = []
                student_start = 0
                
                for i, tid in enumerate(group_teachers):
                    student_end = min(student_start + students_per_teacher, len(all_students))
                    group_students = all_students[student_start:student_end]
                    student_start = student_end
                    
                    session_id = f"S{sid}_G{i+1}_H{hour}"
                    session_groups.append({
                        'id': session_id,
                        'subject': sid,
                        'teacher': tid,
                        'group': i+1,
                        'students': group_students,
                        'candidates': list(combined_cand),
                        'max_per_day': maxpd,
                        'parallel_with': 0  # All share same base group
                    })
                
                # Add all parallel groups together
                for sess in session_groups:
                    sessions.append(sess)
                    subject_sessions.setdefault(sid, []).append(sess)
        else:
            # Handle non-parallel subjects as before
            total_groups = sum(gc for _, gc in teacher_groups)
            students_per_group = math.ceil(len(all_students) / total_groups) if all_students and total_groups else 0
            
            student_idx = 0
            group_counter = 0
            
            for tid, group_count in teacher_groups:
                teacher = teachers.get(tid)
                if not teacher:
                    continue
                    
                cand = []
                for di, day in enumerate(DAYS):
                    if teacher[4 + di]:
                        for p in range(PERIODS_PER_DAY):
                            if hour_blocker[day][p] == 1:
                                cand.append(di * PERIODS_PER_DAY + p)
                
                for g in range(group_count):
                    group_counter += 1
                    start_idx = student_idx
                    end_idx = min(start_idx + students_per_group, len(all_students))
                    group_students = all_students[start_idx:end_idx]
                    student_idx = end_idx
                    
                    for i in range(hours_per_week):
                        session_id = f"S{sid}_G{group_counter}_H{i}"
                        new_session = {
                            'id': session_id,
                            'subject': sid,
                            'teacher': tid,
                            'group': group_counter,
                            'students': group_students,
                            'candidates': cand.copy(),
                            'max_per_day': maxpd,
                            'parallel_with': None
                        }
                        sessions.append(new_session)
                        subject_sessions.setdefault(sid, []).append(new_session)

    return sessions

# --- Greedy Initial Assignment ---
def greedy_initial(sessions):
    """
    Assign each session greedily to the first available slot,
    respecting teacher availability and per-day subject-group limits.
    Returns a list of assigned slot indices, with fallbacks aggregated into one warning.
    """
    teacher_schedule = {}
    subject_daily = {}
    assignment = []
    fallbacks = []

    for sess in sessions:
        sid, grp, maxpd, tid = sess['subject'], sess['group'], sess['max_per_day'], sess['teacher']
        placed = False
        for slot in sess['candidates']:
            day = slot // PERIODS_PER_DAY
            if slot in teacher_schedule.get(tid, set()):
                continue
            if subject_daily.get((sid, grp, day), 0) >= maxpd:
                continue
            teacher_schedule.setdefault(tid, set()).add(slot)
            subject_daily[(sid, grp, day)] = subject_daily.get((sid, grp, day), 0) + 1
            assignment.append(slot)
            placed = True
            break
        if not placed:
            # record fallback, but do not spam log per session
            fallbacks.append((sess['id'], sess['candidates'][:3]))  # show up to 3 candidates
            assignment.append(sess['candidates'][0] if sess['candidates'] else -1)

    if fallbacks:
        # one summary warning
        fallback_info = ", ".join(f"{sid}([{slots}...])" for sid, slots in fallbacks)
        logger.warning(f"Greedy fallback used for {len(fallbacks)} sessions: {fallback_info}")

    return assignment

# --- Backtracking Solver with MRV ---
def score_slot_quality(slot, day_counts, period_counts, max_per_period=3):
    """Score the quality of placing a session in a given slot (lower is better)"""
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    
    # Penalize high concentrations
    day_penalty = day_counts[day] * 2
    period_penalty = period_counts[period] * 3
    
    # Prefer middle periods
    period_preference = abs(period - PERIODS_PER_DAY//2)
    
    # Hard limit on sessions per period
    if period_counts[period] >= max_per_period:
        return float('inf')
        
    return day_penalty + period_penalty + period_preference

def backtracking_schedule(sessions):
    global backtrack_calls
    indexed = list(enumerate(sessions))
    # Sort by complexity: student count, candidate flexibility, and hour constraints
    indexed.sort(key=lambda x: (
        len(x[1]['students']), 
        -len(x[1]['candidates']),
        x[1]['max_per_day']
    ))
    
    assignment = {}
    teacher_schedule = {}
    subject_daily = {}
    day_counts = {d: 0 for d in range(len(DAYS))}
    period_counts = {p: 0 for p in PERIODS_PER_DAY}
    backtrack_calls = 0
    
    def backtrack(idx):
        global backtrack_calls
        backtrack_calls += 1
        if idx == len(indexed):
            return True
            
        sess_index, sess = indexed[idx]
        sid, grp, maxpd, tid = sess['subject'], sess['group'], sess['max_per_day'], sess['teacher']
        
        # Sort candidates by quality score
        candidates = [(slot, score_slot_quality(slot, day_counts, period_counts))
                     for slot in sess['candidates']]
        candidates.sort(key=lambda x: x[1])
        
        for slot, _ in candidates:
            day = slot // PERIODS_PER_DAY
            period = slot % PERIODS_PER_DAY
            
            if slot in teacher_schedule.get(tid, set()): continue
            if subject_daily.get((sid, grp, day), 0) >= maxpd: continue
            
            # Try assignment
            assignment[sess_index] = slot
            teacher_schedule.setdefault(tid, set()).add(slot)
            subject_daily[(sid, grp, day)] = subject_daily.get((sid, grp, day), 0) + 1
            day_counts[day] += 1
            period_counts[period] += 1
            
            if backtrack(idx+1): return True
            
            # Undo assignment
            teacher_schedule[tid].remove(slot)
            subject_daily[(sid, grp, day)] -= 1
            day_counts[day] -= 1
            period_counts[period] -= 1
            del assignment[sess_index]
            
        return False
    
    success = backtrack(0)
    if not success:
        return None
        
    schedule = {}
    for idx, slot in assignment.items():
        di, p = divmod(slot, PERIODS_PER_DAY)
        schedule.setdefault((di, p), []).append(sessions[idx])
    return schedule

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
            if sess['teacher'] in teachers:
                return False
            teachers.add(sess['teacher'])
            
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
            if i != j and sess1['teacher'] != sess2['teacher'] and \
               not set(sess1['students']) & set(sess2['students']) and \
               (sess1['parallel_with'] != sess2['parallel_with'] or \
                sess1['parallel_with'] is None):
                compatible[i].add(j)
    return compatible

@lru_cache(maxsize=1024)
def get_slot_score(day, period):
    """Cache slot quality scores"""
    # Prefer middle periods and distribute across days
    period_penalty = abs(period - PERIODS_PER_DAY//2) * 2
    return period_penalty + day * 3

def try_place_parallel_group(schedule, sess, slot, compatible_sessions):
    """Try to place all sessions in a parallel group together"""
    if sess['parallel_with'] is None:
        return True
        
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    key = (day, period)
    current = schedule.get(key, [])
    
    # Find all other parallel sessions in this time slot
    parallel_sessions = []
    for s in current:
        if isinstance(s, dict) and s['subject'] == sess['subject'] and s['parallel_with'] is not None:
            parallel_sessions.append(s)
    
    # Check if we can fit all parallel sessions in this slot
    if len(current) + len(parallel_sessions) > 3:
        return False
        
    # Check compatibility with existing sessions
    for psess in parallel_sessions:
        for csess in current:
            if isinstance(csess, dict):
                idx1 = next((i for i, s in enumerate(sessions) if s['id'] == psess['id']), None)
                idx2 = next((i for i, s in enumerate(sessions) if s['id'] == csess['id']), None)
                if idx1 is not None and idx2 is not None and idx2 not in compatible_sessions[idx1]:
                    return False
                    
    return True

def solve_timetable(sessions, time_limit=600):
    """Improved solver with better heuristics and caching"""
    start_time = time.time()
    last_log_time = start_time
    last_log_iterations = 0
    best_schedule = {}
    best_score = float('inf')
    
    # Pre-compute compatible sessions
    compatible_sessions = precompute_compatible_slots(sessions)
    
    # Group parallel sessions by subject for faster access
    parallel_groups = {}
    for i, sess in enumerate(sessions):
        if sess['parallel_with'] is not None:
            parallel_groups.setdefault(sess['subject'], []).append(i)
    
    def create_initial_solution():
        schedule = {}
        subject_day_counts = {}
        session_indices = list(range(len(sessions)))
        
        # Sort sessions by constraint difficulty
        session_indices.sort(key=lambda i: (
            -bool(sessions[i]['parallel_with']),  # Parallel groups first
            len(sessions[i]['candidates']),       # Fewer candidates next
            -len(sessions[i]['students']),        # More students next
        ))
        
        for idx in session_indices:
            sess = sessions[idx]
            candidates = [(s, get_slot_score(s // PERIODS_PER_DAY, s % PERIODS_PER_DAY)) 
                         for s in sess['candidates']]
            candidates.sort(key=lambda x: x[1])
            
            placed = False
            for slot, _ in candidates:
                day = slot // PERIODS_PER_DAY
                period = slot % PERIODS_PER_DAY
                key = (day, period)
                
                # Quick rejection checks
                if subject_day_counts.get((sess['subject'], day), 0) >= sess['max_per_day']:
                    continue
                    
                current = schedule.get(key, [])
                if len(current) >= 3:
                    continue
                
                # Check teacher and student conflicts
                if any(s['teacher'] == sess['teacher'] for s in current):
                    continue
                    
                # Try placing this session
                if try_place_parallel_group(schedule, sess, slot, compatible_sessions):
                    schedule.setdefault(key, []).append(sess)
                    subject_day_counts[(sess['subject'], day)] = \
                        subject_day_counts.get((sess['subject'], day), 0) + 1
                    placed = True
                    break
                    
            if not placed:
                # If we can't place a session, try to place it anywhere valid
                for slot in sess['candidates']:
                    day = slot // PERIODS_PER_DAY
                    period = slot % PERIODS_PER_DAY
                    key = (day, period)
                    if len(schedule.get(key, [])) < 3:
                        schedule.setdefault(key, []).append(sess)
                        break
        
        return schedule

    # Main solver loop
    iterations = 0
    stagnant_iterations = 0
    current_schedule = create_initial_solution()
    
    while iterations < MAX_SOLVER_ITERATIONS and time.time() - start_time < time_limit:
        iterations += 1
        
        # Enhanced progress logging with timing metrics
        if iterations % PROGRESS_INTERVAL == 0:
            current_time = time.time()
            elapsed_since_log = current_time - last_log_time
            iterations_since_log = iterations - last_log_iterations
            
            # Calculate timing metrics
            avg_time_per_iter = elapsed_since_log / iterations_since_log
            time_per_hundred = avg_time_per_iter * 100
            
            logger.info(
                f"Iteration {iterations}/{MAX_SOLVER_ITERATIONS}, "
                f"best score: {best_score} (missing: {best_score//1000} sessions), "
                f"avg {avg_time_per_iter:.3f}s/iter, "
                f"100 iterations = {time_per_hundred:.1f}s"
            )
            
            last_log_time = current_time
            last_log_iterations = iterations

        # Check if current solution is perfect
        if best_score == 0:
            logger.info(f"Found perfect solution at iteration {iterations}")
            return best_schedule
        
        # If stuck, restart with new random solution
        if stagnant_iterations >= IMPROVEMENT_THRESHOLD:
            logger.info(f"Restarting search at iteration {iterations}")
            current_schedule = create_initial_solution()
            stagnant_iterations = 0
            continue
        
        improved = False
        
        # Try to improve current solution
        for day in range(len(DAYS)):
            for period in range(PERIODS_PER_DAY):
                key = (day, period)
                if key not in current_schedule:
                    continue
                    
                sessions_at_slot = current_schedule[key]
                for i, sess in enumerate(sessions_at_slot):
                    # Try moving session to a different slot
                    original_slot = sessions_at_slot.pop(i)
                    
                    # Try each candidate slot
                    for new_slot in sess['candidates']:
                        new_day = new_slot // PERIODS_PER_DAY
                        new_period = new_slot % PERIODS_PER_DAY
                        new_key = (new_day, new_period)
                        
                        if new_key == key:
                            continue
                            
                        # Check if move is valid
                        target_slot = current_schedule.get(new_key, [])
                        if len(target_slot) >= 3:
                            continue
                            
                        # Check constraints at new slot
                        if not any(s['teacher'] == sess['teacher'] for s in target_slot) and \
                           not any(set(s['students']) & set(sess['students']) for s in target_slot):
                            
                            # Try the move
                            target_slot.append(sess)
                            score = evaluate_schedule(current_schedule, sessions)
                            
                            if score < best_score:
                                best_score = score
                                best_schedule = {k: v[:] for k, v in current_schedule.items()}
                                improved = True
                                stagnant_iterations = 0
                            else:
                                # Undo move
                                target_slot.remove(sess)
                    
                    # Put session back if no better position found
                    if not improved:
                        sessions_at_slot.insert(i, original_slot)
        
        if not improved:
            stagnant_iterations += 1
    
    logger.info(f"Solver completed {iterations}/{MAX_SOLVER_ITERATIONS} iterations in {time.time() - start_time:.1f}s")
    return best_schedule

def evaluate_schedule(schedule, all_sessions):
    """Score a schedule (lower is better)"""
    score = 0
    
    # Count missing/unscheduled sessions
    scheduled_sessions = set()
    for slots in schedule.values():
        for sess in slots:
            scheduled_sessions.add(sess['id'])
    
    missing_sessions = len(all_sessions) - len(scheduled_sessions)
    missing_penalty = 1000 * missing_sessions
    score += missing_penalty
    
    # Track penalties by type
    teacher_conflicts = 0
    student_conflicts = 0
    daily_limit_violations = 0
    parallel_violations = 0
    
    # Check daily limits and conflicts
    day_counts = {}
    for (day, period), sessions in schedule.items():
        # Teacher conflicts
        teachers = set()
        parallel_groups = {}
        for sess in sessions:
            if sess['teacher'] in teachers:
                teacher_conflicts += 1
            teachers.add(sess['teacher'])
            
            # Track daily subject counts
            key = (day, sess['subject'], sess['group'])
            day_counts[key] = day_counts.get(key, 0) + 1
            if day_counts[key] > sess['max_per_day']:
                daily_limit_violations += 1
            
            # Check parallel group violations
            if sess['parallel_with'] is not None:
                base_group = sess['parallel_with']
                if base_group not in parallel_groups:
                    parallel_violations += 1
                parallel_groups[base_group] = sess
        
        # Student conflicts
        student_counts = {}
        for sess in sessions:
            for student in sess['students']:
                student_counts[student] = student_counts.get(student, 0) + 1
                if student_counts[student] > 1:
                    student_conflicts += 1
    
    score += teacher_conflicts * 500
    score += student_conflicts * 300
    score += daily_limit_violations * 400
    score += parallel_violations * 600  # High penalty for parallel violations
    
    # Log detailed score breakdown when it changes
    if hasattr(evaluate_schedule, 'last_score') and evaluate_schedule.last_score != score:
        logger.debug(f"Score breakdown: missing={missing_penalty}, teachers={teacher_conflicts*500}, students={student_conflicts*300}, daily={daily_limit_violations*400}, parallel={parallel_violations*600}")
    
    evaluate_schedule.last_score = score
    return score

def has_major_conflicts(schedule):
    """Check for deal-breaking conflicts"""
    for sessions in schedule.values():
        # Check teacher conflicts
        teachers = set()
        for sess in sessions:
            if sess['teacher'] in teachers:
                return True
            teachers.add(sess['teacher'])
    return False

def analyze_schedule_issues(schedule, sessions):
    """Return list of issues with the schedule"""
    issues = []
    
    # Track sessions per subject and daily distribution
    subject_counts = {}
    subject_day_counts = {}
    
    for (day, period), slots in schedule.items():
        for sess in slots:
            sid = sess['subject']
            subject_counts[sid] = subject_counts.get(sid, 0) + 1
            
            # Track daily distribution for parallel subjects
            if sess['parallel_with'] is not None:
                key = (sid, day)
                subject_day_counts[key] = subject_day_counts.get(key, 0) + 1
    
    # Check daily distribution for parallel subjects
    for (sid, day), count in subject_day_counts.items():
        if count > 2:  # Max 2 periods per day for parallel subjects
            issues.append(f"Subject {sid} has {count} parallel sessions on {DAYS[day]} (max 2)")
            
    # Check missing/extra sessions
    for sid, count in subject_counts.items():
        expected = sum(1 for s in sessions if s['subject'] == sid)
        if count != expected:
            issues.append(f"Subject {sid} has {count} sessions (expected {expected})")
    
    # Check daily limits
    day_counts = {}
    for (day, period), slots in schedule.items():
        for sess in slots:
            key = (day, sess['subject'], sess['group'])
            day_counts[key] = day_counts.get(key, 0) + 1
            if day_counts[key] > sess['max_per_day']:
                issues.append(f"Subject {sess['subject']} group {sess['group']} exceeds daily limit on {DAYS[day]}")
    
    # Check parallel group violations
    for (day, period), slot_sessions in schedule.items():
        parallel_groups = {}
        for sess in slot_sessions:
            if sess['parallel_with'] is not None:
                base_group = sess['parallel_with']
                if base_group in parallel_groups:
                    issues.append(f"Parallel groups for subject {sess['subject']} must be scheduled together")
                parallel_groups[base_group] = sess
    
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
            tid = sess['teacher']
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
    schedule = solve_timetable(sessions)
    
    if not schedule:
        print("Could not find any valid solution")
        exit(1)

    # Add type check for schedule before validation
    if not isinstance(schedule, dict):
        print("Invalid schedule format")
        exit(1)
        
    # Validate final schedule
    completeness_issues = validate_schedule_completeness(schedule, subjects, sessions)
    teacher_issues = validate_teacher_conflicts(schedule)
    student_issues = validate_student_attendance(schedule, sessions)
    
    print("\nSchedule Validation Results:")
    if completeness_issues:
        print("\nSubject hour requirements not met:")
        for issue in completeness_issues:
            print(f"- {issue}")
            
    if teacher_issues:
        print("\nTeacher scheduling conflicts:")
        for issue in teacher_issues:
            print(f"- {issue}")
            
    if student_issues:
        print("\nStudent attendance issues:")
        for issue in student_issues:
            print(f"- {issue}")
            
    if not (completeness_issues or teacher_issues or student_issues):
        print("All validation checks passed!")
        
    # Print regular schedule output
    print("\nGenerated schedule (issues marked with *):")
    issues = analyze_schedule_issues(schedule, sessions)
    
    for di, day in enumerate(DAYS):
        print(f"\n=== {day.upper()} ===")
        for p in range(PERIODS_PER_DAY):
            se = schedule.get((di, p), [])
            if se:
                print(f"Period {p+1}: ", end="")
                # Mark sessions involved in issues with *
                marked_sessions = []
                for sess in se:
                    marker = "*" if any(str(sess['subject']) in issue for issue in issues) else ""
                    marked_sessions.append(f"{sess['id']}{marker}")
                print(", ".join(marked_sessions))
            else:
                print(f"Period {p+1}: Free")
                
    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"- {issue}")
