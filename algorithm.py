#!/usr/bin/env python3
"""
Algorithm.py
Version: 2.3
Revision: 1

Major Updates:
- Added a worst-case candidate space computation and progress logging in the CP-SAT callback.
- Every 60 seconds the CP callback logs an estimated remaining run time based on the number of candidate options (tables)
  processed so far versus the worst-case total.
- If the mathematical feasibility check (via the conflict graph) indicates that a zero-conflict timetable is possible,
  the CP solver is allowed an extended run time; otherwise it is limited.
- Version/revision tags are added throughout.
"""

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
import copy
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, wait, TimeoutError
from functools import lru_cache, reduce
from operator import mul
from data import get_teacher, get_subject, get_student, get_subject_teacher, get_subject_student
import shelve

# Uncomment the following line if OR-Tools is installed:
# from ortools.sat.python import cp_model

##############################
# GLOBAL PARAMETERS
# Version: 2.3 / Revision: 1
##############################
MIN_CANDIDATE_OPTIONS = 100
MAX_CANDIDATE_OPTIONS = 1000
CONFLICT_THRESHOLD = 50
CP_MAX_RUN_TIME = 30            # seconds per CP-SAT instance when zero-conflict is mathematically impossible.
CP_EXTENDED_RUN_TIME = CP_MAX_RUN_TIME * 10  # e.g. 300 seconds if a zero-conflict solution is possible.
TOTAL_WEEK_PERIODS = 4 * 10     # 4 days * 10 slots per day

##############################
# DYNAMIC CANDIDATE LIMIT FUNCTION
# Version: 1.0 / Revision: 2
##############################
def get_dynamic_max_candidate_options():
    """Determine the maximum number of candidate options to keep based on available memory."""
    mem = psutil.virtual_memory()
    free_gb = mem.available / (1024 ** 3)
    if free_gb <= 1:
        return MIN_CANDIDATE_OPTIONS
    elif free_gb >= 4:
        return MAX_CANDIDATE_OPTIONS
    else:
        scale = (free_gb - 1) / (4 - 1)
        return int(MIN_CANDIDATE_OPTIONS + scale * (MAX_CANDIDATE_OPTIONS - MIN_CANDIDATE_OPTIONS))

##############################
# LOGGING SETUP
# Version: 1.0 / Revision: 1
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
# MEMORY MONITORING (Optional)
# Version: 1.0 / Revision: 1
##############################
def dump_callback(mem_usage):
    logger.error(f"Memory usage reached {mem_usage:.2f} GB. Dumping current state not implemented.")

def memory_monitor(stop_event, memory_limit_gb=1.0, check_interval=5):
    process = psutil.Process(os.getpid())
    while not stop_event.is_set():
        mem_usage = process.memory_info().rss / (1024 ** 3)
        if mem_usage >= memory_limit_gb:
            dump_callback(mem_usage)
        time.sleep(check_interval)

##############################
# HELPER FUNCTIONS FOR SCHEDULING
# Version: 1.0 / Revision: 3
##############################
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
SLOTS_PER_DAY = 10

def get_teacher_available_days(teacher):
    """(v1.0, r3) Return a list of days during which the teacher is available."""
    return [day for day, avail in teacher["available_days"].items() if avail]

def generate_period_distributions(total_periods, available_days, min_periods, max_periods):
    """
    (v1.0, r3) Generate all distributions of total_periods among available_days that respect the min/max constraints.
    """
    distributions = []
    if total_periods % 2 == 1 and min_periods > 1:
        for special_day in available_days:
            day_options = []
            for day in available_days:
                if day == special_day:
                    options = [0, 1] + list(range(min_periods, max_periods + 1))
                    options = sorted(set(options))
                else:
                    options = [0] + list(range(min_periods, max_periods + 1))
                day_options.append(options)
            for combo in itertools.product(*day_options):
                if sum(combo) == total_periods:
                    distributions.append(dict(zip(available_days, combo)))
    day_options = []
    for _ in available_days:
        day_options.append([0] + list(range(min_periods, max_periods + 1)))
    for combo in itertools.product(*day_options):
        if sum(combo) == total_periods:
            distributions.append(dict(zip(available_days, combo)))
    if not distributions:
        logger.warning(f"generate_period_distributions: No valid distributions for total_periods={total_periods}, available_days={available_days}, min={min_periods}, max={max_periods}.")
    return distributions

def generate_timeslot_options(distribution, slots_per_day=SLOTS_PER_DAY):
    """(v1.0, r3) Generate available timeslot options given a period distribution."""
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
    """(v1.0, r3) Partition students into total_groups ensuring no group exceeds max_per_group."""
    num_students = len(students_list)
    if total_groups <= 0:
        return []
    group_size = math.ceil(num_students / total_groups)
    if group_size > max_per_group:
        logger.error(f"Partition failure: {num_students} students into {total_groups} groups requires group size {group_size} > allowed {max_per_group}.")
        return None
    groups = []
    for i in range(total_groups):
        groups.append(students_list[i*group_size:(i+1)*group_size])
    return groups

def simple_partition(lst, n):
    """(v1.0, r2) Evenly partition a list into n parts."""
    size = math.ceil(len(lst) / n)
    return [lst[i*size:(i+1)*size] for i in range(n)]

##############################
# TOTAL CANDIDATE SPACE ESTIMATION
# Version: 1.0 / Revision: 1
##############################
def compute_total_candidate_space(candidate_lists):
    """Compute the product of the number of options in each candidate list (worst-case total)."""
    return reduce(mul, (len(clist) for clist in candidate_lists), 1)

##############################
# DATA LOADING
# Version: 1.0 / Revision: 3
##############################
def load_data():
    try:
        teachers_raw = get_teacher()
        subjects_raw = get_subject()
        students_raw = get_student()
        sub_teacher_raw = get_subject_teacher()
        sub_student_raw = get_subject_student()

        teachers = {}
        for t in teachers_raw:
            teacher_id = t[0]
            teachers[teacher_id] = {
                "id": teacher_id,
                "name": t[1],
                "middle_name": t[2],
                "last_name": t[3],
                "available_days": {
                    "monday": bool(t[4]),
                    "tuesday": bool(t[5]),
                    "wednesday": bool(t[6]),
                    "thursday": bool(t[7])
                }
            }
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
                "min_hours_per_day": s[6]
            }
        subject_teacher_map = {}
        for row in sub_teacher_raw:
            subject_id = row[1]
            teacher_id = row[3]
            group_num = row[7]
            subject_teacher_map.setdefault(subject_id, []).append((teacher_id, group_num))
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
# CONFLICT GRAPH & MAX CLIQUE
# Version: 1.0 / Revision: 1
##############################
def build_subject_conflict_graph(data):
    """
    Build a conflict graph among subjects.
    Two subjects conflict if they share a teacher or if their student sets overlap.
    Returns a dict: {subject_id: set(conflicting_subject_ids)}
    """
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]
    graph = {subj: set() for subj in subjects.keys()}
    subject_ids = list(subjects.keys())
    for i in range(len(subject_ids)):
        for j in range(i+1, len(subject_ids)):
            s1 = subject_ids[i]
            s2 = subject_ids[j]
            teachers1 = set(teacher_id for teacher_id, _ in subject_teacher_map.get(s1, []))
            teachers2 = set(teacher_id for teacher_id, _ in subject_teacher_map.get(s2, []))
            if teachers1.intersection(teachers2):
                graph[s1].add(s2)
                graph[s2].add(s1)
                continue
            students1 = subject_to_students.get(s1, set())
            students2 = subject_to_students.get(s2, set())
            if students1.intersection(students2):
                graph[s1].add(s2)
                graph[s2].add(s1)
    return graph

def bron_kerbosch(R, P, X, graph):
    """(v1.0, r1) Bron–Kerbosch algorithm to compute maximum clique size."""
    max_clique_size = len(R)
    if not P and not X:
        return len(R)
    for v in list(P):
        new_R = R.union({v})
        new_P = P.intersection(graph[v])
        new_X = X.intersection(graph[v])
        clique_size = bron_kerbosch(new_R, new_P, new_X, graph)
        if clique_size > max_clique_size:
            max_clique_size = clique_size
        P.remove(v)
        X.add(v)
    return max_clique_size

def compute_max_clique_size(graph):
    """(v1.0, r1) Compute the maximum clique size in the conflict graph."""
    return bron_kerbosch(set(), set(graph.keys()), set(), graph)

##############################
# PRELIMINARY FEASIBILITY CHECK
# Version: 1.0 / Revision: 4
##############################
def feasibility_check(data):
    """
    Perform preliminary feasibility checks:
      1. Teacher Capacity
      2. Teacher Assignment Distribution
      3. Student Capacity
      4. Student Hours Check
      5. Global Teacher Capacity Check
      6. Conflict Graph Check: Maximum clique size must not exceed TOTAL_WEEK_PERIODS.
    Returns a tuple (hard_feasible, math_possible)
    """
    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]
    hard_feasible = True

    # 1. Teacher Capacity Check
    for tid, teacher in teachers.items():
        available_days = get_teacher_available_days(teacher)
        available_slots = len(available_days) * SLOTS_PER_DAY
        total_required = 0
        for subj_id, assignments in subject_teacher_map.items():
            if subj_id not in subjects:
                logger.error(f"Teacher Capacity: Subject {subj_id} referenced but not found.")
                hard_feasible = False
                continue
            for assignment in assignments:
                teacher_id, _ = assignment
                if teacher_id == tid:
                    total_required += subjects[subj_id]["hours_per_week"]
        if total_required > available_slots:
            logger.error(f"Teacher {tid} ({teachers[tid]['name']}) is overcommitted: requires {total_required} hours, only {available_slots} available.")
            hard_feasible = False

    # 2. Teacher Assignment Distribution Check
    for subj_id, assignments in subject_teacher_map.items():
        if subj_id not in subjects:
            logger.error(f"Teacher Assignment: Subject {subj_id} referenced but not found.")
            hard_feasible = False
            continue
        subj_info = subjects[subj_id]
        for assignment in assignments:
            teacher_id, _ = assignment
            teacher = teachers.get(teacher_id)
            if teacher is None:
                logger.error(f"Teacher Assignment: Teacher {teacher_id} not found for subject {subj_id}.")
                hard_feasible = False
                continue
            avail_days = get_teacher_available_days(teacher)
            distributions = generate_period_distributions(
                subj_info["hours_per_week"],
                avail_days,
                subj_info["min_hours_per_day"],
                subj_info["max_hours_per_day"]
            )
            if not distributions:
                logger.error(f"No valid period distributions for subject {subj_id} with teacher {teacher_id} (min: {subj_info['min_hours_per_day']}, max: {subj_info['max_hours_per_day']}, hours: {subj_info['hours_per_week']}, avail: {avail_days}).")
                hard_feasible = False

    # 3. Student Capacity Check
    for subj_id, students in subject_to_students.items():
        if subj_id not in subjects:
            logger.error(f"Student Capacity: Subject {subj_id} referenced in selections but not found.")
            hard_feasible = False
            continue
        total_students = len(students)
        total_capacity = 0
        assignments = subject_teacher_map.get(subj_id, [])
        subj_info = subjects[subj_id]
        for assignment in assignments:
            _, group_num = assignment
            total_capacity += group_num * subj_info["max_students_per_group"]
        if total_students > total_capacity:
            logger.error(f"Subject {subj_id} requires capacity for {total_students} students, capacity is {total_capacity}.")
            hard_feasible = False

    # 4. Student Hours Check
    student_subjects = {}
    for subj_id, students in subject_to_students.items():
        for s in students:
            student_subjects.setdefault(s, set()).add(subj_id)
    for student, subj_ids in student_subjects.items():
        total_required = 0
        for subj_id in subj_ids:
            if subj_id in subjects:
                total_required += subjects[subj_id]["hours_per_week"]
            else:
                logger.error(f"Student Hours: Subject {subj_id} for student {student} not found.")
                hard_feasible = False
        if total_required > TOTAL_WEEK_PERIODS:
            logger.error(f"Student {student} enrolled in subjects requiring {total_required} periods, only {TOTAL_WEEK_PERIODS} available.")
            hard_feasible = False

    # 5. Global Teacher Capacity Check
    global_capacity = sum(len(get_teacher_available_days(t)) * SLOTS_PER_DAY for t in teachers.values())
    total_required_global = sum(s["hours_per_week"] for s in subjects.values())
    if total_required_global > global_capacity:
        logger.error(f"Global Capacity: Required {total_required_global} hours exceed total capacity {global_capacity}.")
        hard_feasible = False

    # 6. Conflict Graph Check
    graph = build_subject_conflict_graph(data)
    max_clique_size = compute_max_clique_size(graph)
    logger.info(f"Conflict Graph: Maximum clique size (lower bound on timeslots required): {max_clique_size}")
    math_possible = (max_clique_size <= TOTAL_WEEK_PERIODS)
    if not math_possible:
        logger.warning(f"Math Check: Zero-conflict timetable mathematically impossible (clique size {max_clique_size} > {TOTAL_WEEK_PERIODS}).")

    return hard_feasible, math_possible

def preliminary_feasibility(data):
    hard_feasible, math_possible = feasibility_check(data)
    if not hard_feasible:
        logger.error("Preliminary feasibility failed: Hard constraints are violated.")
        return False, math_possible
    logger.info("Preliminary feasibility check passed.")
    return True, math_possible

##############################
# CANDIDATE CLUSTERING FUNCTION
# Version: 1.0 / Revision: 2
##############################
def cluster_candidates(candidate_options):
    clusters = {}
    for candidate in candidate_options:
        teacher_assignment, ts_assignment, student_group = candidate
        key = (tuple(sorted(ts_assignment.items())), len(student_group))
        current_score = sum(start for day, (start, _) in ts_assignment.items())
        if key not in clusters:
            clusters[key] = (candidate, current_score)
        else:
            _, best_score = clusters[key]
            if current_score < best_score:
                clusters[key] = (candidate, current_score)
    return [val[0] for val in clusters.values()]

##############################
# CONFLICT CHECKING UTILITIES WITH CACHING
# Version: 1.0 / Revision: 3
##############################
def freeze_candidate(candidate):
    teacher_assignment, ts_assignment, student_group = candidate
    frozen_ts = tuple(sorted(ts_assignment.items()))
    frozen_students = tuple(sorted(student_group))
    return (teacher_assignment, frozen_ts, frozen_students)

@lru_cache(maxsize=100000)
def _conflict_between_candidates_cached(frozen_c1, frozen_c2):
    teacher1, ts1, students1 = frozen_c1
    teacher2, ts2, students2 = frozen_c2
    if teacher1[0] == teacher2[0]:
        for day1, (start1, dur1) in ts1:
            for day2, (start2, dur2) in ts2:
                if day1 == day2 and (start1 < start2 + dur2 and start2 < start1 + dur1):
                    return True
    common_students = set(students1).intersection(set(students2))
    if common_students:
        for day1, (start1, dur1) in ts1:
            for day2, (start2, dur2) in ts2:
                if day1 == day2 and (start1 < start2 + dur2 and start2 < start1 + dur1):
                    return True
    return False

def conflict_between_candidates_cached(c1, c2):
    frozen_c1 = freeze_candidate(c1)
    frozen_c2 = freeze_candidate(c2)
    key = tuple(sorted((frozen_c1, frozen_c2)))
    return _conflict_between_candidates_cached(*key)

conflict_between_candidates = conflict_between_candidates_cached

##############################
# CONSTRAINT PROGRAMMING SOLUTION (CP-SAT) WITH PORTFOLIO
# Version: 1.0 / Revision: 3
##############################
def cp_solver_instance(candidate_lists, seed, num_instances, cp_max_run_time):
    from ortools.sat.python import cp_model
    try:
        model = cp_model.CpModel()
        n = len(candidate_lists)
        x = []
        for i in range(n):
            xi = model.NewIntVar(0, len(candidate_lists[i]) - 1, f'x_{i}')
            x.append(xi)
        for i in range(n):
            for j in range(i+1, n):
                allowed = []
                for a, cand_i in enumerate(candidate_lists[i]):
                    for b, cand_j in enumerate(candidate_lists[j]):
                        try:
                            if not conflict_between_candidates(cand_i, cand_j):
                                allowed.append([a, b])
                        except Exception as e:
                            logger.error(f"Error in conflict check between lists {i} and {j}: {e}")
                            return None
                if not allowed:
                    logger.error(f"CP-SAT: No allowed combinations between candidate lists {i} and {j}.")
                    return None
                model.AddAllowedAssignments([x[i], x[j]], allowed)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = num_instances
        solver.parameters.log_search_progress = False
        solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        solver.parameters.max_time_in_seconds = cp_max_run_time
        solver.parameters.random_seed = seed

        # Calculate total candidate space for progress estimation.
        total_candidate_space = compute_total_candidate_space(candidate_lists)

        # Custom callback that logs progress every 60 seconds.
        class BestSolutionCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, variables, candidate_lists):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self.variables = variables
                self.candidate_lists = candidate_lists
                self.best_solution = None
                self.best_conflicts = float('inf')
                self.start_time = time.time()
                self.last_log_time = self.start_time
                self.solutions_found = 0

            def OnSolutionCallback(self):
                self.solutions_found += 1
                current_time = time.time()
                elapsed = current_time - self.start_time
                # Estimate progress every 60 seconds.
                if current_time - self.last_log_time >= 60 and self.solutions_found > 0:
                    avg_time_per_solution = elapsed / self.solutions_found
                    remaining = total_candidate_space - self.solutions_found
                    est_remaining_sec = remaining * avg_time_per_solution
                    hrs = int(est_remaining_sec // 3600)
                    mins = int((est_remaining_sec % 3600) // 60)
                    secs = int(est_remaining_sec % 60)
                    logger.info(f"Progress: {self.solutions_found} candidate solutions checked out of ~{total_candidate_space} "
                                f"(worst-case). Elapsed: {int(elapsed)} sec. Estimated remaining time: {hrs}h {mins}m {secs}s.")
                    self.last_log_time = current_time
                current_solution = [self.Value(v) for v in self.variables]
                sol = []
                for i, index in enumerate(current_solution):
                    sol.append(self.candidate_lists[i][index])
                conf = total_conflicts(sol)
                if conf < self.best_conflicts:
                    self.best_conflicts = conf
                    self.best_solution = sol
                if conf == 0:
                    self.StopSearch()

        best_callback = BestSolutionCallback(x, candidate_lists)
        status = solver.SolveWithSolutionCallback(model, best_callback)
        if best_callback.best_solution is not None:
            return best_callback.best_solution
        else:
            return None
    except Exception as e:
        logger.error(f"Exception in cp_solver_instance: {e}")
        return None

def solve_with_cp_portfolio(candidate_lists, num_instances=None, time_limit=CP_MAX_RUN_TIME):
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        logger.error("CP-SAT: OR-Tools is not installed.")
        return None
    if num_instances is None:
        num_instances = os.cpu_count()
    seeds = [random.randint(0, 1000000) for _ in range(num_instances)]
    results = []
    overall_timeout = time_limit + 5  # seconds
    with ProcessPoolExecutor(max_workers=num_instances) as executor:
        futures = [executor.submit(cp_solver_instance, candidate_lists, seed, num_instances, time_limit)
                   for seed in seeds]
        done, not_done = wait(futures, timeout=overall_timeout)
        for future in not_done:
            future.cancel()
        for future in done:
            try:
                res = future.result(timeout=1)
                if res is not None:
                    results.append(res)
            except Exception as e:
                logger.error(f"Exception from CP-SAT worker: {e}")
    if results:
        best = None
        best_conflicts = float('inf')
        for sol in results:
            conf = total_conflicts(sol)
            if conf < best_conflicts:
                best_conflicts = conf
                best = sol
            if conf == 0:
                logger.info("CP-SAT: Found a zero-conflict solution.")
                return sol
        logger.info(f"CP-SAT: Best solution found has {best_conflicts} conflicts.")
        return best
    logger.error("CP-SAT: No valid solution found within the time limit.")
    return None

##############################
# TOTAL CONFLICTS (Helper)
# Version: 1.0 / Revision: 2
##############################
def total_conflicts(assignment):
    conflicts = 0
    n = len(assignment)
    for i in range(n):
        for j in range(i+1, n):
            if conflict_between_candidates(assignment[i], assignment[j]):
                conflicts += 1
    return conflicts

##############################
# TOTAL MISSING STUDENTS CALCULATION
# Version: 1.0 / Revision: 1
##############################
def total_missing_students(timetable, subject_to_students):
    scheduled = {}
    for teacher_id, classes in timetable.items():
        for cl in classes:
            subj_id = cl["subject_id"]
            scheduled.setdefault(subj_id, set()).update(cl["student_group"])
    missing = 0
    for subj_id, picked in subject_to_students.items():
        missing += len(picked - scheduled.get(subj_id, set()))
    return missing

##############################
# TIMETABLE FORMATTING (By Teacher)
# Version: 1.0 / Revision: 2
##############################
def format_timetable(timetable, teachers):
    output_lines = []
    output_lines.append("Best Timetable (Grouped by Teacher):\n")
    sorted_teachers = sorted(timetable.items(), key=lambda item: teachers.get(item[0], {}).get("name", ""))
    day_order = {day.lower(): idx for idx, day in enumerate(DAYS)}
    for tid, classes in sorted_teachers:
        teacher = teachers.get(tid, {})
        teacher_name = teacher.get("name", "Unknown")
        output_lines.append(f"Teacher: {teacher_name} (ID: {tid})")
        def sort_key(cl):
            day = cl["day"].lower()
            day_index = day_order.get(day, 999)
            return (day_index, cl["start"])
        sorted_classes = sorted(classes, key=sort_key)
        for cl in sorted_classes:
            subject_name = cl["subject_name"]
            subject_id = cl["subject_id"]
            day = cl["day"].capitalize()
            start = cl["start"]
            duration = cl["duration"]
            student_group = cl["student_group"]
            student_count = len(student_group) if isinstance(student_group, list) else student_group
            for period in range(start, start + duration):
                output_lines.append(f"  Subject: {subject_name} (ID: {subject_id})")
                output_lines.append(f"    {day}: Period {period}")
                output_lines.append(f"    Student Group (Total: {student_count}): {student_group}")
        output_lines.append("")
    return "\n".join(output_lines)

##############################
# TIMETABLE FORMATTING (By Day)
# Version: 1.0 / Revision: 2
##############################
def format_timetable_by_day(timetable, teachers):
    daily = {day.capitalize(): [] for day in DAYS}
    for tid, classes in timetable.items():
        teacher = teachers.get(tid, {})
        teacher_name = teacher.get("name", "Unknown")
        for cl in classes:
            day = cl["day"].capitalize()
            entry = cl.copy()
            entry["teacher_name"] = teacher_name
            entry["teacher_id"] = tid
            daily.setdefault(day, []).append(entry)
    for day in daily:
        expanded = []
        for entry in daily[day]:
            start = entry["start"]
            duration = entry["duration"]
            for period in range(start, start + duration):
                new_entry = entry.copy()
                new_entry["start"] = period
                new_entry["end"] = period + 1
                new_entry["duration"] = 1
                expanded.append(new_entry)
        daily[day] = sorted(expanded, key=lambda e: e["start"])
    output_lines = []
    output_lines.append("Daily Timetable:\n")
    for day in [d.capitalize() for d in DAYS]:
        output_lines.append(f"{day}:")
        if daily.get(day):
            for entry in daily[day]:
                student_count = len(entry["student_group"]) if isinstance(entry["student_group"], list) else entry["student_group"]
                output_lines.append(
                    f"  {entry['teacher_name']} (ID: {entry['teacher_id']}) - {entry['subject_name']} (ID: {entry['subject_id']}): "
                    f"Period {entry['start']} (Duration: {entry['duration']} period), Students: {student_count}"
                )
        else:
            output_lines.append("  No classes scheduled.")
        output_lines.append("")
    return "\n".join(output_lines)

##############################
# STUDENT COVERAGE VALIDATION
# Version: 1.0 / Revision: 2
##############################
def validate_student_coverage(timetable, subject_to_students):
    scheduled = {}
    for teacher_id, classes in timetable.items():
        for cl in classes:
            subj_id = cl["subject_id"]
            scheduled.setdefault(subj_id, set()).update(cl["student_group"])
    valid = True
    for subj_id, picked_students in subject_to_students.items():
        if subj_id not in scheduled:
            logger.error(f"Validation Failure: Subject {subj_id} has no scheduled classes, but students picked it: {picked_students}.")
            valid = False
        else:
            missing = picked_students - scheduled[subj_id]
            if missing:
                logger.error(f"Validation Failure: Subject {subj_id} is missing students: {missing}.")
                valid = False
    return valid

##############################
# MAIN TIMETABLE GENERATION (CP-SAT Only)
# Version: 1.0 / Revision: 3
##############################
def generate_timetable(USE_CP_SOLVER=False, USE_ITERATIVE_DEEPENING=False):
    data = load_data()
    hard_feasible, math_possible = preliminary_feasibility(data)
    if not hard_feasible:
        logger.error("Hard feasibility check failed. Aborting timetable generation.")
        return None

    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]

    candidate_lists = []
    # --- Candidate Generation Section ---
    for subj_id, teacher_assignments in subject_teacher_map.items():
        if subj_id not in subject_to_students or len(subject_to_students[subj_id]) == 0:
            logger.info(f"Skipping subject {subj_id} because no students selected it.")
            continue
        all_students = sorted(list(subject_to_students[subj_id]))
        subj_info = subjects[subj_id]
        max_students = subj_info["max_students_per_group"]
        total_groups_available = sum(group for teacher_id, group in teacher_assignments)
        required_groups = math.ceil(len(all_students) / max_students)
        if total_groups_available < required_groups:
            logger.error(f"Subject {subj_id} requires at least {required_groups} groups to cover {len(all_students)} students, but only {total_groups_available} available.")
            continue
        all_partitions = simple_partition(all_students, total_groups_available)
        current_index = 0
        for teacher_assignment in teacher_assignments:
            teacher_id, group_num = teacher_assignment
            teacher_assignment_full = (teacher_id, group_num, subj_id)
            assigned_groups = all_partitions[current_index: current_index + group_num]
            current_index += group_num
            teacher_info = teachers.get(teacher_id)
            if teacher_info is None:
                logger.error(f"Candidate Generation: Teacher {teacher_id} not found for subject {subj_id}.")
                continue
            avail_days = get_teacher_available_days(teacher_info)
            if not avail_days:
                logger.warning(f"Candidate Generation: Teacher {teacher_id} has no available days; skipping subject {subj_id}.")
                continue
            total_periods = subj_info["hours_per_week"]
            min_periods = subj_info["min_hours_per_day"]
            max_periods = subj_info["max_hours_per_day"]
            distributions = generate_period_distributions(total_periods, avail_days, min_periods, max_periods)
            if not distributions:
                logger.warning(f"Candidate Generation: No valid period distributions for subject {subj_id} with teacher {teacher_id}.")
                continue
            for group in assigned_groups:
                candidate_options = []
                for dist in distributions:
                    timeslot_opts = generate_timeslot_options(dist, SLOTS_PER_DAY)
                    for ts_assignment in timeslot_opts:
                        candidate_options.append((teacher_assignment_full, ts_assignment, group))
                candidate_options = cluster_candidates(candidate_options)
                candidate_options = sorted(candidate_options,
                                             key=lambda cand: sum(start for day, (start, _) in cand[1].items()))
                dynamic_limit = get_dynamic_max_candidate_options()
                if len(candidate_options) > dynamic_limit:
                    candidate_options = candidate_options[:dynamic_limit]
                    logger.info(f"Candidate Generation: Limited candidate options for subject {subj_id} with teacher {teacher_id} to {len(candidate_options)}.")
                else:
                    logger.info(f"Candidate Generation: Clustered {len(candidate_options)} options for subject {subj_id} with teacher {teacher_id}.")
                if candidate_options:
                    candidate_lists.append(candidate_options)
    # --- End Candidate Generation Section ---
    if not candidate_lists:
        logger.error("Candidate Generation Failure: No candidate options available for scheduling.")
        return None

    # Decide CP time limit based on math_possible.
    if math_possible:
        cp_time_limit = CP_EXTENDED_RUN_TIME
        logger.info("Math check indicates zero-conflict timetable is possible. Running CP-SAT with extended time.")
    else:
        cp_time_limit = CP_MAX_RUN_TIME
        logger.info("Math check indicates zero-conflict timetable is impossible. Running CP-SAT with limited time.")

    logger.info("Using CP-SAT portfolio solver exclusively.")
    sol = solve_with_cp_portfolio(candidate_lists, time_limit=cp_time_limit)
    if sol is not None:
        def convert_to_timetable(solution):
            timetable = {}
            for option in solution:
                teacher_assignment, ts_assignment, student_group = option
                teacher_id = teacher_assignment[0]
                subject_id = teacher_assignment[2]
                subj_name = subjects.get(subject_id, {}).get("name", "Unknown")
                for day, (start, duration) in ts_assignment.items():
                    entry = {"subject_id": subject_id, "subject_name": subj_name,
                             "day": day, "start": start, "end": start + duration,
                             "duration": duration, "student_group": student_group}
                    timetable.setdefault(teacher_id, []).append(entry)
            return timetable
        temp_timetable = convert_to_timetable(sol)
        missing = total_missing_students(temp_timetable, subject_to_students)
        if missing == 0:
            logger.info("CP-SAT solution found with zero missing students.")
        else:
            logger.warning(f"CP-SAT solution found with {missing} missing students.")
        return temp_timetable
    else:
        logger.error("CP-SAT solver failed to produce any solution.")
        return None

##############################
# MAIN
##############################
if __name__ == "__main__":
    multiprocessing.freeze_support()
    USE_CP_SOLVER = True   # Only CP-SAT branch is used.
    USE_ITERATIVE_DEEPENING = False
    try:
        final_timetable = generate_timetable(USE_CP_SOLVER, USE_ITERATIVE_DEEPENING)
        if final_timetable:
            logger.info("Timetable generation succeeded.")
            data = load_data()  # Reload data to update teacher info.
            teacher_view = format_timetable(final_timetable, data["teachers"])
            daily_view = format_timetable_by_day(final_timetable, data["teachers"])
            logger.info("\n" + teacher_view)
            logger.info("\n" + daily_view)
        else:
            logger.error("Timetable generation failed.")
    except Exception as e:
        logger.exception(f"An error occurred during timetable generation: {e}")
