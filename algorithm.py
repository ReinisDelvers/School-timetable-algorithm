#!/usr/bin/env python3
"""
Algorithm.py
Version: 3.3
Revision: 7

Full CP Model with Output Dumping and Enhanced Mathematical Feasibility Check:
  - Builds a complete CP model for school timetabling that models:
      • Required lessons per subject (per teacher assignment group)
      • Teacher availability via domain restrictions on lesson start times
      • Teacher non-overlap (using NoOverlap on lesson intervals)
      • A room/resource constraint via a cumulative constraint
      • Student assignment via binary variables plus a slack variable per subject
        (with an objective to minimize missing assignments)
      • Student non-overlap constraints (ensuring no overlapping lessons for each student)
  - Performs a preliminary feasibility check using teacher, student, and global capacity checks plus an enhanced conflict graph check.
  - The conflict graph check uses both a maximum-total-hours clique, a greedy coloring estimate, and a block-based estimate to decide if a zero-conflict timetable is mathematically possible.
  - After solving, the code constructs teacher, main, and student schedules and writes them to a text file.
  - If the CP solver’s time limit is reached without a zero-slack solution, it returns the best solution found.
  - Data is loaded via load_data(), and helper functions (like get_teacher_available_days()) are defined.
"""

##############################
# GLOBAL PARAMETERS
# Version: 3.3 / Revision: 7
##############################
PERIODS_PER_DAY = 10
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
TOTAL_WEEK_PERIODS = len(DAYS) * PERIODS_PER_DAY

CP_MAX_RUN_TIME = 3         # seconds if zero-conflict is mathematically unlikely.
CP_EXTENDED_RUN_TIME = CP_MAX_RUN_TIME * 10  # extended time if math check indicates zero-conflict is possible.

MAX_ROOMS_PER_TIMESLOT = 20    # Maximum rooms available per global timeslot.

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
from functools import lru_cache, reduce
from operator import mul
import shelve

# Import OR-Tools CP-SAT
from ortools.sat.python import cp_model

# Import data functions from data.py
from data import get_teacher, get_subject, get_student, get_subject_teacher, get_subject_student

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
# LOAD_DATA FUNCTION
# Version: 1.0 / Revision: 3
##############################
def load_data():
    """
    Loads teacher, subject, student, subject-teacher, and subject-student data.
    
    Returns a dictionary with:
      - "teachers": dict mapping teacher id -> teacher info (including available_days)
      - "subjects": dict mapping subject id -> subject info (hours per week, etc.)
      - "subject_teacher_map": dict mapping subject id -> list of (teacher_id, group_number)
      - "subject_to_students": dict mapping subject id -> set of student ids
    """
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
# UTILITY FUNCTIONS: Timeslot Mapping, Domain, and Teacher Available Days
# Version: 1.0 / Revision: 2
##############################
def timeslot_to_day_period(ts):
    """Convert a global timeslot (0 .. TOTAL_WEEK_PERIODS-1) to (day, period)."""
    day_index = ts // PERIODS_PER_DAY
    period = ts % PERIODS_PER_DAY
    return DAYS[day_index], period

def available_timeslot_domain(teacher):
    """Return the list of global timeslot indices when the teacher is available."""
    available = []
    for i, day in enumerate(DAYS):
        if teacher["available_days"].get(day, False):
            start = i * PERIODS_PER_DAY
            available.extend(range(start, start + PERIODS_PER_DAY))
    return available

def get_teacher_available_days(teacher):
    """
    Return a list of days (as strings) on which the teacher is available.
    For example, if teacher["available_days"] is {"monday": True, "tuesday": False, ...},
    this function returns the list of days with True.
    """
    return [day for day, available in teacher.get("available_days", {}).items() if available]

##############################
# DYNAMIC CANDIDATE LIMIT FUNCTION
# Version: 1.0 / Revision: 2
##############################
def get_dynamic_max_candidate_options():
    mem = psutil.virtual_memory()
    free_gb = mem.available / (1024 ** 3)
    if free_gb <= 1:
        return 100
    elif free_gb >= 4:
        return 1000
    else:
        scale = (free_gb - 1) / 3
        return int(100 + scale * (1000 - 100))

##############################
# CONFLICT GRAPH & MAX CLIQUE (Mathematical Feasibility)
# Version: 1.0 / Revision: 1
##############################
def build_subject_conflict_graph(data):
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]
    graph = {subj: set() for subj in subjects.keys()}
    subject_ids = list(subjects.keys())
    for i in range(len(subject_ids)):
        for j in range(i+1, len(subject_ids)):
            s1 = subject_ids[i]
            s2 = subject_ids[j]
            teachers1 = set(t for t, _ in subject_teacher_map.get(s1, []))
            teachers2 = set(t for t, _ in subject_teacher_map.get(s2, []))
            if teachers1.intersection(teachers2):
                graph[s1].add(s2)
                graph[s2].add(s1)
                continue
            students1 = data["subject_to_students"].get(s1, set())
            students2 = data["subject_to_students"].get(s2, set())
            if students1.intersection(students2):
                graph[s1].add(s2)
                graph[s2].add(s1)
    return graph

def bron_kerbosch(R, P, X, graph):
    max_clique_size = len(R)
    if not P and not X:
        return len(R)
    for v in list(P):
        new_R = R.union({v})
        new_P = P.intersection(graph[v])
        new_X = X.intersection(graph[v])
        clique_size = bron_kerbosch(new_R, new_P, new_X, graph)
        max_clique_size = max(max_clique_size, clique_size)
        P.remove(v)
        X.add(v)
    return max_clique_size

def compute_max_clique_size(graph):
    return bron_kerbosch(set(), set(graph.keys()), set(), graph)

# --- NEW: Compute Maximum Total Hours in a Clique ---
def bron_kerbosch_max_total(R, P, X, graph, subjects):
    """
    A variant of Bron–Kerbosch that returns the clique (set of subject ids)
    with the maximum total required hours.
    """
    current_total = sum(subjects[s]["hours_per_week"] for s in R) if R else 0
    best_R = R.copy()
    best_total = current_total
    if not P and not X:
        return R, current_total
    for v in list(P):
        new_R, new_total = bron_kerbosch_max_total(R.union({v}), P.intersection(graph[v]), X.intersection(graph[v]), graph, subjects)
        if new_total > best_total:
            best_total = new_total
            best_R = new_R
        P.remove(v)
        X.add(v)
    return best_R, best_total

def compute_max_total_hours_clique(data):
    subjects = data["subjects"]
    graph = build_subject_conflict_graph(data)
    clique, total_hours = bron_kerbosch_max_total(set(), set(graph.keys()), set(), graph, subjects)
    return clique, total_hours

# --- NEW: Greedy Coloring for an Alternative Estimate ---
def greedy_coloring(graph):
    """
    A simple greedy coloring algorithm on the conflict graph.
    Returns a dict mapping subject id -> color (an integer).
    """
    colors = {}
    for node in sorted(graph, key=lambda x: len(graph[x]), reverse=True):
        assigned = set(colors.get(neighbor) for neighbor in graph[node] if neighbor in colors)
        color = 0
        while color in assigned:
            color += 1
        colors[node] = color
    return colors

def estimate_timeslots_needed(data):
    """
    Uses greedy coloring on the conflict graph to estimate the number of distinct timeslots required.
    Also computes the total hours in each color class and estimates the minimum days needed.
    """
    subjects = data["subjects"]
    graph = build_subject_conflict_graph(data)
    colors = greedy_coloring(graph)
    num_colors = max(colors.values()) + 1 if colors else 0
    color_hours = {i: 0 for i in range(num_colors)}
    for subj, color in colors.items():
        color_hours[color] += subjects[subj]["hours_per_week"]
    max_hours = max(color_hours.values()) if color_hours else 0
    min_days = math.ceil(max_hours / PERIODS_PER_DAY)
    logger.info(f"Greedy Coloring Estimate: {num_colors} colors used; bottleneck total hours = {max_hours} (=> at least {min_days} days required).")
    return num_colors, color_hours, min_days

# --- NEW: Block-Based Conflict Check
def compute_min_days_for_block_clique(data):
    """
    Computes a lower bound on the number of days required based on subject blocks.
    Each subject requires blocks = hours_per_week//2 + (1 if odd).
    Using a Bron–Kerbosch variant, finds the clique with maximum total blocks.
    Blocks per day is defined as (PERIODS_PER_DAY//2) plus one extra if PERIODS_PER_DAY is odd.
    """
    subjects = data["subjects"]
    graph = build_subject_conflict_graph(data)
    
    def required_blocks(subj_id):
        h = subjects[subj_id]["hours_per_week"]
        return h // 2 + (1 if h % 2 != 0 else 0)
    
    def bron_kerbosch_blocks(R, P, X):
        current_blocks = sum(required_blocks(s) for s in R) if R else 0
        best_R = R.copy()
        best_total = current_blocks
        if not P and not X:
            return R, current_blocks
        for v in list(P):
            new_R, new_total = bron_kerbosch_blocks(R.union({v}), P.intersection(graph[v]), X.intersection(graph[v]))
            if new_total > best_total:
                best_total = new_total
                best_R = new_R
            P.remove(v)
            X.add(v)
        return best_R, best_total

    clique, total_blocks = bron_kerbosch_blocks(set(), set(graph.keys()), set())
    blocks_per_day = (PERIODS_PER_DAY // 2) + (1 if PERIODS_PER_DAY % 2 != 0 else 0)
    min_days_required = math.ceil(total_blocks / blocks_per_day)
    logger.info(f"Block-Based Conflict Check: Total required blocks = {total_blocks}, minimum days required = {min_days_required}")
    return min_days_required

##############################
# PRELIMINARY FEASIBILITY CHECK
# Version: 1.0 / Revision: 4
##############################
def feasibility_check(data):
    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]
    hard_feasible = True

    # 1. Teacher Capacity Check
    for tid, teacher in teachers.items():
        available_days = get_teacher_available_days(teacher)
        available_slots = len(available_days) * PERIODS_PER_DAY
        total_required = 0
        for subj_id, assignments in subject_teacher_map.items():
            if subj_id not in subjects:
                logger.error(f"Teacher Capacity: Subject {subj_id} not found.")
                hard_feasible = False
                continue
            for teacher_id, _ in assignments:
                if teacher_id == tid:
                    total_required += subjects[subj_id]["hours_per_week"]
        if total_required > available_slots:
            logger.error(f"Teacher {tid} ({teachers[tid]['name']}) is overcommitted: {total_required} > {available_slots}.")
            hard_feasible = False

    # 2. Teacher Assignment Distribution Check
    for subj_id, assignments in subject_teacher_map.items():
        if subj_id not in subjects:
            logger.error(f"Teacher Assignment: Subject {subj_id} not found.")
            hard_feasible = False
            continue
        subj_info = subjects[subj_id]
        for teacher_id, _ in assignments:
            teacher = teachers.get(teacher_id)
            if teacher is None:
                logger.error(f"Teacher Assignment: Teacher {teacher_id} not found for subject {subj_id}.")
                hard_feasible = False
                continue
            avail_days = get_teacher_available_days(teacher)
            if subj_info["hours_per_week"] > 0 and not avail_days:
                logger.error(f"Teacher {teacher_id} for subject {subj_id} has no available days.")
                hard_feasible = False

    # 3. Student Capacity Check
    for subj_id, students in subject_to_students.items():
        if subj_id not in subjects:
            logger.error(f"Student Capacity: Subject {subj_id} not found.")
            hard_feasible = False
            continue
        total_students = len(students)
        total_capacity = 0
        assignments = subject_teacher_map.get(subj_id, [])
        subj_info = subjects[subj_id]
        for _, group_num in assignments:
            total_capacity += group_num * subj_info["max_students_per_group"]
        if total_students > total_capacity:
            logger.error(f"Subject {subj_id}: capacity {total_capacity} insufficient for {total_students} students.")
            hard_feasible = False

    # 4. Student Hours Check
    student_subjects = {}
    for subj_id, students in subject_to_students.items():
        for s in students:
            student_subjects.setdefault(s, set()).add(subj_id)
    for student, subj_ids in student_subjects.items():
        total_required = sum(subjects[subj]["hours_per_week"] for subj in subj_ids if subj in subjects)
        if total_required > TOTAL_WEEK_PERIODS:
            logger.error(f"Student {student}: requires {total_required} periods, only {TOTAL_WEEK_PERIODS} available.")
            hard_feasible = False

    # 5. Global Teacher Capacity Check
    global_capacity = sum(len(get_teacher_available_days(t)) * PERIODS_PER_DAY for t in teachers.values())
    total_required_global = sum(s["hours_per_week"] for s in subjects.values())
    if total_required_global > global_capacity:
        logger.error(f"Global Capacity: {total_required_global} > {global_capacity}.")
        hard_feasible = False

    # 6. Enhanced Conflict Graph Checks:
    # (a) Maximum Total Hours Clique
    clique, total_hours_clique = compute_max_total_hours_clique(data)
    min_days_required_clique = math.ceil(total_hours_clique / PERIODS_PER_DAY)
    logger.info(f"Conflict Graph (Clique): Total required hours = {total_hours_clique}, minimum days required = {min_days_required_clique}")
    # (b) Greedy Coloring Estimate
    num_colors, color_hours, min_days_required_color = estimate_timeslots_needed(data)
    # (c) Block-Based Estimate
    min_days_required_blocks = compute_min_days_for_block_clique(data)
    # Combined estimate (maximum of the three estimates)
    min_days_required = max(min_days_required_clique, min_days_required_color, min_days_required_blocks)
    logger.info(f"Combined Estimate: Minimum days required = {min_days_required} (available days: {len(DAYS)})")
    math_possible = (min_days_required <= len(DAYS))
    if not math_possible:
        logger.warning(f"Math Check: Zero-conflict timetable mathematically impossible (requires at least {min_days_required} days).")
    else:
        logger.info("Math Check: A zero-conflict timetable is mathematically possible based on the analysis.")
    return hard_feasible, math_possible

def preliminary_feasibility(data):
    hard_feasible, math_possible = feasibility_check(data)
    if not hard_feasible:
        logger.error("Preliminary feasibility failed (hard constraints violated).")
        return False, math_possible
    logger.info("Preliminary feasibility check passed.")
    return True, math_possible

##############################
# FULL CP MODEL WITH OBJECTIVE (Including student assignment slack)
# Version: 3.2 / Revision: 1
##############################
def full_cp_model(data):
    """
    Build a full CP model that respects all restrictions.
    For each subject and student, a binary assignment variable and a slack variable are introduced:
      sum(y) + slack == 1.
    The model minimizes the total slack (i.e. missing student assignments).
    """
    model = cp_model.CpModel()
    teachers = data["teachers"]
    subjects = data["subjects"]
    subject_teacher_map = data["subject_teacher_map"]
    subject_to_students = data["subject_to_students"]

    # Create classes (one per teacher assignment group) with lesson variables.
    class_vars = []   # Each element: dict with keys: 'subject_id', 'teacher_id', 'group_index', 'lesson_starts', 'lesson_intervals'
    class_indices = {}
    for subj_id, assignments in subject_teacher_map.items():
        if subj_id not in subjects:
            logger.error(f"Full CP Model: Subject {subj_id} not found. Skipping.")
            continue
        subj_info = subjects[subj_id]
        hours = subj_info["hours_per_week"]
        for (teacher_id, group_num) in assignments:
            for group_index in range(group_num):
                var_dict = {
                    'subject_id': subj_id,
                    'teacher_id': teacher_id,
                    'group_index': group_index,
                    'lesson_starts': [],
                    'lesson_intervals': []
                }
                teacher = teachers.get(teacher_id)
                if teacher is None:
                    logger.error(f"Full CP Model: Teacher {teacher_id} not found for subject {subj_id}.")
                    continue
                domain = available_timeslot_domain(teacher)
                if not domain:
                    logger.error(f"Full CP Model: Teacher {teacher_id} has no available timeslots.")
                    continue
                for i in range(hours):
                    start = model.NewIntVarFromDomain(cp_model.Domain.FromValues(domain),
                                                      f"subj{subj_id}_t{teacher_id}_g{group_index}_l{i}_start")
                    interval = model.NewIntervalVar(start, 1, start+1,
                                                    f"subj{subj_id}_t{teacher_id}_g{group_index}_l{i}_interval")
                    var_dict['lesson_starts'].append(start)
                    var_dict['lesson_intervals'].append(interval)
                model.AddAllDifferent(var_dict['lesson_starts'])
                class_indices[(subj_id, teacher_id, group_index)] = len(class_vars)
                class_vars.append(var_dict)

    # Teacher NoOverlap: Each teacher's lessons across classes must not overlap.
    teacher_intervals = {}
    for c in class_vars:
        t_id = c['teacher_id']
        teacher_intervals.setdefault(t_id, []).extend(c['lesson_intervals'])
    for t_id, intervals in teacher_intervals.items():
        model.AddNoOverlap(intervals)

    # Room Constraint: Cumulative constraint on all lesson intervals.
    all_intervals = []
    for c in class_vars:
        all_intervals.extend(c['lesson_intervals'])
    demands = [1] * len(all_intervals)
    model.AddCumulative(all_intervals, demands, MAX_ROOMS_PER_TIMESLOT)

    # Student Assignment: For each subject and student, add binary variables and a slack variable.
    student_assignments = {}
    slack_vars = []
    for subj_id, students in subject_to_students.items():
        classes_for_subj = [idx for key, idx in class_indices.items() if key[0] == subj_id]
        for student in students:
            y_vars = []
            for c in classes_for_subj:
                y = model.NewBoolVar(f"y_s{student}_subj{subj_id}_class{c}")
                student_assignments[(student, subj_id, c)] = y
                y_vars.append(y)
            slack = model.NewIntVar(0, 1, f"slack_s{student}_subj{subj_id}")
            slack_vars.append(slack)
            model.Add(sum(y_vars) + slack == 1)

    # Student Non-Overlap: For each student, classes from distinct subjects must not have lessons overlapping.
    for (student, subj1, c1) in student_assignments:
        for (student2, subj2, c2) in student_assignments:
            if student == student2 and subj1 < subj2:
                b1 = student_assignments[(student, subj1, c1)]
                b2 = student_assignments[(student, subj2, c2)]
                for s1 in class_vars[c1]['lesson_starts']:
                    for s2 in class_vars[c2]['lesson_starts']:
                        model.Add(s1 != s2).OnlyEnforceIf([b1, b2])

    # Objective: Minimize total slack (i.e. missing student assignments).
    model.Minimize(sum(slack_vars))
    return model, class_vars, student_assignments, slack_vars

##############################
# PROGRESS CALLBACK FOR FULL CP MODEL
# Version: 1.0 / Revision: 1
##############################
class FullCPCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, class_vars, slack_vars):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.class_vars = class_vars
        self.slack_vars = slack_vars
        self.best_solution = None
        self.solution_count = 0
        self.start_time = time.time()
        self.last_log_time = self.start_time

    def OnSolutionCallback(self):
        self.solution_count += 1
        current_time = time.time()
        elapsed = current_time - self.start_time
        if current_time - self.last_log_time >= 60 and self.solution_count > 0:
            avg_time = elapsed / self.solution_count
            logger.info(f"CP Progress: {self.solution_count} solutions in {int(elapsed)} sec (avg {avg_time:.2f} sec/sol).")
            self.last_log_time = current_time
        current_solution = []
        for c in self.class_vars:
            starts = [self.Value(var) for var in c['lesson_starts']]
            current_solution.append((c['subject_id'], c['teacher_id'], c['group_index'], starts))
        self.best_solution = current_solution
        total_slack = sum(self.Value(s) for s in self.slack_vars)
        if total_slack == 0:
            logger.info("CP Callback: Zero slack achieved. Stopping search.")
            self.StopSearch()

##############################
# SOLVE FULL CP MODEL WITH PROGRESS CALLBACK
# Version: 3.2 / Revision: 1
##############################
def solve_full_cp_model(data):
    model, class_vars, student_assignments, slack_vars = full_cp_model(data)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = os.cpu_count()
    _, math_possible = preliminary_feasibility(data)
    time_limit = CP_EXTENDED_RUN_TIME if math_possible else CP_MAX_RUN_TIME
    solver.parameters.max_time_in_seconds = time_limit
    logger.info(f"Solving full CP model for timetable (time limit: {time_limit} sec, minimizing missing assignments)...")
    
    callback = FullCPCallback(class_vars, slack_vars)
    status = solver.SolveWithSolutionCallback(model, callback)
    
    # Use the best solution found by the callback if any solutions were found.
    if callback.solution_count > 0:
        best_slack = sum(solver.Value(s) for s in slack_vars)
        if best_slack == 0:
            logger.info("Zero slack solution found!")
        else:
            logger.info(f"Time limit reached or no zero-slack solution found. Best solution has total missing assignments = {best_slack}.")
        teacher_schedule = {}
        for (subj_id, teacher_id, group_index, starts) in callback.best_solution:
            subj_name = data["subjects"].get(subj_id, {}).get("name", "Unknown")
            lesson_times = [timeslot_to_day_period(ts) for ts in starts]
            entry = {"subject_id": subj_id, "subject_name": subj_name,
                     "lessons": lesson_times, "group": group_index}
            teacher_schedule.setdefault(teacher_id, []).append(entry)
        student_schedule = {}
        for (student, subj_id, c_index), y in student_assignments.items():
            if solver.Value(y) == 1:
                c = class_vars[c_index]
                teacher_id = c['teacher_id']
                subj_name = data["subjects"].get(subj_id, {}).get("name", "Unknown")
                lessons = [solver.Value(var) for var in c['lesson_starts']]
                lesson_times = [timeslot_to_day_period(ts) for ts in lessons]
                student_schedule.setdefault(student, []).append({
                    "subject_id": subj_id,
                    "subject_name": subj_name,
                    "teacher_id": teacher_id,
                    "group": c["group_index"],
                    "lessons": lesson_times
                })
        return teacher_schedule, student_schedule
    else:
        logger.error("Full CP model: No feasible solution found within time limit.")
        return None, None

##############################
# SCHEDULE FORMATTING FUNCTIONS
# Version: 1.0 / Revision: 2
##############################
def format_timetable_full(teacher_schedule, teachers):
    output_lines = []
    output_lines.append("Full Teacher Schedule:\n")
    sorted_teachers = sorted(teacher_schedule.items(), key=lambda item: teachers.get(item[0], {}).get("name", ""))
    for tid, classes in sorted_teachers:
        teacher = teachers.get(tid, {})
        teacher_name = teacher.get("name", "Unknown")
        output_lines.append(f"Teacher: {teacher_name} (ID: {tid})")
        for cl in classes:
            subject_name = cl["subject_name"]
            subject_id = cl["subject_id"]
            lesson_str = ", ".join([f"{day.capitalize()} P{period}" for day, period in cl["lessons"]])
            output_lines.append(f"  Subject: {subject_name} (ID: {subject_id}) - Group {cl['group']} | Lessons: {lesson_str}")
        output_lines.append("")
    return "\n".join(output_lines)

def format_student_schedule(student_schedule, teachers):
    output_lines = []
    output_lines.append("Student Schedule:\n")
    for student, classes in sorted(student_schedule.items(), key=lambda x: x[0]):
        output_lines.append(f"Student {student}:")
        for cl in classes:
            subj_name = cl["subject_name"]
            teacher_id = cl["teacher_id"]
            teacher_name = teachers.get(teacher_id, {}).get("name", "Unknown")
            lessons = ", ".join([f"{day.capitalize()} P{period}" for day, period in cl["lessons"]])
            output_lines.append(f"  Subject: {subj_name}, Teacher: {teacher_name} (ID: {teacher_id}), Group: {cl['group']} | Lessons: {lessons}")
        output_lines.append("")
    return "\n".join(output_lines)

def format_main_schedule(teacher_schedule, teachers):
    main_entries = []
    for teacher_id, classes in teacher_schedule.items():
        teacher = teachers.get(teacher_id, {})
        teacher_name = teacher.get("name", "Unknown")
        for cl in classes:
            subj_id = cl["subject_id"]
            subj_name = cl["subject_name"]
            for (day, period) in cl["lessons"]:
                day_index = DAYS.index(day.lower())
                global_ts = day_index * PERIODS_PER_DAY + period
                main_entries.append({
                    "global_ts": global_ts,
                    "day": day.capitalize(),
                    "period": period,
                    "teacher_name": teacher_name,
                    "teacher_id": teacher_id,
                    "subject_name": subj_name,
                    "subject_id": subj_id,
                    "group": cl["group"]
                })
    main_entries = sorted(main_entries, key=lambda e: e["global_ts"])
    output_lines = []
    output_lines.append("Main Schedule (Ordered by Timeslot):\n")
    for entry in main_entries:
        output_lines.append(f"{entry['day']} Period {entry['period']} - Teacher: {entry['teacher_name']} (ID: {entry['teacher_id']}), Subject: {entry['subject_name']} (ID: {entry['subject_id']}), Group: {entry['group']}")
    return "\n".join(output_lines)

def write_output_to_file(teacher_schedule, student_schedule, main_schedule, conflict_report, teachers, filename="timetable_output.txt"):
    with open(filename, "w") as f:
        f.write("=== Teacher Schedule ===\n")
        f.write(format_timetable_full(teacher_schedule, teachers) + "\n\n")
        f.write("=== Main Schedule ===\n")
        f.write(main_schedule + "\n\n")
        f.write("=== Student Schedule ===\n")
        f.write(format_student_schedule(student_schedule, teachers) + "\n\n")
        f.write("=== Conflict Report ===\n")
        if conflict_report:
            for conflict in conflict_report:
                f.write(conflict + "\n")
        else:
            f.write("No conflicts detected.\n")
    logger.info(f"Output written to {filename}")

##############################
# SIMPLE CONFLICT VALIDATION (for logging)
# Version: 1.0 / Revision: 2
##############################
def validate_student_coverage(teacher_schedule, subject_to_students):
    scheduled = {}
    for teacher_id, classes in teacher_schedule.items():
        for cl in classes:
            subj_id = cl["subject_id"]
            scheduled.setdefault(subj_id, set()).update(cl["lessons"])
    conflicts = []
    for subj_id, picked_students in subject_to_students.items():
        if subj_id not in scheduled:
            conflicts.append(f"Subject {subj_id} has no scheduled classes, but students picked it: {picked_students}")
    return conflicts

##############################
# MAIN TIMETABLE GENERATION (CP-SAT Full Model)
# Version: 3.3 / Revision: 1
##############################
def generate_timetable(USE_CP_SOLVER=False, USE_ITERATIVE_DEEPENING=False):
    data = load_data()
    hard_feasible, math_possible = preliminary_feasibility(data)
    if not hard_feasible:
        logger.error("Preliminary hard feasibility check failed. Aborting timetable generation.")
        return None
    logger.info("Preliminary feasibility check passed. Proceeding with full CP model.")
    cp_time_limit = CP_EXTENDED_RUN_TIME if math_possible else CP_MAX_RUN_TIME
    logger.info(f"Using CP-SAT solver with a time limit of {cp_time_limit} seconds.")
    teacher_schedule, student_schedule = solve_full_cp_model(data)
    if teacher_schedule is not None and student_schedule is not None:
        logger.info("Full CP model timetable generation succeeded.")
        main_schedule = format_main_schedule(teacher_schedule, data["teachers"])
        conflicts = validate_student_coverage(teacher_schedule, data["subject_to_students"])
        write_output_to_file(teacher_schedule, student_schedule, main_schedule, conflicts, data["teachers"])
        return teacher_schedule, student_schedule, main_schedule, conflicts
    else:
        logger.error("Full CP model timetable generation failed.")
        return None

##############################
# MAIN
##############################
if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        result = generate_timetable(USE_CP_SOLVER=True, USE_ITERATIVE_DEEPENING=False)
        if result:
            logger.info("Timetable generation succeeded.")
        else:
            logger.error("Timetable generation failed.")
    except Exception as e:
        logger.exception(f"An error occurred during timetable generation: {e}")
