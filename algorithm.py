import sqlite3
from collections import defaultdict

# Connect to the database
conn = sqlite3.connect("data.db", check_same_thread=False)

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
    # Map subjects to their teachers and students
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
    
    # Assign students to teachers with a maximum of 30 per teacher
    teacher_student_map = defaultdict(list)  # {teacher_id: [student_ids]}
    teacher_assignments = defaultdict(lambda: defaultdict(list))  # {teacher_id: {teacher_name: [{"subject_name": ..., "students": ...}]}}

    for subject_id, teachers in subject_teacher_map.items():
        students = subject_student_map.get(subject_id, [])
        
        for teacher in teachers:
            teacher_id = teacher["teacher_id"]
            teacher_name = teacher["teacher_name"]
            subject_name = teacher["subject_name"]
            
            assigned_students = []
            for student in students:
                if len(teacher_student_map[teacher_id]) >= 30:
                    break
                
                teacher_student_map[teacher_id].append(student["student_id"])
                assigned_students.append(student["student_name"])
            
            # Record assignments per teacher and subject
            if assigned_students:
                teacher_assignments[teacher_id][teacher_name].append({
                    "subject_name": subject_name,
                    "students": assigned_students,
                })
    
    return teacher_assignments


def generate_timetable():
    teachers, subjects, subject_teachers, students, subject_students = fetch_data()
    
    teacher_assignments = assign_students_to_teachers(subject_teachers, subject_students)
    
    # Initialize timetable structure
    timetable = defaultdict(lambda: defaultdict(list))  # {day: {group: [(subject_name, teacher_name, student_list)]}}
    max_classes_per_day = 8  # Adjust as needed
    
    # Organize data
    teacher_availability = {
        t[0]: {
            "name": f"{t[1]} {t[2]}",
            "days": [t[3], t[4], t[5], t[6]],
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
    
    # Distribute classes
    for subject_id, teachers in subject_teacher_map.items():
        subject = subject_info[subject_id]
        group = subject["group_number"]
        hours_remaining = subject["hours_per_week"]
        
        for day_idx in range(4):  # 0: Monday, ..., 3: Thursday
            if hours_remaining <= 0:
                break
            
            day_classes = timetable[day_idx][group]
            
            # Ensure we don't exceed max classes per day
            if len(day_classes) >= max_classes_per_day:
                continue
            
            for teacher in teachers:
                teacher_id = teacher["teacher_id"]
                teacher_name = teacher["teacher_name"]
                subject_name = teacher["subject_name"]
                
                teacher_avail = teacher_availability[teacher_id]
                
                # Check teacher availability
                if not teacher_avail["days"][day_idx]:
                    continue
                
                # Check for consecutive repetition of the same subject
                if len(day_classes) > 0 and day_classes[-1][0] == subject_name:
                    continue
                
                # Fetch students assigned to this teacher and subject
                students = []
                if teacher_id in teacher_assignments:
                    subject_data = teacher_assignments[teacher_id][teacher_name]
                    for data in subject_data:
                        if data["subject_name"] == subject_name:
                            students = data["students"]
                            break
                
                # Assign class to timetable with student list
                day_classes.append((subject_name, teacher_name, students))
                hours_remaining -= 1
                
                # Break if no more hours left for the day or subject
                if hours_remaining <= 0 or len(day_classes) >= max_classes_per_day:
                    break
    
    return timetable


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

# Generate and display timetable
timetable = generate_timetable()
print_timetable(timetable)

