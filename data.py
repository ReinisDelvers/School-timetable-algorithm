import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)


#CREATING
def teacher_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE teacher"
        """
        CREATE TABLE teacher(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TINYTEXT NOT NULL,
        last_name TINYTEXT NOT NULL,
        monday BOOLEAN NOT NULL DEFAULT 1,
        tuesday BOOLEAN NOT NULL DEFAULT 1,
        wednesday BOOLEAN NOT NULL DEFAULT 1,
        thursday BOOLEAN NOT NULL DEFAULT 1
        )
        """
    )
    conn.commit()
# teacher_table_creator()

def subject_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE subject"
        """
        CREATE TABLE subject(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TINYTEXT NOT NULL,
        group_number INTEGER NOT NULL,
        number_of_hours_per_week INTEGER NOT NULL,
        max_hours_per_day INTEGER NOT NULL
        )
        """
    )
    conn.commit()
# subject_table_creator()

def student_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE student"
        """
        CREATE TABLE student(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TINYTEXT NOT NULL,
        last_name TINYTEXT NOT NULL
        )
        """
    )
    conn.commit()
# student_table_creator()

def subject_teacher_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE subject_teacher"
        """
        CREATE TABLE subject_teacher(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        teacher_id INTEGER NOT NULL,
        group_number INTEGER NOT NULL,
        FOREIGN KEY (subject_id) REFERENCES subject(id),
        FOREIGN KEY (teacher_id) REFERENCES teacher(id),
        FOREIGN KEY (group_number) REFERENCES subject(group_number)
        )
        """
    )
    conn.commit()
# subject_teacher_table_creator()

def subject_student_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE subject_student"
        """
        CREATE TABLE subject_student(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        FOREIGN KEY (subject_id) REFERENCES subject(id),
        FOREIGN KEY (student_id) REFERENCES student(id)
        )
        """
    )
    conn.commit()
# subject_student_table_creator()

# teacher_table_creator()
# subject_table_creator()
# student_table_creator()
# subject_teacher_table_creator()
# subject_student_table_creator()


# ADDING
def add_teacher(name, last_name, monday, tuesday, wednesday, thursday):
    print(f"added teacher {name} {last_name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO teacher(name, last_name, monday, tuesday, wednesday, thursday) VALUES("{name}", "{last_name}", "{monday}", "{tuesday}", "{wednesday}", "{thursday}")
        """
    )
    conn.commit()

def add_subject(name, group_number, number_of_hours_per_week, max_hours_per_day):
    print(f"added subject {name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO subject(name, group_number, number_of_hours_per_week, max_hours_per_day) VALUES("{name}", "{group_number}", "{number_of_hours_per_week}", "{max_hours_per_day}")
        """
    )
    conn.commit()

def add_student(name, last_name):
    print(f"added student {name} {last_name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO student(name, last_name) VALUES("{name}", "{last_name}")
        """
    )
    conn.commit()

def add_subject_teacher(subject_id, teacher_id, group_number):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO subject_teacher(subject_id, teacher_id, group_number) VALUES("{subject_id}","{teacher_id}","{group_number}")
        """
    )
    conn.commit()

def add_subject_student(subject_id, student_id):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO subject_student(subject_id, student_id) VALUES("{subject_id}","{student_id}")
        """
    )
    conn.commit()


#READING
def get_teacher():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, last_name, monday, tuesday, wednesday, thursday FROM teacher
        ORDER BY last_name ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, group_number, number_of_hours_per_week, max_hours_per_day FROM subject
        ORDER BY name ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_student():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, last_name FROM student
        ORDER BY last_name ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_teacherid():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, subject_id, teacher_id, group_number FROM subject_teacher
        ORDER BY id ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_teacher():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT subject_teacher.id, subject.name, teacher.name, teacher.last_name, subject.group_number
        FROM
        (subject_teacher LEFT JOIN subject ON subject.id = subject_teacher.subject_id)
        LEFT JOIN teacher ON teacher.id = subject_teacher.teacher_id

        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_studentid():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, subject_id, student_id FROM subject_student
        ORDER BY id ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_student():
    cur = conn.cursor()
    cur.execute(
        """
        SELECT subject_student.id, subject.id AS subject_id, student.id AS student_id, 
               student.name AS student_name, student.last_name AS student_last_name
        FROM subject_student
        LEFT JOIN subject ON subject.id = subject_student.subject_id
        LEFT JOIN student ON student.id = subject_student.student_id
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data



#REMOVE
def remove_teacher(id):
    print(f"deleted teacher {id}")
    for i in range(len(id)):
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM teacher
            WHERE id = "{id[i]}"
            """
        )
        conn.commit()

def remove_subject(id):
    print(f"deleted subject {id}")
    for i in range(len(id)):
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM subject
            WHERE id = "{id[i]}"
            """
        )
        conn.commit()

def remove_student(id):
    print(f"deleted student {id}")
    for i in range(len(id)):
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM student
            WHERE id = "{id[i]}"
            """
        )
        conn.commit()

def remove_subject_teacher(id):
    print(f"deleted subject/teacher {id}")
    for i in range(len(id)):
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM subject_teacher
            WHERE id = "{id[i]}"
            """
        )
        conn.commit()

def remove_subject_student(id):
    print(f"deleted subject/student {id}")
    for i in range(len(id)):
        cur = conn.cursor()
        cur.execute(
            f"""
            DELETE FROM subject_student
            WHERE id = "{id[i]}"
            """
        )
        conn.commit()


#UPDATE
def update_teacher(id, name, last_name, monday, tuesday, wednesday, thursday):
    print(f"updated teacher {last_name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE teacher
        SET name = "{name}", last_name = "{last_name}", monday = "{monday}", tuesday = "{tuesday}", wednesday = "{wednesday}", thursday = "{thursday}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject(id, name, group_number, number_of_hours_per_week, max_hours_per_day):
    print(f"updated subject {name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject
        SET name = "{name}", group_number = "{group_number}", number_of_hours_per_week = "{number_of_hours_per_week}", max_hours_per_day = "{max_hours_per_day}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_student(id, name, last_name):
    print(f"updated student {last_name}")
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE student
        SET name = "{name}", last_name = "{last_name}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject_teacher(id, subject_id, teacher_id):
    print(f"updated subject/teacher")
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject_teacher
        SET subject_id = "{subject_id}", teacher_id = "{teacher_id}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject_student(id, subject_id, student_id):
    print(f"updated subject/student")
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject_student
        SET subject_id = "{subject_id}", student_id = "{student_id}"
        WHERE id = {id};
        """
    )
    conn.commit()