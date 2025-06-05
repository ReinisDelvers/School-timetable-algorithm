import sqlite3
import math
import logging
import time
import threading
from itertools import groupby
from functools import lru_cache
from collections import defaultdict, Counter
from data import (
    get_teacher, get_subject, get_student,
    get_subject_teacher, get_subject_student, get_hour_blocker
)
import statistics
import copy
import random
import json  # For reading subject–student mappings

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Constants ---
PERIODS_PER_DAY = 10
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
STALL_THRESHOLD = 10000       # Stop if no improvement for 10,000 iterations
LOG_INTERVAL = 1000           # Log status every 1,000 iterations

# --- Helper Functions ---
def group_students_by_subjects(subj_students):
    """Group students who have exactly the same set of subjects."""
    student_subjects = defaultdict(set)
    for sid, students in subj_students.items():
        for student in students:
            student_subjects[student].add(sid)

    groups = defaultdict(list)
    for student, subjects in student_subjects.items():
        group_key = frozenset(subjects)
        groups[group_key].append(student)

    student_to_group = {}
    for subjects, students in groups.items():
        group_rep = students[0]
        for student in students:
            student_to_group[student] = group_rep

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

    # Load subject–student relationships (JSON array in row[1])
    subj_students = {}
    for row in get_subject_student():
        subject_ids = json.loads(row[1])
        student_id = row[3]
        for sid in subject_ids:
            subj_students.setdefault(sid, set()).add(student_id)

    # Group students with identical subject sets
    grouped_subj_students, student_groups = group_students_by_subjects(subj_students)

    hb_row = get_hour_blocker()[0]
    hour_blocker = {
        day: [hb_row[i * PERIODS_PER_DAY + p] for p in range(PERIODS_PER_DAY)]
        for i, day in enumerate(DAYS)
    }

    original_student_count = len({s for students in subj_students.values() for s in students})
    grouped_student_count = len({s for students in grouped_subj_students.values() for s in students})
    logger.info(f"Loaded {len(teachers)} teachers, {len(subjects)} subjects")
    logger.info(f"Grouped {original_student_count} students into {grouped_student_count} unique combinations")

    # Print subject parameter summary
    for sid, subj in subjects.items():
        name = subj[1]
        required = subj[3]
        maxpd = subj[4]
        minpd = max(0, subj[6])
        logger.info(f"Subject {sid} (“{name}”): requires {required}h/week, maxpd={maxpd}, minpd={minpd}")

    return teachers, subjects, students_raw, subject_teachers, grouped_subj_students, hour_blocker, student_groups

def validate_input_data(teachers, subjects, subject_teachers, subj_students):
    """
    Validate that:
      - Each teacher has at least one available day.
      - No subject is assigned more teachers than its group count.
      - Each subject’s required hours fit within assigned teacher’s availability.
    """
    errors = []

    # Check that each teacher is available at least one day
    for tid, teacher in teachers.items():
        available_days = sum(1 for day in range(4) if teacher[4 + day])
        if available_days == 0:
            errors.append(f"Teacher {tid} has no available days")

    # Count teachers per subject
    subject_teacher_counts = defaultdict(int)
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        subject_teacher_counts[sid] += 1

    # Check subject group counts vs assigned teachers
    for sid, subj in subjects.items():
        raw_group_count = subj[2]
        if subj[7] == 1:
            # Parallel offerings: group_count is in subj[2], but each parallel group has its own teacher(s)
            continue
        if sid in subject_teacher_counts:
            teacher_count = subject_teacher_counts[sid]
            if teacher_count > raw_group_count:
                errors.append(f"Subject {sid} has {teacher_count} teachers but only {raw_group_count} groups")

    # Check that each subject’s hours fit within assigned teacher’s total availability
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        if sid not in subjects:
            errors.append(f"Subject {sid} not found for teacher {tid}")
            continue
        if tid not in teachers:
            errors.append(f"Teacher {tid} not found for subject {sid}")
            continue
        subj = subjects[sid]
        teacher = teachers[tid]
        available_slots = 0
        for d in range(4):
            if teacher[4 + d]:
                available_slots += PERIODS_PER_DAY
        required_slots = subj[3]
        if available_slots < required_slots:
            errors.append(f"Subject {sid} needs {required_slots} slots but teacher {tid} only has {available_slots} available")

    if errors:
        for err in errors:
            logger.error(f"Validation error: {err}")
        return False
    return True

# --- Session Creation ---
def build_sessions(teachers, subjects, subject_teachers, subj_students, hour_blocker):
    """
    For each (subject, teacher) pair, create exactly `hours_per_week` session objects,
    each requiring 1 hour. Blocks of size `minpd` will be handled later.
    """
    if not validate_input_data(teachers, subjects, subject_teachers, subj_students):
        logger.error("Input data validation failed")
        return []

    # Count how many sessions we need per subject
    subject_session_counts = defaultdict(int)
    # Map each subject to its list of (teacher_id, group_count)
    subject_teacher_groups = defaultdict(list)
    for st in subject_teachers:
        sid, tid = st[1], st[3]
        group_count = max(1, st[7])
        subject_teacher_groups[sid].append((tid, group_count))

    sessions = []
    for sid, subj in subjects.items():
        hours_per_week = subj[3]
        raw_maxpd = subj[4]
        raw_minpd = subj[6]
        maxpd = max(0, raw_maxpd)
        minpd = max(0, raw_minpd)
        if minpd > maxpd:
            logger.warning(f"Subject {sid}: raw minpd={raw_minpd} > maxpd={raw_maxpd}, clamping to {maxpd}")
            minpd = maxpd

        teacher_groups = subject_teacher_groups.get(sid, [])
        all_students = sorted(list(subj_students.get(sid, set())))

        # We create exactly `hours_per_week` session objects, distributing among teachers round‐robin
        created = 0
        teacher_idx = 0
        while created < hours_per_week:
            if not teacher_groups:
                logger.error(f"No teacher assigned for Subject {sid}, cannot build sessions")
                break
            tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
            session = create_session(
                sid=sid,
                teachers_list=[tid],
                hour=created,
                students=all_students,
                teacher_info=teachers[tid],
                maxpd=maxpd,
                minpd=minpd,
                hour_blocker=hour_blocker,
                subjects_dict=subjects,
                parallel_group=None
            )
            sessions.append(session)
            created += 1
            subject_session_counts[sid] += 1
            teacher_idx += 1

        if subject_session_counts[sid] != hours_per_week:
            logger.error(f"Subject {sid}: built {subject_session_counts[sid]} sessions (required {hours_per_week})")

    # Summary of sessions built
    cnt = Counter(s['subject'] for s in sessions)
    for sid, subj in subjects.items():
        required = subj[3]
        built = cnt[sid]
        logger.info(f"Subject {sid}: built {built} sessions, required {required} (hours)")

    return sessions

def create_session(sid, teachers_list, hour, students, teacher_info, maxpd, minpd, hour_blocker, subjects_dict, parallel_group=None):
    """
    Create a single session dict for subject `sid`.
    Each session requires:
      - `max_per_day` (maxpd)
      - `min_per_day` (minpd)
      - `candidates`: all (day,period) where the assigned teacher(s) are available and not blocked.
    """
    session = {
        'id': f"S{sid}_H{hour}",
        'subject': sid,
        'teachers': teachers_list,
        'group': 1,
        'students': students,
        'candidates': [],
        'max_per_day': maxpd,
        'min_per_day': minpd,
        'parallel_with': parallel_group,
        'is_parallel': (parallel_group is not None),
        'hour': hour
    }

    # Build candidate slots
    for di, day in enumerate(DAYS):
        all_available = all(teacher_info[4 + di] for _ in teachers_list)
        if not all_available:
            continue
        for p in range(PERIODS_PER_DAY):
            if hour_blocker[day][p] == 1:
                session['candidates'].append(di * PERIODS_PER_DAY + p)

    if not session['candidates']:
        logger.error(f"Session {session['id']} (Subject {sid}) has NO CANDIDATES.")
    return session

# --- Evaluation Function ---
def evaluate_schedule(schedule, all_sessions, subjects):
    """
    Compute a numeric score of `schedule`. Lower is better.
    Penalize:
      - Too many or too few sessions per subject per week.
      - Subject daily minpd/maxpd violations (with contiguity checks).
      - Student conflicts (same slot).
      - Teacher conflicts (same slot).
      - Student daily load <4 or >6 (penalized but not hard).
    """
    score = 0
    scheduled_count = defaultdict(int)
    student_schedule = defaultdict(lambda: defaultdict(set))
    student_daily_hours = defaultdict(lambda: defaultdict(int))
    subject_daily_hours = defaultdict(lambda: defaultdict(int))
    teacher_daily_slots = defaultdict(lambda: defaultdict(set))

    # Tally through scheduled slots
    for (day, period), slot_sessions in schedule.items():
        teachers_this_slot = set()
        for sess in slot_sessions:
            sid = sess['subject']
            scheduled_count[sid] += 1
            for student in sess['students']:
                if period in student_schedule[student][day]:
                    score += 8000  # Hard penalty for overlap
                student_schedule[student][day].add(period)
                student_daily_hours[student][day] += 1
            subject_daily_hours[sid][day] += 1
            for tid in sess['teachers']:
                if period in teacher_daily_slots[tid][day]:
                    score += 10000  # Hard penalty
                teacher_daily_slots[tid][day].add(period)
                teachers_this_slot.add(tid)

        # Check subject max per day
        for sess in slot_sessions:
            sid = sess['subject']
            maxpd = sess['max_per_day']
            if subject_daily_hours[sid][day] > maxpd:
                over = subject_daily_hours[sid][day] - maxpd
                score += 5000 * over

    # Enforce minpd and contiguity
    for sid, subj in subjects.items():
        raw_minpd = subj[6]
        raw_maxpd = subj[4]
        minpd = max(0, raw_minpd)
        maxpd = max(0, raw_maxpd)
        if minpd > maxpd:
            minpd = maxpd

        required = subj[3]
        full_blocks = required // minpd if minpd > 0 else 0
        leftover = required - (full_blocks * minpd)

        if minpd <= 0:
            continue

        for d in range(4):
            actual = subject_daily_hours[sid].get(d, 0)
            if actual > maxpd:
                score += 10000 * (actual - maxpd)
            if 0 < actual < minpd and actual != leftover:
                deficit = minpd - actual
                score += 10000 * deficit
            if actual == minpd:
                periods = [
                    p for (dd, p), sl in schedule.items()
                    if dd == d for s in sl if s['subject'] == sid
                ]
                periods.sort()
                if any(periods[i+1] - periods[i] != 1 for i in range(len(periods)-1)):
                    score += 20000  # Contiguity violation

    # Student daily load penalties
    for student, daily in student_daily_hours.items():
        for d, hours in daily.items():
            if hours < 4:
                score += 2000 * (4 - hours)
            if hours > 6:
                score += 3000 * (hours - 6)

    # Weekly hours per subject
    for sid, subj in subjects.items():
        required = subj[3]
        actual = scheduled_count.get(sid, 0)
        if actual != required:
            score += 20000 * abs(actual - required)

    return score

# --- Greedy Initial Construction ---
def greedy_initial(sessions, subjects):
    """
    Build a starting schedule by placing sessions one‐by‐one greedily,
    respecting teacher availability, student overlaps, and subject maxpd.
    The “minpd” (contiguity) constraint is intentionally skipped during this phase,
    so that all sessions can at least be placed. Contiguity will be refined later.
    """
    subject_requirements = defaultdict(int)
    for sess in sessions:
        subject_requirements[sess['subject']] += 1

    subjects_scheduled = defaultdict(int)
    subject_daily = defaultdict(lambda: defaultdict(int))
    teacher_schedule = defaultdict(set)
    student_schedule = defaultdict(lambda: defaultdict(set))

    schedule = {}  # (day,period) -> [session, ...]

    def session_priority(sess):
        sid = sess['subject']
        required = subject_requirements[sid]
        placed = subjects_scheduled[sid]
        no_sessions_yet = (placed == 0)
        remaining_ratio = (required - placed) / required if required > 0 else 0
        earliest_candidate = min(sess['candidates']) if sess['candidates'] else PERIODS_PER_DAY * len(DAYS)
        return (no_sessions_yet, remaining_ratio, -earliest_candidate, len(sess['students']))

    def has_student_conflict(sess, key):
        day, period = key
        return any(period in student_schedule[stu][day] for stu in sess['students'])

    def find_best_slot(sess):
        sid = sess['subject']
        maxpd = sess['max_per_day']

        # Compute how many of this subject already on each day
        current_daily = dict(subject_daily[sid])

        # Build a list of both occupied and free candidate slots, sorted by preference
        occupied = { (day * PERIODS_PER_DAY + p)
                     for (day, p), sl in schedule.items()
                     for s in sl }
        empty_slots = [s for s in sess['candidates'] if s not in occupied]
        all_slots = sorted(list(occupied) + empty_slots, key=lambda sl: (
            sl % PERIODS_PER_DAY < 5,  # prefer morning (False < True)
            sum(len(schedule.get((sl // PERIODS_PER_DAY, p), [])) for p in range(PERIODS_PER_DAY)) > 0,
            -(sl // PERIODS_PER_DAY),
            -(sl % PERIODS_PER_DAY),
            len(schedule.get((sl // PERIODS_PER_DAY, sl % PERIODS_PER_DAY), [])) > 0
        ), reverse=True)

        for sl in all_slots:
            day = sl // PERIODS_PER_DAY
            period = sl % PERIODS_PER_DAY
            key = (day, period)

            # Teacher conflict?
            if any(sl in teacher_schedule[tid] for tid in sess['teachers']):
                continue
            # Student conflict?
            if has_student_conflict(sess, key):
                continue
            # Subject maxpd?
            new_count = current_daily.get(day, 0) + 1
            if new_count > maxpd:
                continue

            # We skip the “minpd” / contiguity check here to allow placement of all sessions.
            return sl

        return None

    total = len(sessions)
    while True:
        pending = [s for s in sessions if subjects_scheduled[s['subject']] < subject_requirements[s['subject']]]
        if not pending:
            break
        pending_sorted = sorted(pending, key=session_priority, reverse=True)
        progress = False
        for sess in pending_sorted:
            if subjects_scheduled[sess['subject']] >= subject_requirements[sess['subject']]:
                continue
            slot = find_best_slot(sess)
            if slot is not None:
                day, period = slot // PERIODS_PER_DAY, slot % PERIODS_PER_DAY
                schedule.setdefault((day, period), []).append(sess)
                for tid in sess['teachers']:
                    teacher_schedule[tid].add(slot)
                for stu in sess['students']:
                    student_schedule[stu][day].add(period)
                subject_daily[sess['subject']][day] += 1
                subjects_scheduled[sess['subject']] += 1
                progress = True
        if not progress:
            break

    placed = sum(subjects_scheduled.values())
    unplaced = [s['id'] for s in sessions if subjects_scheduled[s['subject']] < subject_requirements[s['subject']]]
    logger.info(f"greedy_initial placed {placed} of {total} sessions; unplaced={unplaced}")
    return schedule

# --- Solver with Simulated Annealing ---
def solve_timetable(sessions, subjects, time_limit=1200, stop_flag=None):
    """
    Use simulated annealing to improve the schedule generated by greedy_initial.
    Stop if no improvement for STALL_THRESHOLD iterations, logging every LOG_INTERVAL.
    """
    start_time = time.time()
    best_schedule = None
    best_score = float('inf')
    students_dict = {s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()}
                     for s in get_student()}

    # Initial schedule
    current = greedy_initial(sessions, subjects)
    current_score = evaluate_schedule(current, sessions, subjects)
    best_schedule = copy.deepcopy(current)
    best_score = current_score
    logger.info(f"Initial score: {best_score}")

    temp = 1.0
    cooling_rate = 0.999
    min_temp = 0.001

    iteration = 0
    stall_count = 0

    while temp > min_temp and (time.time() - start_time < time_limit):
        if stop_flag and stop_flag():
            break
        iteration += 1
        neighbor = generate_neighbor(current, subjects)
        neighbor_score = evaluate_schedule(neighbor, sessions, subjects)
        delta = neighbor_score - current_score

        if delta < 0 or random.random() < math.exp(-delta / temp):
            current = neighbor
            current_score = neighbor_score
            if current_score < best_score:
                best_score = current_score
                best_schedule = copy.deepcopy(current)
                logger.info(f"Iter {iteration}: New best score = {best_score}")
                stall_count = 0
            else:
                stall_count += 1
        else:
            stall_count += 1

        if iteration % LOG_INTERVAL == 0:
            logger.info(f"Iter {iteration}, best_score={best_score}, temp={temp:.4f}, stall_count={stall_count}")

        if stall_count >= STALL_THRESHOLD:
            logger.error("Solver stopped due to no improvement for 10,000 iterations.")
            validate_final_schedule(best_schedule, sessions, subjects, teachers)
            break

        temp *= cooling_rate

    return best_schedule, students_dict

def generate_neighbor(schedule, subjects):
    """Randomly pick one of the move heuristics to perturb the schedule."""
    moves = [
        move_session_to_empty_slot,
        swap_two_sessions,
        move_parallel_group,
        reorganize_day
    ]
    move = random.choice(moves)
    new_schedule = copy.deepcopy(schedule)
    return move(new_schedule, subjects)

def _compute_subject_daily(schedule, sid):
    """Count how many sessions of subject `sid` per day in `schedule`."""
    counts = defaultdict(int)
    for (day, period), sl in schedule.items():
        for sess in sl:
            if sess['subject'] == sid:
                counts[day] += 1
    return counts

def has_student_conflict(sess, key, schedule):
    """Check if `sess` has any student conflict at slot `key`."""
    if key not in schedule:
        return False
    sset = set(sess['students'])
    for other in schedule[key]:
        if sset & set(other['students']):
            return True
    return False

# --- Move Heuristics ---
def move_session_to_empty_slot(schedule, subjects):
    """Move a random session from a busy slot to a “lighter” slot."""
    occupied_slots = list(schedule.keys())
    if not occupied_slots:
        return schedule

    # Rebuild teacher_schedule from the current schedule
    teacher_schedule = defaultdict(set)
    for (d, p), sl in schedule.items():
        slot_index = d * PERIODS_PER_DAY + p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_schedule[tid].add(slot_index)

    # Build teacher loads per day
    teacher_loads = defaultdict(lambda: defaultdict(int))
    for (day, period), sessions in schedule.items():
        for sess in sessions:
            for tid in sess['teachers']:
                teacher_loads[tid][day] += 1

    # Pick source slot with highest teacher‐load metric
    slot_scores = []
    for slot in occupied_slots:
        day = slot[0]
        max_load = 0
        for sess in schedule[slot]:
            for tid in sess['teachers']:
                max_load = max(max_load, teacher_loads[tid][day])
        slot_scores.append((max_load, slot))
    source_slot = max(slot_scores, key=lambda x: x[0])[1]

    if source_slot not in schedule or not schedule[source_slot]:
        return schedule

    session = random.choice(schedule[source_slot])
    sid = session['subject']
    required = subjects[sid][3]
    maxpd = session['max_per_day']
    raw_minpd = subjects[sid][6]
    subj_minpd = max(0, raw_minpd)

    orig_daily = _compute_subject_daily(schedule, sid)

    # Candidate target slots: any slot with fewer sessions than source
    target_slots = []
    for day in range(4):
        for p in range(PERIODS_PER_DAY):
            sl = (day, p)
            if sl == source_slot:
                continue
            count_here = len(schedule.get(sl, []))
            count_source = len(schedule[source_slot])
            if count_here < count_source:
                # Compute teacher‐load metric
                day_load = sum(
                    teacher_loads[tid][day]
                    for sess2 in schedule.get(sl, []) for tid in sess2['teachers']
                )
                target_slots.append((day_load, sl))

    if not target_slots:
        return schedule

    def ts_score(x):
        load, (day, period) = x
        return (load, day, period, len(schedule.get((day, period), [])))

    target_slots.sort(key=ts_score)
    for _, target_slot in target_slots:
        new_day = target_slot[0]
        old_day = source_slot[0]
        new_daily = orig_daily.copy()
        new_daily[old_day] -= 1
        new_daily[new_day] += 1

        # Check subject daily maxpd
        if new_daily[new_day] > maxpd:
            continue

        # Teacher conflict?
        target_index = target_slot[0] * PERIODS_PER_DAY + target_slot[1]
        if any(target_index in teacher_schedule[tid] for tid in session['teachers'] if target_slot != source_slot):
            continue
        # Student conflict?
        if has_student_conflict(session, target_slot, schedule):
            continue

        # Commit move
        schedule[source_slot].remove(session)
        if not schedule[source_slot]:
            del schedule[source_slot]
        schedule.setdefault(target_slot, []).append(session)
        return schedule

    return schedule

def swap_two_sessions(schedule, subjects):
    """Swap two randomly picked sessions between different slots."""
    occupied_slots = list(schedule.keys())
    if len(occupied_slots) < 2:
        return schedule

    # Rebuild teacher_schedule from the current schedule
    teacher_schedule = defaultdict(set)
    for (d, p), sl in schedule.items():
        slot_index = d * PERIODS_PER_DAY + p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_schedule[tid].add(slot_index)

    slot1, slot2 = random.sample(occupied_slots, 2)
    if not schedule[slot1] or not schedule[slot2]:
        return schedule

    sess1 = random.choice(schedule[slot1])
    sess2 = random.choice(schedule[slot2])
    sid1, sid2 = sess1['subject'], sess2['subject']
    maxpd1 = sess1['max_per_day']
    maxpd2 = sess2['max_per_day']
    required1 = subjects[sid1][3]
    required2 = subjects[sid2][3]
    subj_minpd1 = max(0, subjects[sid1][6])
    subj_minpd2 = max(0, subjects[sid2][6])

    old_day1, old_day2 = slot1[0], slot2[0]
    daily1 = _compute_subject_daily(schedule, sid1)
    daily2 = _compute_subject_daily(schedule, sid2)

    new_daily1 = daily1.copy()
    new_daily2 = daily2.copy()
    new_daily1[old_day1] -= 1
    new_daily1[old_day2] += 1
    new_daily2[old_day2] -= 1
    new_daily2[old_day1] += 1

    # Check daily maxpd for both subjects
    if new_daily1[old_day2] > maxpd1 or new_daily2[old_day1] > maxpd2:
        return schedule

    # Teacher conflict?
    slot1_index = slot1[0] * PERIODS_PER_DAY + slot1[1]
    slot2_index = slot2[0] * PERIODS_PER_DAY + slot2[1]
    if any(slot2_index in teacher_schedule[tid] for tid in sess1['teachers'] if slot2 != slot1) or \
       any(slot1_index in teacher_schedule[tid] for tid in sess2['teachers'] if slot1 != slot2):
        return schedule

    # Student conflicts?
    if has_student_conflict(sess1, slot2, schedule) or has_student_conflict(sess2, slot1, schedule):
        return schedule

    # Commit swap
    schedule[slot1].remove(sess1)
    schedule[slot1].append(sess2)
    schedule[slot2].remove(sess2)
    schedule[slot2].append(sess1)
    return schedule

def move_parallel_group(schedule, subjects):
    """
    Move all sessions of a parallel group together to a random slot,
    respecting subject daily constraints and teacher/student conflicts.
    """
    # Rebuild teacher_schedule from the current schedule
    teacher_schedule = defaultdict(set)
    for (d, p), sl in schedule.items():
        slot_index = d * PERIODS_PER_DAY + p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_schedule[tid].add(slot_index)

    parallel_groups = defaultdict(list)
    for slot, sl in schedule.items():
        for sess in sl:
            if sess.get('is_parallel'):
                parallel_groups[sess['parallel_with']].append((slot, sess))

    if not parallel_groups:
        return schedule

    group_id = random.choice(list(parallel_groups.keys()))
    group_sessions = parallel_groups[group_id]

    target_day = random.randint(0, 3)
    target_period = random.randint(0, PERIODS_PER_DAY - 1)
    target_slot = (target_day, target_period)

    # Precompute daily counts
    daily_counts = {}
    for _, sess in group_sessions:
        sid = sess['subject']
        if sid not in daily_counts:
            daily_counts[sid] = _compute_subject_daily(schedule, sid)

    # Check feasibility
    for old_slot, sess in group_sessions:
        sid = sess['subject']
        minpd = sess['min_per_day']
        maxpd = sess['max_per_day']
        required = subjects[sid][3]
        subj_minpd = max(0, subjects[sid][6])

        old_day = old_slot[0]
        new_daily = daily_counts[sid].copy()
        new_daily[old_day] -= 1
        new_daily[target_day] += 1

        # Only enforce maxpd here
        if new_daily[target_day] > maxpd:
            return schedule

        # Teacher conflict?
        target_index = target_day * PERIODS_PER_DAY + target_period
        if any(target_index in teacher_schedule[tid] for tid in sess['teachers']):
            return schedule
        # Student conflict?
        if has_student_conflict(sess, target_slot, schedule):
            return schedule

    # Commit moves
    for old_slot, sess in group_sessions:
        schedule[old_slot].remove(sess)
        if not schedule[old_slot]:
            del schedule[old_slot]
        schedule.setdefault(target_slot, []).append(sess)

    return schedule

def reorganize_day(schedule, subjects):
    """
    For a random day, collect all sessions and reassign them to the earliest possible periods,
    attempting to maximize valid parallelization (no student overlap).
    """
    day = random.randint(0, 3)

    day_sessions = []
    for p in range(PERIODS_PER_DAY):
        if (day, p) in schedule:
            day_sessions.extend(schedule[(day, p)])
            del schedule[(day, p)]

    if not day_sessions:
        return schedule

    def parallel_potential(sess):
        return (len(sess['students']), sess['subject'])

    day_sessions.sort(key=parallel_potential)

    period = 0
    while day_sessions and period < PERIODS_PER_DAY:
        current_group = []
        remaining = []
        for sess in day_sessions:
            can_add = True
            for added in current_group:
                if set(sess['students']) & set(added['students']):
                    can_add = False
                    break
            if can_add and len(current_group) < 8:
                current_group.append(sess)
            else:
                remaining.append(sess)

        if current_group:
            schedule[(day, period)] = current_group
            period += 1
        day_sessions = remaining

    return schedule

# --- Output & Validation ---
def format_schedule_output(schedule, subjects, teachers, students_dict):
    subject_dict = {s[0]: {'id': s[0], 'name': s[1], 'group_count': s[2]} for s in subjects.values()}
    teacher_dict = {t[0]: {'id': t[0], 'name': f"{t[1]} {t[2] or ''} {t[3]}".strip()} for t in teachers.values()}

    formatted = {
        'metadata': {
            'num_days': 4,
            'periods_per_day': 10,
            'total_sessions': sum(len(slots) for slots in schedule.values())
        },
        'days': {}
    }

    for (day, period), slot_sessions in schedule.items():
        formatted['days'].setdefault(str(day), {})
        formatted['days'][str(day)][str(period)] = []
        for sess in slot_sessions:
            sid = sess['subject']
            subj_info = subject_dict[sid]
            if sess.get('is_parallel'):
                required_groups = subj_info['group_count']
                student_count = len(sess['students'])
                per_group = math.ceil(student_count / required_groups)
                groups = [sess['students'][i:i+per_group] for i in range(0, student_count, per_group)]
                while len(groups) < required_groups:
                    groups.append([])
                for gi, grp in enumerate(groups):
                    formatted_session = {
                        'id': f"{sess['id']}_G{gi+1}",
                        'subject_id': sid,
                        'subject_name': subj_info['name'],
                        'teachers': [{'id': sess['teachers'][0], 'name': teacher_dict[sess['teachers'][0]]['name']}],
                        'students': [{'id': s, 'name': students_dict[s]['name']} for s in grp],
                        'group': gi+1,
                        'is_parallel': True,
                        'parallel_group_id': sess['id']
                    }
                    formatted['days'][str(day)][str(period)].append(formatted_session)
            else:
                formatted_session = {
                    'id': sess['id'],
                    'subject_id': sid,
                    'subject_name': subj_info['name'],
                    'teachers': [{'id': tid, 'name': teacher_dict[tid]['name']} for tid in sess['teachers']],
                    'students': [{'id': s, 'name': students_dict[s]['name']} for s in sess['students']],
                    'group': sess['group'],
                    'is_parallel': False,
                    'parallel_group_id': None
                }
                formatted['days'][str(day)][str(period)].append(formatted_session)

    return formatted

def validate_final_schedule(schedule, sessions, subjects, teachers):
    """
    Detailed logging of any issues in `schedule`:
      - Student conflicts (same slot).
      - Teacher conflicts (same slot).
      - Subject weekly totals vs required.
      - Subject daily minpd/maxpd and contiguity.
      - Teacher daily load.
      - Student daily load.
    """
    logger.info("\n=== Schedule Validation Results ===")
    stats = {
        'student_conflicts': 0,
        'teacher_conflicts': 0,
        'subject_hours': defaultdict(int),
        'required_hours': {},
        'subject_daily': defaultdict(lambda: defaultdict(int)),
        'teacher_daily_load': defaultdict(lambda: defaultdict(int)),
        'student_daily_load': defaultdict(lambda: defaultdict(int)),
        'student_conflict_details': [],
        'teacher_conflict_details': []
    }

    for sid in subjects:
        stats['required_hours'][sid] = subjects[sid][3]

    # Track slot usage
    for (day, period), slot_sessions in schedule.items():
        teachers_this_slot = defaultdict(list)
        students_this_slot = defaultdict(list)
        for sess in slot_sessions:
            sid = sess['subject']
            stats['subject_hours'][sid] += 1
            stats['subject_daily'][sid][day] += 1
            for tid in sess['teachers']:
                teachers_this_slot[tid].append(sess['id'])
                stats['teacher_daily_load'][tid][day] += 1
            for stu in sess['students']:
                students_this_slot[stu].append(sess['id'])
                stats['student_daily_load'][stu][day] += 1

        for tid, sess_ids in teachers_this_slot.items():
            if len(sess_ids) > 1:
                stats['teacher_conflicts'] += 1
                stats['teacher_conflict_details'].append((tid, day, period, sess_ids))
                logger.error(f"Teacher conflict: Teacher {tid} has sessions {sess_ids} on {DAYS[day]} period {period}")

        for stu, sess_ids in students_this_slot.items():
            if len(sess_ids) > 1:
                stats['student_conflicts'] += 1
                stats['student_conflict_details'].append((stu, day, period, sess_ids))
                logger.error(f"Student conflict: Student {stu} has sessions {sess_ids} on {DAYS[day]} period {period}")

    # Subject weekly totals and daily breakdown
    logger.info("\n--- Subject‐by‐Subject Hours Check ---")
    missing = []
    for sid, required in stats['required_hours'].items():
        actual = stats['subject_hours'].get(sid, 0)
        if actual != required:
            logger.error(f"Subject {sid} has {actual} hours (required: {required})")
            missing.append(sid)
        else:
            logger.info(f"Subject {sid}: {actual}/{required} hours – OK")

        raw_minpd = subjects[sid][6]
        raw_maxpd = subjects[sid][4]
        minpd = max(0, raw_minpd)
        maxpd = max(0, raw_maxpd)
        if minpd > maxpd:
            minpd = maxpd
        full_blocks = required // minpd if minpd > 0 else 0
        leftover = required - (full_blocks * minpd)

        for d in range(4):
            count_d = stats['subject_daily'][sid].get(d, 0)
            logger.info(f"    {DAYS[d].capitalize()}: {count_d} session{'s' if count_d != 1 else ''}")
            if count_d > maxpd:
                logger.error(f"    → Subject {sid} on {DAYS[d]} has {count_d} (> maxpd={maxpd})")
            if minpd > 0:
                if count_d > 0 and count_d < minpd and count_d != leftover:
                    logger.error(f"    → Subject {sid} on {DAYS[d]} has {count_d}, expected block of {minpd} or leftover {leftover}")
                if count_d == minpd:
                    periods = [
                        p for (dd, p), sl in schedule.items()
                        if dd == d for s in sl if s['subject'] == sid
                    ]
                    periods.sort()
                    if any(periods[i+1] - periods[i] != 1 for i in range(len(periods)-1)):
                        logger.error(f"    → Subject {sid} on {DAYS[d]} block not contiguous")

    if missing:
        logger.error(f"\nThe following subjects did not reach required hours: {missing}")
    else:
        logger.info("\nAll subjects reached required weekly totals")

    # Student conflicts summary
    logger.info(f"\n--- Total Student Conflicts: {stats['student_conflicts']} ---")
    for stu, day, period, sess_ids in stats['student_conflict_details']:
        logger.error(f" Student {stu} conflict at {DAYS[day]} period {period}: {sess_ids}")

    # Teacher conflicts summary
    logger.info(f"\n--- Total Teacher Conflicts: {stats['teacher_conflicts']} ---")
    for tid, day, period, sess_ids in stats['teacher_conflict_details']:
        logger.error(f" Teacher {tid} conflict at {DAYS[day]} period {period}: {sess_ids}")

    # Teacher daily loads
    logger.info("\n--- Teacher Daily Loads ---")
    for tid, daily in stats['teacher_daily_load'].items():
        name = f"{teachers[tid][1]} {teachers[tid][3]}"
        logger.info(f"Teacher {tid} ({name}):")
        for d in range(4):
            load = daily.get(d, 0)
            logger.info(f"   {DAYS[d].capitalize()}: {load} session{'s' if load != 1 else ''}")

    # Student maximum load per day
    logger.info("\n--- Maximum Student Load per Day ---")
    max_daily = defaultdict(int)
    for stu, daily in stats['student_daily_load'].items():
        for d, load in daily.items():
            max_daily[d] = max(max_daily[d], load)
    for d in range(4):
        logger.info(f"  {DAYS[d].capitalize()}: {max_daily[d]} session{'s' if max_daily[d] != 1 else ''}")

    logger.info("\n=== End Detailed Validation ===\n")

    return stats

# --- Main Execution ---
if __name__ == '__main__':
    teachers, subjects, students_raw, st_map, subj_students, hb, student_groups = load_data()
    sessions = build_sessions(teachers, subjects, st_map, subj_students, hb)

    # Solve
    schedule, students_dict = solve_timetable(sessions, subjects, time_limit=1200)

    if schedule:
        formatted = format_schedule_output(schedule, subjects, teachers, students_dict)
        stats = validate_final_schedule(schedule, sessions, subjects, teachers)

        logger.info("\nSchedule Summary:")
        logger.info(f"Total sessions scheduled: {formatted['metadata']['total_sessions']}")
        logger.info(f"Days: {formatted['metadata']['num_days']}")
        logger.info(f"Periods per day: {formatted['metadata']['periods_per_day']}")

        with open('schedule_output.json', 'w') as f:
            json.dump(formatted, f, indent=2)

        logger.info("\nDetailed schedule saved to 'schedule_output.json'")
    else:
        logger.error("No solution found")
        exit(1)
