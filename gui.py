import tkinter as tk
 
class MyGUI:

    def __init__(self):

        self.window = tk.Tk()

        self.window.geometry("1280x720")
        self.window.title("School timetable algorithm")

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

        self.btn5 = tk.Button(self.buttonframe, text="a", font=("Arial", 18))
        self.btn5.grid(row=0, column=4, sticky=tk.W+tk.E)

        self.btn6 = tk.Button(self.buttonframe, text="a", font=("Arial", 18))
        self.btn6.grid(row=0, column=5, sticky=tk.W+tk.E)

        self.buttonframe.pack(fill="x")

        self.window.mainloop()
        
    def subjects(self):
        print("sub")

    def classes(self):
        print("cla")

    def classrooms(self):
        print("cle")

    def teachers(self):
        print("tea")

MyGUI()