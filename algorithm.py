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
import copy
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from data import get_teacher, get_subject, get_student, get_subject_teacher, get_subject_student

# Uncomment the following line if you plan to use OR-Tools.
# from ortools.sat.python import cp_model

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
    logger.error(f"Memory usage reached {mem_usage:.2f} GB. Dumping current state not implemented.")

def memory_monitor(stop_event, memory_limit_gb=1.0, check_interval=5):
    process = psutil.Process(os.getpid())
    while not stop_event.is_set():
        mem_usage = process.memory_info().rss / (1024 ** 3)
        if mem_usage >= memory_limit_gb:
            dump_callback(mem_usage)
        time.sleep(check_interval)

##############################
# 3) DATA LOADING
##############################

def load_data():
    try:
        teachers_raw    = get_teacher()
        subjects_raw    = get_subject()
        students_raw    = get_student()
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
                    "monday":    bool(t[4]),
                    "tuesday":   bool(t[5]),
                    "wednesday": bool(t[6]),
                    "thursday":  bool(t[7]),
                },
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
                "min_hours_per_day": s[6],
            }

        subject_teacher_map = {}
        for row in sub_teacher_raw:
            subject_id = row[1]
            teacher_id = row[3]
            group_num  = row[7]
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
# 4) HELPER FUNCTIONS FOR SCHEDULING
##############################

DAYS = ["monday", "tuesday", "wednesday", "thursday"]
SLOTS_PER_DAY = 10

def get_teacher_available_days(teacher):
    return [day for day, avail in teacher["available_days"].items() if avail]

def generate_period_distributions(total_periods, available_days, min_periods, max_periods):
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
        logger.warning(f"generate_period_distributions: No valid distributions for total_periods={total_periods}, available_days={available_days}, min_hours_per_day={min_periods}, max_hours_per_day={max_periods}.")
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
    num_students = len(students_list)
    if total_groups <= 0:
        return []
    group_size = math.ceil(num_students / total_groups)
    if group_size > max_per_group:
        logger.error(f"Partition failure: {num_students} students into {total_groups} groups requires group size {group_size} which exceeds maximum allowed {max_per_group}.")
        return None
    groups = []
    for i in range(total_groups):
        groups.append(students_list[i*group_size:(i+1)*group_size])
    return groups

def simple_partition(lst, n):
    size = math.ceil(len(lst) / n)
    return [lst[i*size:(i+1)*size] for i in range(n)]

##############################
# 4.1) CONFLICT CHECKING UTILITIES
##############################

def intervals_overlap(interval1, interval2):
    return interval1[0] < interval2[1] and interval2[0] < interval1[1]

def has_conflict(candidate, current_intervals):
    teacher_assignment, ts_assignment, student_group = candidate
    teacher_id = teacher_assignment[0]
    for day, (start, duration) in ts_assignment.items():
        candidate_interval = (start, start + duration)
        for existing in current_intervals.get("teachers", {}).get(teacher_id, {}).get(day, []):
            if intervals_overlap(candidate_interval, existing):
                return True
        for student in student_group:
            for existing in current_intervals.get("students", {}).get(student, {}).get(day, []):
                if intervals_overlap(candidate_interval, existing):
                    return True
    return False

def add_candidate_intervals(candidate, current_intervals):
    teacher_assignment, ts_assignment, student_group = candidate
    teacher_id = teacher_assignment[0]
    for day, (start, duration) in ts_assignment.items():
        candidate_interval = (start, start + duration)
        current_intervals.setdefault("teachers", {}).setdefault(teacher_id, {}).setdefault(day, []).append(candidate_interval)
        for student in student_group:
            current_intervals.setdefault("students", {}).setdefault(student, {}).setdefault(day, []).append(candidate_interval)

def remove_candidate_intervals(candidate, current_intervals):
    teacher_assignment, ts_assignment, student_group = candidate
    teacher_id = teacher_assignment[0]
    for day, (start, duration) in ts_assignment.items():
        candidate_interval = (start, start + duration)
        if teacher_id in current_intervals.get("teachers", {}):
            if day in current_intervals["teachers"][teacher_id]:
                try:
                    current_intervals["teachers"][teacher_id][day].remove(candidate_interval)
                except ValueError:
                    pass
        for student in student_group:
            if student in current_intervals.get("students", {}):
                if day in current_intervals["students"][student]:
                    try:
                        current_intervals["students"][student][day].remove(candidate_interval)
                    except ValueError:
                        pass

def conflict_between_candidates(c1, c2):
    teacher1, ts1, students1 = c1
    teacher2, ts2, students2 = c2
    if teacher1[0] == teacher2[0]:
        for day, (start1, dur1) in ts1.items():
            if day in ts2:
                start2, dur2 = ts2[day]
                if intervals_overlap((start1, start1+dur1), (start2, start2+dur2)):
                    return True
    common_students = set(students1).intersection(set(students2))
    if common_students:
        for day, (start1, dur1) in ts1.items():
            if day in ts2:
                start2, dur2 = ts2[day]
                if intervals_overlap((start1, start1+dur1), (start2, start2+dur2)):
                    return True
    return False

##############################
# 4.2) ITERATIVE BACKTRACKING ALGORITHMS
##############################

def iterative_backtracking(candidate_lists):
    initial_state = (0, [], {"teachers": {}, "students": {}})
    stack = [initial_state]
    while stack:
        index, schedule, intervals = stack.pop()
        if index == len(candidate_lists):
            return schedule
        for candidate in candidate_lists[index]:
            if has_conflict(candidate, intervals):
                continue
            new_intervals = copy.deepcopy(intervals)
            add_candidate_intervals(candidate, new_intervals)
            new_schedule = schedule + [candidate]
            stack.append((index+1, new_schedule, new_intervals))
    return None

def iterative_backtracking_with_depth(candidate_lists, depth_limit):
    initial_state = (0, [], {"teachers": {}, "students": {}})
    stack = [initial_state]
    while stack:
        index, schedule, intervals = stack.pop()
        if index == depth_limit:
            if depth_limit == len(candidate_lists):
                return schedule
            else:
                continue
        for candidate in candidate_lists[index]:
            if has_conflict(candidate, intervals):
                continue
            new_intervals = copy.deepcopy(intervals)
            add_candidate_intervals(candidate, new_intervals)
            new_schedule = schedule + [candidate]
            stack.append((index+1, new_schedule, new_intervals))
    return None

def iterative_deepening_backtracking(candidate_lists):
    n = len(candidate_lists)
    for limit in range(1, n+1):
        logger.info(f"Iterative deepening: trying depth limit {limit}")
        solution = iterative_backtracking_with_depth(candidate_lists, limit)
        if solution is not None and len(solution) == n:
            return solution
    return None

##############################
# 4.3) CONSTRAINT PROGRAMMING SOLUTION (CP-SAT)
##############################

def log_candidate_list_summary(candidate_lists):
    summary_lines = []
    for i, clist in enumerate(candidate_lists):
        if clist:
            teacher_assignment = clist[0][0]
            teacher_id, group_num, subj_id = teacher_assignment
            summary_lines.append(f"Candidate List {i}: Subject {subj_id} with Teacher {teacher_id}, {len(clist)} options")
        else:
            summary_lines.append(f"Candidate List {i}: empty")
    logger.info("Candidate List Summary:\n" + "\n".join(summary_lines))

def solve_with_cp(candidate_lists):
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        logger.error("CP-SAT: OR-Tools is not installed. Please install it to use the constraint solver option.")
        return None
    log_candidate_list_summary(candidate_lists)
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
                    if not conflict_between_candidates(cand_i, cand_j):
                        allowed.append([a, b])
            if not allowed:
                logger.error(f"CP-SAT: No allowed combinations between candidate list {i} (length={len(candidate_lists[i])}) and candidate list {j} (length={len(candidate_lists[j])}).")
                logger.error(f"Example candidate from list {i}: {candidate_lists[i][0]}")
                logger.error(f"Example candidate from list {j}: {candidate_lists[j][0]}")
                return None
            model.AddAllowedAssignments([x[i], x[j]], allowed)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = multiprocessing.cpu_count()
    # Increase search time: allow up to 600 seconds.
    solver.parameters.max_time_in_seconds = 600
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = []
        for i in range(n):
            index = solver.Value(x[i])
            solution.append(candidate_lists[i][index])
        return solution
    else:
        logger.error(f"CP-SAT: Solver did not find a feasible or optimal solution. Model status: {status}")
        return None

##############################
# 4.4) SIMULATED ANNEALING SOLVER (Parallel)
##############################

def _simulated_annealing_worker(candidate_lists, max_steps, initial_temp, cooling_rate, seed):
    logger.info(f"SA Worker running on PID: {os.getpid()}")
    random.seed(seed)
    current_assignment = [random.choice(clist) for clist in candidate_lists]
    def cost(assignment):
        return total_conflicts(assignment)
    current_cost = cost(current_assignment)
    temperature = initial_temp
    for step in range(max_steps):
        if current_cost == 0:
            return current_assignment
        i = random.randint(0, len(candidate_lists)-1)
        new_assignment = current_assignment.copy()
        new_assignment[i] = random.choice(candidate_lists[i])
        new_cost = cost(new_assignment)
        delta = new_cost - current_cost
        if delta < 0 or random.random() < math.exp(-delta / temperature):
            current_assignment = new_assignment
            current_cost = new_cost
        temperature *= cooling_rate
    return None

def solve_with_simulated_annealing_parallel(candidate_lists, max_steps=10000, initial_temp=100.0, cooling_rate=0.95, trials=None):
    if trials is None:
        trials = multiprocessing.cpu_count()
    with ProcessPoolExecutor(max_workers=trials) as executor:
        futures = [
            executor.submit(
                _simulated_annealing_worker, candidate_lists, max_steps, initial_temp, cooling_rate, random.randint(0, 1000000)
            )
            for _ in range(trials)
        ]
        for future in as_completed(futures):
            result = future.result()
            if result is not None and total_conflicts(result) == 0:
                return result
    return None

##############################
# 4.5) MIN-CONFLICTS SOLVER (Parallel)
##############################

def _min_conflicts_worker(candidate_lists, max_steps, seed):
    logger.info(f"Min-Conflicts Worker running on PID: {os.getpid()}")
    random.seed(seed)
    current_assignment = [random.choice(clist) for clist in candidate_lists]
    def total_conflicts_local(assignment):
        conflicts = 0
        n = len(assignment)
        for i in range(n):
            for j in range(i+1, n):
                if conflict_between_candidates(assignment[i], assignment[j]):
                    conflicts += 1
        return conflicts
    current_conflicts = total_conflicts_local(current_assignment)
    for step in range(max_steps):
        if current_conflicts == 0:
            return current_assignment
        conflicted = []
        n = len(current_assignment)
        for i in range(n):
            for j in range(n):
                if i != j and conflict_between_candidates(current_assignment[i], current_assignment[j]):
                    conflicted.append(i)
                    break
        if not conflicted:
            return current_assignment
        var = random.choice(conflicted)
        best_candidate = current_assignment[var]
        best_conflicts = current_conflicts
        for candidate in candidate_lists[var]:
            temp_assignment = current_assignment.copy()
            temp_assignment[var] = candidate
            conf = 0
            for i in range(n):
                for j in range(i+1, n):
                    if conflict_between_candidates(temp_assignment[i], temp_assignment[j]):
                        conf += 1
            if conf < best_conflicts:
                best_conflicts = conf
                best_candidate = candidate
        current_assignment[var] = best_candidate
        current_conflicts = 0
        for i in range(n):
            for j in range(i+1, n):
                if conflict_between_candidates(current_assignment[i], current_assignment[j]):
                    current_conflicts += 1
    return None

def solve_with_min_conflicts(candidate_lists, max_steps=10000, trials=None):
    if trials is None:
        trials = multiprocessing.cpu_count()
    with ProcessPoolExecutor(max_workers=trials) as executor:
        futures = [executor.submit(_min_conflicts_worker, candidate_lists, max_steps, random.randint(0, 1000000))
                   for _ in range(trials)]
        for future in as_completed(futures):
            result = future.result()
            if result is not None and total_conflicts(result) == 0:
                return result
    return None

def total_conflicts(assignment):
    conflicts = 0
    n = len(assignment)
    for i in range(n):
        for j in range(i+1, n):
            if conflict_between_candidates(assignment[i], assignment[j]):
                conflicts += 1
    return conflicts

##############################
# 4.6) PARALLEL ITERATIVE BACKTRACKING SOLVER
##############################

def solve_with_iterative_parallel(candidate_lists, trials=None):
    if trials is None:
        trials = multiprocessing.cpu_count()
    def worker(trial):
        logger.info(f"Iterative Backtracking Worker running on PID: {os.getpid()}")
        candidate_lists_shuffled = [random.sample(clist, len(clist)) for clist in candidate_lists]
        return iterative_backtracking(candidate_lists_shuffled)
    with ProcessPoolExecutor(max_workers=trials) as executor:
        futures = [executor.submit(worker, i) for i in range(trials)]
        for future in as_completed(futures):
            sol = future.result()
            if sol is not None and total_conflicts(sol) == 0:
                return sol
    return None

##############################
# 4.7) TIMETABLE FORMATTING (By Teacher)
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
# 4.8) TIMETABLE FORMATTING (By Day)
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
                    f"Period {entry['start']} (Duration: {entry['duration']} period), "
                    f"Students: {student_count}"
                )
        else:
            output_lines.append("  No classes scheduled.")
        output_lines.append("")
    return "\n".join(output_lines)

##############################
# 4.9) STUDENT COVERAGE VALIDATION
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
            logger.error(f"Validation Failure: Subject {subj_id} has no scheduled classes, but students picked it: {picked_students}. Possibly no teacher had available slots.")
            valid = False
        else:
            missing = picked_students - scheduled[subj_id]
            if missing:
                logger.error(f"Validation Failure: Subject {subj_id} is missing students: {missing}. This may be due to insufficient space in classes or no valid timeslot available.")
                valid = False
    return valid

##############################
# 5) MAIN TIMETABLE GENERATION
##############################

def generate_timetable(USE_CP_SOLVER=False, USE_ITERATIVE_DEEPENING=False):
    data = load_data()
    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]

    candidate_lists = []
    # --- NEW CANDIDATE GENERATION SECTION ---
    # For each subject, we partition all the students into as many groups as the total groups available.
    for subj_id, teacher_assignments in subject_teacher_map.items():
        if subj_id not in subject_to_students or len(subject_to_students[subj_id]) == 0:
            logger.info(f"Skipping subject {subj_id} because no students selected it.")
            continue
        all_students = sorted(list(subject_to_students[subj_id]))
        subj_info = subjects[subj_id]
        max_students = subj_info["max_students_per_group"]
        required_groups = math.ceil(len(all_students) / max_students)
        total_groups_available = sum(group for teacher_id, group in teacher_assignments)
        if total_groups_available < required_groups:
            logger.error(f"Subject {subj_id} requires at least {required_groups} groups to cover {len(all_students)} students, but only {total_groups_available} groups are available.")
            continue  # or decide to fail for this subject
        # Partition the entire student list into total_groups_available groups.
        all_partitions = simple_partition(all_students, total_groups_available)
        current_index = 0
        for teacher_assignment in teacher_assignments:
            teacher_id, group_num = teacher_assignment
            teacher_assignment_full = (teacher_id, group_num, subj_id)
            # Assigned groups for this teacher assignment:
            assigned_groups = all_partitions[current_index: current_index + group_num]
            current_index += group_num
            teacher_info = teachers.get(teacher_id)
            if teacher_info is None:
                logger.error(f"Candidate Generation Failure: Teacher {teacher_id} not found for subject {subj_id}.")
                continue
            avail_days = get_teacher_available_days(teacher_info)
            if not avail_days:
                logger.warning(f"Candidate Generation Failure: Teacher {teacher_id} has no available days. Skipping subject {subj_id}.")
                continue
            total_periods = subj_info["hours_per_week"]
            min_periods = subj_info["min_hours_per_day"]
            max_periods = subj_info["max_hours_per_day"]
            distributions = generate_period_distributions(total_periods, avail_days, min_periods, max_periods)
            if not distributions:
                logger.warning(f"Candidate Generation Failure: No valid period distributions for subject {subj_id} with teacher {teacher_id}.")
                continue
            # For each assigned group, generate candidate options.
            for group in assigned_groups:
                candidate_options = []
                for dist in distributions:
                    timeslot_opts = generate_timeslot_options(dist, SLOTS_PER_DAY)
                    for ts_assignment in timeslot_opts:
                        candidate_options.append((teacher_assignment_full, ts_assignment, group))
                # Optionally, limit the candidate options.
                if len(candidate_options) > max_students:
                    candidate_options = random.sample(candidate_options, max_students)
                    logger.info(f"Candidate Generation: Reduced candidate options for subject {subj_id} with teacher {teacher_id} to {len(candidate_options)}.")
                else:
                    logger.info(f"Candidate Generation: Generated {len(candidate_options)} options for subject {subj_id} with teacher {teacher_id}.")
                if candidate_options:
                    candidate_lists.append(candidate_options)
    # --- END NEW CANDIDATE GENERATION SECTION ---
    if not candidate_lists:
        logger.error("Candidate Generation Failure: No candidate options available for scheduling.")
        return None

    solution = None
    # 1. Try CP-SAT solver
    if USE_CP_SOLVER:
        logger.info("Attempting CP-SAT solver for a conflict-free timetable using OR-Tools...")
        solution = solve_with_cp(candidate_lists)
        if solution is not None:
            temp_timetable = {}
            for option in solution:
                teacher_assignment, ts_assignment, student_group = option
                teacher_id = teacher_assignment[0]
                subject_id = teacher_assignment[2]
                subj_name = subjects.get(subject_id, {}).get("name", "Unknown")
                for day, (start, duration) in ts_assignment.items():
                    entry = {"subject_id": subject_id, "subject_name": subj_name,
                             "day": day, "start": start, "end": start + duration,
                             "duration": duration, "student_group": student_group}
                    temp_timetable.setdefault(teacher_id, []).append(entry)
            if not validate_student_coverage(temp_timetable, subject_to_students):
                logger.error("CP-SAT solution failed validation; falling back to alternative algorithms.")
                solution = None
    # 2. Try parallel simulated annealing
    if solution is None:
        logger.info("Attempting parallel simulated annealing search for a conflict-free timetable...")
        solution = solve_with_simulated_annealing_parallel(candidate_lists, max_steps=10000, initial_temp=100.0, cooling_rate=0.95)
        if solution is not None:
            temp_timetable = {}
            for option in solution:
                teacher_assignment, ts_assignment, student_group = option
                teacher_id = teacher_assignment[0]
                subject_id = teacher_assignment[2]
                subj_name = subjects.get(subject_id, {}).get("name", "Unknown")
                for day, (start, duration) in ts_assignment.items():
                    entry = {"subject_id": subject_id, "subject_name": subj_name,
                             "day": day, "start": start, "end": start + duration,
                             "duration": duration, "student_group": student_group}
                    temp_timetable.setdefault(teacher_id, []).append(entry)
            if not validate_student_coverage(temp_timetable, subject_to_students):
                logger.error("Simulated annealing solution failed validation; falling back to parallel min-conflicts search.")
                solution = None
    # 3. Try parallel min-conflicts solver
    if solution is None:
        logger.info("Attempting parallel min-conflicts search for a conflict-free timetable...")
        solution = solve_with_min_conflicts(candidate_lists, max_steps=10000)
        if solution is not None:
            temp_timetable = {}
            for option in solution:
                teacher_assignment, ts_assignment, student_group = option
                teacher_id = teacher_assignment[0]
                subject_id = teacher_assignment[2]
                subj_name = subjects.get(subject_id, {}).get("name", "Unknown")
                for day, (start, duration) in ts_assignment.items():
                    entry = {"subject_id": subject_id, "subject_name": subj_name,
                             "day": day, "start": start, "end": start + duration,
                             "duration": duration, "student_group": student_group}
                    temp_timetable.setdefault(teacher_id, []).append(entry)
            if not validate_student_coverage(temp_timetable, subject_to_students):
                logger.error("Min-conflicts solution failed validation; falling back to parallel iterative backtracking.")
                solution = None
    # 4. Fallback: parallel iterative backtracking
    if solution is None:
        logger.info("Attempting parallel iterative backtracking search for a conflict-free timetable...")
        solution = solve_with_iterative_parallel(candidate_lists)
    if solution is None:
        logger.error("Overall Failure: No valid timetable found without conflicts.")
        return None

    def evaluate_schedule(schedule, teachers):
        teacher_usage = {}
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

    score = evaluate_schedule(solution, teachers)
    logger.info(f"Evaluation: Found a conflict-free timetable with score {score}.")
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
    if not validate_student_coverage(timetable, subject_to_students):
        logger.error("Validation Error: Final timetable validation failed; not every student is scheduled for every subject they picked.")
        return None
    teacher_view = format_timetable(timetable, teachers)
    logger.info(teacher_view)
    daily_view = format_timetable_by_day(timetable, teachers)
    logger.info("\n" + daily_view)
    return timetable

##############################
# 4.7) STUDENT COVERAGE VALIDATION
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
            logger.error(f"Validation Failure: Subject {subj_id} has no scheduled classes, but students picked it: {picked_students}. Possibly no teacher had available slots.")
            valid = False
        else:
            missing = picked_students - scheduled[subj_id]
            if missing:
                logger.error(f"Validation Failure: Subject {subj_id} is missing students: {missing}. This may be due to insufficient space in classes or no valid timeslot available.")
                valid = False
    return valid

##############################
# 4.8) PARALLEL ITERATIVE BACKTRACKING SOLVER
##############################

def solve_with_iterative_parallel(candidate_lists, trials=None):
    if trials is None:
        trials = multiprocessing.cpu_count()
    def worker(trial):
        logger.info(f"Iterative Backtracking Worker running on PID: {os.getpid()}")
        candidate_lists_shuffled = [random.sample(clist, len(clist)) for clist in candidate_lists]
        return iterative_backtracking(candidate_lists_shuffled)
    with ProcessPoolExecutor(max_workers=trials) as executor:
        futures = [executor.submit(worker, i) for i in range(trials)]
        for future in as_completed(futures):
            sol = future.result()
            if sol is not None and total_conflicts(sol) == 0:
                return sol
    return None

##############################
# 4.9) TOTAL CONFLICTS (Helper)
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
# 5) MAIN
##############################

if __name__ == "__main__":
    USE_CP_SOLVER = True
    USE_ITERATIVE_DEEPENING = False
    try:
        final_timetable = generate_timetable(USE_CP_SOLVER, USE_ITERATIVE_DEEPENING)
        if final_timetable:
            logger.info("Timetable generation succeeded.")
        else:
            logger.error("Timetable generation failed.")
    except Exception as e:
        logger.exception(f"An error occurred during timetable generation: {e}")
