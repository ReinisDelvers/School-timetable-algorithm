"""
algorithm.py
Revision 1.1: Updated teacher mapping conversion in build_sessions.

This module loads subjects, teachers, and timetable constraints from the database (via data.py).
It builds a list of sessions that need to be scheduled (each session represents one hour of a subject
for a particular group) and then assigns each session to a timeslot (day, period) using a backtracking
algorithm that enforces the following constraints:
  - The timeslot must be allowed by the hour blocker.
  - The teacher for the session must be available on that day and within their allowed start/end periods.
  - The teacher is not double-booked in the same timeslot.
  - The subject group does not exceed its maximum hours per day.

Future revisions may add additional constraints (for example, student conflicts or minimum hours per day).

Note: Revision 1.1 adds an explicit conversion of teacher_id from the subject_teacher records
to an integer (if possible) and skips any record that does not contain a valid teacher_id.
"""

import json
from data import get_subject, get_teacher, get_subject_teacher, get_hour_blocker

# Global definitions
DAYS = ["monday", "tuesday", "wednesday", "thursday"]
PERIODS = list(range(1, 11))  # Periods 1 to 10

# --- Helper Functions ---

def get_teacher_availability(teacher, day, period):
    """
    Check if a teacher is available on a given day and period.
    Uses the teacher tuple fields:
      - For Monday: teacher[4] (availability), teacher[8] (start), teacher[12] (end)
      - For Tuesday: teacher[5], teacher[9], teacher[13]
      - For Wednesday: teacher[6], teacher[10], teacher[14]
      - For Thursday: teacher[7], teacher[11], teacher[15]
      
    Constraint interpretation:
      - If the day flag is False, the teacher is not available.
      - If the "start" value is nonzero, the teacher cannot teach before that period.
      - If the "end" value is nonzero, the teacher cannot teach after that period.
    
    Revision 1.0: Initial implementation.
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
    Retrieve the hour blocker value for a given day and period.
    The hour_blocker table has 40 columns:
      - Monday periods: indices 0 to 9
      - Tuesday periods: indices 10 to 19
      - Wednesday periods: indices 20 to 29
      - Thursday periods: indices 30 to 39
    A value of 1 means the period is available.
    
    Revision 1.0: Initial implementation.
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

# --- Building Sessions ---

def build_sessions():
    """
    Build a list of session dictionaries to schedule.
    For each subject (from get_subject) and for each group (1 to group_number),
    create one session entry for each hour required per week (number_of_hours_per_week).
    
    Each session dictionary contains:
       - subject_id, subject_name, group (group number),
       - max_per_day (max hours per day for that subject),
       - teacher_id and teacher tuple (from subject_teacher mapping).
       - A unique session_id.
    
    Revision 1.1: Updated teacher mapping conversion.
    """
    sessions = []
    subjects = get_subject()  # subject tuple: (id, name, group_number, number_of_hours_per_week, max_hours_per_day, ..., min_hours_per_day, ...)
    print(f"DEBUG: Found {len(subjects)} subjects.")

    subject_teacher_list = get_subject_teacher()  
    teachers = get_teacher()

    # Build mapping: (subject_id, group_number) -> teacher tuple.
    # Revision 1.1: Explicitly convert teacher_id to int and skip records with missing teacher_id.
    teacher_mapping = {}
    for st in subject_teacher_list:
        subj_id = st[1]
        group = st[7]  # group number for the subject-teacher relation
        teacher_id_raw = st[3]
        if teacher_id_raw is None:
            print(f"DEBUG: Skipping subject_teacher record for subject {subj_id} group {group} because teacher_id is None")
            continue
        try:
            teacher_id = int(teacher_id_raw)
        except Exception as e:
            print(f"DEBUG: Error converting teacher_id '{teacher_id_raw}' for subject {subj_id} group {group}: {e}")
            continue
        teacher_tuple = None
        for t in teachers:
            if t[0] == teacher_id:
                teacher_tuple = t
                break
        if teacher_tuple is not None:
            teacher_mapping[(subj_id, group)] = teacher_tuple

    print(f"DEBUG: Teacher mapping keys: {list(teacher_mapping.keys())}")

    for subj in subjects:
        subj_id, subj_name, group_number, hours_per_week, max_per_day, _, min_per_day, _ = subj
        if group_number <= 0 or hours_per_week <= 0:
            continue
        for group in range(1, group_number + 1):
            teacher_tuple = teacher_mapping.get((subj_id, group))
            if teacher_tuple is None:
                print(f"DEBUG: No teacher found for subject {subj_id} group {group}")
                continue  # Skip if no teacher mapping found
            for i in range(hours_per_week):
                session = {
                    "subject_id": subj_id,
                    "subject_name": subj_name,
                    "group": group,
                    "max_per_day": max_per_day,
                    "min_per_day": min_per_day,  # not currently enforced
                    "teacher_id": teacher_tuple[0],
                    "teacher": teacher_tuple,
                    "session_id": f"{subj_id}_{group}_{i}"
                }
                sessions.append(session)
    print(f"DEBUG: Total sessions built: {len(sessions)}")
    return sessions

# --- Timetable Solver ---

def timetable_solver():
    """
    Solve the timetable by assigning each session to a timeslot (day, period)
    while satisfying the following constraints:
      - The hour blocker permits the period.
      - The teacher is available on that day and period.
      - The teacher is not double-booked.
      - The subject group does not exceed its max sessions per day.
    
    Uses a backtracking search over the list of sessions.
    
    Revision 1.0: Initial implementation.
    """
    sessions = build_sessions()
    timeslots = [(day, period) for day in DAYS for period in PERIODS]
    assignment = {}  # session_id -> (day, period)
    schedule = {(day, period): [] for day in DAYS for period in PERIODS}
    teacher_schedule = {}  # teacher_id -> list of (day, period)
    subject_daily = {}  # (subject_id, group, day) -> count of sessions

    hour_blocker = get_hour_blocker()  # Expected to return one row with 40 values

    def backtrack(index):
        if index == len(sessions):
            return True
        session = sessions[index]
        subj_id = session["subject_id"]
        group = session["group"]
        teacher = session["teacher"]
        teacher_id = session["teacher_id"]
        max_per_day = session["max_per_day"]

        for (day, period) in timeslots:
            if get_hour_blocker_for(day, period, hour_blocker) == 0:
                continue
            if not get_teacher_availability(teacher, day, period):
                continue
            if (day, period) in teacher_schedule.get(teacher_id, []):
                continue
            current_count = subject_daily.get((subj_id, group, day), 0)
            if current_count >= max_per_day:
                continue

            assignment[session["session_id"]] = (day, period)
            schedule[(day, period)].append(session)
            teacher_schedule.setdefault(teacher_id, []).append((day, period))
            subject_daily[(subj_id, group, day)] = current_count + 1

            if backtrack(index + 1):
                return True

            del assignment[session["session_id"]]
            schedule[(day, period)].remove(session)
            teacher_schedule[teacher_id].remove((day, period))
            subject_daily[(subj_id, group, day)] = current_count

        return False

    if backtrack(0):
        return assignment, schedule
    else:
        return None, None

# --- Main Function ---

def main():
    """
    Main function to run the timetable solver.
    Prints the assignment for each session as well as a timeslot-organized schedule.
    
    Revision 1.0: Initial implementation.
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
                        print(f"     {s['subject_name']} (Group {s['group']}) with Teacher ID {s['teacher_id']}")
                else:
                    print(f"  Period {period}: Free")
            print()

if __name__ == "__main__":
    main()
