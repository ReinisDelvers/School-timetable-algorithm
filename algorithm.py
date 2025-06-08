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
STALL_THRESHOLD = 1000       # Stop if no improvement for 10,000 iterations
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
      - No subject is assigned more teachers than its group count (except parallel).
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
            # Parallel offerings: skip this check
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
    Parallel subjects (subj[7] == 1) are treated as a single multi-teacher session and later split.
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

        # All students who take this subject (grouped)
        all_students = sorted(list(subj_students.get(sid, set())))

        # All teachers assigned to this subject
        teacher_groups = subject_teacher_groups.get(sid, [])
        if not teacher_groups:
            logger.error(f"No teacher assigned for Subject {sid}, cannot build sessions")
            continue

        # ----------------------------------------------------------------
        # If subj[7] == 1 → “parallel scheduling” for this subject
        #   * Combine all teachers into one session
        #   * Mark is_parallel = True, parallel_with = sid
        # ----------------------------------------------------------------
        if subj[7] == 1:
            required_groups = subj[2]     # number of parallel groups
            all_tids = [tid for tid, _ in teacher_groups]
            parallel_id = sid

            hours_remaining = hours_per_week
            if minpd >= 2:
                full_blocks = hours_per_week // minpd
                leftover = hours_per_week - (full_blocks * minpd)

                # Create all block sessions of size `minpd`
                for _ in range(full_blocks):
                    block_session = create_block_session(
                        sid=sid,
                        teachers_list=all_tids,
                        students=all_students,
                        teachers_dict=teachers,
                        block_size=minpd,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=parallel_id
                    )
                    block_session['teachers'] = all_tids
                    block_session['is_parallel'] = True
                    block_session['parallel_with'] = parallel_id
                    sessions.append(block_session)
                    hours_remaining -= minpd

                # leftover single-hour session
                if leftover > 0:
                    single_session = create_single_session(
                        sid=sid,
                        teachers_list=all_tids,
                        hour=0,
                        students=all_students,
                        teachers_dict=teachers,
                        maxpd=maxpd,
                        minpd=1,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=parallel_id
                    )
                    single_session['teachers'] = all_tids
                    single_session['is_parallel'] = True
                    single_session['parallel_with'] = parallel_id
                    sessions.append(single_session)
                    hours_remaining -= 1

            else:
                # Build hour-by-hour
                while hours_remaining > 0:
                    single_session = create_single_session(
                        sid=sid,
                        teachers_list=all_tids,
                        hour=(hours_per_week - hours_remaining),
                        students=all_students,
                        teachers_dict=teachers,
                        maxpd=maxpd,
                        minpd=minpd,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=parallel_id
                    )
                    single_session['teachers'] = all_tids
                    single_session['is_parallel'] = True
                    single_session['parallel_with'] = parallel_id
                    sessions.append(single_session)
                    hours_remaining -= 1

            # Double-check that we've created exactly hours_per_week hours
            built = sum(
                sess['block_size'] if sess.get('block_size', 1) > 1 else 1
                for sess in sessions
                if sess['subject'] == sid
            )
            if built != hours_per_week:
                logger.error(f"Subject {sid}: built {built} hrs, required {hours_per_week}")

            # Skip the normal (non-parallel) logic
            continue

        # ----------------------------------------------------------------
        # ORIGINAL (non-parallel) logic: assign each hour to a single teacher
        # ----------------------------------------------------------------
        hours_remaining = hours_per_week
        teacher_idx = 0

        if minpd >= 2:
            full_blocks = hours_per_week // minpd
            leftover = hours_per_week - (full_blocks * minpd)

            for _ in range(full_blocks):
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                block_session = create_block_session(
                    sid=sid,
                    teachers_list=[tid],
                    students=all_students,
                    teachers_dict=teachers,
                    block_size=minpd,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=None
                )
                sessions.append(block_session)
                hours_remaining -= minpd
                teacher_idx += 1

            if leftover > 0:
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                single_session = create_single_session(
                    sid=sid,
                    teachers_list=[tid],
                    hour=0,
                    students=all_students,
                    teachers_dict=teachers,
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
            while hours_remaining > 0:
                tid, _ = teacher_groups[teacher_idx % len(teacher_groups)]
                session = create_single_session(
                    sid=sid,
                    teachers_list=[tid],
                    hour=(hours_per_week - hours_remaining),
                    students=all_students,
                    teachers_dict=teachers,
                    maxpd=maxpd,
                    minpd=minpd,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=None
                )
                sessions.append(session)
                hours_remaining -= 1
                teacher_idx += 1

        created_hours = sum(
            sess['block_size'] if sess.get('block_size', 1) > 1 else 1
            for sess in sessions
            if sess['subject'] == sid
        )
        if created_hours != hours_per_week:
            logger.error(f"Subject {sid}: built {created_hours} sessions, required {hours_per_week} (hours)")

    # Summary of sessions built
    cnt = Counter()
    for sess in sessions:
        cnt[sess['subject']] += sess.get('block_size', 1)
    for sid, subj in subjects.items():
        required = subj[3]
        built = cnt[sid]
        logger.info(f"Subject {sid}: built {built} sessions, required {required} (hours)")

    return sessions

def create_single_session(sid, teachers_list, hour, students, teachers_dict,
                          maxpd, minpd, hour_blocker, subjects_dict,
                          parallel_group=None):
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

    for di, day in enumerate(DAYS):
        # must be available that day
        if not all(teachers_dict[tid][4 + di] for tid in teachers_list):
            continue

        for p in range(PERIODS_PER_DAY):
            # global blocker
            if hour_blocker[day][p] != 1:
                continue

            # half-day blocker  
            half_index = 8 + di if p < PERIODS_PER_DAY//2 else 12 + di
            if any(teachers_dict[tid][half_index] == 1 for tid in teachers_list):
                continue

            session['candidates'].append(di * PERIODS_PER_DAY + p)

    if not session['candidates']:
        logger.error(f"Session {session['id']} (Subject {sid}) has NO CANDIDATES.")
    return session


def create_block_session(sid, teachers_list, students, teachers_dict,
                         block_size, hour_blocker, subjects_dict,
                         parallel_group=None):
    session = {
        'id': f"S{sid}_B{block_size}_{random.randint(0,1_000_000)}",
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

    for di, day in enumerate(DAYS):
        # must be available that day
        if not all(teachers_dict[tid][4 + di] for tid in teachers_list):
            continue

        for p in range(PERIODS_PER_DAY - block_size + 1):
            can_place = True
            for offset in range(block_size):
                # global blocker
                if hour_blocker[day][p + offset] != 1:
                    can_place = False
                    break

                # half-day blocker
                half_index = 8 + di if (p + offset) < PERIODS_PER_DAY//2 else 12 + di
                if any(teachers_dict[tid][half_index] == 1 for tid in teachers_list):
                    can_place = False
                    break

            if can_place:
                session['candidates'].append(di * PERIODS_PER_DAY + p)

    if not session['candidates']:
        logger.error(f"Block session {session['id']} (Subject {sid}, size={block_size}) has NO CANDIDATES.")
    return session



# --- Evaluation Function (penalizes idle gaps) ---
def evaluate_schedule(schedule, all_sessions, subjects):
    """
    Compute a numeric score of `schedule`. Lower is better.
    Penalize:
      - Too many or too few sessions per subject per week.
      - Subject daily minpd/maxpd violations (with contiguity checks).
      - Student conflicts (same slot).
      - Teacher conflicts (same slot).
      - Student daily load <4 or >6 (penalized but not hard).
      - Idle gaps between a student’s classes.
    """
    IDLE_PENALTY = 1000  # penalty per empty period between classes

    score = 0
    scheduled_count = defaultdict(int)
    student_schedule = defaultdict(lambda: defaultdict(list))
    student_daily_hours = defaultdict(lambda: defaultdict(int))
    subject_daily_hours = defaultdict(lambda: defaultdict(int))
    teacher_daily_slots = defaultdict(lambda: defaultdict(set))

    # Tally through scheduled slots
    for (day, period), slot_sessions in schedule.items():
        for sess in slot_sessions:
            sid = sess['subject']
            scheduled_count[sid] += 1
            for student in sess['students']:
                # Check student conflict
                if period in student_schedule[student][day]:
                    score += 8000  # Hard penalty for overlap
                student_schedule[student][day].append(period)
                student_daily_hours[student][day] += 1
            subject_daily_hours[sid][day] += 1
            for tid in sess['teachers']:
                if period in teacher_daily_slots[tid][day]:
                    score += 10000  # Hard penalty for teacher conflict
                teacher_daily_slots[tid][day].add(period)

        # Check subject max per day (redundant with the below, but kept)
        for sess in slot_sessions:
            sid = sess['subject']
            maxpd = sess['max_per_day']
            if subject_daily_hours[sid][day] > maxpd:
                over = subject_daily_hours[sid][day] - maxpd
                score += 5000 * over

    # Enforce minpd and contiguity for each subject
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

    # --- Idle‐time / gap penalty ---
    for student, daily in student_schedule.items():
        for d, periods in daily.items():
            if len(periods) <= 1:
                continue
            sorted_periods = sorted(periods)
            for i in range(len(sorted_periods)-1):
                gap = sorted_periods[i+1] - sorted_periods[i] - 1
                if gap > 0:
                    score += IDLE_PENALTY * gap

    return score

# --- Greedy Initial Construction (now gap-aware) ---
def greedy_initial(sessions, subjects):
    """
    Build a starting schedule by placing sessions one‐by‐one greedily,
    respecting teacher availability, student overlaps, and subject maxpd.
    Now also prioritizes minimizing empty gaps between classes for students.
    """
    subject_requirements = defaultdict(int)
    for sess in sessions:
        subject_requirements[sess['subject']] += sess.get('block_size', 1)

    subjects_scheduled = defaultdict(int)
    subject_daily = defaultdict(lambda: defaultdict(int))
    teacher_schedule = defaultdict(set)
    student_schedule = defaultdict(lambda: defaultdict(list))
    schedule = {}  # (day,period) -> [session, ...]

    def session_priority(sess):
        sid = sess['subject']
        required = subject_requirements[sid]
        placed = subjects_scheduled[sid]
        no_sessions_yet = (placed == 0)
        remaining_ratio = (required - placed) / required if required > 0 else 0
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

    def slot_score(sess, sl):
        """
        Ranking tuple:
          1) prefer morning (period < 5)
          2) prefer less‐busy days
          3) earlier in week
          4) earlier in day
          5) student‐proximity (avg distance to existing)
          6) gap-penalty (fewer new gaps)
        """
        day = sl // PERIODS_PER_DAY
        period = sl % PERIODS_PER_DAY

        # (1) prefer morning
        morning_flag = (period >= 5)

        # (2) prefer less‐busy days
        occupied_count = sum(len(schedule.get((day, p), [])) for p in range(PERIODS_PER_DAY))
        busy_flag = (occupied_count > 0)

        # (3) prefer earlier in week
        week_flag = -day

        # (4) prefer earlier in day
        day_flag = -period

        # (5) student‐proximity measure
        total_dist = 0
        count = 0
        for stu in sess['students']:
            existing = student_schedule[stu][day]
            if not existing:
                total_dist += PERIODS_PER_DAY
            else:
                total_dist += min(abs(period - p0) for p0 in existing)
            count += 1
        avg_dist = (total_dist / count) if count > 0 else PERIODS_PER_DAY
        proximity_flag = -avg_dist

        # (6) gap-penalty: how many new empty slots between first & last
        gap_penalty = 0
        for stu in sess['students']:
            existing = sorted(student_schedule[stu][day])
            if not existing:
                continue
            old_gaps = sum(existing[i+1] - existing[i] - 1 for i in range(len(existing)-1))
            new_list = sorted(existing + [period])
            new_gaps = sum(new_list[i+1] - new_list[i] - 1 for i in range(len(new_list)-1))
            gap_penalty += (new_gaps - old_gaps)
        gap_flag = -gap_penalty

        return (morning_flag, busy_flag, week_flag, day_flag, proximity_flag, gap_flag)

    def find_best_slot(sess):
        sid = sess['subject']
        maxpd = sess['max_per_day']
        bs = sess.get('block_size', 1)
        current_daily = dict(subject_daily[sid])

        for sl in sorted(sess['candidates'], key=lambda x: slot_score(sess, x)):
            day = sl // PERIODS_PER_DAY
            start_p = sl % PERIODS_PER_DAY
            if start_p + bs - 1 >= PERIODS_PER_DAY:
                continue

            new_count = current_daily.get(day, 0) + bs
            if new_count > maxpd:
                continue
            if has_teacher_conflict(sess, day, start_p):
                continue
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
            if subjects_scheduled[sid] >= subject_requirements[sid]:
                continue
            slot = find_best_slot(sess)
            if slot is not None:
                day = slot // PERIODS_PER_DAY
                start_p = slot % PERIODS_PER_DAY
                bs = sess.get('block_size', 1)

                # Place session
                for offset in range(bs):
                    p = start_p + offset
                    schedule.setdefault((day, p), []).append(sess)
                    idx = day * PERIODS_PER_DAY + p
                    for tid in sess['teachers']:
                        teacher_schedule[tid].add(idx)
                    for stu in sess['students']:
                        student_schedule[stu][day].append(p)
                    subject_daily[sid][day] += 1

                subjects_scheduled[sid] += bs
                progress = True

        if not progress:
            break

    placed = sum(subjects_scheduled.values())
    unplaced = [s['id'] for s in sessions if subjects_scheduled[s['subject']] < subject_requirements[s['subject']]]
    logger.info(f"greedy_initial placed {placed} of {total} hours; unplaced={unplaced}")
    return schedule

# --- Solver with Simulated Annealing & Fallback (unchanged) ---
def solve_timetable(sessions, subjects, teachers, hour_blocker, time_limit=1200, stop_flag=None):
    start_time = time.time()
    original_sessions = copy.deepcopy(sessions)

    current = greedy_initial(sessions, subjects)
    placed_counts = count_placed_hours(current)
    missing_any = any(placed_counts.get(sid,0) < subj[3] for sid, subj in subjects.items())

    if missing_any:
        logger.info("Fallback: breaking blocks into singles")
        sessions = fallback_replace_blocks_with_all_singles(
            original_sessions, current, subjects, teachers, hour_blocker
        )
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
    students_dict = {
        s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()}
        for s in get_student()
    }

    while temp > min_temp and (time.time() - start_time < time_limit):
        if stop_flag and stop_flag():
            break
        iteration += 1
        neighbor = generate_neighbor(current, subjects)
        neighbor_score = evaluate_schedule(neighbor, sessions, subjects)
        delta = neighbor_score - current_score

        if delta < 0 or random.random() < math.exp(-delta / temp):
            current, current_score = neighbor, neighbor_score
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
            logger.error("No improvement for too long, stopping.")
            validate_final_schedule(best_schedule, sessions, subjects, teachers)
            break

        temp *= cooling_rate

    return best_schedule, students_dict

def count_placed_hours(schedule):
    placed = defaultdict(int)
    for (_, _), slot in schedule.items():
        for sess in slot:
            placed[sess['subject']] += 1
    return placed

def fallback_replace_blocks_with_all_singles(all_sessions, placed_schedule, subjects, teachers, hour_blocker):
    placed_counts = count_placed_hours(placed_schedule)
    missing = {sid: subj[3] for sid, subj in subjects.items() if placed_counts.get(sid,0) < subj[3]}
    if not missing:
        return all_sessions

    subject_teachers = defaultdict(list)
    for st in get_subject_teacher():
        s_id, t_id = st[1], st[3]
        subject_teachers[s_id].append(t_id)

    new_sessions = [s for s in all_sessions if s['subject'] not in missing]
    for sid, req in missing.items():
        teachers_list = subject_teachers.get(sid,[])
        all_students = next((s['students'] for s in all_sessions if s['subject']==sid),[])
        maxpd = subjects[sid][4]
        for h in range(req):
            tid = teachers_list[h % len(teachers_list)]
            single = create_single_session(
                sid=sid, teachers_list=[tid], hour=h,
                students=all_students, teachers_dict=teachers,
                maxpd=maxpd, minpd=1,
                hour_blocker=hour_blocker,
                subjects_dict=subjects,
                parallel_group=None
            )
            new_sessions.append(single)
    return new_sessions

def generate_neighbor(schedule, subjects):
    moves = [
        move_session_to_empty_slot,
        swap_two_sessions,
        move_parallel_group,
        reorganize_day
    ]
    move = random.choice(moves)
    return move(copy.deepcopy(schedule), subjects)

def _compute_subject_daily(schedule, sid):
    counts = defaultdict(int)
    for (d, p), sl in schedule.items():
        for sess in sl:
            if sess['subject']==sid:
                counts[d]+=1
    return counts

def has_student_conflict(sess, key, schedule):
    if key not in schedule:
        return False
    sset = set(sess['students'])
    for other in schedule[key]:
        if sset & set(other['students']):
            return True
    return False

# --- Move Heuristics (unchanged) ---
def move_session_to_empty_slot(schedule, subjects):
    occupied = list(schedule.keys())
    if not occupied:
        return schedule
    teacher_sched = defaultdict(set)
    for (d,p), sl in schedule.items():
        idx = d*PERIODS_PER_DAY + p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_sched[tid].add(idx)

    loads = defaultdict(lambda: defaultdict(int))
    for (d,p), sl in schedule.items():
        for sess in sl:
            for tid in sess['teachers']:
                loads[tid][d]+=1

    slot_scores = []
    for slot in occupied:
        day = slot[0]
        max_load=0
        for sess in schedule[slot]:
            for tid in sess['teachers']:
                max_load=max(max_load, loads[tid][day])
        slot_scores.append((max_load,slot))
    source = max(slot_scores,key=lambda x:x[0])[1]
    if source not in schedule or not schedule[source]:
        return schedule

    session = random.choice(schedule[source])
    sid=session['subject']
    maxpd=session['max_per_day']
    bs=session.get('block_size',1)
    orig_daily=_compute_subject_daily(schedule,sid)

    target=[]
    for d in range(4):
        for p in range(PERIODS_PER_DAY-bs+1):
            if (d,p)==source: continue
            if len(schedule.get((d,p),[])) < len(schedule[source]):
                day_load=sum(loads[tid][d] for sess2 in schedule.get((d,p),[]) for tid in sess2['teachers'])
                target.append((day_load,(d,p)))

    if not target:
        return schedule

    target.sort(key=lambda x:(x[0],x[1][0],x[1][1],len(schedule.get(x[1],[]))))
    for _,(nd,np) in target:
        if np+bs-1>=PERIODS_PER_DAY: continue
        newd=orig_daily.copy()
        oldd=source[0]
        newd[oldd]-=bs; newd[nd]+=bs
        if newd[nd]>maxpd: continue

        conflict=False
        for off in range(bs):
            idx=nd*PERIODS_PER_DAY+(np+off)
            for tid in session['teachers']:
                if idx in teacher_sched[tid]:
                    conflict=True; break
            if conflict: break
        if conflict: continue

        for off in range(bs):
            if has_student_conflict(session,(nd,np+off),schedule):
                conflict=True; break
        if conflict: continue

        old_slots=[k for k,v in schedule.items() if session in v]
        for os in old_slots:
            schedule[os].remove(session)
            if not schedule[os]: del schedule[os]
        for off in range(bs):
            slot=(nd,np+off)
            schedule.setdefault(slot,[]).append(session)
        return schedule

    return schedule

def swap_two_sessions(schedule, subjects):
    occupied=list(schedule.keys())
    if len(occupied)<2: return schedule
    teacher_sched=defaultdict(set)
    for (d,p),sl in schedule.items():
        idx=d*PERIODS_PER_DAY+p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_sched[tid].add(idx)

    s1,s2=random.sample(occupied,2)
    if not schedule[s1] or not schedule[s2]: return schedule

    sess1=random.choice(schedule[s1])
    sess2=random.choice(schedule[s2])
    sid1,sid2=sess1['subject'],sess2['subject']
    maxpd1,maxpd2=sess1['max_per_day'],sess2['max_per_day']
    bs1,bs2=sess1.get('block_size',1),sess2.get('block_size',1)
    d1,p1=s1; d2,p2=s2

    daily1,_daily2 = _compute_subject_daily(schedule,sid1),_compute_subject_daily(schedule,sid2)
    nd1=daily1.copy(); nd2=_daily2.copy()
    nd1[d1]-=bs1; nd1[d2]+=bs1
    nd2[d2]-=bs2; nd2[d1]+=bs2
    if nd1[d2]>maxpd1 or nd2[d1]>maxpd2: return schedule

    # teacher conflict
    for off in range(bs1):
        idx2=d2*PERIODS_PER_DAY+(p2+off)
        for tid in sess1['teachers']:
            if idx2 in teacher_sched[tid] and (d2,p2+off)!=s1:
                return schedule
    for off in range(bs2):
        idx1=d1*PERIODS_PER_DAY+(p1+off)
        for tid in sess2['teachers']:
            if idx1 in teacher_sched[tid] and (d1,p1+off)!=s2:
                return schedule

    # student conflict
    for off in range(bs1):
        if has_student_conflict(sess1,(d2,p2+off),schedule): return schedule
    for off in range(bs2):
        if has_student_conflict(sess2,(d1,p1+off),schedule): return schedule

    old1=[k for k,v in schedule.items() if sess1 in v]
    old2=[k for k,v in schedule.items() if sess2 in v]
    for o in old1:
        schedule[o].remove(sess1)
        if not schedule[o]: del schedule[o]
    for o in old2:
        schedule[o].remove(sess2)
        if not schedule[o]: del schedule[o]
    for o in old2:
        schedule.setdefault(o,[]).append(sess1)
    for o in old1:
        schedule.setdefault(o,[]).append(sess2)
    return schedule

def move_parallel_group(schedule, subjects):
    teacher_sched=defaultdict(set)
    for (d,p),sl in schedule.items():
        idx=d*PERIODS_PER_DAY+p
        for sess in sl:
            for tid in sess['teachers']:
                teacher_sched[tid].add(idx)

    parallel_groups=defaultdict(list)
    for slot,sl in schedule.items():
        for sess in sl:
            if sess.get('is_parallel'):
                parallel_groups[sess['parallel_with']].append((slot,sess))
    if not parallel_groups:
        return schedule

    group_id=random.choice(list(parallel_groups.keys()))
    group_sessions=parallel_groups[group_id]
    target_day=random.randint(0,3)
    max_block=max(sess.get('block_size',1) for _,sess in group_sessions)
    target_p=random.randint(0,PERIODS_PER_DAY-max_block)

    daily_counts={}
    for _,sess in group_sessions:
        sid=sess['subject']
        daily_counts[sid]=_compute_subject_daily(schedule,sid)

    for old_slot,sess in group_sessions:
        sid=sess['subject']
        maxpd=sess['max_per_day']
        bs=sess.get('block_size',1)
        old_day=old_slot[0]
        new_daily=daily_counts[sid].copy()
        new_daily[old_day]-=bs; new_daily[target_day]+=bs
        if new_daily[target_day]>maxpd: return schedule

        for off in range(bs):
            idx=target_day*PERIODS_PER_DAY+(target_p+off)
            for tid in sess['teachers']:
                if idx in teacher_sched[tid]: return schedule
        for off in range(bs):
            if has_student_conflict(sess,(target_day,target_p+off),schedule):
                return schedule

    # commit
    for old_slot,sess in group_sessions:
        olds=[k for k,v in schedule.items() if sess in v]
        for o in olds:
            schedule[o].remove(sess)
            if not schedule[o]: del schedule[o]
    for _,sess in group_sessions:
        bs=sess.get('block_size',1)
        for off in range(bs):
            slot=(target_day,target_p+off)
            schedule.setdefault(slot,[]).append(sess)
    return schedule

def reorganize_day(schedule, subjects):
    day=random.randint(0,3)
    original=[]
    for p in range(PERIODS_PER_DAY):
        slot=(day,p)
        if slot in schedule:
            for sess in schedule[slot]:
                original.append((p,sess))
            del schedule[slot]
    if not original:
        return schedule

    day_sessions=[]; seen=set()
    for _,sess in original:
        if sess['id'] not in seen:
            seen.add(sess['id'])
            day_sessions.append(sess)

    day_sessions.sort(key=lambda s:(len(s['students']),s['subject']))
    placed={}
    idx=0
    while day_sessions and idx<PERIODS_PER_DAY:
        torem=[]
        for sess in list(day_sessions):
            bs=sess.get('block_size',1)
            if idx+bs-1>=PERIODS_PER_DAY: continue
            ok=True
            for off in range(bs):
                for other in placed.get((day,idx),[]):
                    if set(sess['students'])&set(other['students']):
                        ok=False; break
                if not ok: break
            if ok:
                for off in range(bs):
                    placed.setdefault((day,idx+off),[]).append(sess)
                torem.append(sess)
        if torem:
            idx+=max(s.get('block_size',1) for s in torem)
            for s in torem:
                day_sessions.remove(s)
        else:
            idx+=1

    for slot,sl in placed.items():
        schedule[slot]=sl

    if day_sessions:
        orig_map=defaultdict(list)
        for p,sess in original:
            orig_map[sess['id']].append(p)
        for sess in day_sessions:
            bs=sess.get('block_size',1)
            for start in orig_map[sess['id']]:
                if start+bs-1<PERIODS_PER_DAY:
                    ok=True
                    for off in range(bs):
                        if has_student_conflict(sess,(day,start+off),schedule):
                            ok=False; break
                    if ok:
                        for off in range(bs):
                            schedule.setdefault((day,start+off),[]).append(sess)
                        break
            else:
                for off in range(bs):
                    schedule.setdefault((day,orig_map[sess['id']][0]+off),[]).append(sess)

    return schedule

# --- Output & Validation ---
def format_schedule_output(schedule, subjects, teachers, students_dict):
    subject_dict = {
        s[0]: {'id': s[0], 'name': s[1], 'group_count': s[2]}
        for s in subjects.values()
    }
    teacher_dict = {
        t[0]: {'id': t[0], 'name': f"{t[1]} {t[2] or ''} {t[3]}".strip()}
        for t in teachers.values()
    }

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
            day_str = str(day)
            period_str = str(period)

            if sess.get('is_parallel'):
                required_groups = subj_info['group_count']
                student_count   = len(sess['students'])
                per_group = math.ceil(student_count / required_groups)
                groups = [
                    sess['students'][i : i + per_group]
                    for i in range(0, student_count, per_group)
                ]
                while len(groups) < required_groups:
                    groups.append([])

                for gi, grp in enumerate(groups):
                    if gi < len(sess['teachers']):
                        chosen_tid = sess['teachers'][gi]
                    else:
                        chosen_tid = None

                    formatted_session = {
                        'id': f"{sess['id']}_G{gi+1}",
                        'subject_id': sid,
                        'subject_name': subj_info['name'],
                        'teachers': [],
                        'students': [
                            {'id': s, 'name': students_dict[s]['name']}
                            for s in grp
                        ],
                        'group': gi + 1,
                        'is_parallel': True,
                        'parallel_group_id': sess['id']
                    }
                    if chosen_tid is not None:
                        formatted_session['teachers'] = [
                            {'id': chosen_tid, 'name': teacher_dict[chosen_tid]['name']}
                        ]
                    formatted['days'][day_str][period_str].append(formatted_session)

            else:
                formatted_session = {
                    'id': sess['id'],
                    'subject_id': sid,
                    'subject_name': subj_info['name'],
                    'teachers': [
                        {'id': tid, 'name': teacher_dict[tid]['name']}
                        for tid in sess['teachers']
                    ],
                    'students': [
                        {'id': s, 'name': students_dict[s]['name']}
                        for s in sess['students']
                    ],
                    'group': sess['group'],
                    'is_parallel': False,
                    'parallel_group_id': None
                }
                formatted['days'][day_str][period_str].append(formatted_session)

    return formatted

def validate_final_schedule(schedule, sessions, subjects, teachers):
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

    logger.info(f"\n--- Total Student Conflicts: {stats['student_conflicts']} ---")
    for stu, day, period, sess_ids in stats['student_conflict_details']:
        logger.error(f" Student {stu} conflict at {DAYS[day]} period {period}: {sess_ids}")

    logger.info(f"\n--- Total Teacher Conflicts: {stats['teacher_conflicts']} ---")
    for tid, day, period, sess_ids in stats['teacher_conflict_details']:
        logger.error(f" Teacher {tid} conflict at {DAYS[day]} period {period}: {sess_ids}")

    logger.info("\n--- Teacher Daily Loads ---")
    for tid, daily in stats['teacher_daily_load'].items():
        name = f"{teachers[tid][1]} {teachers[tid][3]}"
        logger.info(f"Teacher {tid} ({name}):")
        for d in range(4):
            load = daily.get(d, 0)
            logger.info(f"   {DAYS[d].capitalize()}: {load} session{'s' if load != 1 else ''}")

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
    teachers, subjects, students_raw, st_map, subj_students, hour_blocker, student_groups = load_data()
    sessions = build_sessions(teachers, subjects, st_map, subj_students, hour_blocker)

    schedule, students_dict = solve_timetable(sessions, subjects, teachers, hour_blocker, time_limit=1200)

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
