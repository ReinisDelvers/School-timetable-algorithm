import tkinter as tk
from tkinter import ttk, END
from tkinter.messagebox import showerror
import json
import pandas as pd

from data import add_student, add_subject, add_teacher, add_subject_student, add_subject_teacher, get_student, get_subject, get_teacher, get_subject_teacher, get_subject_student, remove_student, remove_subject, remove_teacher, remove_subject_teacher, remove_subject_student, update_student, update_subject, update_teacher, update_subject_teacher, update_subject_student

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

        self.menubar = tk.Menu(self.window)

        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Close", command=exit)        
        self.filemenu.add_separator()

        self.menubar.add_cascade(menu=self.filemenu, label="File")

        self.window.config(menu=self.menubar)

        self.frame = tk.Frame(self.window)
        
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.columnconfigure(3, weight=1)
        self.frame.columnconfigure(4, weight=1)
        self.frame.columnconfigure(5, weight=1)

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

        self.btn6 = tk.Button(self.frame, text="", font=("Arial", 18))
        self.btn6.grid(row=0, column=5, sticky=tk.W+tk.E, **options)

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
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
            except:
                showerror("Error", "Group number, number of hours per week, max hours per day, max student count per group need to be a number and min hours per day")
                return
            if name and group_number and number_of_hours_per_week and max_hours_per_day and max_student_count_per_group and min_hours_per_day:
                add_subject(name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day)
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
            ent1.insert(0, subject_list[selected1][1])
            ent2.insert(0, subject_list[selected1][2])
            ent3.insert(0, subject_list[selected1][3])
            ent4.insert(0, subject_list[selected1][4])
            ent5.insert(0, subject_list[selected1][5])
            ent6.insert(0, subject_list[selected1][6])
            selected_subject_id = subject_list[selected1][0]

        def subject_confirm_edit():
            nonlocal selected_subject_id
            name = ent1.get()
            group_number = ent2.get()
            number_of_hours_per_week = ent3.get()
            max_hours_per_day = ent4.get()
            max_student_count_per_group = ent5.get()
            min_hours_per_day = ent6.get()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
                int(max_student_count_per_group)
                int(min_hours_per_day)
            except:
                showerror("Error", "Group number, number of hours per week, max hours per day, max student count per group need to be a number and min hours per day")
                return
            if name and group_number and number_of_hours_per_week and max_hours_per_day and max_student_count_per_group and min_hours_per_day:
                if selected_subject_id != None:
                    update_subject(selected_subject_id, name, group_number, number_of_hours_per_week, max_hours_per_day, max_student_count_per_group, min_hours_per_day)
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
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)
        frame.columnconfigure(5, weight=1)
        frame.columnconfigure(6, weight=1)

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
            monday = checkboxent4.get()
            tuesday = checkboxent5.get()
            wednesday = checkboxent6.get()
            thursday = checkboxent7.get()
            if name and last_name:
                add_teacher(name, middle_name, last_name, monday, tuesday, wednesday, thursday)
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
            ent1.insert(0, teacher_list[selected1][1])
            ent2.insert(0, teacher_list[selected1][2])
            ent3.insert(0, teacher_list[selected1][3])
            checkboxent4.set(teacher_list[selected1][4])
            checkboxent5.set(teacher_list[selected1][5])
            checkboxent6.set(teacher_list[selected1][6])
            checkboxent7.set(teacher_list[selected1][7])
            selected_teacher_id = teacher_list[selected1][0]

        def teacher_confirm_edit():
            nonlocal selected_teacher_id
            name = ent1.get()
            middle_name = ent2.get()
            last_name = ent3.get()
            monday = checkboxent4.get()
            tuesday = checkboxent5.get()
            wednesday = checkboxent6.get()
            thursday = checkboxent7.get()
            if name and last_name:
                if selected_teacher_id != None:
                    update_teacher(selected_teacher_id, name, middle_name, last_name, monday, tuesday, wednesday, thursday)
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
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Name", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)

        label2 = tk.Label(frame, text="Middle name", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        label3 = tk.Label(frame, text="Last name", font=("Arial", 18))
        label3.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        label4 = tk.Label(frame, text="Monday", font=("Arial", 18))
        label4.grid(row=1, column=3, sticky=tk.W+tk.E, **options)

        label5 = tk.Label(frame, text="Tuesday", font=("Arial", 18))
        label5.grid(row=1, column=4, sticky=tk.W+tk.E, **options)

        label6 = tk.Label(frame, text="Wednesday", font=("Arial", 18))
        label6.grid(row=1, column=5, sticky=tk.W+tk.E, **options)

        label7 = tk.Label(frame, text="Thursday", font=("Arial", 18))
        label7.grid(row=1, column=6, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        ent3 = tk.Entry(frame,  font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        checkboxent4 = tk.IntVar(value=1)
        ent4 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent4, offvalue=0, onvalue=1)
        ent4.grid(row=2, column=3, sticky=tk.W+tk.E, **options)

        checkboxent5 = tk.IntVar(value=1)
        ent5 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent5, offvalue=0, onvalue=1)
        ent5.grid(row=2, column=4, sticky=tk.W+tk.E, **options)

        checkboxent6 = tk.IntVar(value=1)
        ent6 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent6, offvalue=0, onvalue=1)
        ent6.grid(row=2, column=5, sticky=tk.W+tk.E, **options)

        checkboxent7 = tk.IntVar(value=1)
        ent7 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent7, offvalue=0, onvalue=1)
        ent7.grid(row=2, column=6, sticky=tk.W+tk.E, **options)   

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
                showerror("Error", "Group number needs to be an integer.")
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
            #this
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
            #to this
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

            print(column_names)





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

        label6 = tk.Label(frame, text="Takes first excel column as student\nand all other as seperate subjects.", font=("Arial", 18))
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



MainGUI()