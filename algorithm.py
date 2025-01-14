import sqlite3
from collections import defaultdict
import itertools
from itertools import permutations, product


# Connect to the database
conn = sqlite3.connect("data.db", check_same_thread=False)

MAX_ATTEMPTS = 10  # Number of timetable generation attempts

# Define the maximum number of students a teacher can handle
MAX_STUDENTS_PER_TEACHER = 30  # Set this value as needed

def fetch_data():
    """Fetch required data from the database."""
    cur = conn.cursor()

    # Fetch teachers
    teachers = cur.execute("SELECT id, name, last_name, monday, tuesday, wednesday, thursday FROM teacher").fetchall()
    print(f"Fetched {len(teachers)} teachers.")

    # Fetch subjects
    subjects = cur.execute("SELECT id, name, group_number, number_of_hours_per_week, max_hours_per_day FROM subject").fetchall()
    print(f"Fetched {len(subjects)} subjects.")

    # Fetch subject-teacher relationships
    subject_teachers = cur.execute("""SELECT subject_teacher.subject_id, subject_teacher.teacher_id, subject.name, teacher.name, teacher.last_name
                                      FROM subject_teacher
                                      JOIN subject ON subject_teacher.subject_id = subject.id
                                      JOIN teacher ON subject_teacher.teacher_id = teacher.id""").fetchall()
    print(f"Fetched {len(subject_teachers)} subject-teacher relationships.")

    # Fetch students
    students = cur.execute("SELECT id, name, last_name FROM student").fetchall()
    print(f"Fetched {len(students)} students.")

    # Fetch subject-student relationships
    subject_students = cur.execute("""SELECT subject_student.subject_id, subject_student.student_id, subject.name, student.name, student.last_name
                                       FROM subject_student
                                       JOIN subject ON subject_student.subject_id = subject.id
                                       JOIN student ON subject_student.student_id = student.id""").fetchall()
    print(f"Fetched {len(subject_students)} subject-student relationships.")

    return teachers, subjects, subject_teachers, students, subject_students



def generate_teacher_combinations(teachers, subjects, time_slots):
    """Generate all possible combinations of teachers assigned to subjects at specific time slots."""
    teacher_combinations = []

    # Generate all permutations of teachers and subjects
    teacher_subject_permutations = list(permutations(teachers, len(subjects)))
    print(f"Generated {len(teacher_subject_permutations)} teacher-subject permutations.")

    # For each combination of teacher-subject assignments, generate possible time slot assignments
    for teacher_subject_assignment in teacher_subject_permutations:
        time_slot_combinations = product(time_slots, repeat=len(subjects))
        # Convert product to list to get the length, as product is lazy
        time_slot_combinations_list = list(time_slot_combinations)
        print(f"Generated {len(time_slot_combinations_list)} time slot combinations for this teacher-subject permutation.")

        for time_slot_assignment in time_slot_combinations_list:
            combination = list(zip(teacher_subject_assignment, subjects, time_slot_assignment))
            teacher_combinations.append(combination)

    print(f"Total teacher combinations: {len(teacher_combinations)}")
    return teacher_combinations



def generate_student_combinations(students, subjects):
    """Generate all possible combinations of students assigned to subjects."""
    student_combinations = list(product(students, repeat=len(subjects)))
    print(f"Generated {len(student_combinations)} student combinations.")
    return student_combinations


def generate_time_slot_combinations(time_slots, num_subjects):
    """Generate all possible combinations of time slots for a set number of subjects."""
    time_slot_combinations = list(product(time_slots, repeat=num_subjects))
    print(f"Generated {len(time_slot_combinations)} time slot combinations.")
    return time_slot_combinations




def assign_students_to_teachers(subject_teachers, subject_students):
    """Assign students to teachers based on subject connections."""
    subject_teacher_map = defaultdict(list)
    subject_student_map = defaultdict(list)

    for st in subject_teachers:
        subject_id = st[0]
        subject_name = st[2]
        teacher_id = st[1]
        teacher_name = f"{st[3]} {st[4]}"
        subject_teacher_map[subject_id].append({
            "teacher_id": teacher_id,
            "teacher_name": teacher_name,
            "subject_name": subject_name,
        })

    for ss in subject_students:
        subject_id = ss[0]
        subject_name = ss[2]
        student_id = ss[1]
        student_name = f"{ss[3]} {ss[4]}"
        subject_student_map[subject_id].append({
            "student_id": student_id,
            "student_name": student_name,
            "subject_name": subject_name,
        })

    teacher_assignments = defaultdict(lambda: defaultdict(list))
    teacher_student_map = defaultdict(list)  # {teacher_id: [student_ids]}

    unassigned_students = defaultdict(list)  # {subject_id: [student_ids]}

    for subject_id, teachers in subject_teacher_map.items():
        students = subject_student_map.get(subject_id, [])

        for teacher in teachers:
            teacher_id = teacher["teacher_id"]
            teacher_name = teacher["teacher_name"]
            subject_name = teacher["subject_name"]

            assigned_students = []
            for student in students:
                if len(teacher_student_map[teacher_id]) >= MAX_STUDENTS_PER_TEACHER:
                    unassigned_students[subject_id].append(student["student_name"])
                    continue  # Skip assigning this student if the teacher has reached max capacity

                teacher_student_map[teacher_id].append(student["student_id"])
                assigned_students.append(student["student_name"])

            if assigned_students:
                teacher_assignments[teacher_id][teacher_name].append({
                    "subject_name": subject_name,
                    "students": assigned_students,
                })

    return teacher_assignments, unassigned_students

def check_student_attendance(subject_students, student_schedule):
    """Check if all students can attend the subjects they have selected and report conflicts."""
    attendance_issues = []

    # Days of the week for better readability in the report
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    
    # Track the student's subject assignments by day and time
    student_subjects_by_time = defaultdict(lambda: defaultdict(list))

    # First, organize the students' scheduled subjects by day and time
    for ss in subject_students:
        student_id = ss[1]
        subject_name = ss[2]
        
        # Look up the student's schedule and assign subjects to specific time slots
        for day_idx in range(4):  # Check each day (0=Monday, ..., 3=Thursday)
            for time_slot in student_schedule.get(student_id, {}).get(day_idx, []):
                if subject_name in time_slot:  # If this subject is assigned in this time slot
                    student_subjects_by_time[student_id][day_idx].append((time_slot, subject_name))

    # Now, check for conflicts and missing assignments
    for ss in subject_students:
        student_id = ss[1]
        subject_name = ss[2]
        student_name = f"{ss[3]} {ss[4]}"

        found_slot = False
        conflicting_slots = []

        # Check each day and time for conflicts
        for day_idx in range(4):  # 0=Monday, ..., 3=Thursday
            day_conflicts = []

            for time_slot in student_schedule.get(student_id, {}).get(day_idx, []):
                # If the student is already scheduled for this subject and time, continue
                if subject_name in time_slot:
                    found_slot = True
                    break

                # Check if the student is already assigned a different subject at the same time
                for scheduled_time, scheduled_subject in student_subjects_by_time[student_id][day_idx]:
                    if scheduled_time == time_slot:
                        day_conflicts.append(scheduled_subject)
            
            # If there are conflicts (overlapping classes) or if the subject is missing for the student
            if day_conflicts:
                conflicting_slots.append((time_slot, day_idx, day_conflicts))

        # Report missing subject (no time slot found)
        if not found_slot:
            for day_idx in range(4):
                for time_slot in student_schedule.get(student_id, {}).get(day_idx, []):
                    attendance_issues.append(
                        f"Student {student_name} cannot attend {subject_name} on {days_of_week[day_idx]} at {time_slot} due to a scheduling issue."
                    )

        # Report conflicts
        for time_slot, day_idx, day_conflicts in conflicting_slots:
            conflict_details = ", ".join(day_conflicts)
            attendance_issues.append(
                f"Student {student_name} has a conflict on {days_of_week[day_idx]} at {time_slot}: "
                f"Scheduled subjects: {conflict_details}."
            )

    return attendance_issues





def generate_timetable():
    teachers, subjects, subject_teachers, students, subject_students = fetch_data()

    teacher_assignments, unassigned_students = assign_students_to_teachers(subject_teachers, subject_students)

    timetable = defaultdict(lambda: defaultdict(list))  # {day: {group: [(subject_name, teacher_name, student_list)]}}
    teacher_schedule = defaultdict(lambda: defaultdict(list))  # {teacher_id: {day: [(time_slot, subject_name, student_list)]}}
    student_schedule = defaultdict(lambda: defaultdict(list))  # {student_id: {day: [time_slot]}}

    max_classes_per_day = 8  # Allow students to attend up to 2 classes per day
    time_slots = [
        "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
        "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"
    ]

    teacher_availability = {
        t[0]: {
            "name": f"{t[1]} {t[2]}",
            "days": [t[3], t[4], t[5], t[6]],  # availability by day (0: Monday, ..., 3: Thursday)
        } for t in teachers
    }

    subject_info = {
        s[0]: {
            "name": s[1],
            "group_number": s[2],
            "hours_per_week": s[3],
            "max_hours_per_day": s[4],
        } for s in subjects
    }

    subject_teacher_map = defaultdict(list)
    for st in subject_teachers:
        subject_teacher_map[st[0]].append({"teacher_id": st[1], "subject_name": st[2], "teacher_name": f"{st[3]} {st[4]}"})

    student_conflicts = []
    teachers_with_no_students = []  # List to track teachers with no students

    for subject_id, teachers in subject_teacher_map.items():
        subject = subject_info[subject_id]
        group = subject["group_number"]
        hours_remaining = subject["hours_per_week"]

        for day_idx in range(4):  # 0: Monday, ..., 3: Thursday
            if hours_remaining <= 0:
                break

            day_classes = timetable[day_idx][group]

            if len(day_classes) >= max_classes_per_day:
                continue

            for teacher in teachers:
                teacher_id = teacher["teacher_id"]
                teacher_name = teacher["teacher_name"]
                subject_name = teacher["subject_name"]

                teacher_avail = teacher_availability[teacher_id]

                if not teacher_avail["days"][day_idx]:
                    continue

                if len(day_classes) > 0 and day_classes[-1][0] == subject_name:
                    continue

                students = []
                if teacher_id in teacher_assignments:
                    subject_data = teacher_assignments[teacher_id][teacher_name]
                    for data in subject_data:
                        if data["subject_name"] == subject_name:
                            students = data["students"]
                            break

                if not students:  # If no students are assigned to this teacher, mark the teacher
                    teachers_with_no_students.append(teacher_name)
                    continue

                time_slot = time_slots[len(day_classes)]  # Assign the next available time slot

                if any(time_slot in student_schedule[student_id][day_idx] for student_id in students):
                    continue

                day_classes.append((subject_name, teacher_name, students))
                teacher_schedule[teacher_id][day_idx].append((time_slot, subject_name, students))

                for student_id in students:
                    student_schedule[student_id][day_idx].append(time_slot)

                hours_remaining -= 1

                if hours_remaining <= 0 or len(day_classes) >= max_classes_per_day:
                    break

    # Check for student attendance issues
    attendance_issues = check_student_attendance(subject_students, student_schedule)

    return timetable, teacher_schedule, student_schedule, attendance_issues, teachers_with_no_students


def evaluate_timetable(student_schedule):
    """Evaluate a timetable for conflicts and log them."""
    conflicts = 0
    conflict_details = []

    for student_id, days in student_schedule.items():
        for day, slots in days.items():
            slot_counts = defaultdict(int)
            for slot in slots:
                slot_counts[slot] += 1
            for slot, count in slot_counts.items():
                if count > 1:  # More than one class at the same time
                    conflicts += count - 1
                    conflict_details.append(
                        f"Student {student_id} has {count} classes overlapping at {slot} on day {day}."
                    )

    return conflicts, conflict_details


def print_timetable(timetable, teacher_schedule, student_schedule, teachers_with_no_students):
    """Print the generated timetable for students and teachers."""
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday"]

    print("\n=== Timetable for Students ===")
    for day_idx, day in enumerate(days_of_week):
        print(f"\n{day}:")
        for group, classes in timetable[day_idx].items():
            print(f"  Group {group}:")
            for subject_name, teacher_name, students in classes:
                student_names = ', '.join(students)
                print(f"    {subject_name} by {teacher_name} - Students: {student_names}")

    print("\n=== Timetable for Teachers ===")
    for teacher_id, days in teacher_schedule.items():
        teacher_name = teacher_schedule[teacher_id]["name"]
        print(f"\n{teacher_name}:")
        for day_idx, classes in days.items():
            if isinstance(day_idx, int):  # Ensure day_idx is an integer
                print(f"  {days_of_week[day_idx]}:")
                for time_slot, subject_name, students in classes:
                    student_names = ', '.join(students)
                    print(f"    {time_slot}: {subject_name} - Students: {student_names}")
            else:
                print(f"Invalid day index: {day_idx}")  # Debug line to detect incorrect types

    # Print out teachers with no students assigned to them
    if teachers_with_no_students:
        print("\n=== Teachers with No Students Assigned ===")
        for teacher_name in teachers_with_no_students:
            print(f"  {teacher_name}")



def brute_force_timetable():
    """True brute-force for every combination of teacher and student assignments."""
    best_timetable = None
    best_teacher_schedule = None
    best_student_schedule = None
    min_conflicts = float("inf")
    teachers_with_no_students = []
    attempt_counter = 0  # Counter to track the number of attempts
    
    print("\nBrute-Force Timetable Generation Attempts:\n")

    # Fetch all required data
    teachers, subjects, subject_teachers, students, subject_students = fetch_data()

    # Limit data for debugging
    teachers = teachers[:3]
    subjects = subjects[:3]
    students = students[:5]
    
    # Define the time slots
    time_slots = [
        "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
        "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"
    ]
    time_slots = time_slots[:3]  # Limit to 3 time slots for debugging

    # Generate all combinations of teachers, students, and time slots
    all_teacher_combinations = generate_teacher_combinations(teachers, subjects, time_slots)
    all_student_combinations = generate_student_combinations(students, subjects)
    all_time_slot_combinations = generate_time_slot_combinations(time_slots, len(subjects))

    # Debug: Check if combinations are generated
    print(f"Generated {len(all_teacher_combinations)} teacher combinations.")
    print(f"Generated {len(all_student_combinations)} student combinations.")
    print(f"Generated {len(all_time_slot_combinations)} time slot combinations.")

    if len(all_teacher_combinations) == 0 or len(all_student_combinations) == 0 or len(all_time_slot_combinations) == 0:
        print("No combinations generated. Exiting brute force process.")
        return None, None, None, None

    # Iterate over all combinations with a limit on the number of attempts
    for teacher_comb in all_teacher_combinations:
        for student_comb in all_student_combinations:
            for time_comb in all_time_slot_combinations:
                if attempt_counter >= MAX_ATTEMPTS:
                    print(f"\nMax attempts ({MAX_ATTEMPTS}) reached. Stopping brute force.")
                    break
                
                attempt_counter += 1
                print(f"Attempt {attempt_counter}/{MAX_ATTEMPTS}")
                
                # Generate the timetable for the current combination
                timetable, teacher_schedule, student_schedule, attendance_issues, teachers_no_students = generate_timetable()

                # Evaluate the timetable for conflicts
                conflicts, conflict_details = evaluate_timetable(student_schedule)
                print(f"  Conflicts: {conflicts}")
                
                # Check if this timetable has fewer conflicts than the best one
                if conflicts < min_conflicts:
                    best_timetable = timetable
                    best_teacher_schedule = teacher_schedule
                    best_student_schedule = student_schedule
                    min_conflicts = conflicts
                
                # Log any attendance issues
                if attendance_issues:
                    for issue in attendance_issues:
                        print(f"  Attendance Issue: {issue}")
                
                teachers_with_no_students.extend(teachers_no_students)

            if attempt_counter >= MAX_ATTEMPTS:
                break  # Exit the loop if the max attempts are reached

        if attempt_counter >= MAX_ATTEMPTS:
            break  # Exit the loop if the max attempts are reached

    print("\nBest Timetable Selected:")
    print(f"Conflicts = {min_conflicts}")
    print_timetable(best_timetable, best_teacher_schedule, best_student_schedule, teachers_with_no_students)
    return best_timetable, best_teacher_schedule, best_student_schedule, teachers_with_no_students








# Generate and display the optimized timetable
best_timetable, best_teacher_schedule, best_student_schedule = brute_force_timetable()

