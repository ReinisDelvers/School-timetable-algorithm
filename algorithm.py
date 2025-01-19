import sqlite3
from itertools import permutations, product
from multiprocessing import cpu_count
from collections import defaultdict
import logging
from data import (
    get_teacher,
    get_subject,
    get_subject_teacher,
    get_subject_student,
)

# Configuration Parameters
CONFIG = {
    "max_students_per_teacher": 30,
    "max_classes_per_day": 8,
    "max_combinations": 1000000000,
    "time_slots": [
        "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
        "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"
    ],
    "cores": cpu_count(),
    "chunksize": 100,
    "max_classes_per_week_per_subject": 9,
    "max_classes_per_day_per_subject": 3,
}

# Logging setup
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')

# Database Connection
conn = sqlite3.connect("data.db", check_same_thread=False)

# Fetch data from the database
def fetch_data():
    try:
        logging.info("Fetching teachers...")
        teachers = get_teacher() or []
        logging.debug(f"Teachers: {teachers}")

        logging.info("Fetching subjects...")
        subjects = get_subject() or []
        logging.debug(f"Subjects: {subjects}")

        logging.info("Fetching subject-teacher mappings...")
        subject_teacher = get_subject_teacher() or []
        logging.debug(f"Subject-Teacher: {subject_teacher}")

        logging.info("Fetching subject-student mappings...")
        subject_student = get_subject_student() or []
        logging.debug(f"Subject-Student: {subject_student}")

        logging.info("Data fetching complete.")
        return teachers, subjects, subject_teacher, subject_student
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        raise

# Generate combinations with optimized filtering
def generate_combinations(teachers, subjects, students, time_slots, subject_teacher):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    subject_teacher_map = defaultdict(list)

    # Initialize combination_count
    combination_count = 0

    # Create a mapping of subjects to teachers
    for sub_id, teacher_id, teacher_name, teacher_last_name, _ in subject_teacher:
        subject_teacher_map[sub_id].append((teacher_id, teacher_name, teacher_last_name))

    # Generate combinations of subjects, teachers, students, and time slots
    for subject_id, teacher_list in subject_teacher_map.items():
        teacher_combinations = permutations(teacher_list, 1)
        student_combinations = product(students, repeat=1)
        time_combinations = product(days, time_slots)

        for teacher_comb in teacher_combinations:
            for student_comb in student_combinations:
                for day, time_comb in time_combinations:
                    if CONFIG["max_combinations"] != -1 and combination_count >= CONFIG["max_combinations"]:
                        return
                    yield (subject_id, teacher_comb, student_comb, day, time_comb)
                    combination_count += 1

    # Return the total number of combinations generated
    return combination_count

# Validate detailed student attendance
def validate_student_attendance_detailed(timetable, subject_student):
    student_subject_counts = defaultdict(lambda: defaultdict(int))
    subject_students = defaultdict(list)
    missing_subjects = defaultdict(list)

    for _, sub_id, stu_id, stu_name, stu_last in subject_student:
        subject_students[sub_id].append((stu_id, stu_name, stu_last))

    for day, times in timetable.items():
        for time, classes in times.items():
            for entry in classes:
                subject_id = entry["subject_id"]
                students = entry["students"]
                for student in students:
                    student_id = student[0]
                    student_subject_counts[student_id][subject_id] += 1

    for subject_id, students in subject_students.items():
        for student_id, student_name, student_last in students:
            if student_subject_counts[student_id][subject_id] < CONFIG["max_classes_per_week_per_subject"]:
                missing_subjects[(student_id, student_name, student_last)].append(subject_id)

    return missing_subjects

# Generate a timetable ensuring students attend each subject max_classes_per_week times
def generate_timetable(
    combination,
    subject_teacher,
    subject_student,
    teachers_without_students,
    student_weekly_limit,
    student_daily_limit,
    timetable,
    teacher_schedules,
    student_schedules,
    day_teacher_assignments,
    weekly_subject_teacher_assignments
):
    subject_id, teacher_comb, student_comb, day, time_comb = combination
    subject_students = defaultdict(list)

    for _, sub_id, stu_id, stu_name, stu_last in subject_student:
        subject_students[sub_id].append((stu_id, stu_name, stu_last))

    teacher_id, teacher_name, teacher_last_name = teacher_comb[0]
    students = subject_students.get(subject_id, [])

    if not students:
        teachers_without_students.add((teacher_id, teacher_name, teacher_last_name))
        return

    if teacher_id in day_teacher_assignments[day][time_comb]:
        return

    eligible_students = [
        student for student in students
        if student_weekly_limit[student[0]][subject_id] < CONFIG["max_classes_per_week_per_subject"] and
        student_daily_limit[day][student[0]][subject_id] < CONFIG["max_classes_per_day_per_subject"]
    ]

    if not eligible_students:
        teachers_without_students.add((teacher_id, teacher_name, teacher_last_name))
        return

    for student in eligible_students:
        student_id = student[0]
        student_weekly_limit[student_id][subject_id] += 1
        student_daily_limit[day][student_id][subject_id] += 1

    # Add to timetable
    if len(timetable[day][time_comb]) < CONFIG["max_students_per_teacher"]:
        timetable[day][time_comb].append({
            "subject_id": subject_id,
            "teacher": (teacher_id, teacher_name, teacher_last_name),
            "students": eligible_students,
        })
        day_teacher_assignments[day][time_comb].add(teacher_id)

    # Add to teacher and student schedules
    for student in eligible_students:
        student_id = student[0]
        student_name = f"{student[1]} {student[2]}"
        student_schedules[student_id].append((day, time_comb, subject_id, teacher_name))

    teacher_schedules[teacher_id].append((day, time_comb, subject_id, eligible_students))

# Print schedules for teachers and students

def print_schedules(teacher_schedules, student_schedules, subject_map, teacher_map, student_map):
    print("\n=== Teacher Schedules ===")
    for teacher_id, schedule in teacher_schedules.items():
        teacher_name = teacher_map.get(teacher_id, "Unknown Teacher")
        print(f"\n{teacher_name}'s Schedule:")
        for day, time, subject_id, students in sorted(schedule):
            subject_name = subject_map.get(subject_id, "Unknown Subject")
            student_names = ", ".join([f"{s[1]} {s[2]}" for s in students])
            print(f"  {day}, {time}: {subject_name} (Students: {student_names})")

    print("\n=== Student Schedules ===")
    for student_id, schedule in student_schedules.items():
        # Directly fetch the student name from student_map
        student_name = student_map.get(student_id, None)
        if not student_name:
            logging.warning(f"Student ID {student_id} is not found in student_map!")
            student_name = f"Unknown Student ({student_id})"  # Fallback to ID if no name found
        print(f"\n{student_name}'s Schedule:")
        for day, time, subject_id, teacher_name in sorted(schedule):
            subject_name = subject_map.get(subject_id, "Unknown Subject")
            print(f"  {day}, {time}: {subject_name} (Teacher: {teacher_name})")

# Main function
def brute_force_timetable():
    logging.info("Fetching data from the database...")
    teachers, subjects, subject_teacher, subject_student = fetch_data()
    time_slots = CONFIG["time_slots"][:CONFIG["max_classes_per_day"]]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday"]

    students = list({(stu_id, stu_name, stu_last) for _, _, stu_id, stu_name, stu_last in subject_student})
    subject_map = {subject[0]: subject[1] for subject in subjects}
    teacher_map = {teacher[0]: f"{teacher[1]} {teacher[2]}" for teacher in teachers}
    student_map = {student[0]: f"{student[1]} {student[2]}" for _, _, student in students}

    logging.debug(f"Student Map: {student_map}")  # Log the full student map

    logging.info("Starting brute-force timetable generation...")
    timetable = defaultdict(lambda: defaultdict(list))
    teachers_without_students = set()
    student_weekly_limit = defaultdict(lambda: defaultdict(int))
    student_daily_limit = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    teacher_schedules = defaultdict(list)
    student_schedules = defaultdict(list)
    day_teacher_assignments = defaultdict(lambda: defaultdict(set))
    weekly_subject_teacher_assignments = defaultdict(lambda: defaultdict(int))

    # Track the number of combinations
    total_combinations = 0
    for combination in generate_combinations(teachers, subjects, students, time_slots, subject_teacher):
        generate_timetable(
            combination,
            subject_teacher,
            subject_student,
            teachers_without_students,
            student_weekly_limit,
            student_daily_limit,
            timetable,
            teacher_schedules,
            student_schedules,
            day_teacher_assignments,
            weekly_subject_teacher_assignments
        )
        total_combinations += 1

    logging.info("Timetable generation complete.")
    missing_subjects = validate_student_attendance_detailed(timetable, subject_student)

    # Print the total number of attempts (combinations)
    print(f"Total combinations generated: {total_combinations}")

    return timetable, teacher_schedules, student_schedules, subject_map, teacher_map, student_map

# Print the best timetable
def print_timetable(timetable, teachers_without_students, subject_map):
    print("\n=== Best Timetable ===")
    for day, times in sorted(timetable.items()):
        print(f"\n{day}:")
        for time, classes in sorted(times.items()):
            print(f"  {time}:")
            for entry in classes:
                teacher = entry["teacher"]
                students = entry["students"]
                subject_id = entry["subject_id"]
                subject_name = subject_map.get(subject_id, "Unknown Subject")
                teacher_name = f"{teacher[1]} {teacher[2]}"
                student_names = ", ".join([f"{s[1]} {s[2]}" for s in students])
                print(f"    Subject: {subject_name}")
                print(f"    Teacher: {teacher_name}")
                print(f"      Students: {student_names}")

    print("\n=== Teachers Without Students ===")
    if teachers_without_students:
        for teacher_id, teacher_name, teacher_last_name in teachers_without_students:
            print(f"  Teacher: {teacher_name} {teacher_last_name}")
    else:
        print("  All teachers were assigned students!")
    print("======================\n")

# Run the timetable generator
if __name__ == "__main__":
    timetable, teacher_schedules, student_schedules, subject_map, teacher_map, student_map = brute_force_timetable()

    print_timetable(timetable, {}, subject_map)
    print_schedules(teacher_schedules, student_schedules, subject_map, teacher_map, student_map)

