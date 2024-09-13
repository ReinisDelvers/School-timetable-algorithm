import tkinter as tk
 
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

        self.buttonframe = tk.Frame(self.window)
        
        self.buttonframe.columnconfigure(0, weight=1)
        self.buttonframe.columnconfigure(1, weight=1)
        self.buttonframe.columnconfigure(2, weight=1)
        self.buttonframe.columnconfigure(3, weight=1)
        self.buttonframe.columnconfigure(4, weight=1)
        self.buttonframe.columnconfigure(5, weight=1)

        self.btn1 = tk.Button(self.buttonframe, text="Subjects", font=("Arial", 18), command=self.subjects)
        self.btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        self.btn2 = tk.Button(self.buttonframe, text="Classes", font=("Arial", 18), command=self.classes)
        self.btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        self.btn3 = tk.Button(self.buttonframe, text="Classrooms", font=("Arial", 18), command=self.classrooms)
        self.btn3.grid(row=0, column=2, sticky=tk.W+tk.E)

        self.btn4 = tk.Button(self.buttonframe, text="Teachers", font=("Arial", 18), command=self.teachers)
        self.btn4.grid(row=0, column=3, sticky=tk.W+tk.E)

        self.btn5 = tk.Button(self.buttonframe, text="", font=("Arial", 18))
        self.btn5.grid(row=0, column=4, sticky=tk.W+tk.E)

        self.btn6 = tk.Button(self.buttonframe, text="", font=("Arial", 18))
        self.btn6.grid(row=0, column=5, sticky=tk.W+tk.E)

        self.buttonframe.pack(fill="x")

        self.window.mainloop()
    

    def subjects(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subjects")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("720x480")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=1)
        buttonframe.columnconfigure(2, weight=1)

        btn1 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.subjectsadd)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Button(buttonframe, text="Edit", font=("Arial", 18), command=self.subjectsedit)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        
        btn3 = tk.Button(buttonframe, text="Remove", font=("Arial", 18), command=self.subjectsremove)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E)


        buttonframe.pack(fill="x")

        wind.mainloop()

    def subjectsadd(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subjects")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("720x480")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=2)

        btn1 = tk.Label(buttonframe, text="Subjects title", font=("Arial", 18))
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Entry(buttonframe,  font=("Arial", 18))
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        
        btn3 = tk.Label(buttonframe, text="Subjects short", font=("Arial", 18))
        btn3.grid(row=1, column=0, sticky=tk.W+tk.E)

        btn4 = tk.Entry(buttonframe,  font=("Arial", 18))
        btn4.grid(row=1, column=1, sticky=tk.W+tk.E)

        btn5 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.subjectsave)
        btn5.grid(row=2, column=0, sticky=tk.W+tk.E)

        buttonframe.pack(fill="x")

        wind.mainloop()

    def subjectsave(self):
        print("a")

    def subjectsedit(self):
        print("a.1")
    
    def subjectsremove(self):
        print("a.2")

    def classes(self):
        wind = tk.Toplevel(self.window) #creates a new window
        wind.title("Classes") #window title
        wind.resizable(False, False) #prevents adjusting Widht, Height
        wind.geometry("720x480") #sets window size
        wind.grab_set() #prevents interacting with previous window
        
        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=1)
        buttonframe.columnconfigure(2, weight=1)

        btn1 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.classesadd)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Button(buttonframe, text="Edit", font=("Arial", 18), command=self.classesedit)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        
        btn3 = tk.Button(buttonframe, text="Remove", font=("Arial", 18), command=self.classesremove)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E)


        buttonframe.pack(fill="x")

        wind.mainloop()

    def classesadd(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subjects")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("720x480")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=2)

        btn1 = tk.Label(buttonframe, text="Clases title", font=("Arial", 18))
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Entry(buttonframe,  font=("Arial", 18))
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        btn3 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.classessave)
        btn3.grid(row=2, column=0, sticky=tk.W+tk.E)

        buttonframe.pack(fill="x")

        wind.mainloop()

    def classessave(self):
        print("b")
    
    def classesedit(self):
        print("b.1")
    
    def classesremove(self):
        print("b.2")

    def classrooms(self):
        wind = tk.Toplevel(self.window) #creates a new window
        wind.title("Classrooms") #window title
        wind.resizable(False, False) #prevents adjusting Widht, Height
        wind.geometry("720x480") #sets window size
        wind.grab_set() #prevents interacting with previous window
        
        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=1)
        buttonframe.columnconfigure(2, weight=1)

        btn1 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.classroomsadd)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Button(buttonframe, text="Edit", font=("Arial", 18), command=self.classroomsedit)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        
        btn3 = tk.Button(buttonframe, text="Remove", font=("Arial", 18), command=self.classroomsremove)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E)


        buttonframe.pack(fill="x")

        wind.mainloop()

    def classroomsadd(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subjects")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("720x480")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=2)

        btn1 = tk.Label(buttonframe, text="Classrooms title", font=("Arial", 18))
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Entry(buttonframe,  font=("Arial", 18))
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        btn3 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.classroomssave)
        btn3.grid(row=2, column=0, sticky=tk.W+tk.E)

        buttonframe.pack(fill="x")

        wind.mainloop()

    def classroomssave(self):
        print("c")
    
    def classroomsedit(self):
        print("c.1")
    
    def classroomsremove(self):
        print("c.2")
  
    def teachers(self):
        wind = tk.Toplevel(self.window) #creates a new window
        wind.title("Teachers") #window title
        wind.resizable(False, False) #prevents adjusting Widht, Height
        wind.geometry("720x480") #sets window size
        wind.grab_set() #prevents interacting with previous window
        
        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=1)
        buttonframe.columnconfigure(2, weight=1)

        btn1 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.teachersadd)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Button(buttonframe, text="Edit", font=("Arial", 18), command=self.teachersedit)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        
        btn3 = tk.Button(buttonframe, text="Remove", font=("Arial", 18), command=self.teachersremove)
        btn3.grid(row=0, column=2, sticky=tk.W+tk.E)


        buttonframe.pack(fill="x")

        wind.mainloop()

    def teachersadd(self):
        wind = tk.Toplevel(self.window)  # creates a new window
        wind.title("Subjects")  # window title
        wind.resizable(False, False)  # prevents adjusting Width, Height
        wind.geometry("720x480")  # sets window size
        wind.grab_set()  # prevents interacting with previous window

        buttonframe = tk.Frame(wind)
        
        buttonframe.columnconfigure(0, weight=1)
        buttonframe.columnconfigure(1, weight=2)

        btn1 = tk.Label(buttonframe, text="Teachers name", font=("Arial", 18))
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Entry(buttonframe,  font=("Arial", 18))
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        btn3 = tk.Button(buttonframe, text="Add", font=("Arial", 18), command=self.teacherssave)
        btn3.grid(row=2, column=0, sticky=tk.W+tk.E)

        buttonframe.pack(fill="x")

        wind.mainloop()

    def teacherssave(self):
        print("d")
    
    def teachersedit(self):
        print("d.1")
    
    def teachersremove(self):
        print("d.2")
    
    

MainGUI()