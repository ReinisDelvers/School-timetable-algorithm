import sqlite3
from collections import defaultdict
import random

# Connect to the database
conn = sqlite3.connect("data.db", check_same_thread=False)

MAX_ATTEMPTS = 10  # Number of timetable generation attempts

# Define the maximum number of students a teacher can handle
MAX_STUDENTS_PER_TEACHER = 20  # Set this value as needed


def fetch_data():
    """Fetch required data from the database."""
    cur = conn.cursor()

    # Fetch teachers
    teachers = cur.execute("SELECT id, name, last_name, monday, tuesday, wednesday, thursday FROM teacher").fetchall()

    # Fetch subjects
    subjects = cur.execute("SELECT id, name, group_number, number_of_hours_per_week, max_hours_per_day FROM subject").fetchall()

    # Fetch subject-teacher relationships
    subject_teachers = cur.execute("""
        SELECT subject_teacher.subject_id, subject_teacher.teacher_id, subject.name, teacher.name, teacher.last_name
        FROM subject_teacher
        JOIN subject ON subject_teacher.subject_id = subject.id
        JOIN teacher ON subject_teacher.teacher_id = teacher.id
    """).fetchall()

    # Fetch students
    students = cur.execute("SELECT id, name, last_name FROM student").fetchall()

    # Fetch subject-student relationships
    subject_students = cur.execute("""
        SELECT subject_student.subject_id, subject_student.student_id, subject.name, student.name, student.last_name
        FROM subject_student
        JOIN subject ON subject_student.subject_id = subject.id
        JOIN student ON subject_student.student_id = student.id
    """).fetchall()

    return teachers, subjects, subject_teachers, students, subject_students


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

                time_slot = time_slots[len(day_classes)]

                if any(time_slot in student_schedule[student_id][day_idx] for student_id in students):
                    continue

                day_classes.append((subject_name, teacher_name, students))
                teacher_schedule[teacher_id][day_idx].append((time_slot, subject_name, students))

                for student_id in students:
                    student_schedule[student_id][day_idx].append(time_slot)

                hours_remaining -= 1

                if hours_remaining <= 0 or len(day_classes) >= max_classes_per_day:
                    break

    student_conflicts = []
    for subject_id, students in unassigned_students.items():
        for student in students:
            student_conflicts.append(f"Student {student} could not be assigned due to teacher student limit.")

    resolve_conflicts(student_schedule, student_conflicts, timetable, teacher_schedule, time_slots, students)

    return timetable, teacher_schedule, student_schedule, student_conflicts




def resolve_conflicts(student_schedule, student_conflicts, timetable, teacher_schedule, time_slots, students):
    """Try to resolve conflicts by shifting students to different available time slots."""
    for conflict in student_conflicts:
        # Check if the conflict has the expected structure
        if "cannot attend" not in conflict or "on" not in conflict:
            print(f"Skipping invalid conflict format: {conflict}")
            continue  # Skip invalid conflict formats

        conflict_parts = conflict.split("cannot attend")
        student_part = conflict_parts[0].replace("Students", "").strip()
        subject_and_time_part = conflict_parts[1].split("on")
        
        if len(subject_and_time_part) < 2:
            print(f"Skipping invalid conflict format (missing 'on'): {conflict}")
            continue  # Skip conflicts that don't have the expected 'on' part
        
        subject_name = subject_and_time_part[0].strip()
        conflicting_time_slot = subject_and_time_part[1].split("due to")[0].strip()

        # Extract student names from the conflict
        student_names = [name.strip() for name in student_part.split("and")]

        # Find the student IDs corresponding to the student names
        student_ids = []
        for student_name in student_names:
            first_name, last_name = student_name.split()
            student_id = next((student[0] for student in students if f"{student[1]} {student[2]}" == student_name), None)
            if student_id:
                student_ids.append(student_id)

        # Attempt to resolve the conflict
        for student_id in student_ids:
            resolved = False
            for day_idx in range(4):  # Try all days: 0=Monday, ..., 3=Thursday
                for new_time_slot in time_slots:
                    if new_time_slot != conflicting_time_slot:
                        # Check if this new slot is free for the student on this day
                        if new_time_slot not in student_schedule[student_id][day_idx]:
                            # Try to reassign the student to this new time slot
                            student_schedule[student_id][day_idx].append(new_time_slot)
                            timetable[day_idx][student_id].append((subject_name, new_time_slot))
                            resolved = True
                            break
                if resolved:
                    break

            if not resolved:
                student_conflicts.append(f"Could not resolve conflict for Student {student_id} in {subject_name}.")





    
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



def optimize_timetable():
    """Generate multiple timetables and pick the best one."""
    best_timetable = None
    best_teacher_schedule = None
    best_student_schedule = None
    min_conflicts = float("inf")

    print("\nTimetable Generation Attempts:\n")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        timetable, teacher_schedule, student_schedule, student_conflicts = generate_timetable()
        conflicts, conflict_details = evaluate_timetable(student_schedule)

        print(f"Attempt {attempt}: Conflicts = {conflicts}")
        for detail in conflict_details:
            print(f"  {detail}")

        if conflicts < min_conflicts:
            best_timetable = timetable
            best_teacher_schedule = teacher_schedule
            best_student_schedule = student_schedule
            min_conflicts = conflicts

        # Print student conflicts
        if student_conflicts:
            for conflict in student_conflicts:
                print(f"  {conflict}")

    print("\nBest Timetable Selected:\n")
    print(f"Conflicts = {min_conflicts}")
    return best_timetable, best_teacher_schedule, best_student_schedule


def print_timetable(timetable):
    """Print the generated timetable."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    for day_idx, day in enumerate(days):
        print(f"\n{day}")
        for group, classes in timetable[day_idx].items():
            print(f"  Group {group}:")
            for subject_name, teacher_name, students in classes:
                print(f"    {subject_name} with {teacher_name}")
                print(f"      Students: {', '.join(students)}")


def print_teacher_schedule(teacher_schedule):
    """Print the schedule for each teacher."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    for teacher_id, schedule in teacher_schedule.items():
        print(f"\nSchedule for Teacher {teacher_id}:")
        for day_idx, classes in schedule.items():
            print(f"  {days[day_idx]}:")
            for time_slot, subject_name, students in classes:
                print(f"    {time_slot}: {subject_name}")
                print(f"      Students: {', '.join(students)}")


# Generate and display the optimized timetable
best_timetable, best_teacher_schedule, best_student_schedule = optimize_timetable()
print_timetable(best_timetable)
print_teacher_schedule(best_teacher_schedule)
