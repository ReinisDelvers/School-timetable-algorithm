import tkinter as tk
from tkinter import ttk, END, messagebox
from tkinter.messagebox import showerror

import json
import pandas as pd
import threading
import logging

from data import (
    add_student, add_subject, add_teacher, add_subject_student, add_subject_teacher,
    get_student, get_subject, get_teacher, get_subject_teacher, get_subject_student,
    remove_student, remove_subject, remove_teacher, remove_subject_teacher,
    remove_subject_student, update_student, update_subject, update_teacher,
    update_subject_teacher, update_subject_student, hour_blocker_save, get_hour_blocker
)

options = {"padx": 5, "pady": 5}

class MainGUI:
    def __init__(self):
        self.window = tk.Tk()
      
        window_width = 1280
        window_height = 720

        # center window on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        center_x = int(screen_width/2 - window_width / 2)
        center_y = int(screen_height/2 - window_height / 2)
        self.window.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.window.title("School timetable algorithm")

        self.menubar = tk.Menu(self.window)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Close", command=exit)
        self.filemenu.add_separator()
        self.menubar.add_cascade(menu=self.filemenu, label="File")
        self.window.config(menu=self.menubar)

        self.frame = tk.Frame(self.window)
        for col in range(7):
            self.frame.columnconfigure(col, weight=1)

        self.btn1 = tk.Button(self.frame, text="Subject", font=("Arial", 18), command=self.subject)
        self.btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)

        self.btn2 = tk.Button(self.frame, text="Teacher", font=("Arial", 18), command=self.teacher)
        self.btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)

        self.btn3 = tk.Button(self.frame, text="Student", font=("Arial", 18), command=self.student)
        self.btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)

        self.btn4 = tk.Button(self.frame, text="Subject/Teacher", font=("Arial", 18), command=self.subject_teacher)
        self.btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        self.btn5 = tk.Button(self.frame, text="Subject/Student", font=("Arial", 18), command=self.subject_student)
        self.btn5.grid(row=0, column=4, sticky=tk.W+tk.E, **options)

        self.btn6 = tk.Button(self.frame, text="Hour blocker", font=("Arial", 18), command=self.hour_blocker)
        self.btn6.grid(row=0, column=5, sticky=tk.W+tk.E, **options)

        self.btn7 = tk.Button(self.frame, text="Algorithm", font=("Arial", 18), command=self.algorithm)
        self.btn7.grid(row=0, column=6, sticky=tk.W+tk.E, **options)

        self.frame.pack(fill="x")
        self.window.mainloop()

    # SUBJECT WINDOW
    def subject(self):
        wind = tk.Toplevel(self.window)
        wind.title("Subject")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        for col in range(7):
            frame.columnconfigure(col, weight=1)

        selected_subject_id = None

        def change_list():
            subject_list = get_subject()
            subject_listbox.delete(0, END)
            for item in subject_list:
                subject_listbox.insert(END, f"{item}")

        def subject_add():
            name = ent1.get().strip()
            group_number = ent2.get().strip()
            number_of_hours_per_week = ent3.get().strip()
            max_hours_per_day = ent4.get().strip()
            max_student_count_per_group = ent5.get().strip()
            min_hours_per_day = ent6.get().strip()
            parallel_subject_groups = ent7.get().strip()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
                int(parallel_subject_groups)
            except:
                showerror("Error", "Numeric fields must be integers.")
                return
            if all([name, group_number, number_of_hours_per_week, max_hours_per_day,
                    max_student_count_per_group, min_hours_per_day, parallel_subject_groups]):
                add_subject(name, group_number, number_of_hours_per_week,
                            max_hours_per_day, max_student_count_per_group,
                            min_hours_per_day, parallel_subject_groups)
                change_list()
            else:
                showerror("Error", "All fields must be filled out.")

        def subject_remove():
            selected = list(subject_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            subject_list = get_subject()
            ids = [subject_list[i][0] for i in selected]
            remove_subject(ids)
            change_list()

        def subject_edit():
            nonlocal selected_subject_id
            selected = list(subject_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            if len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            idx = selected[0]
            subject_list = get_subject()
            item = subject_list[idx]
            ent1.delete(0, END)
            ent2.delete(0, END)
            ent3.delete(0, END)
            ent4.delete(0, END)
            ent5.delete(0, END)
            ent6.delete(0, END)
            ent7.delete(0, END)

            ent1.insert(0, item[1])
            ent2.insert(0, item[2])
            ent3.insert(0, item[3])
            ent4.insert(0, item[4])
            ent5.insert(0, item[5])
            ent6.insert(0, item[6])
            ent7.insert(0, item[7])
            selected_subject_id = item[0]

        def subject_confirm_edit():
            nonlocal selected_subject_id
            name = ent1.get().strip()
            group_number = ent2.get().strip()
            number_of_hours_per_week = ent3.get().strip()
            max_hours_per_day = ent4.get().strip()
            max_student_count_per_group = ent5.get().strip()
            min_hours_per_day = ent6.get().strip()
            parallel_subject_groups = ent7.get().strip()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
                int(parallel_subject_groups)
            except:
                showerror("Error", "Numeric fields must be integers.")
                return
            if all([name, group_number, number_of_hours_per_week,
                    max_hours_per_day, max_student_count_per_group,
                    min_hours_per_day, parallel_subject_groups]):
                if selected_subject_id is not None:
                    update_subject(
                        selected_subject_id, name, group_number,
                        number_of_hours_per_week, max_hours_per_day,
                        max_student_count_per_group, min_hours_per_day,
                        parallel_subject_groups
                    )
                    selected_subject_id = None
                    change_list()
                else:
                    showerror("Error", "Select something to edit.")
            else:
                showerror("Error", "All fields must be filled out.")

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)
        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)
        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        labels = ["Name", "Group number", "Hours/week", "Max hrs/day",
                  "Max students/group", "Min hrs/day", "Parallel groups"]
        for i, text in enumerate(labels):
            lbl = tk.Label(frame, text=text, font=("Arial", 18))
            lbl.grid(row=1, column=i, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame, font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)
        ent2 = tk.Entry(frame, font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        ent3 = tk.Entry(frame, font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)
        ent4 = tk.Entry(frame, font=("Arial", 18))
        ent4.grid(row=2, column=3, sticky=tk.W+tk.E, **options)
        ent5 = tk.Entry(frame, font=("Arial", 18))
        ent5.grid(row=2, column=4, sticky=tk.W+tk.E, **options)
        ent6 = tk.Entry(frame, font=("Arial", 18))
        ent6.grid(row=2, column=5, sticky=tk.W+tk.E, **options)
        ent7 = tk.Entry(frame, font=("Arial", 18))
        ent7.grid(row=2, column=6, sticky=tk.W+tk.E, **options)
        ent7.insert(0, "0")

        frame.pack(fill="x")

        subject_listbox = tk.Listbox(
            wind, selectmode=tk.EXTENDED,
            font=("Arial", 18),
            height=20
        )
        subject_listbox.pack(fill=tk.BOTH, expand=True, **options)

        change_list()
        wind.mainloop()

    # TEACHER WINDOW
    def teacher(self):
        wind = tk.Toplevel(self.window)
        wind.title("Teacher")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        # configure 11 columns
        for col in range(11):
            frame.columnconfigure(col, weight=1)

        selected_teacher_id = None

        def change_list():
            teacher_list = get_teacher()
            teacher_listbox.delete(0, END)
            for item in teacher_list:
                teacher_listbox.insert(END, f"{item}")

        def teacher_add():
            name = ent1.get().strip()
            middle_name = ent2.get().strip()
            last_name = ent3.get().strip()
            monday = checkboxent1.get()
            tuesday = checkboxent2.get()
            wednesday = checkboxent3.get()
            thursday = checkboxent4.get()
            monday1 = ent4.get().strip()
            tuesday1 = ent6.get().strip()
            wednesday1 = ent8.get().strip()
            thursday1 = ent10.get().strip()
            monday2 = ent5.get().strip()
            tuesday2 = ent7.get().strip()
            wednesday2 = ent9.get().strip()
            thursday2 = ent11.get().strip()
            if all([name, last_name, monday1, tuesday1, wednesday1,
                    thursday1, monday2, tuesday2, wednesday2, thursday2]):
                add_teacher(
                    name, middle_name, last_name,
                    monday, tuesday, wednesday, thursday,
                    monday1, tuesday1, wednesday1, thursday1,
                    monday2, tuesday2, wednesday2, thursday2
                )
                change_list()
            else:
                showerror("Error", "All fields except middle name must be filled out.")

        def teacher_remove():
            selected = list(teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            t_list = get_teacher()
            ids = [t_list[i][0] for i in selected]
            remove_teacher(ids)
            change_list()

        def teacher_edit():
            nonlocal selected_teacher_id
            selected = list(teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            if len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            idx = selected[0]
            t_list = get_teacher()
            item = t_list[idx]
            ent1.delete(0, END)
            ent2.delete(0, END)
            ent3.delete(0, END)
            ent4.delete(0, END)
            ent5.delete(0, END)
            ent6.delete(0, END)
            ent7.delete(0, END)
            ent8.delete(0, END)
            ent9.delete(0, END)
            ent10.delete(0, END)
            ent11.delete(0, END)

            ent1.insert(0, item[1])
            ent2.insert(0, item[2])
            ent3.insert(0, item[3])
            checkboxent1.set(item[4])
            checkboxent2.set(item[5])
            checkboxent3.set(item[6])
            checkboxent4.set(item[7])
            ent4.insert(0, item[8])
            ent5.insert(0, item[10])
            ent6.insert(0, item[12])
            ent7.insert(0, item[14])
            ent8.insert(0, item[9])
            ent9.insert(0, item[11])
            ent10.insert(0, item[13])
            ent11.insert(0, item[15])
            selected_teacher_id = item[0]

        def teacher_confirm_edit():
            nonlocal selected_teacher_id
            name = ent1.get().strip()
            middle_name = ent2.get().strip()
            last_name = ent3.get().strip()
            monday = checkboxent1.get()
            tuesday = checkboxent2.get()
            wednesday = checkboxent3.get()
            thursday = checkboxent4.get()
            monday1 = ent4.get().strip()
            tuesday1 = ent6.get().strip()
            wednesday1 = ent8.get().strip()
            thursday1 = ent10.get().strip()
            monday2 = ent5.get().strip()
            tuesday2 = ent7.get().strip()
            wednesday2 = ent9.get().strip()
            thursday2 = ent11.get().strip()
            if all([name, last_name, monday1, tuesday1, wednesday1,
                    thursday1, monday2, tuesday2, wednesday2, thursday2]):
                if selected_teacher_id is not None:
                    update_teacher(
                        selected_teacher_id, name, middle_name, last_name,
                        monday, tuesday, wednesday, thursday,
                        monday1, tuesday1, wednesday1, thursday1,
                        monday2, tuesday2, wednesday2, thursday2
                    )
                    selected_teacher_id = None
                    change_list()
                else:
                    showerror("Error", "Select something to edit.")
            else:
                showerror("Error", "All fields except middle name must be filled out.")

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=teacher_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=teacher_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)
        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=teacher_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)
        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=teacher_confirm_edit)
        btn4.grid(row=0, column=3, columnspan=8, sticky=tk.W+tk.E, **options)

        labels = ["Name", "Middle name", "Last name",
                  "Mon ≤", "Mon ≥", "Tue ≤", "Tue ≥",
                  "Wed ≤", "Wed ≥", "Thu ≤", "Thu ≥"]
        col_positions = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        for pos, text in zip(col_positions, labels):
            lbl = tk.Label(frame, text=text, font=("Arial", 18))
            lbl.grid(row=1, column=pos, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame, font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)
        ent2 = tk.Entry(frame, font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        ent3 = tk.Entry(frame, font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        # Hour constraints
        ent4 = tk.Entry(frame, font=("Arial", 18))
        ent4.grid(row=2, column=3, sticky=tk.W+tk.E, **options)
        ent4.insert(0, "0")
        ent5 = tk.Entry(frame, font=("Arial", 18))
        ent5.grid(row=2, column=4, sticky=tk.W+tk.E, **options)
        ent5.insert(0, "0")
        ent6 = tk.Entry(frame, font=("Arial", 18))
        ent6.grid(row=2, column=5, sticky=tk.W+tk.E, **options)
        ent6.insert(0, "0")
        ent7 = tk.Entry(frame, font=("Arial", 18))
        ent7.grid(row=2, column=6, sticky=tk.W+tk.E, **options)
        ent7.insert(0, "0")
        ent8 = tk.Entry(frame, font=("Arial", 18))
        ent8.grid(row=2, column=7, sticky=tk.W+tk.E, **options)
        ent8.insert(0, "0")
        ent9 = tk.Entry(frame, font=("Arial", 18))
        ent9.grid(row=2, column=8, sticky=tk.W+tk.E, **options)
        ent9.insert(0, "0")
        ent10 = tk.Entry(frame, font=("Arial", 18))
        ent10.grid(row=2, column=9, sticky=tk.W+tk.E, **options)
        ent10.insert(0, "0")
        ent11 = tk.Entry(frame, font=("Arial", 18))
        ent11.grid(row=2, column=10, sticky=tk.W+tk.E, **options)
        ent11.insert(0, "0")

        checkboxent1 = tk.IntVar(value=1)
        box1 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent1, offvalue=0, onvalue=1)
        box1.grid(row=2, column=3, sticky=tk.W+tk.E)
        checkboxent2 = tk.IntVar(value=1)
        box2 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent2, offvalue=0, onvalue=1)
        box2.grid(row=2, column=5, sticky=tk.W+tk.E)
        checkboxent3 = tk.IntVar(value=1)
        box3 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent3, offvalue=0, onvalue=1)
        box3.grid(row=2, column=7, sticky=tk.W+tk.E)
        checkboxent4 = tk.IntVar(value=1)
        box4 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent4, offvalue=0, onvalue=1)
        box4.grid(row=2, column=9, sticky=tk.W+tk.E)

        frame.pack(fill="x")

        teacher_listbox = tk.Listbox(
            wind, selectmode=tk.EXTENDED,
            font=("Arial", 18),
            height=20
        )
        teacher_listbox.pack(fill=tk.BOTH, expand=True, **options)

        change_list()
        wind.mainloop()

    # STUDENT WINDOW
    def student(self):
        wind = tk.Toplevel(self.window)
        wind.title("Student")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        for col in range(5):
            frame.columnconfigure(col, weight=1)

        selected_student_id = None

        def change_list():
            student_list = get_student()
            student_listbox.delete(0, END)
            for item in student_list:
                student_listbox.insert(END, f"{item}")

        def student_add():
            name = ent1.get().strip()
            middle_name = ent2.get().strip()
            last_name = ent3.get().strip()
            if name and last_name:
                add_student(name, middle_name, last_name)
                change_list()
            else:
                showerror("Error", "Name and last name are required.")

        def student_remove():
            selected = list(student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            s_list = get_student()
            ids = [s_list[i][0] for i in selected]
            remove_student(ids)
            change_list()

        def student_edit():
            nonlocal selected_student_id
            selected = list(student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            if len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            idx = selected[0]
            s_list = get_student()
            item = s_list[idx]
            ent1.delete(0, END)
            ent2.delete(0, END)
            ent3.delete(0, END)

            ent1.insert(0, item[1])
            ent2.insert(0, item[2])
            ent3.insert(0, item[3])
            selected_student_id = item[0]

        def student_confirm_edit():
            nonlocal selected_student_id
            name = ent1.get().strip()
            middle_name = ent2.get().strip()
            last_name = ent3.get().strip()
            if name and last_name:
                if selected_student_id is not None:
                    update_student(selected_student_id, name, middle_name, last_name)
                    selected_student_id = None
                    change_list()
                else:
                    showerror("Error", "Select something to edit.")
            else:
                showerror("Error", "Name and last name are required.")

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=student_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=student_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)
        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=student_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)
        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=student_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Name", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)
        label2 = tk.Label(frame, text="Middle name", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)
        label3 = tk.Label(frame, text="Last name", font=("Arial", 18))
        label3.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame, font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)
        ent2 = tk.Entry(frame, font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        ent3 = tk.Entry(frame, font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        frame.pack(fill="x")

        student_listbox = tk.Listbox(
            wind, selectmode=tk.EXTENDED,
            font=("Arial", 18),
            height=20
        )
        student_listbox.pack(fill=tk.BOTH, expand=True, **options)

        change_list()
        wind.mainloop()

    # SUBJECT/TEACHER WINDOW
    def subject_teacher(self):
        wind = tk.Toplevel(self.window)
        wind.title("Subject/Teacher")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        selected_subject_teacher_id = None
        selected_subject_id = None
        selected_teacher_id = None

        def change_list():
            st_list = get_subject_teacher()
            subj_list = get_subject()
            teach_list = get_teacher()

            subject_teacher_listbox.delete(0, END)
            subject_listbox.delete(0, END)
            teacher_listbox.delete(0, END)

            for item in st_list:
                subject_teacher_listbox.insert(END, f"{item}")
            for item in subj_list:
                subject_listbox.insert(END, f"{item}")
            for item in teach_list:
                teacher_listbox.insert(END, f"{item}")

        def subject_teacher_add():
            nonlocal selected_subject_id, selected_teacher_id
            group_number = ent1.get().strip()
            st_list = get_subject_teacher()
            for rec in st_list:
                if (selected_subject_id == rec[1] and
                    selected_teacher_id == rec[3] and
                    rec[0] != selected_subject_teacher_id):
                    showerror("Error", "Duplicate subject-teacher pair.")
                    return
            try:
                int(group_number)
            except:
                showerror("Error", "Group number must be integer.")
                return
            if all([group_number, selected_subject_id, selected_teacher_id]):
                add_subject_teacher(selected_subject_id, selected_teacher_id, group_number)
                change_list()
            else:
                showerror("Error", "Select subject, teacher, and enter group number.")

        def subject_teacher_remove():
            selected = list(subject_teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            st_list = get_subject_teacher()
            ids = [st_list[i][0] for i in selected]
            remove_subject_teacher(ids)
            change_list()

        def subject_teacher_edit():
            nonlocal selected_subject_teacher_id, selected_subject_id, selected_teacher_id
            st_list = get_subject_teacher()
            subj_list = get_subject()
            teach_list = get_teacher()

            selected = list(subject_teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select one to edit.")
                return
            if len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            idx = selected[0]
            rec = st_list[idx]
            selected_subject_teacher_id = rec[0]
            selected_subject_id = rec[1]
            selected_teacher_id = rec[3]

            # show current subject & teacher as text
            for s in subj_list:
                if s[0] == rec[1]:
                    label3.config(text=f"{s}")
                    break
            for t in teach_list:
                if t[0] == rec[3]:
                    label4.config(text=f"{t}")
                    break
            ent1.delete(0, END)
            ent1.insert(0, rec[7])

        def subject_teacher_confirm_edit():
            nonlocal selected_subject_teacher_id, selected_subject_id, selected_teacher_id
            group_number = ent1.get().strip()
            st_list = get_subject_teacher()
            for rec in st_list:
                if (selected_subject_id == rec[1] and
                    selected_teacher_id == rec[3] and
                    rec[0] != selected_subject_teacher_id):
                    showerror("Error", "Duplicate subject-teacher pair.")
                    return
            try:
                int(group_number)
            except:
                showerror("Error", "Group number must be integer.")
                return
            if selected_subject_teacher_id is not None:
                update_subject_teacher(
                    selected_subject_teacher_id,
                    selected_subject_id,
                    selected_teacher_id,
                    group_number
                )
                selected_subject_teacher_id = None
                change_list()
            else:
                showerror("Error", "Select something to edit.")

        def subject_on_selection(_evt):
            nonlocal selected_subject_id
            subj_list = get_subject()
            sel = list(subject_listbox.curselection())
            if not sel:
                return
            idx = sel[0]
            selected_subject_id = subj_list[idx][0]
            label3.config(text=f"{subj_list[idx]}")

        def teacher_on_selection(_evt):
            nonlocal selected_teacher_id
            teach_list = get_teacher()
            sel = list(teacher_listbox.curselection())
            if not sel:
                return
            idx = sel[0]
            selected_teacher_id = teach_list[idx][0]
            label4.config(text=f"{teach_list[idx]}")

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_teacher_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_teacher_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)
        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_teacher_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)
        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_teacher_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Subject", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)
        label2 = tk.Label(frame, text="Teacher", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)
        label3 = tk.Label(frame, text="No subject selected", font=("Arial", 18))
        label3.grid(row=2, column=0, sticky=tk.W+tk.E, **options)
        label4 = tk.Label(frame, text="No teacher selected", font=("Arial", 18))
        label4.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        label5 = tk.Label(frame, text="Group number", font=("Arial", 18))
        label5.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        subject_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 18))
        subject_listbox.grid(row=3, column=0, sticky=tk.W+tk.E, **options)
        subject_listbox.bind("<<ListboxSelect>>", subject_on_selection)

        teacher_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 18))
        teacher_listbox.grid(row=3, column=1, sticky=tk.W+tk.E, **options)
        teacher_listbox.bind("<<ListboxSelect>>", teacher_on_selection)

        ent1 = tk.Entry(frame, font=("Arial", 18))
        ent1.grid(row=3, column=2, sticky=tk.W+tk.E, **options)

        frame.pack(fill="x")

        subject_teacher_listbox = tk.Listbox(
            wind, selectmode=tk.EXTENDED,
            font=("Arial", 18),
            height=20
        )
        subject_teacher_listbox.pack(fill=tk.BOTH, expand=True, **options)

        change_list()
        wind.mainloop()

    # SUBJECT/STUDENT WINDOW
    def subject_student(self):
        wind = tk.Toplevel(self.window)
        wind.title("Subject/Student")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        selected_subject_student_id = None
        selected_subject_ids = None
        selected_student_id = None
        subject_student_list = None

        def change_list():
            nonlocal subject_student_list
            subject_student_list = get_subject_student()
            subject_student_list = [list(item) for item in subject_student_list]
            subj_list = get_subject()
            stud_list = get_student()

            # transform JSON list of subject IDs to names
            for rec in subject_student_list:
                ids = json.loads(rec[1])
                names = []
                for sid in ids:
                    for s in subj_list:
                        if sid == s[0]:
                            names.append(s[1])
                            break
                rec[2] = names

            subject_student_listbox.delete(0, END)
            subject_listbox.delete(0, END)
            student_listbox.delete(0, END)

            for item in subject_student_list:
                subject_student_listbox.insert(END, f"{item}")
            for item in subj_list:
                subject_listbox.insert(END, f"{item}")
            for item in stud_list:
                student_listbox.insert(END, f"{item}")

        def subject_student_add():
            nonlocal selected_subject_ids, selected_student_id
            for rec in subject_student_list:
                if rec[3] == selected_student_id and rec[0] != selected_subject_student_id:
                    showerror("Error", "Student already has a record.")
                    return
            if selected_subject_ids and selected_student_id:
                add_subject_student(json.dumps(selected_subject_ids), selected_student_id)
                change_list()
            else:
                showerror("Error", "Select subject(s) and student.")

        def subject_student_remove():
            nonlocal subject_student_list
            selected = list(subject_student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            ids = [subject_student_list[i][0] for i in selected]
            remove_subject_student(ids)
            change_list()

        def subject_student_edit():
            nonlocal selected_subject_student_id, selected_subject_ids, selected_student_id
            student_list = get_student()
            subj_list = get_subject()
            selected = list(subject_student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            if len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            idx = selected[0]
            rec = subject_student_list[idx]
            selected_subject_student_id = rec[0]
            selected_subject_ids = json.loads(rec[1])
            selected_student_id = rec[3]
            label3.config(text=f"{rec[2]}")
            for i, s in enumerate(subj_list):
                if s[0] in selected_subject_ids:
                    subject_listbox.selection_set(i)
            for i, stu in enumerate(student_list):
                if stu[0] == selected_student_id:
                    label4.config(text=f"{stu}")
                    break

        def subject_student_confirm_edit():
            nonlocal selected_subject_student_id, selected_subject_ids, selected_student_id
            for rec in subject_student_list:
                if rec[3] == selected_student_id and rec[0] != selected_subject_student_id:
                    showerror("Error", "Student already has a record.")
                    return
            if selected_subject_student_id is not None:
                update_subject_student(
                    selected_subject_student_id,
                    selected_subject_ids,
                    selected_student_id
                )
                selected_subject_student_id = None
                change_list()
            else:
                showerror("Error", "Select something to edit.")

        def subject_on_selection(_evt):
            nonlocal selected_subject_ids
            subj_list = get_subject()
            sel = list(subject_listbox.curselection())
            if not sel:
                return
            ids = [subj_list[i][0] for i in sel]
            selected_subject_ids = ids
            names = [subj_list[i][1] for i in sel]
            label3.config(text=f"{names}")

        def student_on_selection(_evt):
            nonlocal selected_student_id
            stud_list = get_student()
            sel = list(student_listbox.curselection())
            if not sel:
                return
            idx = sel[0]
            selected_student_id = stud_list[idx][0]
            label4.config(text=f"{stud_list[idx]}")

        def add_from_excel():
            file_path = ent1.get().strip()
            try:
                file = pd.read_excel(file_path)
            except:
                showerror("Error", "Invalid Excel path.")
                return

            csv_file = "excel.csv"
            file.to_csv(csv_file, index=False)
            file = pd.read_csv(csv_file)
            columns = file.columns.tolist()
            rows = file.values.tolist()

            # build student name list from first column
            stu_names = [ " ".join(str(v).split()) for v in file[columns[0]] ]

            existing_students = list(get_student())
            stud_remade = []
            for rec in existing_students:
                if rec[2] == "":
                    name_concat = rec[1].replace(" ", "") + rec[3].replace(" ", "")
                else:
                    name_concat = rec[1].replace(" ", "") + rec[2].replace(" ", "") + rec[3].replace(" ", "")
                stud_remade.append((rec[0], name_concat))

            missing_students = []
            for nm in stu_names:
                if not any(nm == rec[1] for rec in stud_remade):
                    missing_students.append(nm)

            subj_list = list(get_subject())
            subj_remade = [(rec[0], rec[1]) for rec in subj_list]
            col_subj_names = columns[1:]
            missing_subjects = []
            for nm in col_subj_names:
                if not any(nm == rec[1] for rec in subj_remade):
                    missing_subjects.append(nm)

            if missing_students or missing_subjects:
                result = messagebox.askyesno(
                    "Missing", 
                    f"Add students {missing_students} and subjects {missing_subjects} with defaults?"
                )
                if result:
                    for nm in missing_students:
                        parts = nm.split()
                        if len(parts) == 2:
                            add_student(parts[0], "", parts[1])
                        elif len(parts) == 3:
                            add_student(parts[0], parts[1], parts[2])
                        else:
                            showerror("Error", f"Cannot add {nm}.")
                            return
                    for nm in missing_subjects:
                        add_subject(nm, 1, 6, 2, 30, 2, 0)
                else:
                    showerror("Error", "Excel import aborted.")
                    return

            # refresh student and subject lists
            existing_students = list(get_student())
            stud_remade = []
            for rec in existing_students:
                if rec[2] == "":
                    name_concat = rec[1].replace(" ", "") + rec[3].replace(" ", "")
                else:
                    name_concat = rec[1].replace(" ", "") + rec[2].replace(" ", "") + rec[3].replace(" ", "")
                stud_remade.append((rec[0], name_concat))

            subj_list = list(get_subject())
            subj_remade = [(rec[0], rec[1]) for rec in subj_list]
            col_stu_ids = []
            for nm in stu_names:
                for sid, name_concat in stud_remade:
                    if nm == name_concat:
                        col_stu_ids.append(sid)
                        break

            col_subj_ids = []
            for nm in col_subj_names:
                for sid, name_concat in subj_remade:
                    if nm == name_concat:
                        col_subj_ids.append(sid)
                        break

            existing_ss = list(get_subject_student())
            existing_ss_map = { rec[3]: rec[0] for rec in existing_ss }

            for row_idx, stu_id in enumerate(col_stu_ids):
                sel_subjs = []
                for col_idx in range(1, len(columns)):
                    if str(rows[row_idx][col_idx]) != "nan":
                        sel_subjs.append(col_subj_ids[col_idx-1])
                if stu_id in existing_ss_map:
                    update_subject_student(existing_ss_map[stu_id], sel_subjs, stu_id)
                else:
                    add_subject_student(sel_subjs, stu_id)

            change_list()

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_student_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_student_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)
        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_student_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)
        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_student_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)
        btn5 = tk.Button(frame, text="Add from excel", font=("Arial", 18), command=add_from_excel)
        btn5.grid(row=1, column=3, rowspan=2, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame, font=("Arial", 18))
        ent1.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Subject", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)
        label2 = tk.Label(frame, text="Student", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)
        label3 = tk.Label(frame, text="No subject selected", font=("Arial", 10))
        label3.grid(row=2, column=0, sticky=tk.W+tk.E, **options)
        label4 = tk.Label(frame, text="No student selected", font=("Arial", 18))
        label4.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        label5 = tk.Label(frame, text="Excel file path", font=("Arial", 18))
        label5.grid(row=1, column=2, sticky=tk.W+tk.E, **options)
        label6 = tk.Label(
            frame,
            text="First column: student names\nOther columns: subjects\nEmpty cell = not learning\nNo duplicates",
            font=("Arial", 18)
        )
        label6.grid(row=3, column=2, columnspan=2, sticky=tk.W+tk.E+tk.N, **options)

        subject_listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, font=("Arial", 18))
        subject_listbox.grid(row=3, column=0, sticky=tk.W+tk.E, **options)
        subject_listbox.bind("<<ListboxSelect>>", subject_on_selection)

        student_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 18))
        student_listbox.grid(row=3, column=1, sticky=tk.W+tk.E, **options)
        student_listbox.bind("<<ListboxSelect>>", student_on_selection)

        frame.pack(fill="x")

        subject_student_listbox = tk.Listbox(
            wind, selectmode=tk.EXTENDED,
            font=("Arial", 10),
            height=20
        )
        subject_student_listbox.pack(fill=tk.BOTH, expand=True, **options)

        change_list()
        wind.mainloop()

    # HOUR BLOCKER WINDOW
    def hour_blocker(self):
        wind = tk.Toplevel(self.window)
        wind.title("Hour blocker")
        wind.geometry("1280x800")
        wind.grab_set()

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)
        for col in range(11):
            frame.columnconfigure(col, weight=1)

        checkbox_vars = [tk.IntVar(value=1) for _ in range(40)]

        def change_list():
            hb = get_hour_blocker()[0]
            for i in range(40):
                checkbox_vars[i].set(hb[i])

        def hour_blocker_save1():
            vals = [var.get() for var in checkbox_vars]
            hour_blocker_save(*vals)

        btn1 = tk.Button(frame, text="Save", font=("Arial", 18), command=hour_blocker_save1)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        label1 = tk.Label(
            frame,
            text="Unchecked = hour excluded",
            font=("Arial", 18)
        )
        label1.grid(row=0, column=1, columnspan=10, sticky=tk.W+tk.E, **options)

        # Row labels for days
        days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
        for i, day in enumerate(days, start=2):
            lbl = tk.Label(frame, text=day, font=("Arial", 18))
            lbl.grid(row=i, column=0, sticky=tk.W+tk.E, **options)

        # Hour labels
        for hr in range(1, 11):
            lbl = tk.Label(frame, text=str(hr), font=("Arial", 18))
            lbl.grid(row=1, column=hr, sticky=tk.W+tk.E, **options)

        # Place checkboxes row by row
        idx = 0
        for r in range(2, 6):  # rows 2..5 (Monday..Thursday)
            for c in range(1, 11):  # columns 1..10 (hours)
                box = tk.Checkbutton(
                    frame, font=("Arial", 18),
                    variable=checkbox_vars[idx], offvalue=0, onvalue=1
                )
                box.grid(row=r, column=c, sticky=tk.W+tk.E)
                idx += 1

        frame.pack(fill="x")
        change_list()
        wind.mainloop()

    # ALGORITHM WINDOW
    def algorithm(self):
        wind = tk.Toplevel(self.window)
        wind.title("Algorithm")
        wind.state('zoomed')
        wind.grab_set()

        def on_window_restore(_):
            if wind.state() == 'normal':
                wind.grab_set()

        wind.bind('<Map>', on_window_restore)
        wind.protocol("WM_DELETE_WINDOW", wind.destroy)

        main_container = tk.PanedWindow(wind, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left: timetable
        left_frame = tk.Frame(main_container)
        main_container.add(left_frame)

        # Right: controls
        right_frame = tk.Frame(main_container, width=250)
        main_container.add(right_frame)
        right_frame.pack_propagate(False)

        main_container.paneconfig(left_frame, minsize=900)
        main_container.paneconfig(right_frame, minsize=250, width=250)

        # Control panel
        control_panel = tk.LabelFrame(right_frame, text="Controls", font=("Arial", 12, "bold"))
        control_panel.pack(fill=tk.X, padx=5, pady=5)

        btn_frame = tk.Frame(control_panel)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        start_btn = tk.Button(btn_frame, text="Start Algorithm", font=("Arial", 12))
        start_btn.pack(fill=tk.X, padx=5, pady=2)
        view_btn = tk.Button(btn_frame, text="View Saved Schedule", font=("Arial", 12))
        view_btn.pack(fill=tk.X, padx=5, pady=2)

        # ===== Filter controls =====
        filter_frame = tk.LabelFrame(right_frame, text="Filters", font=("Arial", 12, "bold"))
        filter_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        filter_var = tk.StringVar(value="all")
        tk.Radiobutton(filter_frame, text="Show All", variable=filter_var,
                       value="all", font=("Arial", 10)).pack(anchor=tk.W)
        tk.Radiobutton(filter_frame, text="Show Selected Subject", variable=filter_var,
                       value="subject", font=("Arial", 10)).pack(anchor=tk.W)
        tk.Radiobutton(filter_frame, text="Show Selected Teacher", variable=filter_var,
                       value="teacher", font=("Arial", 10)).pack(anchor=tk.W)
        tk.Radiobutton(filter_frame, text="Show Selected Student", variable=filter_var,
                       value="student", font=("Arial", 10)).pack(anchor=tk.W)

        # Single listbox (no tabs/labels)
        filter_listbox = tk.Listbox(filter_frame, selectmode=tk.SINGLE, font=("Arial", 10), height=8)
        filter_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # We'll store the three sets of names here
        self.filter_subjects = []
        self.filter_teachers = []
        self.filter_students = []

        def repopulate_listbox():
            """Populate filter_listbox based on filter_var."""
            filter_listbox.delete(0, END)
            mode = filter_var.get()
            if mode == "subject":
                for name in sorted(self.filter_subjects):
                    filter_listbox.insert(END, name)
            elif mode == "teacher":
                for name in sorted(self.filter_teachers):
                    filter_listbox.insert(END, name)
            elif mode == "student":
                for name in sorted(self.filter_students):
                    filter_listbox.insert(END, name)
            else:  # "all" → show subjects by default
                for name in sorted(self.filter_subjects):
                    filter_listbox.insert(END, name)

        # Whenever filter_var changes, repopulate
        filter_var.trace('w', lambda *_: repopulate_listbox())

        # Validation panel
        validation_frame = tk.LabelFrame(right_frame, text="Validation Results", font=("Arial", 12, "bold"))
        validation_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        validation_text = tk.Text(validation_frame, font=("Courier", 10), height=8)
        validation_scroll = tk.Scrollbar(validation_frame, command=validation_text.yview)
        validation_text.configure(yscrollcommand=validation_scroll.set)
        validation_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        validation_text.pack(fill=tk.BOTH, expand=True)

        # Timetable canvas
        canvas_frame = tk.Frame(left_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        main_canvas = tk.Canvas(canvas_frame)
        main_scrollbar_y = tk.Scrollbar(canvas_frame, orient="vertical", command=main_canvas.yview)
        main_scrollbar_x = tk.Scrollbar(canvas_frame, orient="horizontal", command=main_canvas.xview)

        timetable_frame = tk.Frame(main_canvas)

        def on_mouse_wheel(event):
            if event.state == 0:
                main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.state & 1:
                main_canvas.xview_scroll(int(-1*(event.delta/120)), "units")

        main_canvas.bind_all("<MouseWheel>", on_mouse_wheel)

        def on_configure(_):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))

        timetable_frame.bind('<Configure>', on_configure)
        main_canvas.create_window((0, 0), window=timetable_frame, anchor='nw')

        main_canvas.configure(yscrollcommand=main_scrollbar_y.set,
                              xscrollcommand=main_scrollbar_x.set)

        main_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        main_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def create_session_card(parent, session, scale=1.0):
            frame = tk.Frame(parent, relief="raised", bd=1, bg='#f5f5f5')

            header = tk.Label(frame, text=f"{session['subject_name']} (G{session.get('group', 1)})",
                              font=("Arial", int(11*scale), "bold"), bg='#e0e0e0')
            header.pack(fill=tk.X, padx=2, pady=1)

            if session.get('teachers'):
                teacher_lbl = tk.Label(frame, text=session['teachers'][0].get('name', ''),
                                       font=("Arial", int(10*scale)), bg='#f5f5f5')
                teacher_lbl.pack(fill=tk.X, padx=2)

            students = session.get('students', [])
            if students:
                count_frame = tk.Frame(frame, bg='#f5f5f5')
                count_frame.pack(fill=tk.X, padx=2)
                tk.Label(count_frame, text=f"Students: {len(students)}",
                         font=("Arial", int(9*scale)), bg='#f5f5f5').pack(side=tk.LEFT)

                def show_students():
                    dialog = tk.Toplevel(wind)
                    dialog.title(f"Students - {session['subject_name']}")
                    dialog.geometry("300x400")
                    list_box = tk.Listbox(dialog, font=("Arial", 10))
                    list_box.pack(fill=tk.BOTH, expand=True)
                    for s in students:
                        list_box.insert(END, s['name'])

                tk.Button(count_frame, text="Show List",
                          font=("Arial", int(8*scale)), command=show_students).pack(side=tk.RIGHT)

            return frame

        def update_timetable_display(schedule_data=None, filter_type=None, filter_value=None):
            for widget in timetable_frame.winfo_children():
                widget.destroy()

            days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
            hours = range(1, 11)

            tk.Label(timetable_frame, text="Hour", font=("Arial", 12, "bold"),
                     width=8).grid(row=0, column=0, sticky='nsew')
            for i, day in enumerate(days):
                tk.Label(timetable_frame, text=day, font=("Arial", 12, "bold"),
                         width=35).grid(row=0, column=i+1, sticky='nsew')

            for hr in hours:
                tk.Label(timetable_frame, text=str(hr),
                         font=("Arial", 12)).grid(row=hr, column=0)
                for d in range(4):
                    cell = tk.Frame(timetable_frame, relief="solid", bd=1)
                    cell.grid(row=hr, column=d+1, padx=2, pady=2, sticky='nsew')
                    cell.configure(width=300, height=150)
                    cell.grid_propagate(False)

                    if schedule_data and str(d) in schedule_data.get('days', {}):
                        sessions = schedule_data['days'][str(d)].get(str(hr-1), [])
                        for session in sessions:
                            show_session = True
                            if filter_type == "subject":
                                show_session = (session['subject_name'] == filter_value)
                            elif filter_type == "teacher":
                                show_session = any(t['name'] == filter_value for t in session['teachers'])
                            elif filter_type == "student":
                                show_session = any(s['name'] == filter_value for s in session['students'])
                            if show_session:
                                card = create_session_card(cell, session)
                                card.pack(fill=tk.X, padx=2, pady=1)

        algorithm_thread = None
        is_running = False

        def toggle_algorithm():
            nonlocal algorithm_thread, is_running
            if not is_running:
                is_running = True
                self.stop_requested = False
                start_btn.config(text="Stop Algorithm")
                update_timetable_display()

                def run_algorithm():
                    try:
                        from algorithm import (
                            load_data, build_sessions, solve_timetable,
                            format_schedule_output, validate_final_schedule, logger
                        )

                        logger.info("Loading data...")
                        teachers, subjects, students_raw, st_map, stud_map, hb, student_groups = load_data()
                        if not teachers or not subjects or not students_raw:
                            raise ValueError("Missing required data")

                        logger.info("Building sessions...")
                        sessions = build_sessions(teachers, subjects, st_map, stud_map, hb)
                        if not sessions:
                            raise ValueError("Failed to create valid sessions")

                        logger.info("Starting solver...")
                        schedule, students_dict = solve_timetable(
                            sessions, subjects, teachers, hb,
                            time_limit=1200, stop_flag=lambda: self.stop_requested
                        )

                        if schedule and not self.stop_requested:
                            logger.info("Schedule found, validating...")
                            formatted_schedule = format_schedule_output(schedule, subjects, teachers, students_dict)
                            validation_stats = validate_final_schedule(schedule, sessions, subjects, teachers)

                            with open('schedule_output.json', 'w') as f:
                                json.dump(formatted_schedule, f, indent=2)

                            # Build the three sets for filters
                            subjects_set = set()
                            teachers_set = set()
                            students_set = set()
                            for day_data in formatted_schedule.get('days', {}).values():
                                for period in day_data.values():
                                    for session in period:
                                        subjects_set.add(session['subject_name'])
                                        for t in session['teachers']:
                                            teachers_set.add(t['name'])
                                        for s in session['students']:
                                            students_set.add(s['name'])

                            self.filter_subjects = list(subjects_set)
                            self.filter_teachers = list(teachers_set)
                            self.filter_students = list(students_set)

                            # Populate the listbox for current filter_var
                            wind.after(0, repopulate_listbox)
                            wind.after(0, lambda: update_timetable_display(formatted_schedule))
                            wind.after(0, lambda: display_validation_results(validation_stats))
                            wind.after(0, lambda: messagebox.showinfo(
                                "Success",
                                f"Schedule generated with {formatted_schedule['metadata']['total_sessions']} sessions"
                            ))
                        elif self.stop_requested:
                            logger.info("Algorithm stopped by user")
                        else:
                            raise ValueError("Could not find valid schedule")

                    except Exception as e:
                        if not self.stop_requested:
                            wind.after(0, lambda: messagebox.showerror("Error", str(e)))
                            logger.exception("Algorithm error")
                    finally:
                        wind.after(0, stop_algorithm)

                algorithm_thread = threading.Thread(target=run_algorithm)
                algorithm_thread.daemon = True
                algorithm_thread.start()
            else:
                self.stop_requested = True
                logger.info("Stopping algorithm...")
                start_btn.config(text="Stopping...", state="disabled")

        def stop_algorithm():
            nonlocal algorithm_thread, is_running
            is_running = False
            algorithm_thread = None
            start_btn.config(text="Start Algorithm", state="normal")

        def display_validation_results(stats):
            validation_text.config(state='normal')
            validation_text.delete(1.0, tk.END)

            validation_text.insert(tk.END, "=== Validation Results ===\n\n")
            validation_text.insert(tk.END, "Conflicts:\n")
            validation_text.insert(tk.END, f"- Student conflicts: {stats['student_conflicts']}\n")
            validation_text.insert(tk.END, f"- Teacher conflicts: {stats['teacher_conflicts']}\n\n")

            validation_text.insert(tk.END, "Subject Hours:\n")
            for sid, sch in stats['subject_hours'].items():
                req = stats['required_hours'][sid]
                status = "✓" if sch == req else "✗"
                validation_text.insert(tk.END, f"- Subject {sid}: {sch}/{req} {status}\n")

            validation_text.insert(tk.END, "\nTeacher Daily Loads:\n")
            for tid, loads in stats['teacher_daily_load'].items():
                validation_text.insert(tk.END, f"- Teacher {tid}:\n")
                for day, cnt in loads.items():
                    validation_text.insert(tk.END, f"  Day {day+1}: {cnt}\n")

            validation_text.config(state='disabled')

        # Bind buttons after defining functions
        start_btn.configure(command=toggle_algorithm)
        view_btn.configure(command=lambda: display_schedule())

        # Initialize empty display
        update_timetable_display()

        # Logging to capture from algorithm module
        class TextHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
        text_handler = TextHandler()
        text_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger = logging.getLogger()
        logger.addHandler(text_handler)

        def display_schedule():
            try:
                with open('schedule_output.json', 'r') as f:
                    schedule_data = json.load(f)

                # rebuild filter sets
                subj_set = set()
                teach_set = set()
                stud_set = set()
                for day_data in schedule_data.get('days', {}).values():
                    for period in day_data.values():
                        for session in period:
                            subj_set.add(session['subject_name'])
                            for t in session['teachers']:
                                teach_set.add(t['name'])
                            for s in session['students']:
                                stud_set.add(s['name'])
                self.filter_subjects = list(subj_set)
                self.filter_teachers = list(teach_set)
                self.filter_students = list(stud_set)

                repopulate_listbox()
                update_timetable_display(schedule_data)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load schedule: {str(e)}")

        def apply_filter(_evt=None):
            filter_type = filter_var.get()
            try:
                with open('schedule_output.json', 'r') as f:
                    schedule_data = json.load(f)
                sel = list(filter_listbox.curselection())
                if filter_type == "subject" and sel:
                    val = filter_listbox.get(sel[0])
                    update_timetable_display(schedule_data, "subject", val)
                elif filter_type == "teacher" and sel:
                    val = filter_listbox.get(sel[0])
                    update_timetable_display(schedule_data, "teacher", val)
                elif filter_type == "student" and sel:
                    val = filter_listbox.get(sel[0])
                    update_timetable_display(schedule_data, "student", val)
                else:
                    update_timetable_display(schedule_data)
            except:
                pass

        # Bind changes
        filter_var.trace('w', apply_filter)
        filter_listbox.bind('<<ListboxSelect>>', apply_filter)

        # Prevent scrolling conflict
        def on_enter_listbox(_):
            main_canvas.unbind_all("<MouseWheel>")

        def on_leave_listbox(_):
            main_canvas.bind_all("<MouseWheel>", on_mouse_wheel)

        filter_listbox.bind('<Enter>', on_enter_listbox)
        filter_listbox.bind('<Leave>', on_leave_listbox)
        validation_text.bind('<Enter>', on_enter_listbox)
        validation_text.bind('<Leave>', on_leave_listbox)

        wind.mainloop()


if __name__ == "__main__":
    MainGUI()
