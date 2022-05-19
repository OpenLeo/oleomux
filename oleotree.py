from re import I
from oleomgr import oleomgr
from tkinter import Toplevel, Button, Scrollbar, Label, Frame
from ttkwidgets import CheckboxTreeview



class oleotree:
    '''
    Window to display the full message/signal tree as a treeview
    which can have whole messages or individual signals ticked

    Can also display a list of "senders/receivers" for filtering purposes
    '''
    select_all = False
    callback = None
    tree_type = "signal"
    
    def __init__(self, master, owner, callback, title = "Choose which to export", tree_type="signal", selection=0):
        self.owner = owner
        self.master = master
        self.callback = callback
        self.tree_type = tree_type
        self.items = []

        print(selection)

        if len(self.owner.omgr.messages) == 0:
            return

        self.win = Toplevel(master)
        self.win.wm_title(title)
        self.win.bind("<Destroy>",self.destroyed)
        self.win.geometry("400x500")

        self.win.rowconfigure(1, weight=1)
        self.win.columnconfigure(0, weight=1)

        if tree_type == "signal":
            self.message = Label(self.win, text="Select the messages and/or signals below")
            self.message.grid(row=0, column=0, columnspan=3)
        else:
            self.message = Label(self.win, text="Select the nodes to filter by")
            self.message.grid(row=0, column=0, columnspan=3)

        self.t = CheckboxTreeview(self.win, show="tree")
        self.t.grid(row=1, column=0,  columnspan=2, sticky="nesw")
        self.scrollbar = Scrollbar(self.win, orient="vertical", command=self.t.yview)
        self.scrollbar.grid(row=1, column=2, sticky="ns")
        self.t.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid_columnconfigure(2, minsize=10)

        

        if tree_type == "signal" or tree_type == "msg":
            self.indexes = []
            self.indexes.append((0,0))
            offset = 1
            message_count = 0

            #for each message
            for message in self.owner.omgr.messages:
                self.t.insert("", offset, offset, text = str(self.owner.omgr.to_hex(message)) + " - " + self.owner.omgr.messages[message].name)
                message_offset = offset
                self.indexes.append((message, -1))

                msg_selected = 0
                if (type(selection) is dict or type(selection) is list) and message in selection:
                    msg_selected = 1

                if msg_selected == 1 or selection == 1:
                    self.t.change_state(offset, "checked")
                
                offset += 1
                message_count += 1

                # only show messages
                if tree_type == "msg":
                    continue

                signal_offset = 0
                # for each signal in message
                for signal in self.owner.omgr.messages[message].signals:
                    sig_selected = 0
                    self.t.insert(message_offset, "end", offset, text = signal.name)
                    self.indexes.append((message, signal_offset))
                    offset += 1

                    if msg_selected == 1:
                        if selection[message] == 1:
                            sig_selected == 1
                        elif type(selection[message]) == dict or type(selection[message]) == list:
                            if signal_offset in selection[message]:
                                sig_selected = 1

                    signal_offset += 1
                    
                    if selection == 1 or sig_selected == 1:
                        self.t.change_state(offset, "checked")

            self.t.config(height=message_count - 1)
            self.item_count = offset
            self.message_count = message_count - 1
        else:
            items = []
            for message in self.owner.omgr.messages:
                if tree_type == "ecu_tx":
                    if self.owner.omgr.messages[message].senders is not None:
                        for sender in self.owner.omgr.messages[message].senders:
                            if sender not in items:
                                items.append(sender)

                if tree_type == "ecu_rx":
                    for signal in self.owner.omgr.messages[message].signals:
                        if signal.receivers is not None:
                            for receiver in signal.receivers:
                                if receiver not in items:
                                    items.append(receiver)

            ctr = 1
            items = sorted(items)
            for item in items:
                self.t.insert("", "end", ctr, text = item)

                if selection == 1 or ((type(selection) is dict or type(selection) is list) and item in selection):
                    self.t.change_state(ctr, "checked")

                ctr += 1
            self.item_count = ctr
            self.message_count = len(items) - 1
            self.items = items

        frame_a = Frame(self.win)

        if selection == 1:
            self.select_button = Button(frame_a, text="Deselect all", command=self.toggle_select)
            self.select_all = True
        else:
            self.select_button = Button(frame_a, text="Select all", command=self.toggle_select)
        self.select_button.grid(row=1, column = 0)
        self.go_button = Button(frame_a, text="Continue...", command=self.action_button)
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
        msg_id = None

        if self.tree_type == "signal" or self.tree_type == "msg":
            results = {}

            for item in self.t.get_children():
                msg_id = self.indexes[int(item)][0]

                if self.t.tag_has("checked", item):
                    results[msg_id] = []
                
                for item_c in self.t.get_children(item):
                    if self.t.tag_has("checked", item_c):
                        if msg_id not in results:
                            results[msg_id] = []
                        results[msg_id].append(self.indexes[int(item_c)][1])
        else:
            results = []
            for item in self.t.get_children():
                if self.t.tag_has("checked", item):
                    results.append(self.items[int(item)-1])

        self.win.destroy()

        if self.callback is not None:
            self.callback(results)


    def destroyed(self, *largs):
        pass