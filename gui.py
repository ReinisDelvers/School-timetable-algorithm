import tkinter as tk
from tkinter import END, messagebox
from tkinter.messagebox import showerror

import json
import pandas as pd
import threading
import logging

from data import add_student, add_subject, add_teacher, add_subject_student, add_subject_teacher, get_student, get_subject, get_teacher, get_subject_teacher, get_subject_student, remove_student, remove_subject, remove_teacher, remove_subject_teacher, remove_subject_student, update_student, update_subject, update_teacher, update_subject_teacher, update_subject_student, hour_blocker_save, get_hour_blocker

options = {"padx": 5, "pady": 5}

class MainGUI:
    def __init__(self):

        self.window = tk.Tk()
      
        window_width = 1280
        window_height = 720

        # get the screen dimension
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        # find the center point
        center_x = int(screen_width/2 - window_width / 2)
        center_y = int(screen_height/2 - window_height / 2)

        # set the position of the window to the center of the screen
        self.window.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        self.window.title("School timetable algorithm")

        self.frame = tk.Frame(self.window)
        
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.columnconfigure(3, weight=1)
        self.frame.columnconfigure(4, weight=1)
        self.frame.columnconfigure(5, weight=1)
        self.frame.columnconfigure(6, weight=1)

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

    #SUBJECT
    def subject(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subject")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)
        frame.columnconfigure(5, weight=1)
        frame.columnconfigure(6, weight=1)

        selected_subject_id = None

        def change_list():
            subject_list = get_subject()
            subject_listbox.delete(0, END)

            for i in range(len(subject_list)):
                subject_listbox.insert("end", f"{subject_list[i]}")

        def subject_add():
            name = ent1.get()
            group_number = ent2.get()
            number_of_hours_per_week = ent3.get()
            max_hours_per_day = ent4.get()
            max_student_count_per_group = ent5.get()
            min_hours_per_day = ent6.get()
            parallel_subject_groups = ent7.get()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
                int(parallel_subject_groups)
            except:
                showerror("Error", "Group number, number of hours per week, max hours per day, max student count per group need to be a number, min hours per day and parallel_subject_groups")
                return
            if name and group_number and number_of_hours_per_week and max_hours_per_day and max_student_count_per_group and min_hours_per_day and parallel_subject_groups:
                add_subject(name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups)
            else:
                showerror("Error", "All fields must be filled out.")
                return
            change_list()

        def subject_remove():
            selected = list(subject_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            
            subject_list = get_subject() 
            selected_id = [] 
            for i in selected:
                selected_id.append(subject_list[i][0])
            remove_subject(selected_id)
            
            change_list()

        def subject_edit():
            nonlocal selected_subject_id
            selected = list(subject_listbox.curselection())
            
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            selected1=selected[0]
            subject_list = get_subject() 
            ent1.delete(0, END)
            ent2.delete(0, END)
            ent3.delete(0, END)
            ent4.delete(0, END)
            ent5.delete(0, END)
            ent6.delete(0, END)
            ent7.delete(0, END)
            ent1.insert(0, subject_list[selected1][1])
            ent2.insert(0, subject_list[selected1][2])
            ent3.insert(0, subject_list[selected1][3])
            ent4.insert(0, subject_list[selected1][4])
            ent5.insert(0, subject_list[selected1][5])
            ent6.insert(0, subject_list[selected1][6])
            ent7.insert(0, subject_list[selected1][7])
            selected_subject_id = subject_list[selected1][0]

        def subject_confirm_edit():
            nonlocal selected_subject_id
            name = ent1.get()
            group_number = ent2.get()
            number_of_hours_per_week = ent3.get()
            max_hours_per_day = ent4.get()
            max_student_count_per_group = ent5.get()
            min_hours_per_day = ent6.get()
            parallel_subject_groups = ent7.get()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
                int(parallel_subject_groups)
            except:
                showerror("Error", "Group number, number of hours per week, max hours per day, max student count per group need to be a number, min hours per day and paralle subject groups")
                return
            if name and group_number and number_of_hours_per_week and max_hours_per_day and max_student_count_per_group and min_hours_per_day and parallel_subject_groups:
                if selected_subject_id != None:
                    update_subject(selected_subject_id, name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day, parallel_subject_groups)
                    selected_subject_id = None
                else:
                    showerror("Error", "Select something to edit.")
                    return
            else:
                    showerror("Error", "All fields must be filled out.")
                    return
            change_list()

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)

        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)

        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)

        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Name", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)

        label2 = tk.Label(frame, text="Group number", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        label3 = tk.Label(frame, text="Number of hours per week", font=("Arial", 18))
        label3.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        label4 = tk.Label(frame, text="Max hours per day", font=("Arial", 18))
        label4.grid(row=1, column=3, sticky=tk.W+tk.E, **options)
        
        label5 = tk.Label(frame, text="Max student count per group", font=("Arial", 18))
        label5.grid(row=1, column=4, sticky=tk.W+tk.E, **options)

        label6 = tk.Label(frame, text="Min hours per day", font=("Arial", 18))
        label6.grid(row=1, column=5, sticky=tk.W+tk.E, **options)

        label7 = tk.Label(frame, text="Parallel subject groups", font=("Arial", 18))
        label7.grid(row=0, column=5, columnspan=2, sticky=tk.E, **options)

        label7 = tk.Label(frame, text="0 = No 1 = Yes", font=("Arial", 18))
        label7.grid(row=1, column=6, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        ent3 = tk.Entry(frame,  font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        ent4 = tk.Entry(frame,  font=("Arial", 18))
        ent4.grid(row=2, column=3, sticky=tk.W+tk.E, **options)

        ent5 = tk.Entry(frame,  font=("Arial", 18))
        ent5.grid(row=2, column=4, sticky=tk.W+tk.E, **options)

        ent6 = tk.Entry(frame,  font=("Arial", 18))
        ent6.grid(row=2, column=5, sticky=tk.W+tk.E, **options) 
        
        ent7 = tk.Entry(frame,  font=("Arial", 18))
        ent7.grid(row=2, column=6, sticky=tk.W+tk.E, **options)
        ent7.insert(0, 0)
        
        frame.pack(fill="x")

        subject_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        subject_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #TEACHER
    def teacher(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Teacher")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=6)
        frame.columnconfigure(4, weight=6)
        frame.columnconfigure(5, weight=6)
        frame.columnconfigure(6, weight=6)
        frame.columnconfigure(7, weight=6)
        frame.columnconfigure(8, weight=6)
        frame.columnconfigure(9, weight=6)
        frame.columnconfigure(10, weight=6)


        selected_teacher_id = None

        def change_list():
            teacher_list = get_teacher()
            teacher_listbox.delete(0, END)

            for i in range(len(teacher_list)):
                teacher_listbox.insert("end", f"{teacher_list[i]}")

        def teacher_add():
            name = ent1.get()
            middle_name = ent2.get()
            last_name = ent3.get()
            monday = checkboxent1.get()
            tuesday = checkboxent2.get()
            wednesday = checkboxent3.get()
            thursday = checkboxent4.get()
            monday1 = ent4.get()
            tuesday1 = ent6.get()
            wednesday1 = ent8.get()
            thursday1 = ent10.get()
            monday2 = ent5.get()
            tuesday2 = ent7.get()
            wednesday2 = ent9.get()
            thursday2 = ent11.get()
            if name and last_name and monday1 and tuesday1 and wednesday1 and thursday1 and monday2 and tuesday2 and wednesday2 and thursday2:
                add_teacher(name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2)
            else:
                showerror("Error", "All fields must be filled out except middle name.")
                return
            change_list()

        def teacher_remove():
            selected = list(teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            
            teacher_list = get_teacher() 
            selected_id = [] 
            for i in selected:
                selected_id.append(teacher_list[i][0])
            remove_teacher(selected_id)
            
            change_list()

        def teacher_edit():
            nonlocal selected_teacher_id
            selected = list(teacher_listbox.curselection())
            
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            selected1=selected[0]
            teacher_list = get_teacher() 
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
            ent1.insert(0, teacher_list[selected1][1])
            ent2.insert(0, teacher_list[selected1][2])
            ent3.insert(0, teacher_list[selected1][3])
            ent4.insert(0, teacher_list[selected1][8])
            ent5.insert(0, teacher_list[selected1][12])
            ent6.insert(0, teacher_list[selected1][9])
            ent7.insert(0, teacher_list[selected1][13])
            ent8.insert(0, teacher_list[selected1][10])
            ent9.insert(0, teacher_list[selected1][14])
            ent10.insert(0, teacher_list[selected1][11])
            ent11.insert(0, teacher_list[selected1][15])
            checkboxent1.set(teacher_list[selected1][4])
            checkboxent2.set(teacher_list[selected1][5])
            checkboxent3.set(teacher_list[selected1][6])
            checkboxent4.set(teacher_list[selected1][7])
            selected_teacher_id = teacher_list[selected1][0]

        def teacher_confirm_edit():
            nonlocal selected_teacher_id
            name = ent1.get()
            middle_name = ent2.get()
            last_name = ent3.get()
            monday = checkboxent1.get()
            tuesday = checkboxent2.get()
            wednesday = checkboxent3.get()
            thursday = checkboxent4.get()
            monday1 = ent4.get()
            tuesday1 = ent6.get()
            wednesday1 = ent8.get()
            thursday1 = ent10.get()
            monday2 = ent5.get()
            tuesday2 = ent7.get()
            wednesday2 = ent9.get()
            thursday2 = ent11.get()
            if name and last_name and monday1 and tuesday1 and wednesday1 and thursday1 and monday2 and tuesday2 and wednesday2 and thursday2:
                if selected_teacher_id != None:
                    update_teacher(selected_teacher_id, name, middle_name, last_name, monday, tuesday, wednesday, thursday, monday1, tuesday1, wednesday1, thursday1, monday2, tuesday2, wednesday2, thursday2)
                    selected_teacher_id = None
                else:
                    showerror("Error", "Select something to edit.")
                    return
            else:
                    showerror("Error", "All fields must be filled out except middle name.")
                    return
            change_list()

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=teacher_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)
        
        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=teacher_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)

        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=teacher_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)

        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=teacher_confirm_edit)
        btn4.grid(row=0, column=3, columnspan=8, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Name", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)

        label2 = tk.Label(frame, text="Middle name", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        label3 = tk.Label(frame, text="Last name", font=("Arial", 18))
        label3.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        label4 = tk.Label(frame, text="Monday", font=("Arial", 18))
        label4.grid(row=1, column=3, columnspan=2, sticky=tk.W+tk.E, **options)

        label5 = tk.Label(frame, text="Tuesday", font=("Arial", 18))
        label5.grid(row=1, column=5, columnspan=2, sticky=tk.W+tk.E, **options)

        label6 = tk.Label(frame, text="Wednesday", font=("Arial", 18))
        label6.grid(row=1, column=7, columnspan=2, sticky=tk.W+tk.E, **options)

        label7 = tk.Label(frame, text="Thursday", font=("Arial", 18))
        label7.grid(row=1, column=9, columnspan=2, sticky=tk.W+tk.E, **options)

        label8 = tk.Label(frame, text="≤", font=("Arial", 18))
        label8.grid(row=3, column=3, sticky=tk.W+tk.E, **options)

        label9 = tk.Label(frame, text="≥", font=("Arial", 18))
        label9.grid(row=3, column=4, sticky=tk.W+tk.E, **options)
        
        label10 = tk.Label(frame, text="≤", font=("Arial", 18))
        label10.grid(row=3, column=5, sticky=tk.W+tk.E, **options)

        label11 = tk.Label(frame, text="≥", font=("Arial", 18))
        label11.grid(row=3, column=6, sticky=tk.W+tk.E, **options)

        label12 = tk.Label(frame, text="≤", font=("Arial", 18))
        label12.grid(row=3, column=7, sticky=tk.W+tk.E, **options)

        label13 = tk.Label(frame, text="≥", font=("Arial", 18))
        label13.grid(row=3, column=8, sticky=tk.W+tk.E, **options)

        label14 = tk.Label(frame, text="≤", font=("Arial", 18))
        label14.grid(row=3, column=9, sticky=tk.W+tk.E, **options)

        label15 = tk.Label(frame, text="≥", font=("Arial", 18))
        label15.grid(row=3, column=10, sticky=tk.W+tk.E, **options)

        label16 = tk.Label(frame, text="≤ means not working until given hour\n≥ means not working past given hour", font=("Arial", 18))
        label16.grid(row=3, column=0, columnspan=3, rowspan=2, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        ent3 = tk.Entry(frame,  font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        ent4 = tk.Entry(frame, font=("Arial", 18))
        ent4.grid(row=4, column=3, sticky=tk.W+tk.E, **options)
        ent4.insert(0, 1)

        ent5 = tk.Entry(frame, font=("Arial", 18))
        ent5.grid(row=4, column=4, sticky=tk.W+tk.E, **options)
        ent5.insert(0, 10)

        ent6 = tk.Entry(frame, font=("Arial", 18))
        ent6.grid(row=4, column=5, sticky=tk.W+tk.E, **options)
        ent6.insert(0, 1)

        ent7 = tk.Entry(frame, font=("Arial", 18))
        ent7.grid(row=4, column=6, sticky=tk.W+tk.E, **options)
        ent7.insert(0, 10)

        ent8 = tk.Entry(frame, font=("Arial", 18))
        ent8.grid(row=4, column=7, sticky=tk.W+tk.E, **options)
        ent8.insert(0, 1)

        ent9 = tk.Entry(frame, font=("Arial", 18))
        ent9.grid(row=4, column=8, sticky=tk.W+tk.E, **options)
        ent9.insert(0, 10)

        ent10 = tk.Entry(frame, font=("Arial", 18))
        ent10.grid(row=4, column=9, sticky=tk.W+tk.E, **options)
        ent10.insert(0, 1)

        ent11 = tk.Entry(frame, font=("Arial", 18))
        ent11.grid(row=4, column=10, sticky=tk.W+tk.E, **options)
        ent11.insert(0, 10)

        checkboxent1 = tk.IntVar(value=1)
        box1 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent1, offvalue=0, onvalue=1)
        box1.grid(row=2, column=3, columnspan=2, sticky=tk.W+tk.E, **options)

        checkboxent2 = tk.IntVar(value=1)
        box2 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent2, offvalue=0, onvalue=1)
        box2.grid(row=2, column=5, columnspan=2, sticky=tk.W+tk.E, **options)

        checkboxent3 = tk.IntVar(value=1)
        box3 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent3, offvalue=0, onvalue=1)
        box3.grid(row=2, column=7, columnspan=2, sticky=tk.W+tk.E, **options)

        checkboxent4 = tk.IntVar(value=1)
        box4 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent4, offvalue=0, onvalue=1)
        box4.grid(row=2, column=9, columnspan=2, sticky=tk.W+tk.E, **options)   

        frame.pack(fill="x")

        teacher_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        teacher_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #STUDENT
    def student(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Student")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)

        selected_student_id = None

        def change_list():
            student_list = get_student()
            student_listbox.delete(0, END)

            for i in range(len(student_list)):
                student_listbox.insert("end", f"{student_list[i]}")

        def student_add():
            name = ent1.get()
            middle_name = ent2.get()
            last_name = ent3.get()
            if name and last_name:
                add_student(name, middle_name, last_name)
            else:
                showerror("Error", "All fields must be filled out except middle name.")
                return
            change_list()

        def student_remove():
            selected = list(student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            
            student_list = get_student() 
            selected_id = [] 
            for i in selected:
                selected_id.append(student_list[i][0])
            remove_student(selected_id)
            
            change_list()

        def student_edit():
            nonlocal selected_student_id
            selected = list(student_listbox.curselection())
            
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            selected1=selected[0]
            student_list = get_student() 
            ent1.delete(0, END)
            ent2.delete(0, END)
            ent3.delete(0, END)
            ent1.insert(0, student_list[selected1][1])
            ent2.insert(0, student_list[selected1][2])
            ent3.insert(0, student_list[selected1][3])
            selected_student_id = student_list[selected1][0]

        def student_confirm_edit():
            nonlocal selected_student_id
            name = ent1.get()
            middle_name = ent2.get()
            last_name = ent3.get()
            if name and last_name:
                if selected_student_id != None:
                    update_student(selected_student_id, name, middle_name, last_name)
                    selected_student_id = None
                else:
                    showerror("Error", "Select something to edit.")
                    return
            else:
                    showerror("Error", "All fields must be filled out except middle name.")
                    return
            change_list()

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

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        ent3 = tk.Entry(frame,  font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)
        
        frame.pack(fill="x")

        student_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        student_listbox.pack(**options)   

        change_list()
        wind.mainloop()     


    #SUBJECT/TEACHER
    def subject_teacher(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subject/Teacher")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window
        
        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        selected_subject_teacher_id = None
        selected_subject_id = None
        selected_teacher_id = None

        def change_list():
            subject_teacher_list = get_subject_teacher()
            subject_list = get_subject()
            teacher_list = get_teacher()

            subject_teacher_listbox.delete(0, END)
            subject_listbox.delete(0, END)
            teacher_listbox.delete(0, END)

            for item in subject_teacher_list:
                subject_teacher_listbox.insert("end", f"{item}")
            for item in subject_list:
                subject_listbox.insert("end", f"{item}")
            for item in teacher_list:
                teacher_listbox.insert("end", f"{item}")

        def subject_teacher_add():
            nonlocal selected_subject_id, selected_teacher_id
            group_number = ent1.get()
            subject_teacher_list = get_subject_teacher()
            for i in range(len(subject_teacher_list)):
                if  selected_subject_id == subject_teacher_list[i][1] and selected_teacher_id == subject_teacher_list[i][3] and subject_teacher_list[i][0] != selected_subject_teacher_id:
                    showerror("Error", "This teacher/subject already exists if you need multiple connections choose a bigger group number by editing existing one.")
                    return
            try:
                int(group_number)
            except:
                showerror("Error", "Group number needs to be an integer.")
                return
            if group_number and selected_subject_id and selected_teacher_id:
                add_subject_teacher(selected_subject_id, selected_teacher_id, group_number)
                change_list()
            else:
                showerror("Error", "You need to select subject, teacher and write a group number.")
                return
            
        def subject_teacher_remove():
            selected = list(subject_teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove from teacher/subject connections.")
                return
            subject_teacher_list = get_subject_teacher()
            selected_id = [] 
            for i in selected:
                selected_id.append(subject_teacher_list[i][0])
            remove_subject_teacher(selected_id)
            
            change_list()

        def subject_teacher_edit():
            nonlocal selected_subject_teacher_id, selected_subject_id, selected_teacher_id
            subject_list = get_subject()
            teacher_list = get_teacher()
            selected = list(subject_teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select subject/teacher connection to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            subject_teacher_list = get_subject_teacher() 
            selected_subject_teacher_id = subject_teacher_list[selected[0]][0]
            selected_subject_id = subject_teacher_list[selected[0]][1]
            selected_teacher_id = subject_teacher_list[selected[0]][3]
            for i in range(len(subject_list)):
                if subject_list[i][0] == subject_teacher_list[selected[0]][1]:
                    label3.config(text=f"{subject_list[i]}")
            for i in range(len(teacher_list)):
                if teacher_list[i][0] == subject_teacher_list[selected[0]][3]:
                    label4.config(text=f"{teacher_list[i]}")
            for i in range(len(subject_teacher_list)):
                if selected_subject_teacher_id == subject_teacher_list[i][0]:
                    ent1.delete(0, END)
                    ent1.insert(0, subject_teacher_list[i][7])
                   


        def subject_teacher_confirm_edit():
            nonlocal selected_subject_teacher_id, selected_subject_id, selected_teacher_id
            group_number = ent1.get()
            subject_teacher_list = get_subject_teacher()
            for i in range(len(subject_teacher_list)):
                if  selected_subject_id == subject_teacher_list[i][1] and selected_teacher_id == subject_teacher_list[i][3] and subject_teacher_list[i][0] != selected_subject_teacher_id:
                    showerror("Error", "This teacher/subject already exists either delete previuos one or edit it.")
                    return
            try:
                int(group_number)
            except:
                showerror("Error", "Group number needs to be a number.")
                return
            if selected_subject_teacher_id != None:
                update_subject_teacher(selected_subject_teacher_id, selected_subject_id, selected_teacher_id, group_number)
                selected_subject_teacher_id = None
            else:
                showerror("Error", "Select something to edit.")
                return
            change_list()

        def subject_on_selection(useless):
            nonlocal selected_subject_id
            subject_list = get_subject()
            selected = list(subject_listbox.curselection()) 
            try:
                selected_subject_id = subject_list[selected[0]][0]
                label3.config(text=f"{subject_list[selected[0]]}")
            except:
                return
            
        def teacher_on_selection(useless):
            nonlocal selected_teacher_id
            teacher_list = get_teacher()
            selected = list(teacher_listbox.curselection())
            try:
                selected_teacher_id = teacher_list[selected[0]][0]
                label4.config(text=f"{teacher_list[selected[0]]}")
            except:
                return

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

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=3, column=2, sticky=tk.W+tk.E+tk.N, **options)

        frame.pack(fill="x")

        subject_teacher_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        subject_teacher_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #SUBJECT/STUDENT
    def subject_student(self):  
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subject/Student")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window
        
        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        selected_subject_student_id = None
        selected_subject_ids = None
        selected_student_id = None
        subject_student_list = None

        def change_list():
            nonlocal subject_student_list
            subject_student_list = get_subject_student()
            subject_student_list = [list(item) for item in subject_student_list]
            subject_list = get_subject()
            subject_list = [list(item) for item in subject_list]
            student_list = get_student()
            
            subject_ids = []
            subject_names = []
            for i in range(len(subject_student_list)):
                subject_ids.append(json.loads(subject_student_list[i][1]))
                subject_student_list[i][1] = subject_ids[i]
            for i in range(len(subject_ids)):
                for b in range(len(subject_ids[i])):
                    for c in range(len(subject_list)):
                        if subject_ids[i][b] == subject_list[c][0]:
                            subject_names.append(subject_list[c][1])
                subject_student_list[i][2] = subject_names
                subject_names = []
            subject_student_listbox.delete(0, END)
            subject_listbox.delete(0, END)
            student_listbox.delete(0, END)
            for item in subject_student_list:
                subject_student_listbox.insert("end", f"{item}")
            for item in subject_list:
                subject_listbox.insert("end", f"{item}")
            for item in student_list:
                student_listbox.insert("end", f"{item}")

        def subject_student_add():
            nonlocal selected_subject_ids, selected_student_id, subject_student_list
            for i in range(len(subject_student_list)):
                if  selected_student_id == subject_student_list[i][3] and subject_student_list[i][0] != selected_subject_student_id:
                    showerror("Error", "This student already has connections delete previous or edit it.")
                    return
            if selected_subject_ids and selected_student_id:
                json_selected_subject_ids = json.dumps(selected_subject_ids)
                add_subject_student(json_selected_subject_ids, selected_student_id)
                change_list()
            else:
                showerror("Error", "You need to select subject and student.")
                return
            
        def subject_student_remove():
            nonlocal subject_student_list
            selected = list(subject_student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove from student/subject connections.")
                return
            selected_id = [] 
            for i in selected:
                selected_id.append(subject_student_list[i][0])
            remove_subject_student(selected_id)            
            change_list()

        
        def subject_student_edit():
            nonlocal selected_subject_student_id, selected_subject_ids, selected_student_id, subject_student_list
            student_list = get_student()
            subject_list = get_subject()
            selected = list(subject_student_listbox.curselection())
            if not selected:
                showerror("Error", "Select subject/student connection to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            selected_subject_student_id = subject_student_list[selected[0]][0]
            selected_subject_ids = subject_student_list[selected[0]][1]
            selected_student_id = subject_student_list[selected[0]][3]
            label3.config(text=f"{subject_student_list[selected[0]][2]}")
            for i in range(len(student_list)):
                if student_list[i][0] == subject_student_list[selected[0]][3]:
                    label4.config(text=f"{student_list[i]}")
            
            for i in selected_subject_ids:
                for b in range(len(subject_list)):
                    if i == subject_list[b][0]:
                        subject_listbox.selection_set(b)


        def subject_student_confirm_edit():
            nonlocal selected_subject_student_id, selected_subject_ids, selected_student_id, subject_student_list
            for i in range(len(subject_student_list)):
                if  selected_student_id == subject_student_list[i][3] and subject_student_list[i][0] != selected_subject_student_id:
                    showerror("Error", "This student already has connections delete previous or edit it.")
                    return
            if selected_subject_student_id != None:
                update_subject_student(selected_subject_student_id, selected_subject_ids, selected_student_id)
                selected_subject_student_id = None
            else:
                showerror("Error", "Select something to edit.")
                return
            change_list()


        def subject_on_selection(useless):
            nonlocal selected_subject_ids
            selected = list(subject_listbox.curselection())
            subject_list = get_subject()
            selected_ids = []
            selected_label = []
            if selected:
                for i in range(len(selected)):
                    selected_ids.append(subject_list[selected[i]][0])
                    selected_label.append(subject_list[selected[i]][1])
                label3.config(text=f"{selected_label}")
                selected_subject_ids = selected_ids
                        
        def student_on_selection(useless):
            nonlocal selected_student_id
            student_list = get_student()
            selected = list(student_listbox.curselection())
            try:
                selected_student_id = student_list[selected[0]][0]
                label4.config(text=f"{student_list[selected[0]]}")
            except:
                return
            
        
        def add_from_ecxel():
            file_path = ent1.get()
            try:
                file = pd.read_excel(file_path)
            except:
                showerror("Error", "Input a valid excel file path")
                return
            
            csv_file = "excel.csv"
            file.to_csv(csv_file, index=False)

            file = pd.read_csv(csv_file)
            column_names = file.columns.tolist()
            row_list = file.values.tolist()

            column_student_names = file[column_names[0]]
            column_student_names_remade = []
            for i in range(len(column_student_names)):
                column_student_names_remade.append(" ".join(column_student_names[i].split()))
            student_tuple = list(get_student())
            student_list = []
            for i in range(len(student_tuple)):
                student_list.append(list(student_tuple[i]))
            student_list_remade = []
            for i in range(len(student_list)):
                if student_list[i][2] == "":
                    student_temp1 = student_list[i][1].replace(" ", "")
                    student_temp3 = student_list[i][3].replace(" ", "")
                    temp = []
                    temp.append(student_list[i][0])
                    temp.append(f"{student_temp1} {student_temp3}")
                    student_list_remade.append(temp)
                else:
                    student_temp1 = student_list[i][1].replace(" ", "")
                    student_temp2 = student_list[i][2].replace(" ", "")  
                    student_temp3 = student_list[i][3].replace(" ", "")
                    temp = []
                    temp.append(student_list[i][0])
                    temp.append(f"{student_temp1} {student_temp2} {student_temp3}")        
                    student_list_remade.append(temp)

            missing_student_names = []
            for name in column_student_names_remade:
                if not any(name == sublist[1] for sublist in student_list_remade):
                    missing_student_names.append(name)

            subject_list = list(get_subject())
            subject_list_remade = []
            for i in range(len(subject_list)):
                temp = []
                temp.append(subject_list[i][0])
                temp.append(subject_list[i][1])
                subject_list_remade.append(temp)
            column_subject_names = column_names
            del column_subject_names[0]

            missing_subject_names = []
            for name in column_subject_names:
                if not any(name == sublist[1] for sublist in subject_list_remade):
                    missing_subject_names.append(name)
          
            if len(missing_student_names) != 0 or len(missing_subject_names) != 0:
                result = messagebox.askyesno("Choose", f"Do you want to add students: {missing_student_names} and subjects: {missing_subject_names} hours will added with some default values please change them and add a teacher for subject.")
                if result:
                    if len(missing_student_names) > 0:
                        for i in range(len(missing_student_names)):
                            temp = missing_student_names[i].split()
                            student_name = ""
                            middle_name = ""
                            last_name = ""
                            if len(temp) == 2:
                                student_name = temp[0]
                                last_name = temp[1]
                            elif len(temp) == 3:
                                student_name = temp[0]
                                middle_name = temp[1]
                                last_name = temp[2]
                            else:
                                showerror("Error", f"Can't add {missing_student_names[i]} it has to 2 or 3 words long!")
                                return
                            add_student(student_name, middle_name, last_name)
                    
                    if len(missing_subject_names) > 0:
                        for i in range(len(missing_subject_names)):
                            missing_subject_names[i]
                            add_subject(missing_subject_names[i], 1, 6, 2, 30, 2, 0)
                    
                else:
                    showerror("Error", "Adding from excel was unsuccessful!")
                    return
            

            column_student_names_remade1 = []
            for i in range(len(column_student_names)):
                column_student_names_remade1.append(" ".join(column_student_names[i].split()))
            student_tuple1 = list(get_student())
            student_list1 = []
            for i in range(len(student_tuple1)):
                student_list1.append(list(student_tuple1[i]))
            student_list_remade1 = []
            for i in range(len(student_list1)):
                if student_list1[i][2] == "":
                    student_temp11 = student_list1[i][1].replace(" ", "")
                    student_temp31 = student_list1[i][3].replace(" ", "")
                    temp1 = []
                    temp1.append(student_list1[i][0])
                    temp1.append(f"{student_temp11} {student_temp31}")
                    student_list_remade1.append(temp1)
                else:
                    student_temp11 = student_list1[i][1].replace(" ", "")
                    student_temp21 = student_list1[i][2].replace(" ", "")  
                    student_temp31 = student_list1[i][3].replace(" ", "")
                    temp1 = []
                    temp1.append(student_list1[i][0])
                    temp1.append(f"{student_temp11} {student_temp21} {student_temp31}")        
                    student_list_remade1.append(temp1)

            column_student_id1 = []
            for i in range(len(column_student_names_remade1)):
                for b in range(len(student_list_remade1)):
                    if column_student_names[i] == student_list_remade1[b][1]:
                        column_student_id1.append(student_list_remade1[b][0])
                        break

            subject_list1 = list(get_subject())
            subject_list_remade1 = []
            for i in range(len(subject_list1)):
                temp1 = []
                temp1.append(subject_list1[i][0])
                temp1.append(subject_list1[i][1])
                subject_list_remade1.append(temp1)

            column_subject_id1 = []
            for i in range(len(column_subject_names)):
                for b in range(len(subject_list_remade1)):
                    if column_subject_names[i] == subject_list_remade1[b][1]:
                        column_subject_id1.append(subject_list_remade1[b][0])
            
            subject_student_list1 = list(get_subject_student())
            subject_student_list_remade1 = []
            for i in range(len(subject_student_list1)):
                temp1 = []
                temp1.append(subject_student_list1[i][0])
                temp1.append(subject_student_list1[i][3])
                subject_student_list_remade1.append(temp1)

            for i in range(len(column_student_id1)):
                real_subject_ids1 = []
                for b in range(1, len(row_list[i])):
                    if str(row_list[i][b]) != "nan":
                        real_subject_ids1.append(column_subject_id1[b-1])
                x=0 
                for c in range(len(subject_student_list_remade1)):
                    if subject_student_list_remade1[c][1] == column_student_id1[i]:
                        update_subject_student(subject_student_list_remade1[c][0], real_subject_ids1, column_student_id1[i])
                        x=1
                        break
                if x == 0:
                    add_subject_student(real_subject_ids1, column_student_id1[i])
            change_list()
            



            
            




        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_student_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)

        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_student_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)

        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_student_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)

        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_student_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        btn5 = tk.Button(frame, text="Add from excel", font=("Arial", 18), command=add_from_ecxel)
        btn5.grid(row=1, column=3, rowspan=2, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
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

        label6 = tk.Label(frame, text="Takes first excel column as student\nall other as seperate subjects.\nMake sure there are no repeating subjects or students in excel or current data.\nStudent is not learning that subject only if\nthe corresponding subject name excel cell is empty.", font=("Arial", 18))
        label6.grid(row=3, column=2, columnspan=2, sticky=tk.W+tk.E+tk.N, **options)

        subject_listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, font=("Arial", 18))
        subject_listbox.grid(row=3, column=0, sticky=tk.W+tk.E, **options)
        subject_listbox.bind("<<ListboxSelect>>", subject_on_selection)

        student_listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=("Arial", 18))
        student_listbox.grid(row=3, column=1, sticky=tk.W+tk.E, **options)
        student_listbox.bind("<<ListboxSelect>>", student_on_selection)
        
        frame.pack(fill="x")

        subject_student_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 10))
        subject_student_listbox.pack(**options)   

        change_list()
        wind.mainloop()   

    #HOUR BLOCKER
    def hour_blocker(self):  
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Hour blocker")  # window title
        # wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window
        
        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)
        frame.columnconfigure(5, weight=1)
        frame.columnconfigure(6, weight=1)
        frame.columnconfigure(7, weight=1)
        frame.columnconfigure(8, weight=1)
        frame.columnconfigure(9, weight=1)
        frame.columnconfigure(10, weight=1)

        def change_list():
            hour_blocker = get_hour_blocker()
            checkboxent1.set(hour_blocker[0][0])
            checkboxent2.set(hour_blocker[0][1])
            checkboxent3.set(hour_blocker[0][2])
            checkboxent4.set(hour_blocker[0][3])
            checkboxent5.set(hour_blocker[0][4])
            checkboxent6.set(hour_blocker[0][5])
            checkboxent7.set(hour_blocker[0][6])
            checkboxent8.set(hour_blocker[0][7])
            checkboxent9.set(hour_blocker[0][8])
            checkboxent10.set(hour_blocker[0][9])
            checkboxent11.set(hour_blocker[0][10])
            checkboxent12.set(hour_blocker[0][11])
            checkboxent13.set(hour_blocker[0][12])
            checkboxent14.set(hour_blocker[0][13])
            checkboxent15.set(hour_blocker[0][14])
            checkboxent16.set(hour_blocker[0][15])
            checkboxent17.set(hour_blocker[0][16])
            checkboxent18.set(hour_blocker[0][17])
            checkboxent19.set(hour_blocker[0][18])
            checkboxent20.set(hour_blocker[0][19])
            checkboxent21.set(hour_blocker[0][20])
            checkboxent22.set(hour_blocker[0][21])
            checkboxent23.set(hour_blocker[0][22])
            checkboxent24.set(hour_blocker[0][23])
            checkboxent25.set(hour_blocker[0][24])
            checkboxent26.set(hour_blocker[0][25])
            checkboxent27.set(hour_blocker[0][26])
            checkboxent28.set(hour_blocker[0][27])
            checkboxent29.set(hour_blocker[0][28])
            checkboxent30.set(hour_blocker[0][29])
            checkboxent31.set(hour_blocker[0][30])
            checkboxent32.set(hour_blocker[0][31])
            checkboxent33.set(hour_blocker[0][32])
            checkboxent34.set(hour_blocker[0][33])
            checkboxent35.set(hour_blocker[0][34])
            checkboxent36.set(hour_blocker[0][35])
            checkboxent37.set(hour_blocker[0][36])
            checkboxent38.set(hour_blocker[0][37])
            checkboxent39.set(hour_blocker[0][38])
            checkboxent40.set(hour_blocker[0][39])

        def hour_blocker_save1():
            monday1 = checkboxent1.get()
            monday2 = checkboxent2.get()
            monday3 = checkboxent3.get()
            monday4 = checkboxent4.get()
            monday5 = checkboxent5.get()
            monday6 = checkboxent6.get()
            monday7 = checkboxent7.get()
            monday8 = checkboxent8.get()
            monday9 = checkboxent9.get()
            monday10 = checkboxent10.get()
            tuesday1 = checkboxent11.get()
            tuesday2 = checkboxent12.get()
            tuesday3 = checkboxent13.get()
            tuesday4 = checkboxent14.get()
            tuesday5 = checkboxent15.get()
            tuesday6 = checkboxent16.get()
            tuesday7 = checkboxent17.get()
            tuesday8 = checkboxent18.get()
            tuesday9 = checkboxent19.get()
            tuesday10 = checkboxent20.get()
            wednesday1 = checkboxent21.get()
            wednesday2 = checkboxent22.get()
            wednesday3 = checkboxent23.get()
            wednesday4 = checkboxent24.get()
            wednesday5 = checkboxent25.get()
            wednesday6 = checkboxent26.get()
            wednesday7 = checkboxent27.get()
            wednesday8 = checkboxent28.get()
            wednesday9 = checkboxent29.get()
            wednesday10 = checkboxent30.get()
            thursday1 = checkboxent31.get()
            thursday2 = checkboxent32.get()
            thursday3 = checkboxent33.get()
            thursday4 = checkboxent34.get()
            thursday5 = checkboxent35.get()
            thursday6 = checkboxent36.get()
            thursday7 = checkboxent37.get()
            thursday8 = checkboxent38.get()
            thursday9 = checkboxent39.get()
            thursday10 = checkboxent40.get()
            hour_blocker_save(monday1, monday2, monday3, monday4, monday5, monday6, monday7, monday8, monday9, monday10, tuesday1, tuesday2, tuesday3, tuesday4, tuesday5, tuesday6, tuesday7, tuesday8, tuesday9, tuesday10, wednesday1, wednesday2, wednesday3, wednesday4, wednesday5, wednesday6, wednesday7, wednesday8, wednesday9, wednesday10, thursday1, thursday2, thursday3, thursday4, thursday5, thursday6, thursday7, thursday8, thursday9, thursday10)


        btn1 = tk.Button(frame, text="Save", font=("Arial", 18), command=hour_blocker_save1)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Without ✓ means that hour won't be included by alghorithm", font=("Arial", 18))
        label1.grid(row=0, column=1, columnspan=10, sticky=tk.W+tk.E, **options)

        label2 = tk.Label(frame, text="Monday", font=("Arial", 18))
        label2.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        label3 = tk.Label(frame, text="Tuesday", font=("Arial", 18))
        label3.grid(row=3, column=0, sticky=tk.W+tk.E, **options)

        label4 = tk.Label(frame, text="Wednesday", font=("Arial", 18))
        label4.grid(row=4, column=0, sticky=tk.W+tk.E, **options)

        label5 = tk.Label(frame, text="Thursday", font=("Arial", 18))
        label5.grid(row=5, column=0, sticky=tk.W+tk.E, **options)

        label6 = tk.Label(frame, text="1", font=("Arial", 18))
        label6.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        label7 = tk.Label(frame, text="2", font=("Arial", 18))
        label7.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        label8 = tk.Label(frame, text="3", font=("Arial", 18))
        label8.grid(row=1, column=3, sticky=tk.W+tk.E, **options)

        label9 = tk.Label(frame, text="4", font=("Arial", 18))
        label9.grid(row=1, column=4, sticky=tk.W+tk.E, **options)

        label10 = tk.Label(frame, text="5", font=("Arial", 18))
        label10.grid(row=1, column=5, sticky=tk.W+tk.E, **options)

        label11 = tk.Label(frame, text="6", font=("Arial", 18))
        label11.grid(row=1, column=6, sticky=tk.W+tk.E, **options)

        label12 = tk.Label(frame, text="7", font=("Arial", 18))
        label12.grid(row=1, column=7, sticky=tk.W+tk.E)

        label13 = tk.Label(frame, text="8", font=("Arial", 18))
        label13.grid(row=1, column=8, sticky=tk.W+tk.E)

        label14 = tk.Label(frame, text="9", font=("Arial", 18))
        label14.grid(row=1, column=9, sticky=tk.W+tk.E)

        label15 = tk.Label(frame, text="10", font=("Arial", 18))
        label15.grid(row=1, column=10, sticky=tk.W+tk.E)

        checkboxent1 = tk.IntVar(value=1)
        box1 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent1, offvalue=0, onvalue=1)
        box1.grid(row=2, column=1, sticky=tk.W+tk.E)

        checkboxent2 = tk.IntVar(value=1)
        box2 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent2, offvalue=0, onvalue=1)
        box2.grid(row=2, column=2, sticky=tk.W+tk.E)

        checkboxent3 = tk.IntVar(value=1)
        box3 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent3, offvalue=0, onvalue=1)
        box3.grid(row=2, column=3, sticky=tk.W+tk.E)

        checkboxent4 = tk.IntVar(value=1)
        box4 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent4, offvalue=0, onvalue=1)
        box4.grid(row=2, column=4, sticky=tk.W+tk.E)

        checkboxent5 = tk.IntVar(value=1)
        box5 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent5, offvalue=0, onvalue=1)
        box5.grid(row=2, column=5, sticky=tk.W+tk.E)

        checkboxent6 = tk.IntVar(value=1)
        box6 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent6, offvalue=0, onvalue=1)
        box6.grid(row=2, column=6, sticky=tk.W+tk.E)

        checkboxent7 = tk.IntVar(value=1)
        box7 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent7, offvalue=0, onvalue=1)
        box7.grid(row=2, column=7, sticky=tk.W+tk.E)

        checkboxent8 = tk.IntVar(value=1)
        box8 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent8, offvalue=0, onvalue=1)
        box8.grid(row=2, column=8, sticky=tk.W+tk.E)

        checkboxent9 = tk.IntVar(value=1)
        box9 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent9, offvalue=0, onvalue=1)
        box9.grid(row=2, column=9, sticky=tk.W+tk.E)

        checkboxent10 = tk.IntVar(value=1)
        box10 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent10, offvalue=0, onvalue=1)
        box10.grid(row=2, column=10, sticky=tk.W+tk.E)

        checkboxent11 = tk.IntVar(value=1)
        box11 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent11, offvalue=0, onvalue=1)
        box11.grid(row=3, column=1, sticky=tk.W+tk.E)

        checkboxent12 = tk.IntVar(value=1)
        box12 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent12, offvalue=0, onvalue=1)
        box12.grid(row=3, column=2, sticky=tk.W+tk.E)

        checkboxent13 = tk.IntVar(value=1)
        box13 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent13, offvalue=0, onvalue=1)
        box13.grid(row=3, column=3, sticky=tk.W+tk.E)

        checkboxent14 = tk.IntVar(value=1)
        box14 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent14, offvalue=0, onvalue=1)
        box14.grid(row=3, column=4, sticky=tk.W+tk.E)

        checkboxent15 = tk.IntVar(value=1)
        box15 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent15, offvalue=0, onvalue=1)
        box15.grid(row=3, column=5, sticky=tk.W+tk.E)

        checkboxent16 = tk.IntVar(value=1)
        box16 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent16, offvalue=0, onvalue=1)
        box16.grid(row=3, column=6, sticky=tk.W+tk.E)

        checkboxent17 = tk.IntVar(value=1)
        box17 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent17, offvalue=0, onvalue=1)
        box17.grid(row=3, column=7, sticky=tk.W+tk.E)

        checkboxent18 = tk.IntVar(value=1)
        box18 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent18, offvalue=0, onvalue=1)
        box18.grid(row=3, column=8, sticky=tk.W+tk.E)

        checkboxent19 = tk.IntVar(value=1)
        box19 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent19, offvalue=0, onvalue=1)
        box19.grid(row=3, column=9, sticky=tk.W+tk.E)

        checkboxent20 = tk.IntVar(value=1)
        box20 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent20, offvalue=0, onvalue=1)
        box20.grid(row=3, column=10, sticky=tk.W+tk.E)

        checkboxent21 = tk.IntVar(value=1)
        box21 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent21, offvalue=0, onvalue=1)
        box21.grid(row=4, column=1, sticky=tk.W+tk.E)

        checkboxent22 = tk.IntVar(value=1)
        box22 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent22, offvalue=0, onvalue=1)
        box22.grid(row=4, column=2, sticky=tk.W+tk.E)

        checkboxent23 = tk.IntVar(value=1)
        box23 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent23, offvalue=0, onvalue=1)
        box23.grid(row=4, column=3, sticky=tk.W+tk.E)

        checkboxent24 = tk.IntVar(value=1)
        box24 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent24, offvalue=0, onvalue=1)
        box24.grid(row=4, column=4, sticky=tk.W+tk.E)

        checkboxent25 = tk.IntVar(value=1)
        box25 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent25, offvalue=0, onvalue=1)
        box25.grid(row=4, column=5, sticky=tk.W+tk.E)

        checkboxent26 = tk.IntVar(value=1)
        box26 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent26, offvalue=0, onvalue=1)
        box26.grid(row=4, column=6, sticky=tk.W+tk.E)

        checkboxent27 = tk.IntVar(value=1)
        box27 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent27, offvalue=0, onvalue=1)
        box27.grid(row=4, column=7, sticky=tk.W+tk.E)

        checkboxent28 = tk.IntVar(value=1)
        box28 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent28, offvalue=0, onvalue=1)
        box28.grid(row=4, column=8, sticky=tk.W+tk.E)

        checkboxent29 = tk.IntVar(value=1)
        box29 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent29, offvalue=0, onvalue=1)
        box29.grid(row=4, column=9, sticky=tk.W+tk.E)

        checkboxent30 = tk.IntVar(value=1)
        box30 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent30, offvalue=0, onvalue=1)
        box30.grid(row=4, column=10, sticky=tk.W+tk.E)

        checkboxent31 = tk.IntVar(value=1)
        box31 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent31, offvalue=0, onvalue=1)
        box31.grid(row=5, column=1, sticky=tk.W+tk.E)

        checkboxent32 = tk.IntVar(value=1)
        box32 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent32, offvalue=0, onvalue=1)
        box32.grid(row=5, column=2, sticky=tk.W+tk.E)

        checkboxent33 = tk.IntVar(value=1)
        box33 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent33, offvalue=0, onvalue=1)
        box33.grid(row=5, column=3, sticky=tk.W+tk.E)

        checkboxent34 = tk.IntVar(value=1)
        box34 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent34, offvalue=0, onvalue=1)
        box34.grid(row=5, column=4, sticky=tk.W+tk.E)

        checkboxent35 = tk.IntVar(value=1)
        box35 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent35, offvalue=0, onvalue=1)
        box35.grid(row=5, column=5, sticky=tk.W+tk.E)

        checkboxent36 = tk.IntVar(value=1)
        box36 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent36, offvalue=0, onvalue=1)
        box36.grid(row=5, column=6, sticky=tk.W+tk.E)

        checkboxent37 = tk.IntVar(value=1)
        box37 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent37, offvalue=0, onvalue=1)
        box37.grid(row=5, column=7, sticky=tk.W+tk.E)

        checkboxent38 = tk.IntVar(value=1)
        box38 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent38, offvalue=0, onvalue=1)
        box38.grid(row=5, column=8, sticky=tk.W+tk.E)

        checkboxent39 = tk.IntVar(value=1)
        box39 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent39, offvalue=0, onvalue=1)
        box39.grid(row=5, column=9, sticky=tk.W+tk.E)

        checkboxent40 = tk.IntVar(value=1)
        box40 = tk.Checkbutton(frame, font=("Arial", 18), variable=checkboxent40, offvalue=0, onvalue=1)
        box40.grid(row=5, column=10, sticky=tk.W+tk.E)

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
        left_frame = tk.Frame(main_container)
        main_container.add(left_frame)
        right_frame = tk.Frame(main_container, width=250)
        main_container.add(right_frame)
        right_frame.pack_propagate(False)
        main_container.paneconfig(left_frame, minsize=900)
        main_container.paneconfig(right_frame, minsize=250, width=250)

        control_panel = tk.LabelFrame(right_frame, text="Controls", font=("Arial", 12, "bold"))
        control_panel.pack(fill=tk.X, padx=5, pady=5)
        btn_frame = tk.Frame(control_panel)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        start_btn = tk.Button(btn_frame, text="Start Algorithm", font=("Arial", 12))
        start_btn.pack(fill=tk.X, padx=5, pady=2)
        view_btn = tk.Button(btn_frame, text="View Saved Schedule", font=("Arial", 12))
        view_btn.pack(fill=tk.X, padx=5, pady=2)

        filter_frame = tk.LabelFrame(right_frame, text="Filters", font=("Arial", 12, "bold"))
        filter_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        filter_var = tk.StringVar(value="all")
        for text, val in [
            ("Show All", "all"),
            ("Show Selected Subject", "subject"),
            ("Show Selected Teacher", "teacher"),
            ("Show Selected Student", "student")
        ]:
            tk.Radiobutton(filter_frame, text=text, variable=filter_var, value=val, font=("Arial", 10)).pack(anchor=tk.W)
        filter_listbox = tk.Listbox(filter_frame, selectmode=tk.SINGLE, font=("Arial", 10), height=8)
        filter_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.filter_subjects = []
        self.filter_teachers = []
        self.filter_students = []

        def repopulate_listbox():
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
            else:
                for name in sorted(self.filter_subjects):
                    filter_listbox.insert(END, name)

        filter_var.trace('w', lambda *_: repopulate_listbox())
        filter_listbox.bind('<<ListboxSelect>>', lambda *_: repopulate_listbox())

        validation_frame = tk.LabelFrame(right_frame, text="Validation Results", font=("Arial", 12, "bold"))
        validation_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        validation_text = tk.Text(validation_frame, font=("Courier", 10), height=8)
        validation_scroll = tk.Scrollbar(validation_frame, command=validation_text.yview)
        validation_text.configure(yscrollcommand=validation_scroll.set)
        validation_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        validation_text.pack(fill=tk.BOTH, expand=True)

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

        # Logging to capture from algorithm module
        class TextHandler(logging.Handler):
            def emit(self, record):
                msg = self.format(record)
                # you can insert msg into a Text widget here if desired

        text_handler = TextHandler()
        text_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger = logging.getLogger()
        # Only add the handler once to prevent duplicates
        if not any(isinstance(h, TextHandler) for h in logger.handlers):
            logger.addHandler(text_handler)

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

            # Format header differently for parallel sessions
            is_parallel = session.get('is_parallel', False)
            header_color = '#e0e0ff' if is_parallel else '#e0e0e0'
            header_text = f"{session['subject_name']} (G{session.get('group', 1)})"
            if is_parallel:
                header_text += " [P]"
                
            header = tk.Label(frame, text=header_text, font=("Arial", int(11*scale), "bold"), bg=header_color)
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
                        
                        # Filter out sessions with no students
                        sessions = [s for s in sessions if s.get('students')]
                        
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
            # Map subject IDs to names
            subj_list = get_subject()
            subj_map = { rec[0]: rec[1] for rec in subj_list }
            # Map teacher IDs to full names
            teach_list = get_teacher()
            teach_map = {}
            for rec in teach_list:
                tid = rec[0]
                first = rec[1]
                mid = rec[2]
                last = rec[3]
                if mid:
                    name = f"{first} {mid} {last}"
                else:
                    name = f"{first} {last}"
                teach_map[tid] = name

            validation_text.config(state='normal')
            validation_text.delete(1.0, tk.END)

            validation_text.insert(tk.END, "=== Validation Results ===\n\n")
            validation_text.insert(tk.END, "Conflicts:\n")
            validation_text.insert(tk.END, f"- Student conflicts: {stats['student_conflicts']}\n")
            validation_text.insert(tk.END, f"- Teacher conflicts: {stats['teacher_conflicts']}\n\n")

            validation_text.insert(tk.END, "Subject Hours:\n")
            for sid, scheduled in stats['subject_hours'].items():
                required = stats['required_hours'][sid]
                status = "✓" if scheduled == required else "✗"
                name = subj_map.get(sid, f"ID {sid}")
                validation_text.insert(tk.END, f"- {name}: {scheduled}/{required} {status}\n")

            validation_text.insert(tk.END, "\nTeacher Daily Loads:\n")
            for tid, loads in stats['teacher_daily_load'].items():
                name = teach_map.get(tid, f"ID {tid}")
                validation_text.insert(tk.END, f"- {name}:\n")
                for day, count in loads.items():
                    validation_text.insert(tk.END, f"  Day {day+1}: {count}\n")

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

                # Filter out sessions with no students
                for day in schedule_data.get('days', {}).values():
                    for period in day.values():
                        period[:] = [s for s in period if s.get('students')]

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

        def apply_filter(*args):
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
