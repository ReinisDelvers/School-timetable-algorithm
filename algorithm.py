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

def calculate_strict_score(sess, key, slot, schedule, subject_daily, 
                         student_subject_sessions, subject_requirements):
    """Calculate score for placing session in a slot with strict constraints"""
    day = slot // PERIODS_PER_DAY
    period = slot % PERIODS_PER_DAY
    score = 0
    
    # Base score - prefer earlier slots
    score += period * 10 + day * 50
    
    # Penalty for having multiple sessions in same slot
    score += len(schedule.get(key, [])) * 500
    
    # Penalty for subject sessions per day
    score += subject_daily[sess['subject']][day] * 200
    
    # Student load balancing
    student_scores = []
    for student in sess['students']:
        # Count how many sessions student has this day
        day_sessions = sum(1 for sessions in schedule.values() 
                         if any(s['students'] and student in s['students'] 
                               for s in sessions))
        student_scores.append(day_sessions)
    
    if student_scores:
        # Penalize uneven distribution
        score += (max(student_scores) - min(student_scores)) * 300
        # Penalize high daily load
        score += max(student_scores) * 400
    
    return score

# --- Solver with Simplified Processing ---
def solve_timetable(sessions, time_limit=1200, stop_flag=None):
    """
    Solve the timetable optimization problem
    stop_flag: Optional callable that returns True if solver should stop
    """
    start_time = time.time()
    best_schedule = None
    best_score = float('inf')
    students_dict = {s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()} 
                    for s in get_student()}

    # Initial solution
    current = greedy_initial(sessions)
    current_score = evaluate_schedule(current, sessions)
    
    if current_score < best_score:
        best_schedule = current
        best_score = current_score

    for iteration in range(MAX_SOLVER_ITERATIONS):
        # Check stop flag if provided
        if stop_flag and stop_flag():
            logger.info("Solver stopped by user request")
            # Return best schedule found so far, even if not complete
            return (best_schedule, students_dict) if best_schedule else (None, students_dict)
            
        # Check time limit
        if time.time() - start_time > time_limit:
            logger.info("Time limit reached")
            break
            
        # ...rest of solving code...

    return (best_schedule, students_dict) if best_schedule else (None, students_dict)

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
