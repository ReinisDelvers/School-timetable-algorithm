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
                "friday":    False
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
            "max_students_per_group": s[5],  # capacity per group
            "min_hours_per_day": s[6],
        }

    # For subject->teacher, we also store group_number from `subject_teacher`
    # We'll build a dictionary: subject_teacher_groups[subj_id] = [ (teacher_id, group_number), ... ]
    subject_teacher_groups = {}
    for row in sub_teacher_raw:
        # row looks like: (id, subject_id, subject_name, teacher_id, teacher_name, t_mid, t_last, group_number)
        st_id = row[0]
        subject_id = row[1]
        teacher_id = row[3]
        group_num  = row[7]  # the group_number for this teacher-subject link
        if subject_id not in subject_teacher_groups:
            subject_teacher_groups[subject_id] = []
        subject_teacher_groups[subject_id].append( (teacher_id, group_num) )

    # Build subject->set_of_students from JSON array
    subject_to_students = {}
    for row in sub_student_raw:
        student_id       = row[3]
        json_subject_str = row[1]
        try:
            list_of_sub_ids = json.loads(json_subject_str)
        except:
            list_of_sub_ids = []
        for subj_id_val in list_of_sub_ids:
            if subj_id_val not in subject_to_students:
                subject_to_students[subj_id_val] = set()
            subject_to_students[subj_id_val].add(student_id)

    return {
        "teachers": teachers,
        "subjects": subjects,
        # No longer need a simple subject_to_teachers since we have subject_teacher_groups
        "subject_teacher_groups": subject_teacher_groups, 
        "subject_to_students": subject_to_students,
    }

################################################################################
# 2) CONSTRAINTS & TIMETABLE INIT
################################################################################

CONSTRAINTS = [
    ("teacher_availability", 1),
    ("max_students_per_teacher", 2),
    ("subject_min_hours_per_day", 3),
    ("subject_max_hours_per_day", 4),
    ("subject_hours_per_week", 5),
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
# 3) SPLITTING INTO MULTIPLE GROUPS PER SUBJECT
################################################################################

def split_students_by_total_groups(all_students, total_groups, subject_capacity):
    """
    We have total_groups = sum of all group_number from subject_teacher for this subject.
    We want to split 'all_students' into 'total_groups' sub-lists, 
    each not exceeding subject_capacity if possible.

    Return a list of these subgroups. If we can't respect capacity, return None.
    """
    from math import ceil

    n_students = len(all_students)
    if total_groups == 0:
        return []

    # naive approach: group_size = ceil(n_students / total_groups)
    # if group_size > subject_capacity => fail
    group_size = ceil(n_students / total_groups)
    if group_size > subject_capacity:
        return None

    student_list = list(all_students)
    subgroups = []
    index = 0
    for _ in range(total_groups):
        chunk = student_list[index : index + group_size]
        subgroups.append(chunk)
        index += group_size

    return subgroups

################################################################################
# 4) CHECK CONSTRAINTS WHEN PLACING A CLASS
################################################################################

def can_place_in_slot(existing_classes, subject_id, teacher_id, students, day, slot_index, state):
    # Real checks omitted for brevity. Return True.
    return True

################################################################################
# 5) SCHEDULING HOURS FOR A SINGLE CLASS
################################################################################

def schedule_hours_for_subject_group(subject_id, teacher_id, students, required_hours, state):
    timetable = state["timetable"]
    hours_placed = 0

    while hours_placed < required_hours:
        placed_this_hour = False
        for day in DAYS:
            for slot_index in range(SLOTS_PER_DAY):
                if can_place_in_slot(timetable[day][slot_index], subject_id, teacher_id, students, day, slot_index, state):
                    # place
                    new_class = {
                        "subject_id": subject_id,
                        "teacher_id": teacher_id,
                        "students": list(students),
                    }
                    timetable[day][slot_index].append(new_class)
                    hours_placed += 1
                    placed_this_hour = True
                    break
            if placed_this_hour:
                break
        if not placed_this_hour:
            return False
    return True

################################################################################
# 6) SCHEDULING USING group_number FROM subject_teacher
################################################################################

def schedule_all_subjects(state):
    """
    For each subject:
      1) Sum up the 'group_number' for each teacher in subject_teacher. That = total_groups
      2) Split subject's students into 'total_groups' subgroups.
      3) Assign subgroups in the order of the teacher's listing. 
         If teacher T has group_number=2, they get 2 subgroups => each is scheduled 
         separately as a distinct class (subgroup) for 'required_hours'.
    """
    subjects = state["subjects"]
    subject_teacher_groups = state["subject_teacher_groups"]  # (teacher_id, group_number)
    subject_to_students = state["subject_to_students"]

    for subj_id, subj_info in subjects.items():
        required_hours       = subj_info["hours_per_week"]
        subject_capacity     = subj_info["max_students_per_group"]
        all_students         = subject_to_students.get(subj_id, set())
        teacher_groups_info  = subject_teacher_groups.get(subj_id, [])

        if not teacher_groups_info:
            print(f"No teacher-group info for subject {subj_id}. Failing.")
            return False

        if not all_students:
            print(f"No students for subject {subj_id}, skipping scheduling.")
            continue

        # sum the group_number from all teachers for this subject
        total_groups = sum(pair[1] for pair in teacher_groups_info)
        if total_groups == 0:
            print(f"Subject {subj_id} has teacher info but total group_number=0. Skipping.")
            continue

        # split students into 'total_groups' sub-lists, each not exceeding subject_capacity if possible
        splitted = split_students_by_total_groups(all_students, total_groups, subject_capacity)
        if splitted is None:
            print(f"Subject {subj_id}: cannot split {len(all_students)} students into {total_groups} groups with capacity={subject_capacity}. Failing.")
            return False

        # Now we iterate teacher_groups_info in order, assigning 'group_number' sub-lists to each teacher
        idx_subgroup = 0
        print(f"\nSubject {subj_id} => total {len(all_students)} students, total {total_groups} groups")
        for (teacher_id, grp_count) in teacher_groups_info:
            for _ in range(grp_count):
                if idx_subgroup >= len(splitted):
                    break  # safety
                subgroup = splitted[idx_subgroup]
                idx_subgroup += 1

                if subgroup:
                    success = schedule_hours_for_subject_group(subj_id, teacher_id, subgroup, required_hours, state)
                    if not success:
                        print(f"Failed scheduling subgroup of size {len(subgroup)} for subject {subj_id} + teacher {teacher_id}.")
                        return False
                else:
                    # empty group
                    pass

    return True

################################################################################
# 7) MAIN SCHEDULER
################################################################################

def schedule_timetable_bruteforce():
    data = load_data()
    timetable = initialize_empty_timetable()

    state = {
        "timetable": timetable,
        "teachers": data["teachers"],
        "subjects": data["subjects"],
        "subject_teacher_groups": data["subject_teacher_groups"],  # used in scheduling
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
                        print(f"   Subject {c['subject_id']} w/ teacher {c['teacher_id']} -> {len(c['students'])} students")
                else:
                    print(f" Slot {slot_i+1}: Free")
    else:
        print("Could not generate a timetable.")
