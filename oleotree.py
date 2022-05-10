from oleomgr import oleomgr
from tkinter import Toplevel, Button, Scrollbar, Label, Frame
from ttkwidgets import CheckboxTreeview


class oleotree:
    select_all = False
    callback = None
    
    def __init__(self, master, owner, callback):
        self.owner = owner
        self.master = master
        self.callback = callback

        if len(self.owner.omgr.messages) == 0:
            return

        self.win = Toplevel(master)
        self.win.wm_title("Message tree for export")
        self.win.bind("<Destroy>",self.destroyed)
        self.win.geometry("400x500")

        self.win.rowconfigure(1, weight=1)
        self.win.columnconfigure(0, weight=1)

        self.message = Label(self.win, text="Select the messages and/or signals below")
        self.message.grid(row=0, column=0, columnspan=3)

        self.t = CheckboxTreeview(self.win, show="tree")
        self.t.grid(row=1, column=0,  columnspan=2, sticky="nesw")
        self.scrollbar = Scrollbar(self.win, orient="vertical", command=self.t.yview)
        self.scrollbar.grid(row=1, column=2, sticky="ns")
        self.t.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid_columnconfigure(2, minsize=10)

        self.indexes = []
        self.indexes.append((0,0))
        offset = 1
        message_count = 0
        for message in self.owner.omgr.messages:
            self.t.insert("", offset, offset, text = str(self.owner.omgr.to_hex(message)) + " - " + self.owner.omgr.messages[message].name)
            message_offset = offset
            self.indexes.append((message, -1))
            offset += 1
            message_count += 1

            signal_offset = 0
            for signal in self.owner.omgr.messages[message].signals:
                self.t.insert(message_offset, "end", offset, text = signal.name)
                self.indexes.append((message, signal_offset))
                offset += 1
                signal_offset += 1

        self.t.config(height=message_count - 1)
        self.item_count = offset
        self.message_count = message_count - 1

        frame_a = Frame(self.win)
        self.select_button = Button(frame_a, text="Select all", command=self.toggle_select)
        self.select_button.grid(row=1, column = 0)
        self.go_button = Button(frame_a, text="Export...", command=self.action_button)
        self.go_button.grid(row=1, column=1)
        frame_a.grid(row=2, column=0, sticky="nesw")


    def toggle_select(self):
        '''
        Called when user presses select/deselect all
        '''
        state = "checked"

        if self.select_all:
            # deselect all
            self.select_button.configure(text="Select all")
            self.select_all = False
            state = "unchecked"
        
        else:
            self.select_button.configure(text = "Deselect all")
            self.select_all = True
        
        for i in range(1, self.item_count):
            self.t.change_state(i, state)

    
    def action_button(self):
        '''
        '''
        results = {}
        msg_id = None

        for item in self.t.get_children():
            msg_id = self.indexes[int(item)][0]

            if self.t.tag_has("checked", item):
                results[msg_id] = []
            
            for item_c in self.t.get_children(item):
                if self.t.tag_has("checked", item_c):
                    if msg_id not in results:
                        results[msg_id] = []
                    results[msg_id].append(self.indexes[int(item_c)][1])

        if self.callback is not None:
            self.callback(results)


    def destroyed(self, *largs):
        pass