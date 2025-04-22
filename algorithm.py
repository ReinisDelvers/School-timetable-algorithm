import sqlite3
import math
import logging
import time
import threading
from itertools import groupby
from functools import lru_cache
from data import (
    get_teacher, get_subject, get_student,
    get_subject_teacher, get_subject_student, get_hour_blocker
)
from ortools.sat.python import cp_model

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Constants ---
PERIODS_PER_DAY = 10
DAYS = ["monday", "tuesday", "wednesday", "thursday"]

# --- Global counters for periodic summary ---
backtrack_calls = 0
cp_start_time = 0.0

def periodic_summary():
    # Runs every 5 seconds, logs summary
    while True:
        time.sleep(5)
        elapsed = time.time() - cp_start_time
        logger.info(f"[Summary] elapsed={elapsed:.1f}s, backtracks={backtrack_calls}")

# --- Data Loading ---
def load_data():
    teachers = {t[0]: t for t in get_teacher()}
    subjects = {s[0]: s for s in get_subject()}
    students_raw = get_student()
    subject_teachers = get_subject_teacher()

    subj_students = {}
    for row in get_subject_student():
        sid = row[1]
        subj_students.setdefault(sid, set()).add(row[3])

    hb_row = get_hour_blocker()[0]
    hour_blocker = {
        day: [hb_row[i*PERIODS_PER_DAY + p] for p in range(PERIODS_PER_DAY)]
        for i, day in enumerate(DAYS)
    }
    logger.info(f"Loaded {len(teachers)} teachers, {len(subjects)} subjects, {len(students_raw)} students")
    return teachers, subjects, students_raw, subject_teachers, subj_students, hour_blocker

# --- Session Creation ---
def build_sessions(teachers, subjects, subject_teachers, subj_students, hour_blocker):
    sessions = []
    # Determine total groups per subject (sum of teacher group assignments)
    subj_teacher_map = {}
    for st in subject_teachers:
        sid = st[1]
        grp_num = st[7]
        subj_teacher_map[sid] = subj_teacher_map.get(sid, 0) + grp_num

    # Prepare student partitions, including subjects with zero groups
    student_partitions = {}
    for sid, total_groups in subj_teacher_map.items():
        students = sorted(subj_students.get(sid, []))
        # If no groups specified, treat as single group
        if total_groups <= 0:
            parts = [students]
        else:
            size = math.ceil(len(students) / total_groups) if students else 0
            parts = [students[i*size:(i+1)*size] for i in range(total_groups)]
        student_partitions[sid] = parts

    # Track which partition index to assign next for each subject
    partition_index = {sid: 0 for sid in student_partitions}

    # Create sessions
    for st in subject_teachers:
        sid, tid, grp = st[1], st[3], st[7]
        # Treat zero group assignment as one group
        grp_count = grp if grp > 0 else 1
        teacher = teachers.get(tid)
        subj = subjects.get(sid)
        if not teacher or not subj:
            logger.error(f"Missing data for subject={sid}, teacher={tid}")
            continue
        hours = subj[3]
        maxpd = min(subj[4], 2)
        # Build candidate slots from availability and hour blocker
        cand = []
        for di, day in enumerate(DAYS):
            if not teacher[4 + di]:
                continue
            for p in range(PERIODS_PER_DAY):
                if hour_blocker[day][p] == 1:
                    cand.append(di * PERIODS_PER_DAY + p)
        if not cand:
            logger.error(f"No candidate slots for teacher={tid}, subject={sid}")
        # Assign student partitions
        parts = student_partitions.get(sid, [[]])
        for g in range(grp_count):
            idx = partition_index.get(sid, 0)
            group_students = parts[idx] if idx < len(parts) else []
            partition_index[sid] = idx + 1
            for i in range(hours):
                sessions.append({
                    'id': f"S{sid}_G{g+1}_H{i}",
                    'subject': sid,
                    'teacher': tid,
                    'group': g+1,
                    'students': group_students,
                    'candidates': cand.copy(),
                    'max_per_day': maxpd
                })
    # Log any zero/low candidate sessions
    zero = [s['id'] for s in sessions if not s['candidates']]
    low = [(s['id'], len(s['candidates'])) for s in sessions if 0 < len(s['candidates']) < 3]
    if zero:
        logger.error(f"Sessions with zero candidates: {zero}")
    if low:
        logger.warning(f"Sessions with low candidates: {low}")
    logger.info(f"Built {len(sessions)} sessions")
    return sessions

# --- Greedy Initial Assignment ---
def greedy_initial(sessions):
    """
    Assign each session greedily to the first available slot,
    respecting teacher availability and per-day subject-group limits.
    Returns a list of assigned slot indices, with fallbacks aggregated into one warning.
    """
    teacher_schedule = {}
    subject_daily = {}
    assignment = []
    fallbacks = []

    for sess in sessions:
        sid, grp, maxpd, tid = sess['subject'], sess['group'], sess['max_per_day'], sess['teacher']
        placed = False
        for slot in sess['candidates']:
            day = slot // PERIODS_PER_DAY
            if slot in teacher_schedule.get(tid, set()):
                continue
            if subject_daily.get((sid, grp, day), 0) >= maxpd:
                continue
            teacher_schedule.setdefault(tid, set()).add(slot)
            subject_daily[(sid, grp, day)] = subject_daily.get((sid, grp, day), 0) + 1
            assignment.append(slot)
            placed = True
            break
        if not placed:
            # record fallback, but do not spam log per session
            fallbacks.append((sess['id'], sess['candidates'][:3]))  # show up to 3 candidates
            assignment.append(sess['candidates'][0] if sess['candidates'] else -1)

    if fallbacks:
        # one summary warning
        fallback_info = ", ".join(f"{sid}([{slots}...])" for sid, slots in fallbacks)
        logger.warning(f"Greedy fallback used for {len(fallbacks)} sessions: {fallback_info}")

    return assignment

# --- Backtracking Solver with MRV --- with MRV ---
def backtracking_schedule(sessions):
    global backtrack_calls
    indexed = list(enumerate(sessions))
    indexed.sort(key=lambda x: len(x[1]['candidates']))
    assignment = {}
    teacher_schedule = {}
    subject_daily = {}
    backtrack_calls = 0
    
    def backtrack(idx):
        global backtrack_calls
        backtrack_calls += 1
        if idx == len(indexed):
            return True
        sess_index, sess = indexed[idx]
        sid, grp, maxpd, tid = sess['subject'], sess['group'], sess['max_per_day'], sess['teacher']
        for slot in sess['candidates']:
            day = slot // PERIODS_PER_DAY
            if slot in teacher_schedule.get(tid, set()): continue
            if subject_daily.get((sid, grp, day), 0) >= maxpd: continue
            assignment[sess_index] = slot
            teacher_schedule.setdefault(tid, set()).add(slot)
            subject_daily[(sid, grp, day)] = subject_daily.get((sid, grp, day), 0) + 1
            if backtrack(idx+1): return True
            teacher_schedule[tid].remove(slot)
            subject_daily[(sid, grp, day)] -= 1
            del assignment[sess_index]
        logger.debug(f"Backtrack dead end at session {sess['id']}")
        return False
    
    success = backtrack(0)
    if not success:
        return None
    schedule = {}
    for idx, slot in assignment.items():
        di, p = divmod(slot, PERIODS_PER_DAY)
        schedule.setdefault((di, p), []).append(sessions[idx])
    return schedule

# --- CP-SAT Solver ---
def solve_timetable(sessions):
    global cp_start_time
    logger.info(f"Starting CP-SAT on {len(sessions)} sessions")
    model = cp_model.CpModel()
    starts, days = [], []
    for i, sess in enumerate(sessions):
        dom = cp_model.Domain.FromValues(sess['candidates'])
        s = model.NewIntVarFromDomain(dom, f"start_{i}")
        d = model.NewIntVar(0, len(DAYS)-1, f"day_{i}")
        model.AddDivisionEquality(d, s, PERIODS_PER_DAY)
        starts.append(s); days.append(d)
    for tid, _ in groupby(sessions, key=lambda ss: ss['teacher']):
        idxs = [i for i, ss in enumerate(sessions) if ss['teacher']==tid]
        model.AddNoOverlap([model.NewIntervalVar(starts[i],1,starts[i]+1,f"int_{tid}_{i}") for i in idxs])
    for (sid, grp), _ in groupby(sessions, key=lambda ss: (ss['subject'], ss['group'])):
        idxs = [i for i, ss in enumerate(sessions) if ss['subject']==sid and ss['group']==grp]
        maxpd = sessions[idxs[0]]['max_per_day']
        for di in range(len(DAYS)):
            bools=[]
            for i in idxs:
                b = model.NewBoolVar(f"b_{i}_{di}")
                model.Add(days[i]==di).OnlyEnforceIf(b)
                model.Add(days[i]!=di).OnlyEnforceIf(b.Not())
                bools.append(b)
            model.Add(sum(bools) <= maxpd)
    init = greedy_initial(sessions)
    for i, val in enumerate(init): model.AddHint(starts[i], val)
    # Start periodic summary thread
    cp_start_time = time.time()
    summary_thread = threading.Thread(target=periodic_summary, daemon=True)
    summary_thread.start()
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = False
    solver.parameters.max_time_in_seconds = 120  # limit to 2 minutes for best effort
    status = solver.Solve(model)
    cp_elapsed = time.time() - cp_start_time
    logger.info(f"CP-SAT {solver.StatusName(status)} in {cp_elapsed:.2f}s")
    # Fallback if needed
    if status != cp_model.INFEASIBLE and status != cp_model.UNKNOWN:
        # Accept partial or full solution within time limit
        schedule={}
        for i, sess in enumerate(sessions):
            slot=solver.Value(starts[i]); di,p=divmod(slot,PERIODS_PER_DAY)
            schedule.setdefault((di,p),[]).append(sess)
        return schedule
    logger.warning("CP-SAT infeasible, trying backtracking")
    sched = backtracking_schedule(sessions)
    if sched:
        logger.info(f"Backtracking succeeded after {backtrack_calls} calls")
        return sched
    logger.error("Backtracking also failed; no valid timetable")
    return {}

# --- Main ---
if __name__ == '__main__':
    teachers, subjects, students_raw, st_map, stud_map, hb = load_data()
    sessions = build_sessions(teachers, subjects, st_map, stud_map, hb)
    schedule = solve_timetable(sessions)
    for di, day in enumerate(DAYS):
        print(f"=== {day.upper()} ===")
        for p in range(PERIODS_PER_DAY):
            se = schedule.get((di, p), [])
            if se:
                print(f"Period {p+1}: ", end="")
                print(", ".join(s['id'] for s in se))
            else:
                print(f"Period {p+1}: Free")
        print()
