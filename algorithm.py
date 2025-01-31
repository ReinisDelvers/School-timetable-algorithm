import copy
import json
import multiprocessing
from math import ceil
from data import (
    get_teacher,
    get_subject,
    get_student,
    get_subject_teacher,
    get_subject_student,
)
import os
import sys
from datetime import datetime
import traceback
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
import argparse
import psutil
import threading
import time

################################################################################
# 1) LOGGING SETUP
################################################################################

def setup_logging(log_queue, log_file):
    """
    Configures the root logger to send logs to a multiprocessing queue.
    """
    queue_handler = QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Adjust as needed (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    logger.addHandler(queue_handler)
    
    # Prevent log messages from being propagated to the root logger
    logger.propagate = False

def listener_configurer(log_file):
    """
    Configures the listener to handle log records from the queue.
    """
    root = logging.getLogger()
    handler = RotatingFileHandler(log_file, maxBytes=10**6, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(processName)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

def listener_process(log_queue, log_file):
    """
    The listener process that receives log records from the queue and writes them to the log file.
    """
    listener_configurer(log_file)
    listener = QueueListener(log_queue, *logging.getLogger().handlers)
    listener.start()
    try:
        while True:
            record = log_queue.get()
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
    finally:
        listener.stop()

def worker_configurer(log_queue):
    """
    Configures the worker process to send log records to the queue.
    
    Args:
        log_queue (multiprocessing.Queue): The logging queue.
    """
    queue_handler = QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Adjust as needed (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    logger.addHandler(queue_handler)
    logger.propagate = False

################################################################################
# 2) MEMORY MONITORING
################################################################################

def memory_monitor(stop_event, dump_callback, memory_limit_gb, check_interval=5):
    """
    Monitors the memory usage of the current process and triggers a callback if the limit is exceeded.
    
    Args:
        stop_event (threading.Event): Event to signal the monitor to stop.
        dump_callback (callable): Function to call when memory limit is exceeded.
        memory_limit_gb (float): Memory limit in GB.
        check_interval (int): Time interval between checks in seconds.
    """
    process = psutil.Process(os.getpid())
    while not stop_event.is_set():
        mem_usage = process.memory_info().rss / (1024 ** 3)  # Convert to GB
        if mem_usage >= memory_limit_gb:
            dump_callback(mem_usage)
        time.sleep(check_interval)

def dump_callback(mem_usage):
    """
    Callback function to handle memory limit exceedance.
    
    Args:
        mem_usage (float): Current memory usage in GB.
    """
    logger = logging.getLogger()
    logger.error(f"Memory usage reached {mem_usage:.2f} GB. Initiating dump and continuing attempts.")
    
    # Implement the logic to dump the current timetable or state
    # For example, save the current timetable to a JSON file
    # Since 'state' is within worker processes, consider logging and allowing workers to handle their own dumps
    # Alternatively, implement periodic dumps within the scheduling functions
    
    # Example: If you have access to the current state globally, you could do:
    # with open("partial_timetable.json", "w") as f:
    #     json.dump(state["timetable"], f, indent=4)
    
    # However, accessing 'state' from here is not straightforward. Consider implementing state dumps within worker functions.
    pass

################################################################################
# 3) DATA LOADING
################################################################################

def load_data(logger):
    try:
        teachers_raw      = get_teacher()
        subjects_raw      = get_subject()
        students_raw      = get_student()
        sub_teacher_raw   = get_subject_teacher()
        sub_student_raw   = get_subject_student()

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
                    # Friday is removed
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

        # Build subject->list_of(teacher_id, group_number) from subject_teacher
        subject_teacher_map = {}
        for row in sub_teacher_raw:
            # row = (id, subject_id, subject_name, teacher_id, teacher_name, t_mid, t_last, group_number)
            subject_id = row[1]
            teacher_id = row[3]
            group_num  = row[7]
            if subject_id not in subject_teacher_map:
                subject_teacher_map[subject_id] = []
            subject_teacher_map[subject_id].append((teacher_id, group_num))

        # Build subject->set_of_students from JSON array of subject IDs
        subject_to_students = {}
        for row in sub_student_raw:
            # row: (id, json_subject_ids, subject_name, student_id, student_name, etc.)
            student_id       = row[3]
            json_subject_str = row[1]
            try:
                subj_ids = json.loads(json_subject_str)  # e.g., "[5,16]" -> [5,16]
            except json.JSONDecodeError:
                subj_ids = []
            for sid in subj_ids:
                if sid not in subject_to_students:
                    subject_to_students[sid] = set()
                subject_to_students[sid].add(student_id)

        data = {
            "teachers": teachers,
            "subjects": subjects,
            "subject_teacher_map": subject_teacher_map,
            "subject_to_students": subject_to_students,
        }

        # Log the number of loaded entities
        logger.info(f"Loaded {len(data['teachers'])} teachers.")
        logger.info(f"Loaded {len(data['subjects'])} subjects.")
        for subj_id, teachers_info in data["subject_teacher_map"].items():
            logger.info(f"Subject ID {subj_id} has {len(teachers_info)} teacher assignments.")
        for subj_id, students in data["subject_to_students"].items():
            logger.info(f"Subject ID {subj_id} has {len(students)} students.")

        return data

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        traceback.print_exc()
        sys.exit(1)

################################################################################
# 4) TIMETABLE SETUP
################################################################################

DAYS = ["monday", "tuesday", "wednesday", "thursday"]  # Friday removed
SLOTS_PER_DAY = 10

def initialize_empty_timetable():
    # Using fixed-size lists for efficiency
    timetable = {day: [[] for _ in range(SLOTS_PER_DAY)] for day in DAYS}
    return timetable

################################################################################
# 5) SPLIT STUDENTS BY TOTAL GROUP_NUMBER
################################################################################

def split_students_equally(all_students, total_groups, max_per_group):
    """
    Partition 'all_students' into 'total_groups' sub-lists,
    ensuring we don't exceed the subject's capacity in each group if possible.
    """
    num_students = len(all_students)
    if total_groups == 0:
        return []

    group_size = ceil(num_students / total_groups)
    if group_size > max_per_group:
        # Cannot split without exceeding group capacity
        return None

    subgroups = []
    student_list = list(all_students)
    idx = 0
    for _ in range(total_groups):
        chunk = student_list[idx : idx + group_size]
        subgroups.append(chunk)
        idx += group_size
    return subgroups

################################################################################
# 6) CONSTRAINT CHECK (with optimized logging)
################################################################################

def can_place_in_slot(existing_classes, subject_id, teacher_id, students, day, slot_index, state, logger):
    """
    Check if a class can be placed in the given slot under current constraints.
    """
    subjects  = state["subjects"]
    teachers  = state["teachers"]
    timetable = state["timetable"]
    subj_info = subjects.get(subject_id)

    if subj_info is None:
        logger.error(f"Subject ID {subject_id} not found in subjects.")
        return False

    # 1) Check subject_max_hours_per_day
    day_count = sum(1 for cls in timetable[day][slot_index] if cls["subject_id"] == subject_id)
    logger.debug(f"Checking subject {subject_id} on {day}, slot {slot_index+1}: current count {day_count}, max {subj_info['max_hours_per_day']}.")

    if day_count >= subj_info["max_hours_per_day"]:
        logger.warning(f"Subject {subject_id} daily limit reached on {day}.")
        return False

    # 2) Check teacher availability for the day
    teacher_info = teachers.get(teacher_id)
    if teacher_info is None:
        logger.error(f"Teacher ID {teacher_id} not found in teachers.")
        return False

    if not teacher_info["available_days"].get(day, False):
        logger.warning(f"Teacher {teacher_id} not available on {day}.")
        return False

    # 3) Check if teacher is already teaching in this slot
    if any(cls["teacher_id"] == teacher_id for cls in timetable[day][slot_index]):
        logger.warning(f"Teacher {teacher_id} is already teaching another subject in slot {slot_index+1} on {day}.")
        return False

    # 4) Check if students are already in another class in this slot
    student_conflict = any(set(cls["students"]).intersection(students) for cls in timetable[day][slot_index])
    if student_conflict:
        logger.warning(f"Some students are already assigned to another class in slot {slot_index+1} on {day}.")
        return False

    logger.debug(f"Can place subject {subject_id} with teacher {teacher_id} in slot {slot_index+1} on {day}.")
    return True

################################################################################
# 7) SCHEDULE HOURS FOR A SINGLE GROUP (Recursive Backtracking)
################################################################################

def dump_current_state(state, attempt_number, logger):
    """
    Dumps the current timetable to a JSON file.
    
    Args:
        state (dict): Current state of the timetable.
        attempt_number (int): The current attempt number for file naming.
        logger (Logger): Logger instance.
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dump_filename = f"partial_timetable_attempt_{attempt_number}_{timestamp}.json"
        with open(dump_filename, "w") as f:
            json.dump(state["timetable"], f, indent=4)
        logger.info(f"Dumped current timetable to {dump_filename}")
    except Exception as e:
        logger.error(f"Failed to dump current state: {e}")

def schedule_hours_for_group(subject_id, teacher_id, students, required_hours, state, best_schedule, logger, max_depth, current_depth, attempt_counter, attempt_lock, attempt_limit, dump_threshold=1000):
    """
    Recursively attempt to place required_hours for a group in the timetable.
    Update best_schedule if a better schedule is found.
    
    Args:
        subject_id (int): ID of the subject.
        teacher_id (int): ID of the teacher.
        students (set): Set of student IDs.
        required_hours (int): Number of hours to schedule.
        state (dict): Current state of the timetable.
        best_schedule (dict): Current best schedule.
        logger (Logger): Logger instance.
        max_depth (int or None): Maximum recursion depth, None for no limit.
        current_depth (int): Current recursion depth.
        attempt_counter (multiprocessing.Value): Shared attempt counter.
        attempt_lock (multiprocessing.Lock): Lock to synchronize access to attempt_counter.
        attempt_limit (int or None): Maximum number of placement attempts, None for no limit.
        dump_threshold (int): Number of attempts after which to dump state.
    """
    if max_depth is not None and current_depth > max_depth:
        logger.warning(f"Max recursion depth {max_depth} reached while scheduling subject {subject_id}. Pruning.")
        return

    if required_hours == 0:
        # All required hours placed; evaluate and update best_schedule if necessary
        score = evaluate_schedule(state["timetable"])
        if best_schedule['score'] is None or score > best_schedule['score']:
            best_schedule['timetable'] = copy.deepcopy(state["timetable"])
            best_schedule['score'] = score
            logger.debug("Found a better schedule.")
        return

    for d in DAYS:
        for slot_i in range(SLOTS_PER_DAY):
            if can_place_in_slot(state["timetable"][d][slot_i], subject_id, teacher_id, set(students), d, slot_i, state, logger):
                # Check attempt limit
                if attempt_limit is not None:
                    with attempt_lock:
                        if attempt_counter.value >= attempt_limit:
                            logger.info(f"Attempt limit {attempt_limit} reached. Stopping scheduling.")
                            return
                        attempt_counter.value += 1
                        current_attempt = attempt_counter.value
                    logger.debug(f"Attempt {current_attempt}: Placing subject {subject_id} (Teacher {teacher_id}) in {d}, slot {slot_i+1}")
                else:
                    logger.debug(f"Attempt: Placing subject {subject_id} (Teacher {teacher_id}) in {d}, slot {slot_i+1}")

                # Place the class
                new_class = {
                    "subject_id": subject_id,
                    "teacher_id": teacher_id,
                    "students": list(students),
                }
                state["timetable"][d][slot_i].append(new_class)
                logger.debug(f"Placed subject {subject_id} (Teacher {teacher_id}) in {d}, slot {slot_i+1}")

                # Periodically dump state
                if dump_threshold > 0 and attempt_limit is not None and attempt_counter.value % dump_threshold == 0:
                    dump_current_state(state, attempt_counter.value, logger)

                # Recurse with one less required hour and incremented depth
                schedule_hours_for_group(
                    subject_id,
                    teacher_id,
                    students,
                    required_hours - 1,
                    state,
                    best_schedule,
                    logger,
                    max_depth,
                    current_depth +1,
                    attempt_counter,
                    attempt_lock,
                    attempt_limit,
                    dump_threshold
                )

                # Remove the class to backtrack
                state["timetable"][d][slot_i].pop()
                logger.debug(f"Removed subject {subject_id} (Teacher {teacher_id}) from {d}, slot {slot_i+1}")

################################################################################
# 8) MAIN SCHEDULING (Brute-Force Backtracking)
################################################################################

def evaluate_schedule(timetable):
    """
    Heuristic: maximize the total number of classes.
    """
    total_classes = 0
    for d in DAYS:
        for slot in timetable[d]:
            total_classes += len(slot)
    return total_classes

def schedule_all_subjects(subjects_list, subjects, subject_teacher_map, subject_to_students, initial_assignments, max_depth, attempt_counter, attempt_lock, attempt_limit):
    """
    Generate a valid timetable by placing each class using backtracking.
    Each process handles a subset of initial_assignments.
    
    Args:
        subjects_list (list): List of (subject_id, subject_info) tuples.
        subjects (dict): All subjects.
        subject_teacher_map (dict): Mapping from subject_id to list of (teacher_id, group_num).
        subject_to_students (dict): Mapping from subject_id to set of student_ids.
        initial_assignments (list): List of initial class assignments to start with.
        max_depth (int or None): Maximum recursion depth, None for no limit.
        attempt_counter (multiprocessing.Value): Shared attempt counter.
        attempt_lock (multiprocessing.Lock): Lock to synchronize access to attempt_counter.
        attempt_limit (int or None): Maximum number of placement attempts, None for no limit.
    
    Returns:
        dict: The best timetable found, or None if no valid schedule.
    """
    logger = logging.getLogger()
    logger.info("Starting scheduling process.")

    timetable = initialize_empty_timetable()
    state = {
        "timetable": timetable,
        "teachers": subjects["teachers"],
        "subjects": subjects["subjects"],
        "subject_teacher_map": subject_teacher_map,
        "subject_to_students": subject_to_students,
    }

    # Apply all initial assignments
    for assignment in initial_assignments:
        subject_id = assignment["subject_id"]
        teacher_id = assignment["teacher_id"]
        students = set(assignment["students"])
        required_hours = subjects["subjects"].get(subject_id, {}).get("hours_per_week", 0)

        if required_hours == 0:
            logger.warning(f"Subject {subject_id} has 0 required hours. Skipping.")
            continue

        # Attempt to place the initial class
        placed = False
        for d in DAYS:
            for slot_i in range(SLOTS_PER_DAY):
                if can_place_in_slot(state["timetable"][d][slot_i], subject_id, teacher_id, students, d, slot_i, state, logger):
                    new_class = {
                        "subject_id": subject_id,
                        "teacher_id": teacher_id,
                        "students": list(students),
                    }
                    state["timetable"][d][slot_i].append(new_class)
                    logger.info(f"Placed initial subject {subject_id} (Teacher {teacher_id}) in {d}, slot {slot_i+1}")
                    placed = True
                    break
            if placed:
                break
        if not placed:
            logger.error(f"Failed to place initial subject {subject_id} (Teacher {teacher_id}).")
            return None  # Invalid initial assignment

        # Schedule remaining hours for this group
        best_schedule = {'timetable': None, 'score': None}
        schedule_hours_for_group(
            subject_id,
            teacher_id,
            students,
            required_hours - 1,
            state,
            best_schedule,
            logger,
            max_depth,
            current_depth=1,
            attempt_counter=attempt_counter,
            attempt_lock=attempt_lock,
            attempt_limit=attempt_limit
        )

    # Initialize the overall best schedule
    overall_best_schedule = {'timetable': None, 'score': None}

    # Start backtracking for the remaining subjects
    def backtrack(subject_index, state, overall_best_schedule, logger, current_depth, max_depth, attempt_counter, attempt_lock, attempt_limit):
        if max_depth is not None and current_depth > max_depth:
            logger.warning(f"Max recursion depth {max_depth} reached at subject index {subject_index}. Pruning.")
            return

        if subject_index >= len(subjects_list):
            # All subjects have been scheduled; evaluate and update overall_best_schedule
            score = evaluate_schedule(state["timetable"])
            if overall_best_schedule['score'] is None or score > overall_best_schedule['score']:
                overall_best_schedule['timetable'] = copy.deepcopy(state["timetable"])
                overall_best_schedule['score'] = score
                logger.info("Found a new best schedule.")
            return

        # Get subject details
        subj_id, subj_info = subjects_list[subject_index]
        required_hours     = subj_info["hours_per_week"]
        max_students_group = subj_info["max_students_per_group"]
        all_students       = subject_to_students.get(subj_id, set())
        teacher_rows       = subject_teacher_map.get(subj_id, [])

        if not teacher_rows:
            logger.error(f"Subject {subj_id} has no teacher assignments. Skipping.")
            backtrack(subject_index + 1, state, overall_best_schedule, logger, current_depth +1, max_depth, attempt_counter, attempt_lock, attempt_limit)
            return
        if not all_students:
            logger.info(f"Subject {subj_id} has no students. Skipping.")
            backtrack(subject_index + 1, state, overall_best_schedule, logger, current_depth +1, max_depth, attempt_counter, attempt_lock, attempt_limit)
            return

        total_groups = sum(row[1] for row in teacher_rows)
        splitted = split_students_equally(all_students, total_groups, max_students_group)
        if splitted is None:
            logger.error(f"Cannot split {len(all_students)} students into {total_groups} groups with capacity {max_students_group}. Skipping subject {subj_id}.")
            backtrack(subject_index + 1, state, overall_best_schedule, logger, current_depth +1, max_depth, attempt_counter, attempt_lock, attempt_limit)
            return

        logger.info(f"\nScheduling Subject {subj_id}: {len(all_students)} students, {total_groups} groups, {required_hours} hrs/week, max/day={subj_info['max_hours_per_day']}")

        # Assign each group to a teacher
        for g_index, (teacher_id, group_num) in enumerate(teacher_rows):
            for g in range(group_num):
                if g >= len(splitted):
                    break
                students = set(splitted[g])
                # Schedule the required hours for this group
                best_schedule = {'timetable': None, 'score': None}
                schedule_hours_for_group(
                    subj_id,
                    teacher_id,
                    students,
                    required_hours,
                    state,
                    best_schedule,
                    logger,
                    max_depth,
                    current_depth +1,
                    attempt_counter,
                    attempt_lock,
                    attempt_limit
                )

                # Update overall_best_schedule if a better one is found
                if best_schedule['timetable'] and (overall_best_schedule['score'] is None or best_schedule['score'] > overall_best_schedule['score']):
                    overall_best_schedule['timetable'] = best_schedule['timetable']
                    overall_best_schedule['score'] = best_schedule['score']
                    logger.info("Updated the overall best schedule.")

        # Proceed to next subject
        backtrack(subject_index + 1, state, overall_best_schedule, logger, current_depth +1, max_depth, attempt_counter, attempt_lock, attempt_limit)

    backtrack(0, state, overall_best_schedule, logger, current_depth=1, max_depth=max_depth, attempt_counter=attempt_counter, attempt_lock=attempt_lock, attempt_limit=attempt_limit)

    if overall_best_schedule['timetable'] is None:
        logger.error("\n-> FAIL: No valid schedules found under current constraints.")
        return None

    logger.info(f"\n-> SUCCESS: Found the best schedule with score {overall_best_schedule['score']}.")
    return overall_best_schedule['timetable']
