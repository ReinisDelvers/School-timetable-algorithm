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
        middle_name TINYTEXT NOT NULL,
        last_name TINYTEXT,
        monday BOOLEAN NOT NULL DEFAULT 1,
        tuesday BOOLEAN NOT NULL DEFAULT 1,
        wednesday BOOLEAN NOT NULL DEFAULT 1,
        thursday BOOLEAN NOT NULL DEFAULT 1
        monday1 INTEGER NOT NULL DEFAULT 0,
        tuesday1 INTEGER NOT NULL DEFAULT 0,
        wednesday1 INTEGER NOT NULL DEFAULT 0,
        thursday1 INTEGER NOT NULL DEFAULT 0,
        monday2 INTEGER NOT NULL DEFAULT 0,
        tuesday2 INTEGER NOT NULL DEFAULT 0,
        wednesday2 INTEGER NOT NULL DEFAULT 0,
        thursday2 INTEGER NOT NULL DEFAULT 0;
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
        max_hours_per_day INTEGER NOT NULL,
        max_student_count_per_group INTEGER NOT NULL,
        min_hours_per_day INTEGER NOT NULL,
        parallel_subject_groups INTEGER NOT NULL DEFAULT 0;
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
        middle_name TINYTEXT,
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
        FOREIGN KEY (teacher_id) REFERENCES teacher(id)
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
        json_subject_ids INTEGER NOT NULL,
        student_id INTEGER NOT NULL,

        FOREIGN KEY (student_id) REFERENCES student(id)
        )
        """
        # FOREIGN KEY (json_subject_ids) REFERENCES subject(id),
    )
    conn.commit()
# subject_student_table_creator()

def hour_blocker_table_creator():
    cur = conn.cursor()
    cur.execute(
        # "DROP TABLE hour_blocker"
        """
        CREATE TABLE hour_blocker (
        monday1 INTEGER NOT NULL DEFAULT 1,
        monday2 INTEGER NOT NULL DEFAULT 1,
        monday3 INTEGER NOT NULL DEFAULT 1,
        monday4 INTEGER NOT NULL DEFAULT 1,
        monday5 INTEGER NOT NULL DEFAULT 1,
        monday6 INTEGER NOT NULL DEFAULT 1,
        monday7 INTEGER NOT NULL DEFAULT 1,
        monday8 INTEGER NOT NULL DEFAULT 1,
        monday9 INTEGER NOT NULL DEFAULT 1,
        monday10 INTEGER NOT NULL DEFAULT 1,
        tuesday1 INTEGER NOT NULL DEFAULT 1,
        tuesday2 INTEGER NOT NULL DEFAULT 1,
        tuesday3 INTEGER NOT NULL DEFAULT 1,
        tuesday4 INTEGER NOT NULL DEFAULT 1,
        tuesday5 INTEGER NOT NULL DEFAULT 1,
        tuesday6 INTEGER NOT NULL DEFAULT 1,
        tuesday7 INTEGER NOT NULL DEFAULT 1,
        tuesday8 INTEGER NOT NULL DEFAULT 1,
        tuesday9 INTEGER NOT NULL DEFAULT 1,
        tuesday10 INTEGER NOT NULL DEFAULT 1,
        wednesday1 INTEGER NOT NULL DEFAULT 1,
        wednesday2 INTEGER NOT NULL DEFAULT 1,
        wednesday3 INTEGER NOT NULL DEFAULT 1,
        wednesday4 INTEGER NOT NULL DEFAULT 1,
        wednesday5 INTEGER NOT NULL DEFAULT 1,
        wednesday6 INTEGER NOT NULL DEFAULT 1,
        wednesday7 INTEGER NOT NULL DEFAULT 1,
        wednesday8 INTEGER NOT NULL DEFAULT 1,
        wednesday9 INTEGER NOT NULL DEFAULT 1,
        wednesday10 INTEGER NOT NULL DEFAULT 1,
        thursday1 INTEGER NOT NULL DEFAULT 1,
        thursday2 INTEGER NOT NULL DEFAULT 1,
        thursday3 INTEGER NOT NULL DEFAULT 1,
        thursday4 INTEGER NOT NULL DEFAULT 1,
        thursday5 INTEGER NOT NULL DEFAULT 1,
        thursday6 INTEGER NOT NULL DEFAULT 1,
        thursday7 INTEGER NOT NULL DEFAULT 1,
        thursday8 INTEGER NOT NULL DEFAULT 1,
        thursday9 INTEGER NOT NULL DEFAULT 1,
        thursday10 INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    conn.commit()
# hour_blocker_table_creator()

# teacher_table_creator()
# subject_table_creator()
# student_table_creator()
# subject_teacher_table_creator()
# subject_student_table_creator()
# hour_blocker_table_creator()


# ADD
def add_teacher(name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO teacher(name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2) VALUES("{name}", "{middle_name}", "{last_name}", "{monday}", "{tuesday}", "{wednesday}", "{thursday}", "{monday1}", "{tuesday1}", "{wednesday1}", "{thursday1}", "{monday2}", "{tuesday2}", "{wednesday2}", "{thursday2}")
        """
    )
    conn.commit()

def add_subject(name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO subject(name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups) VALUES("{name}", "{group_number}", "{number_of_hours_per_week}", "{max_hours_per_day}", "{max_student_count_per_group}", "{min_hours_per_day}", "{parallel_subject_groups}")
        """
    )
    conn.commit()

def add_student(name, middle_name, last_name):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO student(name, middle_name, last_name) VALUES("{name}", "{middle_name}", "{last_name}")
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

def add_subject_student(json_subject_ids, student_id):
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO subject_student(json_subject_ids, student_id) VALUES("{json_subject_ids}","{student_id}")
        """
    )
    conn.commit()


#GET
def get_teacher():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT id, name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2 FROM teacher
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
        SELECT id, name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups FROM subject
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
        SELECT id, name, middle_name, last_name FROM student
        ORDER BY last_name ASC
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_teacher():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT subject_teacher.id, subject.id AS subject_id, subject.name AS subject_name,
        teacher.id AS teacher_id, teacher.name AS teacher_name, teacher.middle_name AS teacher_middle_name, teacher.last_name AS teacher_last_name, subject_teacher.group_number
        FROM subject_teacher
        LEFT JOIN subject ON subject.id = subject_teacher.subject_id
        LEFT JOIN teacher ON teacher.id = subject_teacher.teacher_id
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data

def get_subject_student():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT subject_student.id, subject_student.json_subject_ids AS json_subject_ids, subject.name AS subject_name, student.id AS student_id, 
        student.name AS student_name, student.middle_name AS student_middle_name, student.last_name AS student_last_name
        FROM subject_student
        LEFT JOIN subject ON subject.id = subject_student.json_subject_ids
        LEFT JOIN student ON student.id = subject_student.student_id
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data


#REMOVE
def remove_teacher(id):
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
def update_teacher(id, name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE teacher
        SET name = "{name}", middle_name = "{middle_name}", last_name = "{last_name}", monday = "{monday}", tuesday = "{tuesday}", wednesday = "{wednesday}", thursday = "{thursday}", monday1 = "{monday1}", tuesday1 = "{tuesday1}", wednesday1 = "{wednesday1}", thursday1 = "{thursday1}", monday2 = "{monday2}", tuesday2 = "{tuesday2}", wednesday2 = "{wednesday2}", thursday2 = "{thursday2}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject(id, name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject
        SET name = "{name}", group_number = "{group_number}", number_of_hours_per_week = "{number_of_hours_per_week}", max_hours_per_day = "{max_hours_per_day}", max_student_count_per_group = "{max_student_count_per_group}", min_hours_per_day = "{min_hours_per_day}", parallel_subject_groups = "{parallel_subject_groups}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_student(id, name, middle_name, last_name):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE student
        SET name = "{name}", middle_name = "{middle_name}", last_name = "{last_name}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject_teacher(id, subject_id, teacher_id, group_number):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject_teacher
        SET subject_id = "{subject_id}", teacher_id = "{teacher_id}", group_number = "{group_number}"
        WHERE id = {id};
        """
    )
    conn.commit()

def update_subject_student(id, json_subject_ids, student_id):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE subject_student
        SET json_subject_ids = "{json_subject_ids}", student_id = "{student_id}"
        WHERE id = {id};
        """
    )
    conn.commit()

#HOUR BLOCKER
def hour_blocker_save(monday1, monday2, monday3, monday4, monday5, monday6, monday7, monday8, monday9, monday10, tuesday1, tuesday2, tuesday3, tuesday4, tuesday5, tuesday6, tuesday7, tuesday8, tuesday9, tuesday10, wednesday1, wednesday2, wednesday3, wednesday4, wednesday5, wednesday6, wednesday7, wednesday8, wednesday9, wednesday10, thursday1, thursday2, thursday3, thursday4, thursday5, thursday6, thursday7, thursday8, thursday9, thursday10):
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE hour_blocker
        SET monday1 = "{monday1}", monday2 = "{monday2}", monday3 = "{monday3}", monday4 = "{monday4}", monday5 = "{monday5}", 
            monday6 = "{monday6}", monday7 = "{monday7}", monday8 = "{monday8}", monday9 = "{monday9}", monday10 = "{monday10}", 
            tuesday1 = "{tuesday1}", tuesday2 = "{tuesday2}", tuesday3 = "{tuesday3}", tuesday4 = "{tuesday4}", tuesday5 = "{tuesday5}", 
            tuesday6 = "{tuesday6}", tuesday7 = "{tuesday7}", tuesday8 = "{tuesday8}", tuesday9 = "{tuesday9}", tuesday10 = "{tuesday10}", 
            wednesday1 = "{wednesday1}", wednesday2 = "{wednesday2}", wednesday3 = "{wednesday3}", wednesday4 = "{wednesday4}", wednesday5 = "{wednesday5}", 
            wednesday6 = "{wednesday6}", wednesday7 = "{wednesday7}", wednesday8 = "{wednesday8}", wednesday9 = "{wednesday9}", wednesday10 = "{wednesday10}", 
            thursday1 = "{thursday1}", thursday2 = "{thursday2}", thursday3 = "{thursday3}", thursday4 = "{thursday4}", thursday5 = "{thursday5}", 
            thursday6 = "{thursday6}", thursday7 = "{thursday7}", thursday8 = "{thursday8}", thursday9 = "{thursday9}", thursday10 = "{thursday10}"
        """
    )
    conn.commit()

def get_hour_blocker():
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT monday1, monday2, monday3, monday4, monday5, monday6, monday7, monday8, monday9, monday10,
               tuesday1, tuesday2, tuesday3, tuesday4, tuesday5, tuesday6, tuesday7, tuesday8, tuesday9, tuesday10,
               wednesday1, wednesday2, wednesday3, wednesday4, wednesday5, wednesday6, wednesday7, wednesday8,
               wednesday9, wednesday10, thursday1, thursday2, thursday3, thursday4, thursday5, thursday6,
               thursday7, thursday8, thursday9, thursday10
        FROM hour_blocker
        """
    )
    conn.commit()
    data = cur.fetchall()
    return data