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
    
    # Debugging: Ensure data is fetched correctly
    print("Teachers:", teachers)
    print("Subjects:", subjects)
    print("Subject-Teacher Relationships:", subject_teachers)
    print("Students:", students)
    print("Subject-Student Relationships:", subject_students)
    
    return teachers, subjects, subject_teachers, students, subject_students

def assign_students_to_teachers(subject_teachers, subject_students):
    """Assign students to teachers based on subject connections."""
    # Map subjects to their teachers and students
    subject_teacher_map = defaultdict(list)
    subject_student_map = defaultdict(list)
    
    for st in subject_teachers:
        subject_teacher_map[st[0]].append({"teacher_id": st[1], "teacher_name": f"{st[3]} {st[4]}"})
    
    for ss in subject_students:
        subject_student_map[ss[0]].append({"student_id": ss[1], "student_name": f"{ss[3]} {ss[4]}"})
    
    # Debugging: Check mappings
    print("Subject-Teacher Map:", subject_teacher_map)
    print("Subject-Student Map:", subject_student_map)
    
    # Assign students to teachers with a maximum of 30 per teacher
    teacher_student_map = defaultdict(list)  # {teacher_id: [student_ids]}
    teacher_assignments = defaultdict(lambda: defaultdict(list))  # {teacher_id: {subject_name: [student_names]}}

    for subject_id, teachers in subject_teacher_map.items():
        students = subject_student_map.get(subject_id, [])
        
        for teacher in teachers:
            teacher_id = teacher["teacher_id"]
            teacher_name = teacher["teacher_name"]
            
            assigned_students = []
            for student in students:
                if len(teacher_student_map[teacher_id]) >= 30:
                    break
                
                teacher_student_map[teacher_id].append(student["student_id"])
                assigned_students.append(student["student_name"])
            
            # Record assignments per teacher and subject
            if assigned_students:
                teacher_assignments[teacher_id][teacher_name].append({
                    "subject_name": subject_teachers[0][2],  # First subject name for this ID
                    "students": assigned_students
                })
    
    # Debugging: Check teacher assignments
    print("Teacher Assignments:", teacher_assignments)
    
    return teacher_assignments
