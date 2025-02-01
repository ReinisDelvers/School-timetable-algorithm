#!/usr/bin/env python3
import itertools
import math
import json
import logging
import multiprocessing
import os
import psutil
import random
import threading
import time
from datetime import datetime
from data import get_teacher, get_subject, get_student, get_subject_teacher, get_subject_student

##############################
# 1) LOGGING SETUP
##############################

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(processName)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger()

logger = setup_logging()

##############################
# 2) MEMORY MONITORING (Optional)
##############################

def dump_callback(mem_usage):
    logger.error(f"Memory usage reached {mem_usage:.2f} GB. Dumping current state not implemented in this example.")

def memory_monitor(stop_event, memory_limit_gb=1.0, check_interval=5):
    process = psutil.Process(os.getpid())
    while not stop_event.is_set():
        mem_usage = process.memory_info().rss / (1024 ** 3)  # in GB
        if mem_usage >= memory_limit_gb:
            dump_callback(mem_usage)
        time.sleep(check_interval)

##############################
# 3) DATA LOADING (adapted from your previous algorithm)
##############################

def load_data():
    try:
        teachers_raw    = get_teacher()
        subjects_raw    = get_subject()
        students_raw    = get_student()
        sub_teacher_raw = get_subject_teacher()
        sub_student_raw = get_subject_student()

        # Build teachers dict
        teachers = {}
        for t in teachers_raw:
            teacher_id = t[0]
            teachers[teacher_id] = {
                "id": teacher_id,
                "name": t[1],
                "middle_name": t[2],
                "last_name": t[3],
                "available_days": {
                    "monday":    bool(t[4]),
                    "tuesday":   bool(t[5]),
                    "wednesday": bool(t[6]),
                    "thursday":  bool(t[7]),
                },
            }

        # Build subjects dict
        subjects = {}
        for s in subjects_raw:
            subj_id = s[0]
            subjects[subj_id] = {
                "id": subj_id,
                "name": s[1],
                "group_number": s[2],
                "hours_per_week": s[3],
                "max_hours_per_day": s[4],
                "max_students_per_group": s[5],
                "min_hours_per_day": s[6],
            }

        # Build subject_teacher_map: subject_id -> list of (teacher_id, group_number)
        subject_teacher_map = {}
        for row in sub_teacher_raw:
            subject_id = row[1]
            teacher_id = row[3]
            group_num  = row[7]
            subject_teacher_map.setdefault(subject_id, []).append((teacher_id, group_num))

        # Build subject_to_students: subject_id -> set(student_ids)
        subject_to_students = {}
        for row in sub_student_raw:
            student_id = row[3]
            json_subject_str = row[1]
            try:
                subj_ids = json.loads(json_subject_str)
            except json.JSONDecodeError:
                subj_ids = []
            for sid in subj_ids:
                subject_to_students.setdefault(sid, set()).add(student_id)

        logger.info(f"Loaded {len(teachers)} teachers, {len(subjects)} subjects.")
        for subj_id, teacher_list in subject_teacher_map.items():
            logger.info(f"Subject {subj_id} has {len(teacher_list)} teacher assignment(s).")
        for subj_id, student_set in subject_to_students.items():
            logger.info(f"Subject {subj_id} has {len(student_set)} student(s).")

        return {
            "teachers": teachers,
            "subjects": subjects,
            "subject_teacher_map": subject_teacher_map,
            "subject_to_students": subject_to_students
        }
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

##############################
# 4) HELPER FUNCTIONS FOR SCHEDULING
##############################

# Days and slots settings
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
SLOTS_PER_DAY = 10

def get_teacher_available_days(teacher):
    return [day for day, avail in teacher["available_days"].items() if avail]

def generate_period_distributions(total_periods, available_days, min_periods, max_periods):
    day_options = []
    for _ in available_days:
        options = [0] + list(range(min_periods, max_periods + 1))
        day_options.append(options)
    distributions = []
    for combo in itertools.product(*day_options):
        if sum(combo) == total_periods:
            distributions.append(dict(zip(available_days, combo)))
    return distributions

def generate_timeslot_options(distribution, slots_per_day=SLOTS_PER_DAY):
    days_with_class = [day for day, periods in distribution.items() if periods > 0]
    if not days_with_class:
        return [{}]
    possible_starts = []
    for day in days_with_class:
        duration = distribution[day]
        possible_starts.append(list(range(0, slots_per_day - duration + 1)))
    timeslot_options = []
    for combo in itertools.product(*possible_starts):
        assignment = {}
        for i, day in enumerate(days_with_class):
            assignment[day] = (combo[i], distribution[day])
        timeslot_options.append(assignment)
    return timeslot_options

def partition_students(students_list, total_groups, max_per_group):
    """
    Partition students_list into total_groups groups, ensuring each group does not exceed max_per_group.
    Returns a list of groups (each a list of student ids) or None if not possible.
    """
    num_students = len(students_list)
    if total_groups <= 0:
        return []
    group_size = math.ceil(num_students / total_groups)
    if group_size > max_per_group:
        return None
    groups = []
    for i in range(total_groups):
        groups.append(students_list[i*group_size:(i+1)*group_size])
    return groups

def simple_partition(lst, n):
    """Partition lst evenly into n parts (without a max constraint)."""
    size = math.ceil(len(lst) / n)
    return [lst[i*size:(i+1)*size] for i in range(n)]

def candidate_conflict_check(schedule):
    """
    Given a complete schedule (a list of candidate options, each is (teacher_assignment, ts_assignment, student_group)),
    check that no teacher or student is double-booked.
    """
    teacher_schedule = {}  # teacher_id -> day -> list of intervals
    student_schedule = {}  # student_id -> day -> list of intervals

    for option in schedule:
        teacher_assignment, ts_assignment, student_group = option
        teacher_id = teacher_assignment[0]
        for day, (start, duration) in ts_assignment.items():
            interval = (start, start + duration)
            teacher_schedule.setdefault(teacher_id, {}).setdefault(day, []).append(interval)
            for student in student_group:
                student_schedule.setdefault(student, {}).setdefault(day, []).append(interval)
    def overlaps(intervals):
        intervals_sorted = sorted(intervals, key=lambda x: x[0])
        for i in range(1, len(intervals_sorted)):
            if intervals_sorted[i][0] < intervals_sorted[i-1][1]:
                return True
        return False
    for tid, days in teacher_schedule.items():
        for day, ints in days.items():
            if overlaps(ints):
                return True
    for sid, days in student_schedule.items():
        for day, ints in days.items():
            if overlaps(ints):
                return True
    return False

def conflict_between(option, current_schedule):
    """
    Returns True if adding option to current_schedule would create a conflict.
    (It only checks conflicts for the teacher and students in option.)
    """
    teacher_assignment, ts_assignment, student_group = option
    teacher_id = teacher_assignment[0]
    # Build current intervals for the teacher and for each student in option.
    current_teacher_intervals = {}
    current_student_intervals = {}
    for cand in current_schedule:
        ta, tsa, grp = cand
        tid = ta[0]
        for day, (start, duration) in tsa.items():
            interval = (start, start + duration)
            if tid not in current_teacher_intervals:
                current_teacher_intervals[tid] = {}
            current_teacher_intervals[tid].setdefault(day, []).append(interval)
            for student in grp:
                current_student_intervals.setdefault(student, {}).setdefault(day, []).append(interval)
    # Check teacher intervals for this option
    for day, (start, duration) in ts_assignment.items():
        interval = (start, start + duration)
        for existing in current_teacher_intervals.get(teacher_id, {}).get(day, []):
            if interval[0] < existing[1] and existing[0] < interval[1]:
                return True
    # Check each student in this option
    for student in student_group:
        for day, (start, duration) in ts_assignment.items():
            interval = (start, start + duration)
            for existing in current_student_intervals.get(student, {}).get(day, []):
                if interval[0] < existing[1] and existing[0] < interval[1]:
                    return True
    return False

def backtrack(candidate_lists, index, current_schedule):
    """
    Recursively select one candidate option from each candidate list (for each teacher assignment)
    while checking for conflicts incrementally.
    Returns a complete conflict-free schedule (list of candidate options) or None if none exists.
    """
    if index == len(candidate_lists):
        # Finished; check overall conflict (should be conflict-free already)
        if not candidate_conflict_check(current_schedule):
            return current_schedule
        return None
    for option in candidate_lists[index]:
        if not conflict_between(option, current_schedule):
            new_schedule = current_schedule + [option]
            result = backtrack(candidate_lists, index + 1, new_schedule)
            if result is not None:
                return result
    return None

def evaluate_schedule(schedule, teachers):
    """Compute a simple score as the sum of idle periods (unused slots) over all teachers."""
    teacher_usage = {}  # teacher_id -> day -> scheduled periods
    for option in schedule:
        teacher_assignment, ts_assignment, _ = option
        teacher_id = teacher_assignment[0]
        for day, (start, duration) in ts_assignment.items():
            teacher_usage.setdefault(teacher_id, {}).setdefault(day, 0)
            teacher_usage[teacher_id][day] += duration
    total_idle = 0
    for tid, teacher in teachers.items():
        avail_days = get_teacher_available_days(teacher)
        for day in avail_days:
            used = teacher_usage.get(tid, {}).get(day, 0)
            total_idle += (SLOTS_PER_DAY - used)
    return total_idle

##############################
# 5) MAIN TIMETABLE GENERATION
##############################

def generate_timetable():
    data = load_data()
    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]

    candidate_lists = []  # Each element is a list of candidate options for one teacher–group assignment

    # For each subject:
    for subj_id, teacher_assignments in subject_teacher_map.items():
        if subj_id not in subject_to_students or len(subject_to_students[subj_id]) == 0:
            logger.info(f"Skipping subject {subj_id} because no students selected it.")
            continue

        # Get all students for the subject (sorted for consistency)
        all_students = sorted(list(subject_to_students[subj_id]))
        num_teacher_assignments = len(teacher_assignments)
        # Evenly partition the subject's students among the teacher assignments.
        teacher_chunks = simple_partition(all_students, num_teacher_assignments)

        for i, assignment in enumerate(teacher_assignments):
            teacher_id, group_num = assignment
            # Embed subject id into teacher_assignment tuple: (teacher_id, group_num, subj_id)
            teacher_assignment = (teacher_id, group_num, subj_id)
            teacher_info = teachers.get(teacher_id)
            if teacher_info is None:
                logger.error(f"Teacher {teacher_id} not found for subject {subj_id}.")
                continue
            avail_days = get_teacher_available_days(teacher_info)
            if not avail_days:
                logger.warning(f"Teacher {teacher_id} is not available on any day. Skipping assignment for subject {subj_id}.")
                continue

            subj_info = subjects[subj_id]
            total_periods = subj_info["hours_per_week"]
            min_periods = subj_info["min_hours_per_day"]
            max_periods = subj_info["max_hours_per_day"]

            distributions = generate_period_distributions(total_periods, avail_days, min_periods, max_periods)
            if not distributions:
                logger.warning(f"No valid period distributions for subject {subj_id} with teacher {teacher_id}.")
                continue

            # Get the chunk of students assigned to this teacher assignment.
            assigned_students = teacher_chunks[i] if i < len(teacher_chunks) else []
            # Partition these assigned students into the number of groups specified by the teacher assignment.
            groups = partition_students(assigned_students, group_num, subj_info["max_students_per_group"])
            if groups is None:
                logger.error(f"Cannot partition {len(assigned_students)} students into {group_num} groups for subject {subj_id}.")
                continue

            candidate_options = []
            # For each period distribution and timeslot option, create a candidate option for each group.
            for dist in distributions:
                timeslot_opts = generate_timeslot_options(dist, SLOTS_PER_DAY)
                for ts_assignment in timeslot_opts:
                    for group in groups:
                        candidate_options.append((teacher_assignment, ts_assignment, group))
            # Use the subject's max_students_per_group as the candidate limit.
            candidate_limit = subj_info["max_students_per_group"]
            if len(candidate_options) > candidate_limit:
                candidate_options = random.sample(candidate_options, candidate_limit)
                logger.info(f"Reduced candidate options for subject {subj_id} with teacher {teacher_id} to {len(candidate_options)} options (limit from subject max_students_per_group).")
            else:
                logger.info(f"Generated {len(candidate_options)} options for subject {subj_id} with teacher {teacher_id}.")
            if candidate_options:
                candidate_lists.append(candidate_options)

    if not candidate_lists:
        logger.error("No candidate options available for scheduling.")
        return None

    # Now, use backtracking to choose one candidate option from each list such that there is no conflict.
    logger.info("Starting backtracking search for a conflict-free timetable...")
    solution = backtrack(candidate_lists, 0, [])
    if solution is None:
        logger.error("No valid timetable found without conflicts.")
        return None

    score = evaluate_schedule(solution, teachers)
    logger.info(f"Found a conflict-free timetable with score {score}.")

    timetable = {}
    for option in solution:
        teacher_assignment, ts_assignment, student_group = option
        teacher_id = teacher_assignment[0]
        subject_id = teacher_assignment[2]
        subj_name = subjects.get(subject_id, {}).get("name", "Unknown")
        for day, (start, duration) in ts_assignment.items():
            entry = {
                "subject_id": subject_id,
                "subject_name": subj_name,
                "day": day,
                "start": start,
                "end": start + duration,
                "duration": duration,
                "student_group": student_group
            }
            timetable.setdefault(teacher_id, []).append(entry)

    logger.info("Best Timetable:")
    for tid, classes in timetable.items():
        teacher = teachers.get(tid, {})
        teacher_name = teacher.get("name", "Unknown")
        logger.info(f"\nTeacher {teacher_name} (ID: {tid}):")
        for cl in classes:
            logger.info(f"  Subject: {cl['subject_name']} (ID: {cl['subject_id']})")
            logger.info(f"    Day: {cl['day']}, Periods: {cl['start']} - {cl['end']} (Duration: {cl['duration']} period(s))")
            logger.info(f"    Student Group: {cl['student_group']}")
    return timetable

##############################
# 6) MAIN
##############################

if __name__ == "__main__":
    try:
        final_timetable = generate_timetable()
        if final_timetable:
            logger.info("Timetable generation succeeded.")
        else:
            logger.error("Timetable generation failed.")
    except Exception as e:
        logger.exception(f"An error occurred during timetable generation: {e}")
