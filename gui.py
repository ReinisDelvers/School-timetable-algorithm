import tkinter as tk
from tkinter import ttk, END
from tkinter.messagebox import showerror

from data import add_student, add_subject, add_teacher, add_subject_student, add_subject_teacher, get_student, get_subject, get_teacher, get_subject_teacher, get_subject_teacherid, get_subject_student, get_subject_studentid, remove_student, remove_subject, remove_teacher, remove_subject_teacher, remove_subject_student, update_student, update_subject, update_teacher, update_subject_teacher, update_subject_student

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
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        def change_list():
            subject_list = get_subject()
            subject_listbox.delete(0, END)

            for i in range(len(subject_list)):
                subject_listbox.insert("end", f"{subject_list[i]}")

        def subject_add():
            name = ent1.get().capitalize()
            group_number = ent2.get()
            number_of_hours_per_week = ent3.get()
            max_hours_per_day = ent4.get()
            subject_list = get_subject()
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
            except:
                showerror("Error", "Group number, number of hours per week and max hours per day need to be a number")
                return
            for i in subject_list:
                if name == i[1]:
                    showerror("Error", "This subject already exists.")
                    return
            if name and group_number and number_of_hours_per_week and max_hours_per_day:
                add_subject(name, group_number, number_of_hours_per_week, max_hours_per_day)
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

        selected_subject_id = None

        def subject_edit():
            global selected_subject_id
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
            ent1.insert(0, subject_list[selected1][1])
            ent2.insert(0, subject_list[selected1][2])
            ent3.insert(0, subject_list[selected1][3])
            ent4.insert(0, subject_list[selected1][4])
            selected_subject_id = subject_list[selected1][0]
            change_list()

        def subject_confirm_edit():
            global selected_subject_id
            name = ent1.get().capitalize()
            group_number = ent2.get()
            number_of_hours_per_week = ent3.get()
            max_hours_per_day = ent4.get()
            subject_list = get_subject()
            
            try:
                int(group_number)
                int(number_of_hours_per_week)
                int(max_hours_per_day)
            except:
                showerror("Error", "Group number, number of hours per week and max hours per day need to be a number")
                return
            selected_subject_name = ""
            for i in subject_list:
                if selected_subject_id == i[0]:
                    selected_subject_name = i[1]
                    break
            for i in subject_list:
                if name == i[1] and not(name == selected_subject_name):
                    showerror("Error", "This subject already exists.")
                    return
            if name and group_number and number_of_hours_per_week and max_hours_per_day:
                if selected_subject_id != None:
                    update_subject(selected_subject_id, name, group_number, number_of_hours_per_week, max_hours_per_day)
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

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        ent3 = tk.Entry(frame,  font=("Arial", 18))
        ent3.grid(row=2, column=2, sticky=tk.W+tk.E, **options)

        ent4 = tk.Entry(frame,  font=("Arial", 18))
        ent4.grid(row=2, column=3, sticky=tk.W+tk.E, **options)    
        
        frame.pack(fill="x")

        subject_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        subject_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #TEACHER
    def teacher(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Teacher")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
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

        def change_list():
            teacher_list = get_teacher()
            teacher_listbox.delete(0, END)

            for i in range(len(teacher_list)):
                teacher_listbox.insert("end", f"{teacher_list[i]}")

        def teacher_add():
            name = ent1.get().capitalize()
            last_name = ent2.get().capitalize()
            monday = checkboxent3.get()
            tuesday = checkboxent4.get()
            wednesday = checkboxent5.get()
            thursday = checkboxent6.get()
            teacher_list = get_teacher()
            for i in teacher_list:
                if name == i[1] and last_name == i[2]:
                    showerror("Error", "This teacher already exists.")
                    return
            if name and last_name:
                add_teacher(name, last_name, monday, tuesday, wednesday, thursday)
            else:
                showerror("Error", "All fields must be filled out.")
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

        selected_teacher_id = None

        def teacher_edit():
            global selected_teacher_id
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
            ent1.insert(0, teacher_list[selected1][1])
            ent2.insert(0, teacher_list[selected1][2])
            checkboxent3.set(teacher_list[selected1][3])
            checkboxent4.set(teacher_list[selected1][4])
            checkboxent5.set(teacher_list[selected1][5])
            checkboxent6.set(teacher_list[selected1][6])
            selected_teacher_id = teacher_list[selected1][0]
            change_list()

        def teacher_confirm_edit():
            global selected_teacher_id
            name = ent1.get().capitalize()
            last_name = ent2.get().capitalize()
            monday = checkboxent3.get()
            tuesday = checkboxent4.get()
            wednesday = checkboxent5.get()
            thursday = checkboxent6.get()
            teacher_list = get_teacher()
            selected_teacher_name = ""
            selected_teacher_last_name = ""
            for i in teacher_list:
                if selected_teacher_id == i[0]:
                    selected_teacher_name = i[1]
                    selected_teacher_last_name = i[2]
                    break
            for i in teacher_list:
                if name == i[1] and last_name == i[2] and not (last_name == selected_teacher_last_name and name == selected_teacher_name):
                    showerror("Error", "This teacher already exists.")
                    return

            if name and last_name:
                if selected_teacher_id != None:
                    update_teacher(selected_teacher_id, name, last_name, monday, tuesday, wednesday, thursday)
                    selected_teacher_id = None
                else:
                    showerror("Error", "Select something to edit.")
                    return
            else:
                    showerror("Error", "All fields must be filled out.")
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

        label2 = tk.Label(frame, text="Last name", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        label3 = tk.Label(frame, text="Monday", font=("Arial", 18))
        label3.grid(row=1, column=2, sticky=tk.W+tk.E, **options)

        label4 = tk.Label(frame, text="Tuesday", font=("Arial", 18))
        label4.grid(row=1, column=3, sticky=tk.W+tk.E, **options)

        label5 = tk.Label(frame, text="Wednesday", font=("Arial", 18))
        label5.grid(row=1, column=4, sticky=tk.W+tk.E, **options)

        label6 = tk.Label(frame, text="Thursday", font=("Arial", 18))
        label6.grid(row=1, column=5, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)

        checkboxent3 = tk.IntVar(value=1)
        ent3 = tk.Checkbutton(frame,  font=("Arial", 18), variable=checkboxent3, offvalue=0, onvalue=1)
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

        frame.pack(fill="x")

        teacher_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        teacher_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #STUDENT
    def student(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Student")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        def change_list():
            student_list = get_student()
            student_listbox.delete(0, END)

            for i in range(len(student_list)):
                student_listbox.insert("end", f"{student_list[i]}")

        def student_add():
            name = ent1.get().capitalize()
            last_name = ent2.get().capitalize()
            student_list = get_student()
            for i in student_list:
                if name == i[1] and last_name == i[2]:
                    showerror("Error", "This student already exists.")
                    return
            if name and last_name:
                add_student(name, last_name)
            else:
                showerror("Error", "All fields must be filled out.")
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

        selected_student_id = None

        def student_edit():
            global selected_student_id
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
            ent1.insert(0, student_list[selected1][1])
            ent2.insert(0, student_list[selected1][2])
            selected_student_id = student_list[selected1][0]
            change_list()

        def student_confirm_edit():
            global selected_student_id
            name = ent1.get().capitalize()
            last_name = ent2.get().capitalize()
            student_list = get_student()
            selected_student_name = ""
            selected_student_last_name = ""
            for i in student_list:
                if selected_student_id == i[0]:
                    selected_student_name = i[1]
                    selected_student_last_name == i[2]
                    break
            for i in student_list:
                if name == i[1] and last_name == i[2] and not(name == selected_student_name and last_name == selected_student_last_name):
                    showerror("Error", "This student already exists.")
                    return
            if name and last_name:
                if selected_student_id != None:
                    update_student(selected_student_id, name, last_name)
                    selected_student_id = None
                else:
                    showerror("Error", "Select something to edit.")
                    return
            else:
                    showerror("Error", "All fields must be filled out.")
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

        label2 = tk.Label(frame, text="Last name", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        ent1 = tk.Entry(frame,  font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        ent2 = tk.Entry(frame,  font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        
        frame.pack(fill="x")

        student_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        student_listbox.pack(**options)   

        change_list()
        wind.mainloop()     


    #SUBJECT/TEACHER
    def subject_teacher(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subject/Teacher")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window
        
        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        def change_list():
            global optionent1 
            global optionent2
            vent1= []
            vent2 = []

            subject_teacher_list = get_subject_teacher()
            subject_list = get_subject()
            teacher_list = get_teacher()

            subject_teacher_listbox.delete(0, END)

            for item in subject_teacher_list:
                subject_teacher_listbox.insert("end", f"{item}")

            for item in subject_list:
                vent1.append(f"{item[1]}")
            for item in teacher_list:
                vent2.append(f"{item[1]} {item[2]}")
            
            optionent1 = vent1
            optionent2 = vent2

            if optionent1:
                optionmenuent1.set(optionent1[0])
            else:
                optionmenuent1.set("") 

            menu1 = ent1["menu"]
            menu1.delete(0, "end")
            for i in optionent1:
                menu1.add_command(label=i, command=lambda v=i: optionmenuent1.set(v))

            if optionent2:
                optionmenuent2.set(optionent2[0])
            else:
                optionmenuent2.set("")

            menu2 = ent2["menu"]
            menu2.delete(0, "end")
            for i in optionent2:
                menu2.add_command(label=i, command=lambda v=i: optionmenuent2.set(v))

        def subject_teacher_add():
            subject_list = get_subject()
            teacher_list = get_teacher()
            subject_name = optionmenuent1.get()
            teacher_name = optionmenuent2.get()
            subject_id = None
            group_number = None
            subject_teacher_list = get_subject_teacher()
            for i in subject_teacher_list:
                if subject_name == i[1] and teacher_name == f"{i[2]} {i[3]}":
                    showerror("Error", "This teacher/subject already exists.")
            for i in subject_list:
                if i[1] == subject_name:
                    subject_id = i[0]
                    group_number = i[2]
                    break
            teacher_id = None
            for i in teacher_list:
                if f"{i[1]} {i[2]}" == teacher_name:
                    teacher_id = i[0]
                    break

            add_subject_teacher(subject_id, teacher_id, group_number)
            change_list()
            


        def subject_teacher_remove():
            selected = list(subject_teacher_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            
            subject_teacher_list = get_subject_teacherid() 
            selected_id = [] 
            for i in selected:
                selected_id.append(subject_teacher_list[i][0])
            remove_subject_teacher(selected_id)
            
            change_list()

        selected_subject_teacher_id = None

        def subject_teacher_edit():
            global selected_subject_teacher_id
            selected = list(subject_teacher_listbox.curselection())
            
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            
            selected1=selected[0]
            subject_teacher_list = get_subject_teacher() 
            selected_subject_teacher_id = subject_teacher_list[selected[0]][0]
            optionmenuent1.set(subject_teacher_list[selected1][1])
            optionmenuent2.set(f"{subject_teacher_list[selected1][2]} {subject_teacher_list[selected1][3]}")
        


        def subject_teacher_confirm_edit():
            global selected_subject_teacher_id
            subject_name = optionmenuent1.get()
            teacher_name = optionmenuent2.get()
            subject_list = get_subject()
            teacher_list = get_teacher()
            subject_teacher_list = get_subject_teacher()
            selected_teacher_name = ""
            selected_subject_name = ""
            for i in subject_teacher_list:
                if selected_subject_teacher_id == i[0]:
                    selected_subject_name = i[1]
                    selected_teacher_name = f"{i[2]} {i[3]}"
            for i in subject_teacher_list:
                if subject_name == i[1] and teacher_name == f"{i[2]} {i[3]}" and not(subject_name == selected_subject_name and teacher_name == selected_teacher_name):
                    showerror("Error", "This teacher/subject already exists.")
            subject_id = None
            for i in subject_list:
                if i[1] == subject_name:
                    subject_id = i[0]
                    break
            teacher_id = None
            for i in teacher_list:
                if f"{i[1]} {i[2]}" == teacher_name:
                    teacher_id = i[0]
                    break
            
            if selected_subject_teacher_id != None:
                update_subject_teacher(selected_subject_teacher_id, subject_id, teacher_id)
                selected_subject_teacher_id = None
            else:
                showerror("Error", "Select something to edit.")
                return
            
            change_list()

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

        optionent1 = []
        optionmenuent1 = tk.StringVar() 
        ent1 = tk.OptionMenu(frame, optionmenuent1, optionent1)
        ent1.config(font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        optionent2 = []
        optionmenuent2 = tk.StringVar() 
        ent2 = tk.OptionMenu(frame, optionmenuent2, optionent2)
        ent2.config(font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        
        frame.pack(fill="x")

        subject_teacher_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        subject_teacher_listbox.pack(**options)   

        change_list()
        wind.mainloop()


    #SUBJECT/STUDENT
    def subject_student(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subject/Student")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("1280x800")  # sets window size
        wind.grab_set()  # prevents interacting with previous window
        
        frame = tk.Frame(wind)
        frame.grid(row=0, column=0)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        def change_list():
            global optionent1 
            global optionent2
            vent1= []
            vent2 = []

            subject_student_list = get_subject_student()
            subject_list = get_subject()
            student_list = get_student()

            subject_student_listbox.delete(0, END)

            for item in subject_student_list:
                subject_student_listbox.insert("end", f"{item}")

            for item in subject_list:
                vent1.append(f"{item[1]}")
            for item in student_list:
                vent2.append(f"{item[1]} {item[2]}")
            
            optionent1 = vent1
            optionent2 = vent2

            if optionent1:
                optionmenuent1.set(optionent1[0])
            else:
                optionmenuent1.set("") 

            menu1 = ent1["menu"]
            menu1.delete(0, "end")
            for i in optionent1:
                menu1.add_command(label=i, command=lambda v=i: optionmenuent1.set(v))

            if optionent2:
                optionmenuent2.set(optionent2[0])
            else:
                optionmenuent2.set("")

            menu2 = ent2["menu"]
            menu2.delete(0, "end")
            for i in optionent2:
                menu2.add_command(label=i, command=lambda v=i: optionmenuent2.set(v))

        def subject_student_add():
            subject_list = get_subject()
            student_list = get_student()
            subject_name = optionmenuent1.get()
            student_name = optionmenuent2.get()
            subject_id = None
            group_number = None
            subject_student_list = get_subject_student()
            for i in subject_student_list:
                if subject_name == i[1] and student_name == f"{i[2]} {i[3]}":
                    showerror("Error", "This student/subject already exists.")
            for i in subject_list:
                if i[1] == subject_name:
                    subject_id = i[0]
                    group_number = i[2]
                    break
            student_id = None
            for i in student_list:
                if f"{i[1]} {i[2]}" == student_name:
                    student_id = i[0]
                    break

            add_subject_student(subject_id, student_id)
            change_list()
            


        def subject_student_remove():
            selected = list(subject_student_listbox.curselection())
            if not selected:
                showerror("Error", "Select something to remove.")
                return
            
            subject_student_list = get_subject_studentid() 
            selected_id = [] 
            for i in selected:
                selected_id.append(subject_student_list[i][0])
            remove_subject_student(selected_id)
            
            change_list()

        selected_subject_student_id = None

        def subject_student_edit():
            global selected_subject_student_id
            selected = list(subject_student_listbox.curselection())
            
            if not selected:
                showerror("Error", "Select something to edit.")
                return
            elif len(selected) > 1:
                showerror("Error", "Select only one to edit.")
                return
            
            selected1=selected[0]
            subject_student_list = get_subject_student() 
            selected_subject_student_id = subject_student_list[selected[0]][0]
            optionmenuent1.set(subject_student_list[selected1][1])
            optionmenuent2.set(f"{subject_student_list[selected1][2]} {subject_student_list[selected1][3]}")
        


        def subject_student_confirm_edit():
            global selected_subject_student_id
            subject_name = optionmenuent1.get()
            student_name = optionmenuent2.get()
            subject_list = get_subject()
            student_list = get_student()
            subject_student_list = get_subject_student()
            selected_student_name = ""
            selected_subject_name = ""
            for i in subject_student_list:
                if selected_subject_student_id == i[0]:
                    selected_subject_name = i[1]
                    selected_student_name = f"{i[2]} {i[3]}"
            for i in subject_student_list:
                if subject_name == i[1] and student_name == f"{i[2]} {i[3]}" and not(subject_name == selected_subject_name and student_name == selected_student_name):
                    showerror("Error", "This student/subject already exists.")
            subject_id = None
            for i in subject_list:
                if i[1] == subject_name:
                    subject_id = i[0]
                    break
            student_id = None
            for i in student_list:
                if f"{i[1]} {i[2]}" == student_name:
                    student_id = i[0]
                    break
            
            if selected_subject_student_id != None:
                update_subject_student(selected_subject_student_id, subject_id, student_id)
                selected_subject_student_id = None
            else:
                showerror("Error", "Select something to edit.")
                return
            
            change_list()

        btn1 = tk.Button(frame, text="Add", font=("Arial", 18), command=subject_student_add)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E, **options)

        btn2 = tk.Button(frame, text="Remove", font=("Arial", 18), command=subject_student_remove)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E, **options)

        btn3 = tk.Button(frame, text="Edit", font=("Arial", 18), command=subject_student_edit)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E, **options)

        btn4 = tk.Button(frame, text="Confirm edit", font=("Arial", 18), command=subject_student_confirm_edit)
        btn4.grid(row=0, column=3, sticky=tk.W+tk.E, **options)

        label1 = tk.Label(frame, text="Subject", font=("Arial", 18))
        label1.grid(row=1, column=0, sticky=tk.W+tk.E, **options)

        label2 = tk.Label(frame, text="Student", font=("Arial", 18))
        label2.grid(row=1, column=1, sticky=tk.W+tk.E, **options)

        optionent1 = []
        optionmenuent1 = tk.StringVar() 
        ent1 = tk.OptionMenu(frame, optionmenuent1, optionent1)
        ent1.config(font=("Arial", 18))
        ent1.grid(row=2, column=0, sticky=tk.W+tk.E, **options)

        optionent2 = []
        optionmenuent2 = tk.StringVar() 
        ent2 = tk.OptionMenu(frame, optionmenuent2, optionent2)
        ent2.config(font=("Arial", 18))
        ent2.grid(row=2, column=1, sticky=tk.W+tk.E, **options)
        
        frame.pack(fill="x")

        subject_student_listbox = tk.Listbox(wind, selectmode=tk.EXTENDED, height=self.window.winfo_height(), width=self.window.winfo_width(), font=("Arial", 18))
        subject_student_listbox.pack(**options)   

        change_list()
        wind.mainloop()   



MainGUI()