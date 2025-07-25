import math
import logging
import time
from collections import defaultdict, Counter
from data import (
    get_teacher, get_subject, get_student,
    get_subject_teacher, get_subject_student, get_hour_blocker
)
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
    Build sessions for all subjects.
      - Parallel subjects (subj[7] == 1) produce `hours_per_week` combined sessions
        requiring ALL assigned teachers at once (no student grouping yet).
      - Non-parallel subjects split into student groups up front as before.
    Each parallel session is tagged with 'parallel_with' = subject_id for later splitting.
    """
    # 1) validate inputs
    if not validate_input_data(teachers, subjects, subject_teachers, subj_students):
        logger.error("Input data validation failed")
        return []

    # 2) map subject → list of (teacher_id, group_count)
    subject_teacher_groups = defaultdict(list)
    for st in subject_teachers:
        sid = st[1]
        tid = st[3]
        grp = max(1, st[7])
        subject_teacher_groups[sid].append((tid, grp))

    sessions = []

    # 3) build sessions
    for sid, subj in subjects.items():
        hours_per_week = subj[3]
        maxpd = max(0, subj[4])
        minpd = max(1, subj[6])
        if minpd > maxpd:
            minpd = maxpd

        all_students   = sorted(subj_students.get(sid, []))
        teacher_groups = subject_teacher_groups.get(sid, [])
        if not teacher_groups:
            logger.error(f"No teacher assigned for Subject {sid}")
            continue

        # flatten teacher list (respect group counts)
        flat_teachers = [tid for (tid, cnt) in teacher_groups for _ in range(cnt)]

        # --- PARALLEL SUBJECTS ---
        if subj[7] == 1:
            # create one combined single-hour session per required hour
            for hour in range(hours_per_week):
                sess = create_single_session(
                    sid=sid,
                    teachers_list=flat_teachers,
                    hour=hour,
                    students=all_students,
                    teachers_dict=teachers,
                    maxpd=maxpd,
                    minpd=minpd,
                    hour_blocker=hour_blocker,
                    subjects_dict=subjects,
                    parallel_group=sid
                )
                sessions.append(sess)
            continue

        # --- NON-PARALLEL SUBJECTS ---
        n_groups = subj[2]
        size = math.ceil(len(all_students) / n_groups)
        student_groups = [
            all_students[i*size:(i+1)*size]
            for i in range(n_groups)
        ]
        
        # Check if there are fewer teachers than groups for non-parallel subjects
        fewer_teachers = len(flat_teachers) < n_groups
        if fewer_teachers:
            logger.warning(f"Subject {sid}: {len(flat_teachers)} teachers for {n_groups} groups - distributing carefully")
            
        # Distribute teachers to groups, ensuring each teacher knows which groups they teach
        teacher_groups_map = defaultdict(list)  # {teacher_id: [group_indices]}
        
        # Assign teachers to groups evenly
        for grp_idx, studs in enumerate(student_groups):
            if not studs:
                continue
                
            if grp_idx < len(flat_teachers):
                # If we have enough teachers, assign one per group
                tid = flat_teachers[grp_idx]
            else:
                # Otherwise, find the teacher with the least groups assigned
                tid = min(flat_teachers, key=lambda t: len(teacher_groups_map[t]))
                
            # Track which groups this teacher is assigned to
            teacher_groups_map[tid].append(grp_idx)

        # Now create sessions for each group with their assigned teacher
        for grp_idx, studs in enumerate(student_groups):
            if not studs:
                continue
                
            # Find which teacher is assigned to this group
            assigned_teacher = None
            for tid, groups in teacher_groups_map.items():
                if grp_idx in groups:
                    assigned_teacher = tid
                    break
                    
            if not assigned_teacher:
                logger.error(f"No teacher assigned for group {grp_idx+1} of subject {sid}")
                continue

            # Add teacher conflict info for scheduler
            teacher_conflict_groups = teacher_groups_map[assigned_teacher]
            
            if minpd >= 2:
                full = hours_per_week // minpd
                left = hours_per_week - full * minpd

                # full-block sessions
                for _ in range(full):
                    blk = create_block_session(
                        sid=sid,
                        teachers_list=[assigned_teacher],
                        students=studs,
                        teachers_dict=teachers,
                        block_size=minpd,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=None
                    )
                    blk['group'] = grp_idx + 1
                    
                    # Mark which other groups share this teacher to prevent conflicts
                    if len(teacher_conflict_groups) > 1:
                        blk['teacher_shared_with'] = teacher_conflict_groups
                        
                    sessions.append(blk)

                # leftover single-hour sessions
                for i in range(left):
                    single = create_single_session(
                        sid=sid,
                        teachers_list=[assigned_teacher],
                        hour=i,
                        students=studs,
                        teachers_dict=teachers,
                        maxpd=maxpd,
                        minpd=1,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=None
                    )
                    single['group'] = grp_idx + 1
                    
                    # Mark which other groups share this teacher to prevent conflicts
                    if len(teacher_conflict_groups) > 1:
                        single['teacher_shared_with'] = teacher_conflict_groups
                        
                    sessions.append(single)

            else:
                # hour-by-hour scheduling
                for h in range(hours_per_week):
                    sess = create_single_session(
                        sid=sid,
                        teachers_list=[assigned_teacher],
                        hour=h,
                        students=studs,
                        teachers_dict=teachers,
                        maxpd=maxpd,
                        minpd=minpd,
                        hour_blocker=hour_blocker,
                        subjects_dict=subjects,
                        parallel_group=None
                    )
                    sess['group'] = grp_idx + 1
                    
                    # Mark which other groups share this teacher to prevent conflicts
                    if len(teacher_conflict_groups) > 1:
                        sess['teacher_shared_with'] = teacher_conflict_groups
                        
                    sessions.append(sess)

    return sessions

def split_parallel_sessions(schedule, subjects, subj_students):
    """
    After scheduling, expand each parallel session into its
    subj[2] student-groups—keeping them all in the same timeslot.
    When teacher count < group count, ensure proper teacher distribution
    and track which groups can't be scheduled in the same hour.
    """
    result = {}
    
    # Process each timeslot
    for slot, slot_sessions in schedule.items():
        result_slot = []
        
        # Track which teachers are already assigned in this slot
        teachers_in_slot = set()
        
        # First add all non-parallel sessions to the result and track their teachers
        for sess in slot_sessions:
            if 'parallel_with' not in sess:
                result_slot.append(sess)
                for tid in sess['teachers']:
                    teachers_in_slot.add(tid)
        
        # Now process parallel sessions
        parallel_sessions = [sess for sess in slot_sessions if 'parallel_with' in sess]
        
        # Sort by subject to ensure consistent processing
        parallel_sessions.sort(key=lambda s: s['subject'])
        
        for sess in parallel_sessions:
            sid = sess['subject']
            subj = subjects[sid]
            n_groups = subj[2]
            all_students = sorted(subj_students.get(sid, []))
            
            # Skip if no students
            if not all_students:
                continue
                
            # Calculate group size and split students
            size = max(1, math.ceil(len(all_students) / n_groups))
            student_groups = []
            for i in range(n_groups):
                start_idx = i * size
                end_idx = min(start_idx + size, len(all_students))
                if start_idx < len(all_students):
                    student_groups.append(all_students[start_idx:end_idx])
            
            # Create a pool of available teachers for this subject
            available_teachers = [t for t in sess['teachers'] if t not in teachers_in_slot]
            
            # If we have more groups than available teachers, we need to reschedule
            if len(student_groups) > (len(available_teachers) + len(sess['teachers']) - len(available_teachers)):
                logger.warning(f"Not enough teachers for all groups in subject {sid} at {slot}. Some groups will need rescheduling.")
            
            # Create split sessions for each group
            for grp_idx, students in enumerate(student_groups, start=1):
                if not students:
                    continue
                    
                # Create a copy of the session for this group
                split_sess = copy.deepcopy(sess)
                split_sess['students'] = students
                split_sess['group'] = grp_idx
                
                # Remove parallel_with marker
                if 'parallel_with' in split_sess:
                    del split_sess['parallel_with']
                
                # Assign a teacher if available
                if available_teachers:
                    assigned_tid = available_teachers.pop(0)
                    split_sess['teachers'] = [assigned_tid]
                    teachers_in_slot.add(assigned_tid)
                else:
                    # We need to force this group to be scheduled in a different timeslot
                    # by creating an impossible conflict
                    if sess['teachers']:
                        assigned_tid = random.choice(sess['teachers'])
                        split_sess['teachers'] = [assigned_tid]
                        # We do NOT add to teachers_in_slot to ensure this conflict is detected
                
                result_slot.append(split_sess)
        
        result[slot] = result_slot
    
    # Final validation: ensure no teacher conflicts
    for slot, sessions in result.items():
        teachers_used = {}
        for sess in sessions:
            for tid in sess['teachers']:
                if tid in teachers_used:
                    logger.error(f"Teacher {tid} assigned to multiple sessions at {slot}")
                teachers_used[tid] = sess['id']
    
    return result

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
        'block_size': 1,
        'hour': hour
    }
    
    # Add parallel_with marker if this is a parallel session
    if parallel_group is not None:
        session['parallel_with'] = parallel_group

    for di, day in enumerate(DAYS):
        # must be available that day
        if not all(teachers_dict[tid][4 + di] for tid in teachers_list):
            continue

        # each teacher's allowed window on that day:
        # start = teachers_dict[tid][8+di], end = teachers_dict[tid][12+di]
        for p in range(PERIODS_PER_DAY):
            if hour_blocker[day][p] != 1:
                continue

            ok = True
            for tid in teachers_list:
                start, end = teachers_dict[tid][8 + di], teachers_dict[tid][12 + di]
                # p is zero‐based, hours are 1‐based:
                if not (start - 1 <= p <= end - 1):
                    ok = False
                    break
            if not ok:
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
        if not all(teachers_dict[tid][4 + di] for tid in teachers_list):
            continue

        # each teacher's allowed window on that day
        starts = [teachers_dict[tid][8 + di] - 1 for tid in teachers_list]
        ends   = [teachers_dict[tid][12 + di] - 1 for tid in teachers_list]

        for p in range(PERIODS_PER_DAY - block_size + 1):
            can_place = True
            for offset in range(block_size):
                idx = p + offset
                # global blocker
                if hour_blocker[day][idx] != 1:
                    can_place = False
                    break

                # window check
                if any(idx < s or idx > e for s, e in zip(starts, ends)):
                    can_place = False
                    break

            if can_place:
                session['candidates'].append(di * PERIODS_PER_DAY + p)

    if not session['candidates']:
        logger.error(f"Block session {session['id']} (Subject {sid}, size={block_size}) has NO CANDIDATES.")
    return session

def evaluate_schedule(schedule, all_sessions, subjects):
    """
    Compute a numeric score of `schedule`. Lower is better.
    Treats each (subject, group) separately for minpd/maxpd/weekly totals.
    **Returns float('inf') immediately if any teacher or student conflict exists.**
    """
    IDLE_PENALTY = 5000

    # CRITICAL CHECK: Detect teachers assigned to multiple sessions at the same time
    teacher_timeslots = {}  # (teacher_id, day, period) -> session_id
    
    for (day, period), sessions_here in schedule.items():
        for sess in sessions_here:
            for tid in sess['teachers']:
                key = (tid, day, period)
                if key in teacher_timeslots:
                    # Teacher already has a session at this time - IMMEDIATE REJECTION
                    return float('inf')
                teacher_timeslots[key] = sess['id']

    score = 0
    teacher_conflicts = 0
    student_conflicts = 0

    # Structures for counting
    scheduled_count     = defaultdict(lambda: defaultdict(int))
    subject_daily_hours = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    student_schedule    = defaultdict(lambda: defaultdict(list))
    teacher_slots       = defaultdict(lambda: defaultdict(set))

    # 1) Tally and detect conflicts
    for (day, period), sessions_here in schedule.items():
        for sess in sessions_here:
            sid, grp = sess['subject'], sess['group']
            blk = sess.get('block_size', 1)

            # accumulate for min/max checks later
            scheduled_count[sid][grp] += blk
            subject_daily_hours[sid][grp][day] += blk

            # detect student conflict
            for st in sess['students']:
                if period in student_schedule[st][day]:
                    student_conflicts += 1
                student_schedule[st][day].append(period)

            # detect teacher conflict
            for tid in sess['teachers']:
                if period in teacher_slots[tid][day]:
                    teacher_conflicts += 1
                teacher_slots[tid][day].add(period)

    # Hard‐fail if any conflicts
    if teacher_conflicts or student_conflicts:
        return float('inf')

    # 2) Build daily load counts for students
    student_daily_hours = {
        st: {d: len(ps) for d, ps in days.items()}
        for st, days in student_schedule.items()
    }

    # 3) Enforce per‐group minpd/maxpd & contiguity + weekly totals
    for sid, subj in subjects.items():
        minpd = max(0, subj[6])
        maxpd = max(0, subj[4])
        if minpd > maxpd:
            minpd = maxpd
        req = subj[3]
        leftover = req - (req // minpd) * minpd if minpd > 0 else 0

        for grp in range(1, subj[2] + 1):
            for d in range(4):
                actual = subject_daily_hours[sid][grp].get(d, 0)
                if actual > maxpd:
                    score += 5000 * (actual - maxpd)
                if 0 < actual < minpd and actual != leftover:
                    score += 10000 * (minpd - actual)
                if actual == minpd:
                    # check contiguity
                    periods = sorted(
                        p for (dd, p), sl in schedule.items()
                        if dd == d for s in sl
                        if s['subject'] == sid and s['group'] == grp
                    )
                    for i in range(len(periods)-1):
                        if periods[i+1] - periods[i] != 1:
                            score += 20000
            # weekly total
            actual_week = scheduled_count[sid][grp]
            if actual_week != req:
                score += 20000 * abs(actual_week - req)

    # 4) Student daily‐load penalties
    for st, daily in student_daily_hours.items():
        for d, h in daily.items():
            if h < 4:
                score += 2000 * (4 - h)
            elif h > 6:
                score += 3000 * (h - 6)

    # 5) Idle‐time gaps
    for st, days in student_schedule.items():
        for d, ps in days.items():
            if len(ps) < 2:
                continue
            ps_sorted = sorted(ps)
            for i in range(len(ps_sorted)-1):
                gap = ps_sorted[i+1] - ps_sorted[i] - 1
                if gap > 0:
                    score += IDLE_PENALTY * gap

    return score

# --- Evaluation Function (penalizes idle gaps) ---
def greedy_initial(sessions, subjects):
    """
    Build a starting schedule by placing sessions one-by-one greedily,
    treating each (subject, group) separately.
    """
    # keyed by [subject][group]
    subject_requirements = defaultdict(lambda: defaultdict(int))
    for sess in sessions:
        sid, grp = sess['subject'], sess['group']
        subject_requirements[sid][grp] += sess.get('block_size', 1)

    subjects_scheduled = defaultdict(lambda: defaultdict(int))
    subject_daily      = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    teacher_schedule   = defaultdict(set)
    student_schedule   = defaultdict(lambda: defaultdict(list))
    schedule           = {}  # (day,period) -> [session, ...]

    def session_priority(sess):
        sid, grp = sess['subject'], sess['group']
        required = subject_requirements[sid][grp]
        placed   = subjects_scheduled[sid][grp]
        no_sessions_yet = (placed == 0)
        remaining_ratio = (required - placed) / required if required > 0 else 0
        earliest = min(sess['candidates']) if sess['candidates'] else PERIODS_PER_DAY * len(DAYS)
        return (no_sessions_yet, remaining_ratio, -earliest, len(sess['students']))

    def has_student_conflict(sess, day, start_period):
        bs = sess.get('block_size', 1)
        for offset in range(bs):
            period = start_period + offset
            for stu in sess['students']:
                if period in student_schedule[stu][day]:
                    return True
        return False

    def has_teacher_conflict(sess, day, period, schedule):
        """
        Check if placing session 'sess' at (day, period) would create 
        a teacher conflict with any existing sessions.
        Returns True if there would be a conflict (teacher has 2+ groups).
        """
        bs = sess.get('block_size', 1)
        
        for offset in range(bs):
            target_slot = (day, period + offset)
            if target_slot in schedule:
                for existing_sess in schedule[target_slot]:
                    # Skip comparing with self (for swap operations)
                    if existing_sess.get('id') == sess.get('id'):
                        continue
                    
                    # Check for any common teachers - that would be a conflict
                    for tid in sess['teachers']:
                        if tid in existing_sess['teachers']:
                            return True
                            
        return False

    def slot_score(sess, sl):
        day = sl // PERIODS_PER_DAY
        period = sl % PERIODS_PER_DAY

        # 1) prefer morning
        morning_flag = (period >= 5)
        # 2) prefer less-busy days
        busy_flag = (sum(len(schedule.get((day, p), [])) for p in range(PERIODS_PER_DAY)) > 0)
        # 3) earlier in week/day
        week_flag = -day
        day_flag  = -period

        # 4) student-proximity
        total_dist, count = 0, 0
        for stu in sess['students']:
            existing = student_schedule[stu][day]
            if not existing:
                total_dist += PERIODS_PER_DAY
            else:
                total_dist += min(abs(period - p0) for p0 in existing)
            count += 1
        proximity_flag = -(total_dist / count if count else PERIODS_PER_DAY)

        # 5) gap-penalty
        gap_penalty = 0
        for stu in sess['students']:
            ex = sorted(student_schedule[stu][day])
            if len(ex) <= 1:
                continue
            old_gaps = sum(ex[i+1] - ex[i] - 1 for i in range(len(ex)-1))
            new_list = sorted(ex + [period])
            new_gaps = sum(new_list[i+1] - new_list[i] - 1 for i in range(len(new_list)-1))
            gap_penalty += (new_gaps - old_gaps)
        gap_flag = -gap_penalty

        return (morning_flag, busy_flag, week_flag, day_flag, proximity_flag, gap_flag)

    def find_best_slot(sess):
        sid, grp = sess['subject'], sess['group']
        maxpd = sess['max_per_day']
        bs    = sess.get('block_size', 1)
        daily = subject_daily[sid][grp]

        for sl in sorted(sess['candidates'], key=lambda x: slot_score(sess, x)):
            d, p0 = sl // PERIODS_PER_DAY, sl % PERIODS_PER_DAY
            if p0 + bs > PERIODS_PER_DAY:
                continue
            if daily.get(d, 0) + bs > maxpd:
                continue
            if has_teacher_conflict(sess, d, p0, schedule):  # Pass schedule here
                continue
            if has_student_conflict(sess, d, p0):
                continue
            return sl
        return None

    total = sum(sess.get('block_size', 1) for sess in sessions)

    while True:
        pending = [
            s for s in sessions
            if subjects_scheduled[s['subject']][s['group']] < subject_requirements[s['subject']][s['group']]
        ]
        if not pending:
            break
        pending.sort(key=session_priority, reverse=True)
        progress = False
        for sess in pending:
            sid, grp = sess['subject'], sess['group']
            if subjects_scheduled[sid][grp] >= subject_requirements[sid][grp]:
                continue
            slot = find_best_slot(sess)
            if slot is not None:
                d, p0 = slot // PERIODS_PER_DAY, slot % PERIODS_PER_DAY
                bs = sess.get('block_size', 1)
                for off in range(bs):
                    p = p0 + off
                    schedule.setdefault((d, p), []).append(sess)
                    idx = d * PERIODS_PER_DAY + p
                    for tid in sess['teachers']:
                        teacher_schedule[tid].add(idx)
                    for stu in sess['students']:
                        student_schedule[stu][d].append(p)
                    subject_daily[sid][grp][d] += 1
                subjects_scheduled[sid][grp] += bs
                progress = True
        if not progress:
            break

    placed = sum(sum(g.values()) for g in subjects_scheduled.values())
    unplaced = [
        s['id'] for s in sessions
        if subjects_scheduled[s['subject']][s['group']] < subject_requirements[s['subject']][s['group']]
    ]
    logger.info(f"greedy_initial placed {placed}/{total} hours; unplaced={unplaced}")
    return schedule

def count_placed_hours_per_group(schedule):
    """
    Count placed hours per (subject, group).
    Returns a dict: placed[sid][grp] = hours.
    """
    placed = defaultdict(lambda: defaultdict(int))
    for (day, period), slot_sessions in schedule.items():
        for sess in slot_sessions:
            sid, grp = sess['subject'], sess['group']
            placed[sid][grp] += sess.get('block_size', 1)
    return placed

# --- Solver with Simulated Annealing & Fallback ---
def solve_timetable(sessions, subjects, teachers, hour_blocker, time_limit=1200, stop_flag=None):
    """
    Greedy initial → fallback for missing → simulated annealing loop.
    """
    start_time = time.time()
    original_sessions = copy.deepcopy(sessions)

    # 1) Greedy initial
    current = greedy_initial(sessions, subjects)

    # 2) Fallback if any (sid,grp) under-scheduled
    placed_counts = count_placed_hours_per_group(current)
    missing_any = any(
        placed_counts[sid].get(grp, 0) < subj[3]
        for sid, subj in subjects.items()
        for grp in range(1, subj[2] + 1)
    )
    if missing_any:
        logger.info("Fallback: replacing incomplete groups with singles")
        sessions = fallback_replace_blocks_with_all_singles(
            original_sessions, current, subjects, teachers, hour_blocker
        )
        current = greedy_initial(sessions, subjects)

    # 3) Score & keep best
    current_score = evaluate_schedule(current, sessions, subjects)
    best_schedule = copy.deepcopy(current)
    best_score = current_score
    logger.info(f"Initial score: {best_score}")

    # 4) Simulated annealing
    temp = 1.0
    cooling_rate = 0.999
    min_temp = 0.001
    iteration = 0
    stall_count = 0
    last_log_time = start_time
    max_iterations = 100000  # Add a hard iteration limit

    while temp > min_temp and (time.time() - start_time < time_limit) and iteration < max_iterations:
        if stop_flag and stop_flag():
            break
            
        # Safety timeout check - log progress and check if we're making progress
        current_time = time.time()
        if current_time - last_log_time > 30:  # Log every 30 seconds
            logger.info(f"Still running... Iter {iteration}, best_score={best_score}, temp={temp:.4f}")
            last_log_time = current_time
            
        # Hard timeout safety
        if current_time - start_time > time_limit * 0.95:
            logger.warning("Time limit nearly reached, finishing up...")
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
            break

        temp *= cooling_rate

    # Load the subject-student mapping for splitting parallel sessions
    subj_students = {}
    for row in get_subject_student():
        subject_ids = json.loads(row[1])
        student_id = row[3]
        for sid in subject_ids:
            subj_students.setdefault(sid, set()).add(student_id)

    # Now split the parallel sessions in the best schedule
    logger.info("Splitting parallel subject groups...")
    best_schedule = split_parallel_sessions(best_schedule, subjects, subj_students)
    
    # 5) Build students_dict for output
    students_dict = {
        s[0]: {'id': s[0], 'name': f"{s[1]} {s[2] or ''} {s[3]}".strip()}
        for s in get_student()
    }
    return best_schedule, students_dict

def has_teacher_conflict(sess, day, period, schedule):
    """
    Check if placing session 'sess' at (day, period) would create 
    a teacher conflict with any existing sessions.
    Returns True if there would be a conflict (teacher has 2+ groups).
    """
    bs = sess.get('block_size', 1)
    
    for offset in range(bs):
        target_slot = (day, period + offset)
        if target_slot in schedule:
            for existing_sess in schedule[target_slot]:
                # Skip comparing with self (for swap operations)
                if existing_sess.get('id') == sess.get('id'):
                    continue
                
                # Check for any common teachers - that would be a conflict
                for tid in sess['teachers']:
                    if tid in existing_sess['teachers']:
                        return True
                        
    return False

def count_placed_hours(schedule):
    placed = defaultdict(int)
    for (_, _), slot in schedule.items():
        for sess in slot:
            placed[sess['subject']] += 1
    return placed

def fallback_replace_blocks_with_all_singles(all_sessions, placed_schedule, subjects, teachers, hour_blocker):
    """
    Replace only those (subject, group) combos that missed required hours
    with single-hour sessions tagged to their group.
    """
    placed_counts = count_placed_hours_per_group(placed_schedule)
    missing = []
    for sid, subj in subjects.items():
        req = subj[3]
        for grp in range(1, subj[2] + 1):
            if placed_counts[sid].get(grp, 0) < req:
                missing.append((sid, grp))
    if not missing:
        return all_sessions

    subject_teachers = defaultdict(list)
    for st in get_subject_teacher():
        s_id, t_id = st[1], st[3]
        subject_teachers[s_id].append(t_id)

    new_sessions = [
        s for s in all_sessions
        if (s['subject'], s['group']) not in missing
    ]
    for sid, grp in missing:
        req = subjects[sid][3]
        teachers_list = subject_teachers.get(sid, [])
        all_students = next(
            (s['students'] for s in all_sessions
             if s['subject']==sid and s['group']==grp),
            []
        )
        maxpd = subjects[sid][4]
        for h in range(req):
            if not teachers_list:
                continue
            tid = teachers_list[h % len(teachers_list)]
            single = create_single_session(
                sid=sid,
                teachers_list=[tid],
                hour=h,
                students=all_students,
                teachers_dict=teachers,
                maxpd=maxpd,
                minpd=1,
                hour_blocker=hour_blocker,
                subjects_dict=subjects,
                parallel_group=None
            )
            single['group'] = grp
            new_sessions.append(single)
    return new_sessions


def generate_neighbor(schedule, subjects):
    """
    Generate a neighbor state from the current schedule.
    Ensures that teachers are never assigned to multiple groups at the same time.
    """
    moves = [
        move_session_to_empty_slot,
        swap_two_sessions,
        move_parallel_group,
        reorganize_day
    ]
    
    # Try up to 10 times to generate a valid neighbor
    for _ in range(10):
        move = random.choice(moves)
        neighbor = copy.deepcopy(schedule)
        neighbor = move(neighbor, subjects)
        
        # Validate: check that no teacher has multiple groups at the same time
        teacher_timeslots = {}  # (tid, day, period) -> session_id
        has_conflicts = False
        
        for (day, period), sessions_here in neighbor.items():
            for sess in sessions_here:
                for tid in sess['teachers']:
                    key = (tid, day, period)
                    if key in teacher_timeslots:
                        has_conflicts = True
                        break
                    teacher_timeslots[key] = sess['id']
                if has_conflicts:
                    break
            if has_conflicts:
                break
                
        if not has_conflicts:
            return neighbor
    
    # If all attempts failed, return a copy of the original schedule
    return copy.deepcopy(schedule)

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

        # Use our new teacher conflict check function
        if has_teacher_conflict(session, nd, np, schedule):
            continue

        # Student conflict check
        conflict = False
        for off in range(bs):
            if has_student_conflict(session,(nd,np+off),schedule):
                conflict=True
                break
        if conflict:
            continue

        # Execute the move
        old_slots=[k for k,v in schedule.items() if session in v]
        for os in old_slots:
            schedule[os].remove(session)
            if not schedule[os]:
                del schedule[os]
        for off in range(bs):
            slot=(nd,np+off)
            schedule.setdefault(slot,[]).append(session)
        return schedule

    return schedule

def swap_two_sessions(schedule, subjects):
    occupied=list(schedule.keys())
    if len(occupied)<2: return schedule
    
    s1,s2=random.sample(occupied,2)
    if not schedule[s1] or not schedule[s2]: return schedule

    sess1=random.choice(schedule[s1])
    sess2=random.choice(schedule[s2])
    sid1,sid2=sess1['subject'],sess2['subject']
    maxpd1,maxpd2=sess1['max_per_day'],sess2['max_per_day']
    bs1,bs2=sess1.get('block_size',1),sess2.get('block_size',1)
    d1,p1=s1; d2,p2=s2

    daily1,daily2 = _compute_subject_daily(schedule,sid1),_compute_subject_daily(schedule,sid2)
    nd1=daily1.copy(); nd2=daily2.copy()
    nd1[d1]-=bs1; nd1[d2]+=bs1
    nd2[d2]-=bs2; nd2[d1]+=bs2
    if nd1[d2]>maxpd1 or nd2[d1]>maxpd2: return schedule

    # Create temporary schedules for conflict checking
    test_schedule1 = copy.deepcopy(schedule)
    test_schedule2 = copy.deepcopy(schedule)
    
    # Remove sess1 from its slots in test_schedule1
    for slot in [s1]:
        for off in range(bs1):
            test_slot = (slot[0], slot[1] + off)
            if test_slot in test_schedule1:
                if sess1 in test_schedule1[test_slot]:
                    test_schedule1[test_slot].remove(sess1)
                    
    # Remove sess2 from its slots in test_schedule2
    for slot in [s2]:
        for off in range(bs2):
            test_slot = (slot[0], slot[1] + off)
            if test_slot in test_schedule2:
                if sess2 in test_schedule2[test_slot]:
                    test_schedule2[test_slot].remove(sess2)
    
    # Check if sess1 can go to sess2's position without teacher conflicts
    if has_teacher_conflict(sess1, d2, p2, test_schedule1):
        return schedule
        
    # Check if sess2 can go to sess1's position without teacher conflicts
    if has_teacher_conflict(sess2, d1, p1, test_schedule2):
        return schedule

    # Student conflict checks remain the same
    for off in range(bs1):
        if has_student_conflict(sess1,(d2,p2+off),schedule): return schedule
    for off in range(bs2):
        if has_student_conflict(sess2,(d1,p1+off),schedule): return schedule

    # Execute swap
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
    """
    Format the schedule for output with proper parallel class identification.
    """
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
            'periods_per_day': PERIODS_PER_DAY,
            'total_sessions': sum(len(slots) for slots in schedule.values())
        },
        'days': {}
    }

    for (day, period), slot_sessions in schedule.items():
        day_str = str(day)
        per_str = str(period)
        formatted['days'].setdefault(day_str, {})\
                         .setdefault(per_str, [])

        for sess in slot_sessions:
            # Skip sessions with no students
            if not sess['students']:
                continue
                
            sid = sess['subject']
            subj = subject_dict[sid]

            # Determine if this is from a parallel subject
            is_parallel = subjects[sid][7] == 1

            teachers_out = [
                {'id': tid, 'name': teacher_dict[tid]['name']}
                for tid in sess['teachers'] if tid is not None
            ]
            students_out = [
                {'id': st, 'name': students_dict[st]['name']}
                for st in sess['students']
            ]

            formatted_session = {
                'id': sess['id'],
                'subject_id': sid,
                'subject_name': subj['name'],
                'teachers': teachers_out,
                'students': students_out,
                'group': sess.get('group', 1),
                'is_parallel': is_parallel
            }
            formatted['days'][day_str][per_str].append(formatted_session)

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

    # For each subject, set the required hours properly accounting for parallel subjects
    for sid, subj in subjects.items():
        hours_per_week = subj[3]
        if subj[7] == 1:  # If it's a parallel subject
            group_count = subj[2]
            stats['required_hours'][sid] = hours_per_week * group_count
        else:
            stats['required_hours'][sid] = hours_per_week
    
    # Track unique (day, period, subject) combinations to count actual hours correctly
    subject_slots = defaultdict(set)
    
    # Process all sessions to find student/teacher conflicts
    for (day, period), slot_sessions in schedule.items():
        teachers_this_slot = defaultdict(list)
        students_this_slot = defaultdict(list)
        
        # First pass: collect all data for this slot
        for sess in slot_sessions:
            sid = sess['subject']
            
            # Add this timeslot to the subject's set
            subject_slots[sid].add((day, period))
            
            # Daily tracking for the UI display
            stats['subject_daily'][sid][day] += 1
            
            # Track teachers and students for conflict detection
            for tid in sess['teachers']:
                teachers_this_slot[tid].append(sess['id'])
                stats['teacher_daily_load'][tid][day] += 1
                
            for stu in sess['students']:
                students_this_slot[stu].append(sess['id'])
                stats['student_daily_load'][stu][day] += 1

        # Check for conflicts
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
    
    # Count hours correctly by examining each subject's slots and sessions
    for sid, subj in subjects.items():
        is_parallel = subj[7] == 1
        group_count = subj[2] if is_parallel else 1
        
        if is_parallel:
            # For parallel subjects, count how many groups were actually created
            # by counting unique group numbers within each time slot
            for (day, period) in subject_slots[sid]:
                groups_in_slot = set()
                for sess in schedule.get((day, period), []):
                    if sess['subject'] == sid:
                        groups_in_slot.add(sess.get('group', 1))
                
                # Count once per actual group present
                stats['subject_hours'][sid] += len(groups_in_slot)
        else:
            # For regular subjects, just count the number of slots where it appears
            stats['subject_hours'][sid] = len(subject_slots[sid])

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
