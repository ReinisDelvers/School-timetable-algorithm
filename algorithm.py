"""
algorithm.py - Revision 1.5
This revision adds an extra candidate filtering step (forward checking) during backtracking.
For each session, we recompute the candidate timeslots by filtering out those that conflict
with current teacher bookings or exceed the per-day limit for that subject and group.
This should prune the search space and reduce memory usage.
"""

import math
from data import get_subject, get_teacher, get_subject_teacher, get_hour_blocker, get_student_count_by_subject

# Global definitions
DEBUG = True
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
PERIODS = list(range(1, 11))  # Periods 1 to 10

def get_teacher_availability(teacher, day, period):
    """
    Check if a teacher is available on a given day and period.
    Uses teacher tuple fields:
      - Monday: teacher[4] (flag), teacher[8] (allowed start), teacher[12] (allowed end)
      - Tuesday: teacher[5], teacher[9], teacher[13]
      - Wednesday: teacher[6], teacher[10], teacher[14]
      - Thursday: teacher[7], teacher[11], teacher[15]
    """
    if day == "monday":
        available = teacher[4]
        start = teacher[8]
        end = teacher[12]
    elif day == "tuesday":
        available = teacher[5]
        start = teacher[9]
        end = teacher[13]
    elif day == "wednesday":
        available = teacher[6]
        start = teacher[10]
        end = teacher[14]
    elif day == "thursday":
        available = teacher[7]
        start = teacher[11]
        end = teacher[15]
    else:
        return False

    if not available:
        return False

    allowed_start = start if start > 0 else 1
    allowed_end = end if end > 0 else 10
    return allowed_start <= period <= allowed_end

def get_hour_blocker_for(day, period, hour_blocker):
    """
    Retrieve the hour blocker value for the given day and period.
    The hour_blocker row has 40 columns:
      - Monday: indices 0-9, Tuesday: 10-19, Wednesday: 20-29, Thursday: 30-39.
    A value of 1 means the period is available.
    """
    if day == "monday":
        offset = 0
    elif day == "tuesday":
        offset = 10
    elif day == "wednesday":
        offset = 20
    elif day == "thursday":
        offset = 30
    else:
        return 0
    index = offset + (period - 1)
    return hour_blocker[0][index]

def build_sessions():
    """
    Build a list of session dictionaries to schedule.
    For each subject and for each group (as defined by group_number),
    create hours_per_week sessions. This represents that the teacher teaches
    each group as separate classes.
    
    Also, compute the number of students per group by dividing the total enrolled
    student count by group_number (using ceiling division).
    """
    sessions = []
    subjects = get_subject()  # (id, name, group_number, hours_per_week, max_hours_per_day, max_student_count, min_hours_per_day, ...)
    if DEBUG:
        print(f"DEBUG: Found {len(subjects)} subjects.")
    subject_teacher_list = get_subject_teacher()  
    teachers = get_teacher()

    # Get total student counts per subject.
    student_counts = get_student_count_by_subject()

    # Build teacher mapping: (subject_id, group) -> teacher tuple.
    teacher_mapping = {}
    for st in subject_teacher_list:
        subj_id = st[1]
        group = st[7]  # group number for subject-teacher mapping
        teacher_id_raw = st[3]
        if teacher_id_raw is None:
            if DEBUG:
                print(f"DEBUG: Skipping subject_teacher record for subject {subj_id} group {group} due to missing teacher_id")
            continue
        try:
            teacher_id = int(teacher_id_raw)
        except Exception as e:
            if DEBUG:
                print(f"DEBUG: Error converting teacher_id '{teacher_id_raw}' for subject {subj_id} group {group}: {e}")
            continue
        teacher_tuple = next((t for t in teachers if t[0] == teacher_id), None)
        if teacher_tuple is not None:
            teacher_mapping[(subj_id, group)] = teacher_tuple

    if DEBUG:
        print(f"DEBUG: Teacher mapping keys: {list(teacher_mapping.keys())}")

    # Precompute candidate timeslots for each teacher using the hour_blocker constraints.
    hour_blocker = get_hour_blocker()  # Expecting one row with 40 values.
    teacher_slots = {}
    for t in teachers:
        tid = t[0]
        slots = []
        for day in DAYS:
            for period in PERIODS:
                if get_teacher_availability(t, day, period) and get_hour_blocker_for(day, period, hour_blocker) == 1:
                    slots.append((day, period))
        teacher_slots[tid] = slots
        if DEBUG:
            print(f"DEBUG: Teacher {tid} has {len(slots)} candidate timeslots.")
    
    # Build session list.
    for subj in subjects:
        subj_id, subj_name, group_number, hours_per_week, max_per_day, max_student_count, _, _ = subj
        if group_number <= 0 or hours_per_week <= 0:
            continue

        # Compute how many students should be in each group.
        total_students = student_counts.get(subj_id, 0)
        group_student_count = math.ceil(total_students / group_number) if group_number > 0 else 0
        if group_student_count > max_student_count:
            print(f"WARNING: Subject {subj_id} '{subj_name}' has {group_student_count} students per group which exceeds its max of {max_student_count}.")

        for group in range(1, group_number + 1):
            teacher_tuple = teacher_mapping.get((subj_id, group))
            if teacher_tuple is None:
                if DEBUG:
                    print(f"DEBUG: No teacher found for subject {subj_id} group {group}")
                continue
            # Get available timeslots for the teacher.
            candidates = teacher_slots.get(teacher_tuple[0], [])
            # For each group, schedule one session per required hour.
            for i in range(hours_per_week):
                session = {
                    "subject_id": subj_id,
                    "subject_name": subj_name,
                    "group": group,
                    "session_type": "class",  # A separate class for this group
                    "max_per_day": max_per_day,  # subject-defined daily maximum (capped at 2 per group)
                    "teacher_id": teacher_tuple[0],
                    "teacher": teacher_tuple,
                    "session_id": f"{subj_id}_{group}_{i}",
                    "candidates": candidates,
                    "group_student_count": group_student_count
                }
                sessions.append(session)
    if DEBUG:
        print(f"DEBUG: Total sessions built: {len(sessions)}")
    # Sort sessions by the number of candidate timeslots (MRV heuristic)
    sessions.sort(key=lambda s: len(s.get("candidates", [])))
    return sessions

def timetable_solver():
    """
    Solve the timetable by assigning each session to a (day, period) timeslot while satisfying:
      - The session is assigned to one of its candidate timeslots.
      - A teacher is not double-booked.
      - For any given subject and group, no more than 2 sessions occur on the same day.
      - All sessions for each subject (for each group) are scheduled, ensuring that the subject's
        required hours per week are met.
    """
    sessions = build_sessions()
    schedule = {(day, period): [] for day in DAYS for period in PERIODS}  # (day, period) -> list of sessions
    assignment = {}  # session_id -> (day, period)
    teacher_schedule = {}  # teacher_id -> set of (day, period)
    subject_daily = {}  # (subject_id, group, day) -> count of sessions scheduled that day

    def backtrack(index):
        if index == len(sessions):
            return True
        session = sessions[index]
        subj_id = session["subject_id"]
        group = session["group"]
        teacher_id = session["teacher_id"]
        allowed_sessions = min(session["max_per_day"], 2)  # Limit: no more than 2 sessions per subject per group per day
        
        # Forward checking: filter candidate timeslots based on current assignment.
        filtered_candidates = []
        for candidate in session.get("candidates", []):
            day, period = candidate
            if (day, period) in teacher_schedule.get(teacher_id, set()):
                continue
            if subject_daily.get((subj_id, group, day), 0) >= allowed_sessions:
                continue
            filtered_candidates.append(candidate)
        
        if DEBUG:
            print(f"DEBUG: Session {session['session_id']} filtered candidates: {len(filtered_candidates)}")
        
        if not filtered_candidates:
            return False

        for candidate in filtered_candidates:
            day, period = candidate
            if DEBUG:
                print(f"DEBUG: Attempting session {session['session_id']} at {day} period {period}")
            assignment[session["session_id"]] = (day, period)
            schedule[(day, period)].append(session)
            teacher_schedule.setdefault(teacher_id, set()).add((day, period))
            subject_daily[(subj_id, group, day)] = subject_daily.get((subj_id, group, day), 0) + 1

            if backtrack(index + 1):
                return True

            if DEBUG:
                print(f"DEBUG: Backtracking session {session['session_id']} from {day} period {period}")
            del assignment[session["session_id"]]
            schedule[(day, period)].remove(session)
            teacher_schedule[teacher_id].remove((day, period))
            subject_daily[(subj_id, group, day)] -= 1

        return False

    if backtrack(0):
        return assignment, schedule
    else:
        return None, None

def main():
    """
    Main function to run the timetable solver.
    Prints the assignment for each session and the full schedule organized by day.
    """
    assignment, schedule = timetable_solver()
    if assignment is None:
        print("No valid timetable found.")
    else:
        print("Timetable assignment:")
        for session_id, timeslot in assignment.items():
            print(f"  Session {session_id} assigned to {timeslot}")
        print("\nFull Schedule by Day:")
        for day in DAYS:
            print(f"{day.capitalize()}:")
            for period in PERIODS:
                sessions_in_slot = schedule[(day, period)]
                if sessions_in_slot:
                    print(f"  Period {period}:")
                    for s in sessions_in_slot:
                        print(f"     {s['subject_name']} (Group {s['group']}, {s['session_type']}) with Teacher ID {s['teacher_id']}")
                else:
                    print(f"  Period {period}: Free")
            print()

if __name__ == "__main__":
    main()
