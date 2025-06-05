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
    For each (subject, teacher) pair, create either:
      - multiple 1-hour sessions (if minpd <= 1),
      - or block sessions of size `minpd` plus possibly a leftover 1-hour session.
    Each session (or block) has a list of candidate start slots that guarantee contiguity.
    """
    if not validate_input_data(teachers, subjects, subject_teachers, subj_students):
        logger.error("Input data validation failed")
        return []

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

        if not teacher_groups:
            logger.error(f"No teacher assigned for Subject {sid}, cannot build sessions")
            continue

        # Distribute hours among teachers round-robin
        hours_remaining = hours_per_week
        teacher_idx = 0

        if minpd >= 2:
            # Number of full blocks (each of size `minpd`)
            full_blocks = hours_per_week // minpd
            leftover = hours_per_week - (full_blocks * minpd)

            # Create full_blocks block-sessions
            for b in range(full_blocks):
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                block_session = create_block_session(
                    sid=sid,
                    teachers_list=[tid],
                    students=all_students,
                    teacher_info=teachers[tid],
                    block_size=minpd,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=None
                )
                sessions.append(block_session)
                hours_remaining -= minpd
                teacher_idx += 1

            # If there's a leftover 1-hour, create a single-hour session
            if leftover > 0:
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                single_session = create_single_session(
                    sid=sid,
                    teachers_list=[tid],
                    hour=0,
                    students=all_students,
                    teacher_info=teachers[tid],
                    maxpd=maxpd,
                    minpd=1,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=None
                )
                sessions.append(single_session)
                hours_remaining -= 1
                teacher_idx += 1

        else:
            # All sessions are 1-hour if minpd <= 1
            while hours_remaining > 0:
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                session = create_single_session(
                    sid=sid,
                    teachers_list=[tid],
                    hour=(hours_per_week - hours_remaining),
                    students=all_students,
                    teacher_info=teachers[tid],
                    maxpd=maxpd,
                    minpd=minpd,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=None
                )
                sessions.append(session)
                hours_remaining -= 1
                teacher_idx += 1

        # Log how many sessions/blocks we created
        created_hours = sum(
            sess['block_size'] if sess.get('block_size', 1) > 1 else 1
            for sess in sessions
            if sess['subject'] == sid
        )
        if created_hours != hours_per_week:
            logger.error(f"Subject {sid}: created {created_hours} hours (blocks + singles), required {hours_per_week}")

    # Summary of sessions built
    cnt = Counter()
    for sess in sessions:
        cnt[sess['subject']] += sess.get('block_size', 1)
    for sid, subj in subjects.items():
        required = subj[3]
        built = cnt[sid]
        logger.info(f"Subject {sid}: built {built} sessions, required {required} (hours)")

    return sessions

def create_single_session(sid, teachers_list, hour, students, teacher_info, maxpd, minpd, hour_blocker, subjects_dict, parallel_group=None):
    """
    Create a single 1-hour session dict for subject `sid`.
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
        'block_size': 1,
        'hour': hour
    }

    # Build candidate slots (1-hour each). Here: hour_blocker == 1 means free.
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

def create_block_session(sid, teachers_list, students, teacher_info, block_size, hour_blocker, subjects_dict, parallel_group=None):
    """
    Create a block session of size `block_size` hours for subject `sid`.
    The session must occupy `block_size` consecutive periods on the same day.
    We store candidate 'start-slot' indices that guarantee contiguity.
    """
    session = {
        'id': f"S{sid}_B{block_size}_{random.randint(0,1_000_000)}",  # unique ID
        'subject': sid,
        'teachers': teachers_list,
        'group': 1,
        'students': students,
        'candidates': [],
        'max_per_day': subjects_dict[sid][4],
        'min_per_day': block_size,
        'parallel_with': parallel_group,
        'is_parallel': (parallel_group is not None),
        'block_size': block_size
    }

    # Build candidate start slots where all block_size consecutive periods are free & teacher is available
    # hour_blocker == 1 means free
    for di, day in enumerate(DAYS):
        if not all(teacher_info[4 + di] for _ in teachers_list):
            continue
        for p in range(PERIODS_PER_DAY - block_size + 1):
            can_place = True
            for offset in range(block_size):
                if hour_blocker[day][p + offset] != 1:
                    can_place = False
                    break
            if can_place:
                session['candidates'].append(di * PERIODS_PER_DAY + p)

    if not session['candidates']:
        logger.error(f"Block session {session['id']} (Subject {sid}, size={block_size}) has NO CANDIDATES.")
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
                # Check contiguity: find all periods for this subject on day d
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
    Now also respects block_size so that block sessions occupy consecutive periods.
    The “minpd” (contiguity) constraint is skipped here only insofar as not remapping blocks;
    but because block sessions have only block-aligned candidates, we enforce contiguity by construction.
    """
    subject_requirements = defaultdict(int)
    for sess in sessions:
        subject_requirements[sess['subject']] += sess.get('block_size', 1)

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
        # For blocks, look at earliest possible start
        earliest_candidate = min(sess['candidates']) if sess['candidates'] else PERIODS_PER_DAY * len(DAYS)
        return (no_sessions_yet, remaining_ratio, -earliest_candidate, len(sess['students']))

    def has_student_conflict(sess, day, start_period):
        bs = sess.get('block_size', 1)
        for offset in range(bs):
            period = start_period + offset
            for stu in sess['students']:
                if period in student_schedule[stu][day]:
                    return True
        return False

    def has_teacher_conflict(sess, day, start_period):
        bs = sess.get('block_size', 1)
        for offset in range(bs):
            slot_index = day * PERIODS_PER_DAY + (start_period + offset)
            for tid in sess['teachers']:
                if slot_index in teacher_schedule[tid]:
                    return True
        return False

    def find_best_slot(sess):
        sid = sess['subject']
        maxpd = sess['max_per_day']
        bs = sess.get('block_size', 1)

        # Compute how many of this subject are already on each day
        current_daily = dict(subject_daily[sid])

        # Build a list of candidate starts (some may be occupied or free)
        # We sort so that mornings are preferred, fewer already-occupied slots, etc.
        def slot_score(sl):
            day = sl // PERIODS_PER_DAY
            period = sl % PERIODS_PER_DAY
            occupied_count = sum(len(schedule.get((day, p), [])) for p in range(PERIODS_PER_DAY))
            return (
                period >= 5,                         # prefer morning (False < True)
                occupied_count > 0,                  # prefer less-busy days
                -day,                                # prefer earlier in week
                -period                              # prefer earlier in day
            )

        # Check each candidate start slot in order of preference
        for sl in sorted(sess['candidates'], key=slot_score):
            day = sl // PERIODS_PER_DAY
            start_p = sl % PERIODS_PER_DAY

            # Ensure block fits in the day
            if start_p + bs - 1 >= PERIODS_PER_DAY:
                continue

            # Subject maxpd: if placing bs periods, new daily total = current_daily.get(day,0) + bs
            new_count = current_daily.get(day, 0) + bs
            if new_count > maxpd:
                continue

            # Teacher conflict?
            if has_teacher_conflict(sess, day, start_p):
                continue

            # Student conflict?
            if has_student_conflict(sess, day, start_p):
                continue

            return sl

        return None

    total = sum(sess.get('block_size', 1) for sess in sessions)
    while True:
        pending = [s for s in sessions if subjects_scheduled[s['subject']] < subject_requirements[s['subject']]]
        if not pending:
            break
        pending_sorted = sorted(pending, key=session_priority, reverse=True)
        progress = False
        for sess in pending_sorted:
            sid = sess['subject']
            already = subjects_scheduled[sid]
            if already >= subject_requirements[sid]:
                continue
            slot = find_best_slot(sess)
            if slot is not None:
                day = slot // PERIODS_PER_DAY
                start_p = slot % PERIODS_PER_DAY
                bs = sess.get('block_size', 1)

                # Place the session (block_size consecutive periods)
                for offset in range(bs):
                    p = start_p + offset
                    schedule.setdefault((day, p), []).append(sess)
                    slot_index = day * PERIODS_PER_DAY + p
                    for tid in sess['teachers']:
                        teacher_schedule[tid].add(slot_index)
                    for stu in sess['students']:
                        student_schedule[stu][day].add(p)
                    subject_daily[sid][day] += 1

                subjects_scheduled[sid] += bs
                progress = True

        if not progress:
            break

    placed = sum(subjects_scheduled.values())
    unplaced = []
    for sess in sessions:
        sid = sess['subject']
        bs = sess.get('block_size', 1)
        if subjects_scheduled[sid] < subject_requirements[sid]:
            unplaced.append(sess['id'])
    logger.info(f"greedy_initial placed {placed} of {total} hours; unplaced={unplaced}")
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
            validate_final_schedule(best_schedule, sessions, subjects, teachers=None)
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
    """Check if `sess` has any student conflict at slot `key` (for block_size=1 or 2)."""
    if key not in schedule:
        return False
    sset = set(sess['students'])
    for other in schedule[key]:
        if sset & set(other['students']):
            return True
    return False

# --- Move Heuristics ---
def move_session_to_empty_slot(schedule, subjects):
    """Move a random session (possibly a block) from a busy slot to a “lighter” slot."""
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
    maxpd = session['max_per_day']
    raw_minpd = subjects[sid][6]
    subj_minpd = max(0, raw_minpd)
    bs = session.get('block_size', 1)

    orig_daily = _compute_subject_daily(schedule, sid)

    # Candidate target starts: any start where fewer sessions than source slot
    target_slots = []
    for day in range(4):
        for p in range(PERIODS_PER_DAY - bs + 1):
            if (day, p) == source_slot:
                continue
            count_here = len(schedule.get((day, p), []))
            count_source = len(schedule[source_slot])
            if count_here < count_source:
                day_load = sum(
                    teacher_loads[tid][day]
                    for sess2 in schedule.get((day, p), []) for tid in sess2['teachers']
                )
                target_slots.append((day_load, (day, p)))

    if not target_slots:
        return schedule

    def ts_score(x):
        load, (day, period) = x
        return (load, day, period, len(schedule.get((day, period), [])))

    target_slots.sort(key=ts_score)
    for _, (new_day, new_p) in target_slots:
        # Check block fits
        if new_p + bs - 1 >= PERIODS_PER_DAY:
            continue

        new_daily = orig_daily.copy()
        old_day = source_slot[0]
        new_daily[old_day] -= bs
        new_daily[new_day] += bs

        # Check subject daily maxpd
        if new_daily[new_day] > maxpd:
            continue

        # Teacher conflict?
        conflict = False
        for offset in range(bs):
            target_index = new_day * PERIODS_PER_DAY + (new_p + offset)
            for tid in session['teachers']:
                if target_index in teacher_schedule[tid]:
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            continue

        # Student conflict?
        conflict = False
        for offset in range(bs):
            if has_student_conflict(session, (new_day, new_p + offset), schedule):
                conflict = True
                break
        if conflict:
            continue

        # Commit move: remove from old block-size spans, add to new spans
        for offset in range(bs):
            old_slot = (old_day, source_slot[1] + offset)
            schedule[old_slot].remove(session)
            if not schedule[old_slot]:
                del schedule[old_slot]
        for offset in range(bs):
            new_slot = (new_day, new_p + offset)
            schedule.setdefault(new_slot, []).append(session)
        return schedule

    return schedule

def swap_two_sessions(schedule, subjects):
    """Swap two randomly picked sessions (possibly blocks) between different slots."""
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
    raw_minpd1 = subjects[sid1][6]
    raw_minpd2 = subjects[sid2][6]
    bs1 = sess1.get('block_size', 1)
    bs2 = sess2.get('block_size', 1)

    old_day1, old_p1 = slot1[0], slot1[1]
    old_day2, old_p2 = slot2[0], slot2[1]
    daily1 = _compute_subject_daily(schedule, sid1)
    daily2 = _compute_subject_daily(schedule, sid2)

    new_daily1 = daily1.copy()
    new_daily1[old_day1] -= bs1
    new_daily1[old_day2] += bs1
    new_daily2 = daily2.copy()
    new_daily2[old_day2] -= bs2
    new_daily2[old_day1] += bs2

    if new_daily1[old_day2] > maxpd1 or new_daily2[old_day1] > maxpd2:
        return schedule

    # Teacher conflict?
    conflict = False
    for offset in range(bs1):
        slot2_index = old_day2 * PERIODS_PER_DAY + (old_p2 + offset)
        for tid in sess1['teachers']:
            if slot2_index in teacher_schedule[tid] and (old_day2, old_p2 + offset) != slot1:
                conflict = True
                break
        if conflict:
            break
    if not conflict:
        for offset in range(bs2):
            slot1_index = old_day1 * PERIODS_PER_DAY + (old_p1 + offset)
            for tid in sess2['teachers']:
                if slot1_index in teacher_schedule[tid] and (old_day1, old_p1 + offset) != slot2:
                    conflict = True
                    break
            if conflict:
                break
    if conflict:
        return schedule

    # Student conflicts?
    for offset in range(bs1):
        if has_student_conflict(sess1, (old_day2, old_p2 + offset), schedule):
            return schedule
    for offset in range(bs2):
        if has_student_conflict(sess2, (old_day1, old_p1 + offset), schedule):
            return schedule

    # Commit swap
    for offset in range(bs1):
        slot_ = (old_day1, old_p1 + offset)
        schedule[slot_].remove(sess1)
        if not schedule[slot_]:
            del schedule[slot_]
    for offset in range(bs2):
        slot_ = (old_day2, old_p2 + offset)
        schedule[slot_].remove(sess2)
        if not schedule[slot_]:
            del schedule[slot_]

    for offset in range(bs1):
        slot_ = (old_day2, old_p2 + offset)
        schedule.setdefault(slot_, []).append(sess1)
    for offset in range(bs2):
        slot_ = (old_day1, old_p1 + offset)
        schedule.setdefault(slot_, []).append(sess2)

    return schedule

def move_parallel_group(schedule, subjects):
    """
    Move all sessions of a parallel group together to a random slot,
    respecting subject daily constraints and teacher/student conflicts.
    (Block sessions are treated similarly since their 'block_size' ensures
    only block-aligned candidates were allowed initially.)
    """
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
    max_block = max(sess.get('block_size', 1) for _, sess in group_sessions)
    target_p = random.randint(0, PERIODS_PER_DAY - max_block)
    target_slot = (target_day, target_p)

    daily_counts = {}
    for _, sess in group_sessions:
        sid = sess['subject']
        if sid not in daily_counts:
            daily_counts[sid] = _compute_subject_daily(schedule, sid)

    for old_slot, sess in group_sessions:
        sid = sess['subject']
        minpd = sess['min_per_day']
        maxpd = sess['max_per_day']
        bs = sess.get('block_size', 1)

        old_day = old_slot[0]
        new_daily = daily_counts[sid].copy()
        new_daily[old_day] -= bs
        new_daily[target_day] += bs

        if new_daily[target_day] > maxpd:
            return schedule

        for offset in range(bs):
            target_index = target_day * PERIODS_PER_DAY + (target_p + offset)
            for tid in sess['teachers']:
                if target_index in teacher_schedule[tid]:
                    return schedule

        for offset in range(bs):
            if has_student_conflict(sess, (target_day, target_p + offset), schedule):
                return schedule

    for old_slot, sess in group_sessions:
        bs = sess.get('block_size', 1)
        old_day, old_p = old_slot
        for offset in range(bs):
            slot_ = (old_day, old_p + offset)
            schedule[slot_].remove(sess)
            if not schedule[slot_]:
                del schedule[slot_]
        for offset in range(bs):
            new_slot = (target_day, target_p + offset)
            schedule.setdefault(new_slot, []).append(sess)

    return schedule

def reorganize_day(schedule, subjects):
    """
    For a random day, collect all sessions (including block sessions expanded into individual periods)
    and reassign them to the earliest possible periods, attempting to maximize valid parallelization
    (no student overlap). Block sessions remain intact during this process because their 'block_size'
    ensures they stay together.
    """
    day = random.randint(0, 3)

    original_entries = []
    for period in range(PERIODS_PER_DAY):
        slot = (day, period)
        if slot in schedule:
            for sess in schedule[slot]:
                original_entries.append((period, sess))
            del schedule[slot]

    if not original_entries:
        return schedule

    day_sessions = []
    seen_ids = set()
    for (_, sess) in original_entries:
        if sess['id'] not in seen_ids:
            seen_ids.add(sess['id'])
            day_sessions.append(sess)

    def parallel_potential(sess):
        return (len(sess['students']), sess['subject'])

    day_sessions.sort(key=parallel_potential)

    placed_slots = {}  # (day, period) -> [session, ...]
    period_idx = 0

    while day_sessions and period_idx < PERIODS_PER_DAY:
        to_remove = []
        for sess in list(day_sessions):
            bs = sess.get('block_size', 1)
            if period_idx + bs - 1 >= PERIODS_PER_DAY:
                continue
            can_add = True
            for offset in range(bs):
                for other in placed_slots.get((day, period_idx), []):
                    if set(sess['students']) & set(other['students']):
                        can_add = False
                        break
                if not can_add:
                    break
            if can_add:
                for offset in range(bs):
                    placed_slots.setdefault((day, period_idx + offset), []).append(sess)
                to_remove.append(sess)

        if to_remove:
            max_bs = max(sess.get('block_size', 1) for sess in to_remove)
            period_idx += max_bs
            for sess in to_remove:
                day_sessions.remove(sess)
        else:
            period_idx += 1

    for slot, sess_list in placed_slots.items():
        schedule[slot] = sess_list

    if day_sessions:
        original_map = defaultdict(list)
        for pr, sess in original_entries:
            original_map[sess['id']].append(pr)

        for sess in day_sessions:
            bs = sess.get('block_size', 1)
            orig_periods = sorted(original_map[sess['id']])
            placed = False
            for start_p in orig_periods:
                if start_p + bs - 1 < PERIODS_PER_DAY:
                    can_place = True
                    for offset in range(bs):
                        if has_student_conflict(sess, (day, start_p + offset), schedule):
                            can_place = False
                            break
                    if can_place:
                        for offset in range(bs):
                            slot_ = (day, start_p + offset)
                            schedule.setdefault(slot_, []).append(sess)
                        placed = True
                        break
            if not placed:
                start_p = orig_periods[0]
                for offset in range(bs):
                    slot_ = (day, start_p + offset)
                    schedule.setdefault(slot_, []).append(sess)

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
        formatted['days'][str(day)].setdefault(str(period), [])
        for sess in slot_sessions:
            sid = sess['subject']
            subj_info = subject_dict[sid]
            bs = sess.get('block_size', 1)
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
    if teachers:
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
