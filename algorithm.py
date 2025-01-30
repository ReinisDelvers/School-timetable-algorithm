import copy
import json
from data import (
    get_teacher,
    get_subject,
    get_student,
    get_subject_teacher,
    get_subject_student,
)

################################################################################
# 1) DATA LOADING
################################################################################

def load_data():
    teachers_raw      = get_teacher()
    subjects_raw      = get_subject()
    students_raw      = get_student()
    sub_teacher_raw   = get_subject_teacher()
    sub_student_raw   = get_subject_student()

    # Build teacher dictionary
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
                "friday":    False  # if you want a fallback day
            },
        }

    # Build subject dictionary
    subjects = {}
    for s in subjects_raw:
        subj_id = s[0]
        subjects[subj_id] = {
            "id": subj_id,
            "name": s[1],
            "group_number": s[2],
            "hours_per_week": s[3],
            "max_hours_per_day": s[4],
            "max_students_per_group": s[5],  # capacity for each subject
            "min_hours_per_day": s[6],
        }

    # subject -> list of teachers
    subject_to_teachers = {}
    for st in sub_teacher_raw:
        subject_id = st[1]
        teacher_id = st[3]
        if subject_id not in subject_to_teachers:
            subject_to_teachers[subject_id] = []
        subject_to_teachers[subject_id].append(teacher_id)

    # Build subject->set_of_students from JSON array of IDs
    subject_to_students = {}
    for row in sub_student_raw:
        # row: (id, json_subject_ids, subject_name, student_id, ...)
        student_id       = row[3]
        json_subject_str = row[1]

        try:
            list_of_sub_ids = json.loads(json_subject_str)  # e.g. "[5,16,3]" -> [5,16,3]
        except:
            list_of_sub_ids = []

        for subj_id_val in list_of_sub_ids:
            if subj_id_val not in subject_to_students:
                subject_to_students[subj_id_val] = set()
            subject_to_students[subj_id_val].add(student_id)

    return {
        "teachers": teachers,
        "subjects": subjects,
        "subject_to_teachers": subject_to_teachers,
        "subject_to_students": subject_to_students,
    }

################################################################################
# 2) CONSTRAINTS & DAYS
################################################################################

CONSTRAINTS = [
    ("teacher_availability", 1),
    ("max_students_per_teacher", 2),      
    ("subject_min_hours_per_day", 3),
    ("subject_max_hours_per_day", 4),
    ("subject_hours_per_week", 5),
    # etc. 
]

ACTIVE_CONSTRAINTS = {c[0]: True for c in CONSTRAINTS}

def disable_lowest_priority_constraint():
    # same logic as before
    pass

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
SLOTS_PER_DAY = 10

def initialize_empty_timetable():
    timetable = {}
    for d in DAYS:
        timetable[d] = []
        for _ in range(SLOTS_PER_DAY):
            timetable[d].append([])
    return timetable

################################################################################
# 3) SPLITTING STUDENTS BASED ON SUBJECT CAPACITY
################################################################################

def split_students_among_teachers(all_students, teacher_ids, subject_capacity):
    """
    Distribute `all_students` as evenly as possible among
    len(teacher_ids) teacher-based groups, each with capacity = subject_capacity.

    If any group would exceed subject_capacity, we fail (return None).
    """
    from math import ceil

    n_teachers = len(teacher_ids)
    student_list = list(all_students)
    n_students = len(student_list)

    # "group_size" is how many students each teacher group can get at max
    # We'll do a naive approach: group_size = ceil(n_students / n_teachers)
    # If group_size > subject_capacity => we can't assign them properly
    group_size = ceil(n_students / n_teachers)
    if group_size > subject_capacity:
        return None

    groups = []
    for i in range(n_teachers):
        start = i * group_size
        end   = start + group_size
        subgroup = student_list[start:end]
        groups.append(subgroup)

    return groups

################################################################################
# 4) CHECK CONSTRAINTS WHEN PLACING A CLASS
################################################################################

def can_place_in_slot(existing_classes, subject_id, teacher_id, students, day, slot_index, state):
    """
    This is where you'd check 'teacher_availability', concurrency, 
    'subject_max_hours_per_day', etc.

    We skip the details here. Return True for brevity.
    """
    return True

################################################################################
# 5) SCHEDULING HOURS FOR A SINGLE TEACHER/SUBJECT GROUP
################################################################################

def schedule_hours_for_subject_group(subject_id, teacher_id, students, required_hours, state):
    """
    Attempt to schedule 'required_hours' blocks for a single group 
    (teacher + subset-of-students) for the given subject.
    """
    timetable = state["timetable"]
    hours_placed = 0

    while hours_placed < required_hours:
        placed_this_hour = False
        for day in DAYS:
            for slot_index in range(SLOTS_PER_DAY):
                existing_classes = timetable[day][slot_index]
                if can_place_in_slot(existing_classes, subject_id, teacher_id, students, day, slot_index, state):
                    new_class = {
                        "subject_id": subject_id,
                        "teacher_id": teacher_id,
                        "students": list(students),
                    }
                    existing_classes.append(new_class)
                    hours_placed += 1
                    placed_this_hour = True
                    break  # go to next hour
            if placed_this_hour:
                break
        if not placed_this_hour:
            return False
    return True

################################################################################
# 6) MAIN SCHEDULING LOOP (Using Subject Capacity)
################################################################################

def schedule_all_subjects(state):
    """
    For each subject:
      - Retrieve its 'max_students_per_group' from the subject dictionary
      - Retrieve all students & teachers
      - Split those students into teacher-based groups with that capacity
      - Schedule the subject's required hours once per group
    """
    subjects = state["subjects"]
    subject_to_teachers = state["subject_to_teachers"]
    subject_to_students = state["subject_to_students"]

    for subj_id, subj_info in subjects.items():
        required_hours = subj_info["hours_per_week"]
        subject_capacity  = subj_info["max_students_per_group"]  
        teacher_list   = subject_to_teachers.get(subj_id, [])
        all_students   = subject_to_students.get(subj_id, set())

        if not teacher_list:
            print(f"No teachers for subject {subj_id} - failing.")
            return False

        if not all_students:
            print(f"No students need subject {subj_id}, skipping scheduling.")
            continue

        # We'll try to split 'all_students' among teacher_list, 
        # using the subject's capacity as the max for each teacher group
        groups = split_students_among_teachers(all_students, teacher_list, subject_capacity)
        if groups is None:
            print(f"Cannot split {len(all_students)} students among {len(teacher_list)} teachers for subject {subj_id}. Exceeds capacity.")
            return False

        print(f"Scheduling subject {subj_id} with {len(all_students)} total students, {len(teacher_list)} teachers, capacity={subject_capacity}")
        
        # Now schedule the hours for each group
        for i, subgroup in enumerate(groups):
            t_id = teacher_list[i]
            if subgroup:
                success = schedule_hours_for_subject_group(subj_id, t_id, subgroup, required_hours, state)
                if not success:
                    print(f"Could not schedule subject {subj_id}, teacher {t_id}, subgroup size {len(subgroup)}.")
                    return False
            else:
                # This teacher gets no students, which is fine if leftover is small
                pass
    return True

################################################################################
# 7) MAIN BRUTE-FORCE SCHEDULER
################################################################################

def schedule_timetable_bruteforce():
    data = load_data()
    timetable = initialize_empty_timetable()

    state = {
        "timetable": timetable,
        "teachers": data["teachers"],
        "subjects": data["subjects"],
        "subject_to_teachers": data["subject_to_teachers"],
        "subject_to_students": data["subject_to_students"],
    }

    while True:
        success = schedule_all_subjects(state)
        if success:
            print("\nTimetable created successfully!")
            return state["timetable"]
        else:
            disabled = disable_lowest_priority_constraint()
            if not disabled:
                print("\nNo more constraints to disable. Scheduling failed.")
                return None

################################################################################
# 8) RUN / TEST
################################################################################

if __name__ == "__main__":
    final_timetable = schedule_timetable_bruteforce()
    if final_timetable:
        for day in DAYS:
            print(f"\n=== {day.upper()} ===")
            for slot_i, classes_in_slot in enumerate(final_timetable[day]):
                if classes_in_slot:
                    print(f" Slot {slot_i+1}:")
                    for c in classes_in_slot:
                        print(f"   Subject {c['subject_id']} with teacher {c['teacher_id']} -> {len(c['students'])} students")
                else:
                    print(f" Slot {slot_i+1}: Free")
    else:
        print("Could not generate a timetable.")
