from cantools.database.can.signal import NamedSignalValue
from tkinter import END, Canvas, Scrollbar, Spinbox, Tk, Text, Label, Button, Entry, filedialog, StringVar, Menu, Frame, SUNKEN, W, DISABLED, NORMAL, Toplevel, BooleanVar, IntVar, DoubleVar, messagebox
from tkinter.ttk import Combobox, Treeview
import cantools

class signal_editor:
    '''
    WINDOW DEFINITION
    Subwindow to edit signal properties
    '''
    created = False
    visible = False
    
    user_title = "dictionary"
    dict_input = {}
    callback = None

    active_ref = -1
    active_dic = -1
    created = 0

    choice_editor = None

    txt = {}
    lbl = []
    svs = {}


    def __init__(self, window_master, application, user_title, mid, sid):
        self.master = window_master
        self.app = application
        self.mid = mid
        self.sid = sid
        self.user_title = user_title
        self.app.log("DCE", "Generate signal editor UI - " + str(user_title))
        self.createWin()


    def createWin(self):
        '''
        Create and populate the UI instance
        '''
        if not self.created:          
            self.win = Toplevel(self.master)
            self.win.wm_title("Edit signal - " + str(self.user_title))
            self.win.bind("<Destroy>",self.destroyed)

            info = Label(self.win, text="Add information in the boxes below")
            info.grid(row=1, column=1, columnspan=1)

            self.lbl = []
            self.field = []
            sig: cantools.database.can.Signal = self.app.omgr.messages[self.mid].signals[self.sid]

            self.svs["bits"] = StringVar(value=self.app.omgr.yml_bits_encode(sig, output_mode = self.app.bit_display_mode))
            self.svs["name"] = StringVar(value=sig.name)
            #self.svs["comment"] = sig.comment
            self.svs["min"] = DoubleVar(value=sig.minimum)
            self.svs["max"] = DoubleVar(value=sig.maximum)
            self.svs["factor"] = DoubleVar(value=sig.scale)
            self.svs["offset"] = DoubleVar(value=sig.offset)
            self.svs["receivers"] = StringVar(value=",".join(sig.receivers))
            self.svs["choices"] = self.app.omgr.txt_choices_encode(sig)
            self.svs["units"] = StringVar(value=sig.unit)
            self.svs["signed"] = IntVar(value=sig.is_signed)

            self.lbl.append(Label(self.win, text="Bits"))
            self.field.append(Entry(self.win, text = self.svs["bits"]))

            self.lbl.append(Label(self.win, text="Name"))
            self.field.append(Entry(self.win, text = self.svs["name"], width=50))

            comment_fields = self.app.omgr.yml_comment_encode(sig.comment)

            self.svs["name_en"] =  StringVar(value=comment_fields["name_en"])
            self.svs["comment_en"] = comment_fields["comment_en"]
            self.svs["comment_fr"] = comment_fields["comment_fr"]
            self.svs["src"] = comment_fields["src"]

            self.lbl.append(Label(self.win, text="Name (EN)"))
            self.field.append(Entry(self.win, text = self.svs["name_en"], width=50))

            self.lbl.append(Label(self.win, text="Comment (EN)"))
            self.comment_field_en = Text(self.win, height=2, width=50)
            self.field.append(self.comment_field_en)
            self.field[-1].insert(END, str(self.svs["comment_en"]))

            self.lbl.append(Label(self.win, text="Comment (FR)"))
            self.comment_field_fr = Text(self.win, height=2, width=50)
            self.field.append(self.comment_field_fr)
            self.field[-1].insert(END, str(self.svs["comment_fr"]))

            self.lbl.append(Label(self.win, text="Min"))
            self.field.append(Spinbox(self.win, text = self.svs["min"]))

            self.lbl.append(Label(self.win, text="Max"))
            self.field.append(Spinbox(self.win, text = self.svs["max"]))

            self.lbl.append(Label(self.win, text="Signed"))
            self.field.append(Spinbox(self.win, text = self.svs["signed"], from_=0, to=1))

            self.lbl.append(Label(self.win, text="Factor"))
            self.field.append(Spinbox(self.win, text = self.svs["factor"]))

            self.lbl.append(Label(self.win, text="Offset"))
            self.field.append(Spinbox(self.win, text = self.svs["offset"]))

            self.lbl.append(Label(self.win, text="Units"))
            self.field.append(Entry(self.win, text = self.svs["units"]))

            self.lbl.append(Label(self.win, text="Receivers"))
            self.field.append(Entry(self.win, text = self.svs["receivers"]))

            self.lbl.append(Label(self.win, text="Values"))

            columns = ('Value', 'Name', 'Comment')
            self.chc_frame = Frame(self.win)
            self.choice_tree = Treeview(self.chc_frame, columns=columns, show='headings')
            self.choice_tree.heading('Value', text='Value')
            self.choice_tree.heading('Name', text='Name')
            self.choice_tree.heading('Comment', text='Comment')
            self.choice_tree.column('Value', width=60)
            self.choice_tree.pack(side='left', fill='both')
            self.choice_tree.bind("<Double-1>", self.edit_choice)
            self.chc_vsb =  Scrollbar(self.chc_frame, orient="vertical", command=self.choice_tree.yview)
            self.chc_vsb.pack(side='right', fill='y')
            self.choice_tree.configure(yscrollcommand=self.chc_vsb.set)
            self.field.append(self.chc_frame)

            self.reload_choices()

            cnt = 2
            for lbl in self.lbl:
                lbl.grid(row = cnt, column = 1)
                self.field[cnt - 2].grid(sticky="W", row = cnt, column = 2)
                cnt += 1
        
            cnt += 1

            saveopen = Button(self.win, text="Apply", command=self.save)
            saveclose = Button(self.win, text="Save & Close", command=self.saveclose)
            saveopen.grid(row=cnt, column=1, columnspan=1)
            saveclose.grid(row=cnt, column=2, columnspan=1)
            self.win.grid_columnconfigure(1, minsize=120)
            self.win.grid_columnconfigure(2, minsize=120)

            self.created = 1
    

    def edit_choice(self, event, *largs):
        '''
        Open the signal choice editor
        '''
        clicked = self.choice_tree.identify('item',event.x,event.y)

        if clicked == None or clicked == "":
            # make a new one
            new_choice = len(self.app.omgr.messages[self.mid].signals[self.sid].choices)
            self.app.omgr.messages[self.mid].signals[self.sid].choices[new_choice] = NamedSignalValue(new_choice, "New choice " + str(new_choice), {})
            self.reload_choices()
            self.choice_editor = choice_editor(self.master, self.app, self, "Edit new choice value", self.mid, self.sid, new_choice)
            return

        cid = int(clicked) - 1
        self.choice_editor = choice_editor(self.master, self.app, self, str(self.app.omgr.messages[self.mid].signals[self.sid].choices[cid]), self.mid, self.sid, cid)


    def reload_choices(self):
        '''
        Reload the choice list when one gets changed
        '''
        choices = self.app.omgr.messages[self.mid].signals[self.sid].choices

        if choices is None:
            return
        if len(choices) == 0:
            return

        for item in self.choice_tree.get_children():
            self.choice_tree.delete(item)

        for chc in choices:
            if type(choices[chc]) == NamedSignalValue:
                this_chc = (chc, choices[chc].name, choices[chc].comments)
            else:
                this_chc = (chc, choices[chc], "")

            self.choice_tree.insert('', "end", int(chc) + 1, values=this_chc)


    def save(self):
        '''
        Write modifications to signal definition
        '''
        start, lng = self.app.omgr.yml_bits_decode(self.svs["bits"].get(), input_mode = self.app.bit_display_mode)

        self.app.omgr.messages[self.mid].signals[self.sid].start = start
        self.app.omgr.messages[self.mid].signals[self.sid].length = lng
        self.app.omgr.messages[self.mid].signals[self.sid].name = self.svs["name"].get()

        comments_collection = {}
        comments_collection["comment_en"] = self.comment_field_en.get("1.0", "end-1c")
        comments_collection["comment_fr"] = self.comment_field_fr.get("1.0", "end-1c")
        comments_collection["name_en"] = self.svs["name_en"].get()
        comments_collection["src"] = self.svs["src"]            # not user editable, atm

        comments_joined = self.app.omgr.yml_comment_decode(comments_collection)

        self.app.omgr.messages[self.mid].signals[self.sid].comment = comments_joined
        self.app.omgr.messages[self.mid].signals[self.sid].min = self.svs["min"].get()
        self.app.omgr.messages[self.mid].signals[self.sid].max = self.svs["max"].get()
        self.app.omgr.messages[self.mid].signals[self.sid].scale = self.svs["factor"].get()
        self.app.omgr.messages[self.mid].signals[self.sid].offset = self.svs["offset"].get()
        self.app.omgr.messages[self.mid].signals[self.sid].receivers = self.svs["receivers"].get().split(",")
        self.app.omgr.messages[self.mid].signals[self.sid].is_signed = self.svs["signed"].get()
        # self.app.messages[self.mid].signals[self.sid].choices = xx

        self.app.reload_signal_ui()
    
    def saveclose(self):
        '''
        '''
        self.save()
        self.win.destroy()


    def destroyed(self, *largs):
        '''
        Reset the existence pointer
        '''
        self.created = 0
        if self.choice_editor is not None:
            if self.choice_editor.created == 1:
                self.choice_editor.win.destroy()



class choice_editor:
    created = 0
    svs = {}
    lbl = []
    field = []

    def __init__(self, window_master, application, signal_editor, user_title, mid, sid, cid):
        self.master = window_master
        self.app = application
        self.mid = mid
        self.sid = sid
        self.cid = cid
        self.sig_editor = signal_editor
        self.user_title = user_title
        self.app.log("DCE", "Generate choice editor UI - " + str(user_title))
        self.createWin()


    def createWin(self):
        '''
        Create and populate the UI instance
        '''
        if not self.created:          
            self.win = Toplevel(self.master)
            self.win.wm_title("Edit signal value - " + str(self.user_title))
            self.win.bind("<Destroy>",self.destroyed)

            info = Label(self.win, text="Add information in the boxes below")
            info.grid(row=1, column=1, columnspan=1)

            self.lbl = []
            self.field = []
            chc = self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid]

            self.svs["value"] = IntVar(value=self.cid)
            self.svs["name"] = StringVar(value=chc.name)

            self.lbl.append(Label(self.win, text="Value"))
            self.field.append(Entry(self.win, text = self.svs["value"]))

            self.lbl.append(Label(self.win, text="Name"))
            self.field.append(Entry(self.win, text = self.svs["name"], width=50))

            comment_fields = self.app.omgr.yml_comment_encode(chc.comments)

            self.svs["name_en"] =  StringVar(value=comment_fields["name_en"])
            self.svs["comment_en"] = comment_fields["comment_en"]
            self.svs["comment_fr"] = comment_fields["comment_fr"]
            self.svs["src"] = comment_fields["src"]

            self.lbl.append(Label(self.win, text="Name (EN)"))
            self.field.append(Entry(self.win, text = self.svs["name_en"], width=50))

            self.lbl.append(Label(self.win, text="Comment (EN)"))
            self.comment_field_en = Text(self.win, height=2, width=50)
            self.field.append(self.comment_field_en)
            self.field[-1].insert(END, str(self.svs["comment_en"]))

            self.lbl.append(Label(self.win, text="Comment (FR)"))
            self.comment_field_fr = Text(self.win, height=2, width=50)
            self.field.append(self.comment_field_fr)
            self.field[-1].insert(END, str(self.svs["comment_fr"]))

            cnt = 2
            for lbl in self.lbl:
                lbl.grid(row = cnt, column = 1)
                self.field[cnt - 2].grid(sticky="W", row = cnt, column = 2)
                cnt += 1

            delete_btn = Button(self.win, text="Delete", command=self.delete_choice)
            delete_btn.grid(row=cnt, column=1, columnspan=1)
            saveclose = Button(self.win, text="Save & Close", command=self.saveclose)
            saveclose.grid(row=cnt, column=2, columnspan=1)
            self.win.grid_columnconfigure(1, minsize=120)
            self.win.grid_columnconfigure(2, minsize=120)

            self.created = 1
    


    def save(self):
        '''
        Write modifications to CHOICE definition
        '''

        # make sure the signal choices have a NamedSignalValue type
        if type(self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid]) != NamedSignalValue:
            self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid] = NamedSignalValue(self.cid, self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid], "")

        if self.svs["value"].get() != self.cid:
            self.app.omgr.messages[self.mid].signals[self.sid].choices.pop(self.cid, 0)
            self.cid = self.svs["value"].get()
            self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid] = NamedSignalValue(self.cid, "", "")

        self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid].name = self.svs["name"].get()

        comments_collection = {}
        comments_collection["comment_en"] = self.comment_field_en.get("1.0", "end-1c")
        comments_collection["comment_fr"] = self.comment_field_fr.get("1.0", "end-1c")
        comments_collection["name_en"] = self.svs["name_en"].get()
        comments_collection["src"] = self.svs["src"]            # not user editable, atm

        comments_joined = self.app.omgr.yml_comment_decode(comments_collection)

        self.app.omgr.messages[self.mid].signals[self.sid].choices[self.cid].comments = comments_joined

        self.app.reload_signal_ui()
        self.sig_editor.reload_choices()


    def delete_choice(self):
        '''
        Remove the choice
        '''
        try:
            self.app.omgr.messages[self.mid].signals[self.sid].choices.pop(self.cid)
        except:
            self.log("Failed to delete signal choice")
            messagebox.showerror(title="Sacre bleu", message="Failed to delete signal choice")

        self.sig_editor.reload_choices()
        self.win.destroy()
        
    
    def saveclose(self):
        '''
        '''
        self.save()
        self.win.destroy()


    def destroyed(self, *largs):
        '''
        Reset the existence pointer
        '''
        self.created = 0

    


