import tkinter as tk
import webbrowser
#import customtkinter
 
class MainGUI:

    def __init__(self):

        self.window = tk.Tk()

        self.window.geometry("1280x720")
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
        creator = tk.Toplevel(self.window)  # creates a new window
        creator.title("Subjects")  # window title
        creator.resizable(False, False)  # prevents adjusting Width, Height
        creator.geometry("720x480")  # sets window size
        creator.grab_set()  # prevents interacting with previous window

        crebuttonframe = tk.Frame(creator)
        
        crebuttonframe.columnconfigure(0, weight=1)
        crebuttonframe.columnconfigure(1, weight=1)
        crebuttonframe.columnconfigure(2, weight=1)

        btn1 = tk.Button(crebuttonframe, text="Subjects", font=("Arial", 18), command=self.subjects)
        btn1.grid(row=0, column=0, sticky=tk.W+tk.E)

        btn2 = tk.Button(crebuttonframe, text="Classes", font=("Arial", 18), command=self.classes)
        btn2.grid(row=0, column=1, sticky=tk.W+tk.E)

        crebuttonframe.pack(fill="x")

        creator.mainloop()

    def classes(self):
        creator = tk.Toplevel(self.window) #creates a new window
        creator.title("Classes") #window title
        creator.resizable(False, False) #prevents adjusting Widht, Height
        creator.geometry("720x480") #sets window size
        creator.grab_set() #prevents interacting with previous window

    def classrooms(self):
        creator = tk.Toplevel(self.window) #creates a new window
        creator.title("Classrooms") #window title
        creator.resizable(False, False) #prevents adjusting Widht, Height
        creator.geometry("720x480") #sets window size
        creator.grab_set() #prevents interacting with previous window

    def teachers(self):
        creator = tk.Toplevel(self.window) #creates a new window
        creator.title("Teachers") #window title
        creator.resizable(False, False) #prevents adjusting Widht, Height
        creator.geometry("720x480") #sets window size
        creator.grab_set() #prevents interacting with previous window

MainGUI()