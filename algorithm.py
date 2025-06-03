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
import copy
import random
import json  # Add at top with other imports

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
    last_active_period = defaultdict(int)
    gaps_in_day = defaultdict(int)
    
    # First pass - find last active period and count gaps
    for day in range(4):
        has_active = False
        for period in range(PERIODS_PER_DAY):
            key = (day, period)
            if key in schedule and schedule[key]:
                if not has_active:  # Found first active period
                    has_active = True
                last_active_period[day] = period
            elif has_active:  # Count gaps between first and last active
                gaps_in_day[day] += 1
    
    # Calculate penalties
    for day, last_period in last_active_period.items():
        # Exponential penalty for length of day
        day_penalties += (last_period + 1) ** 2 * 300
        
        # Heavy penalty for gaps
        day_penalties += gaps_in_day[day] * 1000
        
        # Penalty for longer days after shorter ones
        if day > 0 and last_period > last_active_period[day-1]:
            day_penalties += (last_period - last_active_period[day-1]) * 2000
    
    score += day_penalties
    
    # Keep existing penalties for incorrect session counts
    for subject, req_count in required.items():
        actual = scheduled[subject]
        if actual != req_count:
            score += abs(actual - req_count) * 20000
    
    return score

def greedy_initial(sessions):
    """Modified to prioritize unscheduled subjects and enforce their scheduling"""
    # Initialize tracking structures
    student_subject_sessions = defaultdict(lambda: defaultdict(int))
    subject_requirements = defaultdict(int)
    subject_scheduled = defaultdict(int)
    student_schedule = defaultdict(lambda: defaultdict(set))
    schedule = {}  # Initialize empty schedule
    teacher_schedule = defaultdict(set)
    subject_daily = defaultdict(lambda: defaultdict(int))
    subjects_scheduled = defaultdict(int)
    
    # Pre-compute requirements
    for sess in sessions:
        sid = sess['subject']
        subject_requirements[sid] += 1
    
    def session_priority(sess):
        sid = sess['subject']
        required = subject_requirements[sid]
        current = subjects_scheduled[sid]
        
        # Extreme priority for subjects with no sessions scheduled yet
        subjects_with_no_sessions = subjects_scheduled[sid] == 0
        
        # Calculate remaining ratio for urgency
        remaining_ratio = (required - current) / required if required > 0 else 0
        
        earliest_slot = min(sess['candidates']) if sess['candidates'] else PERIODS_PER_DAY * len(DAYS)
        
        return (
            subjects_with_no_sessions,  # Highest priority: unscheduled subjects
            remaining_ratio,            # Second: subjects with most remaining sessions
            -earliest_slot,            # Third: prefer earlier slots
            len(sess['students'])      # Last: prefer sessions with more students
        )
    
    # Group sessions by subject for better tracking
    sessions_by_subject = defaultdict(list)
    for sess in sessions:
        sessions_by_subject[sess['subject']].append(sess)
    
    # Process subjects in order of their requirements
    while any(subject_requirements[sid] > subject_scheduled[sid] for sid in subject_requirements):
        # Sort all remaining sessions
        remaining_sessions = [s for s in sessions if subject_scheduled[s['subject']] < subject_requirements[s['subject']]]
        sorted_sessions = sorted(remaining_sessions, key=session_priority, reverse=True)
        
        progress_made = False
        for sess in sorted_sessions:
            sid = sess['subject']
            if subject_scheduled[sid] >= subject_requirements[sid]:
                continue
            
            # Try harder to find slots for unscheduled subjects
            best_slot = find_best_slot_strict(
                sess, schedule, teacher_schedule,
                subject_daily, student_schedule,
                student_subject_sessions, subject_requirements,
                force_schedule=(subjects_scheduled[sid] == 0)  # Force scheduling for unscheduled subjects
            )
            
            if best_slot is not None:
                place_session_strict(
                    sess, best_slot, schedule,
                    teacher_schedule, subject_daily,
                    subject_scheduled, student_schedule,
                    student_subject_sessions, subject_requirements
                )
                subjects_scheduled[sid] += 1
                progress_made = True
        
        if not progress_made:
            break
    
    return schedule

def place_session_strict(sess, slot, schedule, teacher_schedule, subject_daily,
                        subject_scheduled, student_schedule, student_subject_sessions,
                        subject_requirements):
    """Place a session in the schedule with strict validation"""
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    key = (day, period)
    sid = sess['subject']
    
    # Add session to schedule
    if key not in schedule:
        schedule[key] = []
    schedule[key].append(sess)
    
    # Update tracking structures
    for tid in sess['teachers']:
        teacher_schedule[tid].add(slot)
    
    for student in sess['students']:
        student_schedule[student][day].add(period)
        student_subject_sessions[student][sid] += 1
    
    subject_daily[sid][day] += 1
    subject_scheduled[sid] += 1

def find_best_slot_strict(sess, schedule, teacher_schedule, subject_daily,
                         student_schedule, student_subject_sessions, subject_requirements,
                         force_schedule=False):
    """Modified to force shorter days"""
    best_slot = None
    min_score = float('inf')
    sid = sess['subject']
    
    # Calculate how many sessions of this subject are already scheduled
    subject_scheduled = sum(1 for slots in schedule.values() 
                          for s in slots if s['subject'] == sid)
    
    # First try slots that already have sessions
    occupied_slots = [slot for slot in sess['candidates'] 
                     if slot in [s[0]*PERIODS_PER_DAY + s[1] for s in schedule.keys()]]
    
    # Then try empty slots if no good occupied slot is found
    empty_slots = [s for s in sess['candidates'] if s not in occupied_slots]
    
    # Combine and sort all slots based on priority
    def slot_priority(slot):
        d = slot // PERIODS_PER_DAY
        p = slot % PERIODS_PER_DAY
        key = (d, p)
        
        # Get current day utilization
        day_sessions = sum(1 for (sd, _), sessions in schedule.items() 
                         if sd == d and sessions)
        
        return (
            p < 5,              # Highest priority: first 5 periods
            day_sessions > 0,   # Second: use days that already have sessions
            -d,                 # Third: prefer earlier days
            -p,                # Fourth: prefer earlier periods
            len(schedule.get(key, [])) > 0  # Last: prefer slots with sessions
        )
    
    all_slots = sorted(occupied_slots + empty_slots, key=slot_priority, reverse=True)
    
    # Increase parallel session limit when forcing schedule
    max_parallel = 10 if force_schedule else (8 if subject_requirements[sid] > subject_scheduled else 6)
    
    # Rest of the function remains the same
    for slot in all_slots:
        day = slot // PERIODS_PER_DAY
        period = slot % PERIODS_PER_DAY
        key = (day, period)
        
        if len(schedule.get(key, [])) >= max_parallel:
            continue
        
        # Basic constraint checks
        if any(slot in teacher_schedule[tid] for tid in sess['teachers']):
            continue
        
        if has_student_conflicts(sess, key, schedule):
            continue
        
        score = calculate_strict_score(
            sess, key, slot,
            schedule, subject_daily,
            student_subject_sessions, subject_requirements
        )
        
        if score < min_score:
            min_score = score
            best_slot = slot
    
    return best_slot

def calculate_strict_score(sess, key, slot, schedule, subject_daily, 
                         student_subject_sessions, subject_requirements):
    """Enhanced scoring focused on minimizing day length"""
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    score = 0
    sid = sess['subject']
    
    # Extreme penalty for using later periods
    score += period ** 4 * 500  # Much stronger period penalty
    
    # Get comprehensive day statistics
    day_stats = {d: {'start': PERIODS_PER_DAY, 'end': -1, 'gaps': 0, 'sessions': 0} 
                for d in range(len(DAYS))}
    
    # Analyze existing schedule
    for (d, p), sessions in schedule.items():
        if sessions:
            day_stats[d]['start'] = min(day_stats[d]['start'], p)
            day_stats[d]['end'] = max(day_stats[d]['end'], p)
            day_stats[d]['sessions'] += len(sessions)

    # Calculate effective day length and target
    current_day_sessions = sum(1 for _, sessions in schedule.items() 
                             if any(s['subject'] == sid for s in sessions))
    target_periods = max(5, current_day_sessions // len(DAYS))  # Target 5 periods or less per day
    
    # Extreme penalties for exceeding target day length
    if period >= target_periods:
        score += 50000 * (period - target_periods + 1) ** 2

    # Strong reward for using earliest possible periods
    score -= (PERIODS_PER_DAY - period) * 8000

    # Super aggressive parallelization rewards
    parallel_sessions = len(schedule.get(key, []))
    if parallel_sessions > 0:
        score -= 10000 * parallel_sessions  # Double the parallel reward
        if period < target_periods:
            score -= 20000  # Extra reward for parallel in early periods

    # Force compression by heavily penalizing gaps
    if day_stats[day]['end'] >= 0:
        gaps = sum(1 for p in range(day_stats[day]['start'], day_stats[day]['end'] + 1)
                  if (day, p) not in schedule or not schedule[(day, p)])
        score += gaps * 15000  # Triple gap penalty

    # Strongly prefer consecutive periods
    if period > 0 and (day, period-1) in schedule and schedule[(day, period-1)]:
        score -= 12000  # Double consecutive reward
        
    # Critical: Penalize using new days when current days aren't full
    used_days = len([d for d in range(day) if any((d, p) in schedule for p in range(PERIODS_PER_DAY))])
    if day > used_days and period >= 3:  # Only allow new day if really necessary
        score += 100000
    
    # Additional penalties/rewards
    if subject_daily[sid][day] >= sess['max_per_day']:
        score += 15000
    
    # Balance teacher and student loads but with lower priority
    teacher_scores = []
    student_scores = []
    for tid in sess['teachers']:
        day_sessions = sum(1 for sessions in schedule.values()
                         if any(s['teachers'] and tid in s['teachers']
                               for s in sessions))
        teacher_scores.append(day_sessions)
    
    for student in sess['students']:
        day_sessions = sum(1 for sessions in schedule.values() 
                         if any(s['students'] and student in s['students'] 
                               for s in sessions))
        student_scores.append(day_sessions)
    
    if teacher_scores:
        score += (max(teacher_scores) - min(teacher_scores)) * 50
    if student_scores:
        score += (max(student_scores) - min(student_scores)) * 50
    
    return score

def has_student_conflicts(sess, key, schedule):
    """Helper to check for student conflicts"""
    if key not in schedule:
        return False
        
    sess_students = set(sess['students'])
    for other in schedule[key]:
        if sess_students & set(other['students']):
            return True
    return False

# --- Solver with Simplified Processing ---
def solve_timetable(sessions, time_limit=1200, stop_flag=None):
    """
    Solve the timetable optimization problem using simulated annealing
    """
    start_time = time.time()
    best_schedule = None
    best_score = float('inf')
    students_dict = {s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()} 
                    for s in get_student()}

    # Initial solution
    current = greedy_initial(sessions)
    current_score = evaluate_schedule(current, sessions)
    
    # Simulated annealing parameters
    temp = 1.0
    cooling_rate = 0.995
    min_temp = 0.001

    while temp > min_temp and (time.time() - start_time < time_limit):
        if stop_flag and stop_flag():
            break

        # Generate neighbor solution
        neighbor = generate_neighbor(current)
        neighbor_score = evaluate_schedule(neighbor, sessions)
        
        # Calculate acceptance probability
        delta = neighbor_score - current_score
        if delta < 0 or random.random() < math.exp(-delta / temp):
            current = neighbor
            current_score = neighbor_score
            
            if current_score < best_score:
                best_score = current_score
                best_schedule = copy.deepcopy(current)
                logger.info(f"New best score: {best_score}")
        
        temp *= cooling_rate

    return (best_schedule, students_dict) if best_schedule else (None, students_dict)

def generate_neighbor(schedule):
    """Generate a neighboring solution using one of several moves"""
    moves = [
        move_session_to_empty_slot,
        swap_two_sessions,
        move_parallel_group,
        reorganize_day
    ]
    
    move = random.choice(moves)
    new_schedule = copy.deepcopy(schedule)
    return move(new_schedule)

def move_session_to_empty_slot(schedule):
    """Move a random session to an empty slot with teacher load consideration"""
    occupied_slots = list(schedule.keys())
    if not occupied_slots:
        return schedule
        
    # Select source slot prioritizing overloaded teachers
    teacher_loads = defaultdict(lambda: defaultdict(int))
    for (day, period), sessions in schedule.items():
        for sess in sessions:
            for tid in sess['teachers']:
                teacher_loads[tid][day] += 1
    
    # Find slots with highest teacher loads
    slot_scores = []
    for slot in occupied_slots:
        day = slot[0]
        max_load = max(teacher_loads[tid][day] 
                      for sessions in schedule[slot]
                      for tid in sessions['teachers'])
        slot_scores.append((max_load, slot))
    
    # Prioritize moving sessions from overloaded slots
    source_slot = max(slot_scores, key=lambda x: x[0])[1]
    
    # Rest of existing move logic
    if not schedule[source_slot]:
        return schedule
        
    target_slots = []
    for day in range(4):
        for period in range(PERIODS_PER_DAY):
            slot = (day, period)
            if slot not in schedule or len(schedule[slot]) < len(schedule[source_slot]):
                # Calculate teacher load for this day
                day_load = sum(teacher_loads[tid][day] 
                             for sessions in schedule.get(slot, [])
                             for tid in sessions['teachers'])
                target_slots.append((day_load, slot))
    
    # Modify target slot selection to prefer early periods
    def target_slot_score(slot_info):
        day_load, (day, period) = slot_info
        return (
            day_load,           # Primary: minimize teacher load
            day,               # Secondary: prefer earlier days
            period,           # Tertiary: prefer earlier periods
            len(schedule.get((day, period), []))  # Last: prefer slots with sessions
        )
    
    if target_slots:
        target_slot = min(target_slots, key=target_slot_score)[1]
        session = random.choice(schedule[source_slot])
        
        schedule[source_slot].remove(session)
        if not schedule[source_slot]:
            del schedule[source_slot]
            
        if target_slot not in schedule:
            schedule[target_slot] = []
        schedule[target_slot].append(session)
    
    return schedule

def swap_two_sessions(schedule):
    """Swap two random sessions"""
    occupied_slots = list(schedule.keys())
    if len(occupied_slots) < 2:
        return schedule
        
    slot1, slot2 = random.sample(occupied_slots, 2)
    if schedule[slot1] and schedule[slot2]:
        session1 = random.choice(schedule[slot1])
        session2 = random.choice(schedule[slot2])
        
        schedule[slot1].remove(session1)
        schedule[slot2].remove(session2)
        
        schedule[slot1].append(session2)
        schedule[slot2].append(session1)
    
    return schedule

def move_parallel_group(schedule):
    """Move a parallel group of sessions together"""
    # Find parallel sessions
    parallel_groups = defaultdict(list)
    for slot, sessions in schedule.items():
        for sess in sessions:
            if sess.get('is_parallel'):
                parallel_groups[sess['parallel_group_id']].append((slot, sess))
    
    if not parallel_groups:
        return schedule
    
    # Select random parallel group and move it
    group_id = random.choice(list(parallel_groups.keys()))
    group_sessions = parallel_groups[group_id]
    
    # Find valid target slots
    target_day = random.randint(0, 3)
    target_period = random.randint(0, PERIODS_PER_DAY-1)
    target_slot = (target_day, target_period)
    
    # Move all sessions in group
    for old_slot, sess in group_sessions:
        schedule[old_slot].remove(sess)
        if not schedule[old_slot]:
            del schedule[old_slot]
            
        if target_slot not in schedule:
            schedule[target_slot] = []
        schedule[target_slot].append(sess)
    
    return schedule

def reorganize_day(schedule):
    """Modified to compress days"""
    day = random.randint(0, 3)
    
    # Collect all sessions for the day
    day_sessions = []
    for p in range(PERIODS_PER_DAY):
        if (day, p) in schedule:
            day_sessions.extend(schedule[(day, p)])
            del schedule[(day, p)]
    
    if not day_sessions:
        return schedule

    # Sort sessions by parallel potential
    def parallel_potential(sess):
        return (len(sess['students']), sess['subject'])
    
    day_sessions.sort(key=parallel_potential)
    
    # Redistribute to earliest possible periods with maximum parallelization
    period = 0
    while day_sessions:
        current_group = []
        remaining = []
        
        # Try to pack as many compatible sessions as possible into current period
        for sess in day_sessions:
            can_add = True
            for added in current_group:
                if any(s in sess['students'] for s in added['students']):
                    can_add = False
                    break
            if can_add and len(current_group) < 8:  # Allow up to 8 parallel sessions
                current_group.append(sess)
            else:
                remaining.append(sess)
        
        if current_group:
            schedule[(day, period)] = current_group
            period += 1
        
        day_sessions = remaining
    
    return schedule

# --- Output Formatting and Validation ---
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

def validate_final_schedule(schedule, sessions, subjects, teachers):
    """Validate the final schedule for conflicts and constraint violations"""
    logger.info("\n=== Schedule Validation Results ===")
    
    # Track statistics
    stats = {
        'student_conflicts': 0,
        'teacher_conflicts': 0,
        'subject_hours': defaultdict(int),
        'required_hours': {},
        'teacher_daily_load': defaultdict(lambda: defaultdict(int)),
        'student_daily_load': defaultdict(lambda: defaultdict(int))
    }
    
    # Get required hours for each subject
    for sid in subjects:
        stats['required_hours'][sid] = subjects[sid][3]  # number_of_hours_per_week
    
    # Enhanced tracking
    student_subject_hours = defaultdict(lambda: defaultdict(int))  # student -> subject -> hours
    teacher_subject_hours = defaultdict(lambda: defaultdict(int))  # teacher -> subject -> hours
    student_subjects_needed = defaultdict(set)  # student -> set of required subjects
    
    # Build requirements
    for sess in sessions:
        for student in sess['students']:
            student_subjects_needed[student].add(sess['subject'])
    
    # Add explicit subject period tracking
    subject_period_counts = defaultdict(int)  # Track actual periods per subject
    
    # Check each time slot
    for (day, period), slot_sessions in schedule.items():
        # Track who is busy this period
        teachers_this_slot = set()
        students_this_slot = set()
        
        for sess in slot_sessions:
            # Count subject hours
            stats['subject_hours'][sess['subject']] += 1
            
            # Check teacher conflicts
            for tid in sess['teachers']:
                if tid in teachers_this_slot:
                    stats['teacher_conflicts'] += 1
                    logger.error(f"Teacher conflict: {tid} has multiple sessions on day {day} period {period}")
                teachers_this_slot.add(tid)
                stats['teacher_daily_load'][tid][day] += 1
            
            # Check student conflicts
            for sid in sess['students']:
                if sid in students_this_slot:
                    stats['student_conflicts'] += 1
                    logger.error(f"Student conflict: {sid} has multiple sessions on day {day} period {period}")
                students_this_slot.add(sid)
                stats['student_daily_load'][sid][day] += 1
    
            sid = sess['subject']
            
            # Track hours per student per subject
            for student in sess['students']:
                student_subject_hours[student][sid] += 1
            
            # Track hours per teacher per subject
            for tid in sess['teachers']:
                teacher_subject_hours[tid][sid] += 1
    
    # Validate completeness
    logger.info("\nCompleteness Check:")
    
    # Check if all students get all their required subjects
    student_missing = []
    for student, required_subjects in student_subjects_needed.items():
        for sid in required_subjects:
            required = subjects[sid][3]  # hours per week needed
            actual = student_subject_hours[student][sid]
            if actual < required:
                student_missing.append((student, sid, required, actual))
    
    if student_missing:
        logger.error("Students missing required subject hours:")
        for student, sid, req, actual in student_missing:
            logger.error(f"Student {student} needs {req} hours of subject {sid}, got {actual}")
    else:
        logger.info("All students have their required subject hours")
    
    # Check if all teachers can deliver their assigned classes
    teacher_overloaded = []
    for tid, subj_hours in teacher_subject_hours.items():
        teacher = teachers[tid]
        available_slots = sum(PERIODS_PER_DAY for day in range(4) if teacher[4 + day])
        total_assigned = sum(hours for hours in subj_hours.values())
        if total_assigned > available_slots:
            teacher_overloaded.append((tid, available_slots, total_assigned))
    
    if teacher_overloaded:
        logger.error("Teachers with more classes than available slots:")
        for tid, available, assigned in teacher_overloaded:
            logger.error(f"Teacher {tid} has {assigned} classes but only {available} available slots")
    else:
        logger.info("All teachers have manageable schedules")
    
    # Check for unscheduled sessions
    total_sessions_needed = sum(subj[3] for subj in subjects.values())  # Total hours needed across all subjects
    total_sessions_scheduled = sum(len(slots) for slots in schedule.values())
    if total_sessions_needed != total_sessions_scheduled:
        logger.error(f"Missing sessions: needed {total_sessions_needed}, scheduled {total_sessions_scheduled}")
    else:
        logger.info("All required sessions are scheduled")

    # Report results
    logger.info("\nSchedule Statistics:")
    logger.info(f"- Student conflicts: {stats['student_conflicts']}")
    logger.info(f"- Teacher conflicts: {stats['teacher_conflicts']}")
    
    # Check subject hours
    logger.info("\nSubject Hours Check:")
    for sid, scheduled in stats['subject_hours'].items():
        required = stats['required_hours'][sid]
        if scheduled != required:
            logger.error(f"Subject {sid} has {scheduled} hours (required: {required})")
        else:
            logger.info(f"Subject {sid}: {scheduled}/{required} hours - OK")
    
    # Check teacher loads
    logger.info("\nTeacher Daily Loads:")
    for tid, daily_load in stats['teacher_daily_load'].items():
        teacher_name = f"{teachers[tid][1]} {teachers[tid][3]}"
        logger.info(f"\nTeacher {teacher_name}:")
        for day in range(4):
            load = daily_load[day]
            logger.info(f"  Day {day+1}: {load} sessions")
    
    # Check student loads
    max_daily = defaultdict(int)
    for sid, daily_load in stats['student_daily_load'].items():
        for day, load in daily_load.items():
            max_daily[day] = max(max_daily[day], load)
    
    logger.info("\nMaximum Student Load per Day:")
    for day in range(4):
        logger.info(f"Day {day+1}: {max_daily[day]} sessions")
    
    logger.info("\n=== End Validation ===\n")
    
    return stats

if __name__ == '__main__':
    teachers, subjects, students_raw, st_map, stud_map, hb, student_groups = load_data()
    sessions = build_sessions(teachers, subjects, st_map, stud_map, hb)
    
    MAX_SOLVER_ITERATIONS = 3000
    schedule, students_dict = solve_timetable(sessions, time_limit=1200)
    
    if schedule:
        # Format schedule for output
        formatted_schedule = format_schedule_output(schedule, subjects, teachers, students_dict)
        
        # Validate and display statistics
        validation_stats = validate_final_schedule(schedule, sessions, subjects, teachers)
        
        # Print compact summary
        logger.info("\nSchedule Summary:")
        logger.info(f"Total sessions scheduled: {formatted_schedule['metadata']['total_sessions']}")
        logger.info(f"Days: {formatted_schedule['metadata']['num_days']}")
        logger.info(f"Periods per day: {formatted_schedule['metadata']['periods_per_day']}")
        
        # Save to file
        with open('schedule_output.json', 'w') as f:
            json.dump(formatted_schedule, f, indent=2)
        
        logger.info("\nDetailed schedule has been saved to 'schedule_output.json'")
    else:
        logger.error("No solution found")
        exit(1)
