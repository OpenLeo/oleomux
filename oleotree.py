from oleomgr import oleomgr
from tkinter import Toplevel, Frame, Button
from ttkwidgets import CheckboxTreeview


class oleotree:
    
    def __init__(self, master):

        self.win = Toplevel(master)
        self.win.wm_title("Message tree for export")
        self.win.bind("<Destroy>",self.destroyed)

        self.tvf = Frame(self.win)
        self.tvf.pack()

        t = CheckboxTreeview(self.tvf, show="tree")
        t.pack(anchor="n")
        t.insert("", 0, "1", text="1")
        t.insert("1", "end", "11", text="1")
        t.insert("1", "end", "12", text="2")
        t.insert("12", "end", "121", text="1")
        t.insert("12", "end", "122", text="2")
        t.insert("122", "end", "1221", text="1")
        t.insert("1", "end", "13", text="3")
        t.insert("13", "end", "131", text="1")

        self.go_button = Button(self.tvf, text="Export...")
        self.go_button.pack(anchor="s")

    def destroyed(self, *largs):
        pass