from tkinter import END, Canvas, Scrollbar, Spinbox, Tk, Text, Label, Button, Entry, filedialog, StringVar, Menu, Frame, SUNKEN, W, DISABLED, NORMAL, Toplevel, BooleanVar, IntVar, messagebox
from tkinter.simpledialog import askstring
from tkinter.ttk import Combobox, Treeview
from typing import OrderedDict

from cantools.database.can.signal import NamedSignalValue

from source_handler import CandumpHandler, InvalidFrame, CANHandler, SerialHandler, ArdLogHandler
from recordclass import recordclass

from functools import partial
import cantools, pprint, serial, can, csv, numexpr, threading, sys, traceback, time, serial.tools.list_ports
from os import listdir
from os.path import isfile, join

from oleomgr import oleomgr
from oleotree import oleotree

#   ###########################################################################
#
#   CAN Logger, Visualiser and Property Editor 
#   (c) 2020 - 2022 OpenLeo.org -  @ld
#   - Parses custom CSV-based file format to store message properties
#   - Visualise live CAN data or process a historic log file
#
#   Uses code from:
#   - canmonitor by alexandreblin (MIT)
#   - uses cantools (MIT)
#
#   Uses CAN message data compiled from:
#   - 207 project by alexandreblin 
#   - OpenLEO databases
#   - contributors to autowp.github.io documentation
#   - EMU Projects own research
#
#   The software will accept either raw serial input from the accompanying
#   Arduino sketch, or a dump file previously created from that sketch
#
#   The timestamp and bus are optional, but you cannot have bus without timestamp
#   
#   Sim/Dump Format: timestamp bus can_id bytes ...
#
# ##############################################################################

# hex_id, formal_name, friendly_name (en/fr), transmitter(s), receiver(s) (list of int names), signals (list of can_def)
msg_def = ["msg_def", "id name label_en label_fr tx rx signals"]

# hex_id, bitpos, formal_name, friendly_name (en/fr), factor, offset, if_special_func, current_value, unit, states (list of can_state), min, max
sig_def = ["can_def", "hex ref offset lenbi name label_en label_fr formula factor f_offset special value unit states min max"]

# raw_value (bin), friendly name (en/fr)
sig_state = ["can_state", "value label_en label_fr"]


def make_dict(d_src):
    out = {}
    src = d_src[1].split(" ")
    for key in src:
        if key == "signals" or key == "states":
            out[key] = []
        else:
            out[key] = ""
    return out


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
            self.svs["min"] = IntVar(value=sig.minimum)
            self.svs["max"] = IntVar(value=sig.maximum)
            self.svs["factor"] = IntVar(value=sig.scale)
            self.svs["offset"] = IntVar(value=sig.offset)
            self.svs["receivers"] = StringVar(value=",".join(sig.receivers))
            self.svs["choices"] = self.app.omgr.txt_choices_encode(sig)
            self.svs["units"] = StringVar(value=sig.unit)

            self.lbl.append(Label(self.win, text="Bits"))
            self.field.append(Entry(self.win, text = self.svs["bits"]))

            self.lbl.append(Label(self.win, text="Name"))
            self.field.append(Entry(self.win, text = self.svs["name"], width=50))

            comment_fields = self.app.omgr.yml_comment_encode(sig.comment)

            self.svs["name_en"] =  StringVar(comment_fields["name_en"])
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

        self.choice_tree.delete(*self.choice_tree.get_children())

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


class message_editor:
    '''
    WINDOW DEFINITION
    Subwindow to edit message properties
    '''
    created = False
    visible = False
    
    user_title = "dictionary"
    dict_input = {}
    callback = None

    active_ref = -1
    active_dic = -1
    created = 0

    txt = {}
    lbl = []
    svs = {}


    def __init__(self, window_master, application, user_title, mid):
        self.master = window_master
        self.app = application
        self.mid = mid
        self.user_title = user_title
        self.app.log("DCE", "Generate dictionary editor UI - " + str(user_title))
        self.createWin()

    def createWin(self):
        '''
        Create and populate the UI instance
        '''
        if not self.created:          
            self.win = Toplevel(self.master)
            self.win.wm_title("Edit - " + str(self.user_title))
            self.win.bind("<Destroy>",self.destroyed)

            info = Label(self.win, text="Add information in the boxes below")
            info.grid(row=1, column=1, columnspan=1)

            self.lbl = []
            self.field = []
            msg: cantools.database.can.Message = self.app.omgr.messages[self.mid]

            id = "0x" + str(self.app.omgr.to_hex(msg.frame_id))

            self.svs["id"] = StringVar(value=id)
            self.svs["name"] = StringVar(value=msg.name)
            self.svs["length"] = IntVar(value=msg.length)
            self.svs["comment"] = str(msg.comment)
            self.svs["periodicity"] = IntVar(value=msg.cycle_time)
            self.svs["senders"] = StringVar(value=",".join(msg.senders))
            self.svs["signals"] = len(msg.signals)
            #self.svs["receivers"] = StringVar(",".join(msg.receivers))

            self.lbl.append(Label(self.win, text="Frame ID"))
            self.field.append(Label(self.win, text = self.svs["id"].get()))

            self.lbl.append(Label(self.win, text="Name"))
            self.field.append(Entry(self.win, text = self.svs["name"]))

            self.lbl.append(Label(self.win, text="Length"))
            self.field.append(Spinbox(self.win, text = self.svs["length"]))


            comment_fields = self.app.omgr.yml_comment_encode(msg.comment)
            self.svs["name_en"] =  StringVar(comment_fields["name_en"])
            self.svs["comment_en"] = comment_fields["comment_en"]
            self.svs["comment_fr"] = comment_fields["comment_fr"]
            self.svs["src"] = comment_fields["src"]

            self.lbl.append(Label(self.win, text="Name (EN)"))
            self.field.append(Entry(self.win, text = self.svs["name_en"]))

            self.lbl.append(Label(self.win, text="Comment (EN)"))
            self.comment_field_en = Text(self.win, height=2, width=30)
            self.field.append(self.comment_field_en)
            self.field[-1].insert(END, str(self.svs["comment_en"]))

            self.lbl.append(Label(self.win, text="Comment (FR)"))
            self.comment_field_fr = Text(self.win, height=2, width=30)
            self.field.append(self.comment_field_fr)
            self.field[-1].insert(END, str(self.svs["comment_fr"]))

            self.lbl.append(Label(self.win, text="Periodicity"))
            self.field.append(Spinbox(self.win, text = self.svs["periodicity"], state="disabled"))

            self.lbl.append(Label(self.win, text="Senders"))
            self.field.append(Entry(self.win, text = self.svs["senders"], state="disabled"))

            self.lbl.append(Label(self.win, text="Signals"))
            self.field.append(Label(self.win, text = str(self.svs["signals"])))

            cnt = 2
            for lbl in self.lbl:
                lbl.grid(row = cnt, column = 1)
                self.field[cnt - 2].grid(sticky="W", row = cnt, column = 2)
                cnt += 1

            saveopen = Button(self.win, text="Apply", command=self.save)
            saveclose = Button(self.win, text="Save & Close", command=self.saveclose)
            saveopen.grid(row=cnt, column=1, columnspan=1)
            saveclose.grid(row=cnt, column=2, columnspan=1)
            self.win.grid_columnconfigure(1, minsize=120)
            self.win.grid_columnconfigure(2, minsize=120)

            self.created = 1
    


    def save(self):
        '''
        Write modifications to message definition
        '''
        try:
            self.app.omgr.messages[self.mid].frame_id = int(self.svs["id"].get(), 16)
        except:
            pass

        self.app.omgr.messages[self.mid].name = self.svs["name"].get()
        self.app.omgr.messages[self.mid].length = self.svs["length"].get()

        comments_collection = {}
        comments_collection["comment_en"] = self.comment_field_en.get("1.0", "end-1c")
        comments_collection["comment_fr"] = self.comment_field_fr.get("1.0", "end-1c")
        comments_collection["name_en"] = self.svs["name_en"].get()
        comments_collection["src"] = self.svs["src"]            # not user editable, atm

        comments_joined = self.app.omgr.yml_comment_decode(comments_collection)

        self.app.omgr.messages[self.mid].comment = comments_joined
        
        # -- TODO: These are missing "setter" functions in cantools upstream
        self.app.omgr.messages[self.mid].senders = self.svs["senders"].get().split(",")
        self.app.omgr.messages[self.mid].cycle_time = self.svs["periodicity"].get()

        self.app.reload_msg_list()

    
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



# One row of boxes for a given property definition
class CANDef:
    #owner: oleomux = None

    # ref is the id of this CANDef within the current displayed ones
    # dic is the id of this CANDef inside the dictionary of message definitions
    def __init__(self, master, owner, sid, mid):
        # in this overview we show only
        # offset, name, label, value, unit, min, max

        print("[CDE] Create new row "+ str(mid) + ":" + str(sid))
        self.mid = mid
        self.sid = sid
        self.owner = owner

        self.strValue = StringVar()
        self.ref = Entry(self.owner.scrollable_frame, width=7)
        self.ref.insert(0, self.owner.omgr.yml_bits_encode(self.owner.omgr.messages[mid].signals[sid], output_mode=self.owner.bit_display_mode))
        self.ref.configure(disabledbackground="white", disabledforeground="black", state='readonly')

        self.name = Entry(self.owner.scrollable_frame)
        self.name.insert(0, self.owner.omgr.messages[mid].signals[sid].name)
        self.name.configure(state="readonly", disabledbackground="white", disabledforeground="black")

        comment_fields = self.owner.omgr.yml_comment_encode(self.owner.omgr.messages[mid].signals[sid].comment)

        self.label_en = Entry(self.owner.scrollable_frame, width=20)
        self.label_en.insert(0, comment_fields["name_en"])
        self.label_en.configure(disabledbackground="white", disabledforeground="black", state="readonly")

        self.value = Entry(self.owner.scrollable_frame, textvariable=self.strValue, state='readonly', width=20)
        self.strValue.set("")

        self.unit = Entry(self.owner.scrollable_frame, width=12, )

        if self.owner.omgr.messages[mid].signals[sid].unit is not None:
            self.unit.insert(0, self.owner.omgr.messages[mid].signals[sid].unit)   
        else:
            self.unit.insert(0, "")   
        
        self.unit.configure(disabledbackground="white", disabledforeground="black", state='readonly')

        self.min = Entry(self.owner.scrollable_frame, width=8)
        self.max = Entry(self.owner.scrollable_frame, width=8, state='readonly')

        if self.owner.omgr.messages[mid].signals[sid].minimum is not None:
            self.min.insert(0, self.owner.omgr.messages[mid].signals[sid].minimum)   
        else:
            self.min.insert(0, "--")  

        if self.owner.omgr.messages[mid].signals[sid].maximum is not None:
            self.max.insert(0, self.owner.omgr.messages[mid].signals[sid].maximum)   
        else:
            self.max.insert(0, "--")  

        self.min.configure(disabledbackground="white", disabledforeground="black", state='readonly')
        self.max.configure(disabledbackground="white", disabledforeground="black", state='readonly')

        act = partial(self.owner.edit_signal, self.mid, self.sid)
        self.save = Button(self.owner.scrollable_frame, text="[]", command=act)

        act_del = partial(self.owner.delete_signal, self.mid, self.sid)
        self.dele = Button(self.owner.scrollable_frame, text="X", command=act_del)

        z = 6 + self.sid

        owner.frame.grid(row=7 + self.sid, column=0, columnspan=10, sticky="ew")

        self.ref.grid(column=1, row=z)
        self.name.grid(column=2, row=z)
        self.label_en.grid(column=3, row=z)
        self.value.grid(column=4, row=z)
        self.unit.grid(column=5, row=z)
        self.min.grid(column=6, row=z)
        self.max.grid(column=7, row=z)
        self.save.grid(column=8, row=z)
        self.dele.grid(column=9, row=z)


    def update(self, msg):
        '''
        Update the "value"
        '''
        self.strValue.set(self.owner.can_to_formatted(msg, self.mid, self.sid))


    def destroy(self):
        self.ref.destroy()
        self.name.destroy()
        self.label_en.destroy()
        self.value.destroy()
        self.unit.destroy()
        self.save.destroy()  
        self.min.destroy()
        self.max.destroy()    
        self.dele.destroy()


class oleomux:

    USE_CAN = 1
    USE_SERIAL = 2

    MSGDEF = 1
    SIGDEF = 2
    STADEF = 3

    conn = USE_CAN
    messageMap = None
    
    types = []
    ids = []
    messages = {}

    win_mprops = None
    win_sprops = None

    omgr: oleomgr = None
    lang = "en"

    bit_display_mode = 0

    overview_cmbs_messages = []
    overview_cmbs_signals = []
    overview_output_textboxs = []
    overview_output_svars = []
    overview_unit_svars = []
    overview_messages_subscribed = []
    overview_selected_signal = []
    overview_unit_textboxs = []


    def log(self, ma, msg = None):
        if msg is None:
            print("[OMG] " + str(ma))
        else:
            print(str(ma) + " " + str(msg))

    def importYAMLfile(self):
        '''
        Import a single YAML file
        '''
        f = filedialog.askopenfilename(initialdir = "", 
                                                    title = "Select a CAN definition file", 
                                                    filetypes = (("CAN Message Descriptors", 
                                                                    "*.yml*"), 
                                                                ("all files", 
                                                                    "*.*"))) 
        if f == ():
            return

        file_list = [f]
        self.omgr.import_from_yaml(file_list)
        self.log("Loaded " + str(len(self.omgr.messages)) + " messages from YAML file")
        self.reload_internal_from_omgr()

    def update_progress(self, item_count, index, *largs):
        self.status['text'] = "Processing " + str(index) + " / " + str(item_count)
        self.master.update()
        

    def importYAMLfolder(self):
        '''
        Import all YAML files in a chosen folder
        '''
        fd = filedialog.askdirectory(initialdir = "", 
                                                    title = "Select a folder of YAML definitions")
        if fd == () or fd is None:
            return

        file_list = [(fd + "/" + f) for f in listdir(fd) if isfile(join(fd, f))]
        self.omgr.import_from_yaml(file_list, callback = partial(self.update_progress, len(file_list)))
        self.reload_internal_from_omgr()
    

    def saveYAMLall(self):
        '''
        Show a tickbox view of all the loaded messages
        to choose which ones to export to YAML (or all)
        '''
        olt = oleotree(self.master, self, self.saveYAMLchosen, "Choose messages or signals to export to YAML")


    def saveYAMLchosen(self, results):
        '''
        Actually do the export
        '''
        if len(results) > 0:
            fd = filedialog.askdirectory(initialdir = "", 
                                                    title = "Select a folder to export to")
            if fd == () or fd is None:
                return

            result = self.omgr.export_to_yaml(fd, results)
            if result:
                messagebox.showinfo(title="OK", message="Export to YAML done!")
            else:
                messagebox.showerror(title="Oh no!", message="The export could not be completed.")

        else:
            messagebox.showwarning(title="Nope", message="No messages selected for export!")
            return


    def saveYAMLselected(self):
        '''
        Export the currently selected message to YAML
        '''
        fname = filedialog.asksaveasfile(title = "Choose filename for export to YAML...",
                                        filetypes = (("YAML files", 
                                                                    "*.yml*"), 
                                                                ("all files", 
                                                                    "*.*"))) 
        if fname == () or fname == None:
            return

        result = self.omgr.export_to_yaml(fname.name, self.active_message)
        if result:
            messagebox.showinfo(title="OK", message="Export to YAML done!")
        else:
            messagebox.showerror(title="Oh no!", message="The export could not be completed.")


    def exportCaction(self, results):
        '''
        Actually do the export
        '''
        fname = filedialog.asksaveasfile(title = "Choose filename for export to C...",
                                        filetypes = (("C files", "*.c*"), 
                                                     ("all files", "*.*"))) 
        if fname == ():
            return

        h_file = str(fname.name).replace(".c", "").split("/")[-1]

        self.omgr.export_to_struct(h_file, results)
        self.omgr.export_parser_c(h_file, results)

        result = True

        if result:
            messagebox.showinfo(title="OK", message="Export done to " + str(h_file))
        else:
            messagebox.showerror(title="Oh no!", message="The export could not be completed.")
        

    def exportCoptions(self):
        '''
        Show a tickbox view of all the loaded messages
        to choose which ones to export to C
        '''
        olt = oleotree(self.master, self, self.exportCaction, "Choose messages or signals to export to C")
        

    def importDBC(self):
        '''
        Import a DBC
        '''
        f = filedialog.askopenfilename(initialdir = "", 
                                                    title = "Select a CAN database", 
                                                    filetypes = (("CAN Message Database", 
                                                                    "*.dbc*"), 
                                                                ("all files", 
                                                                    "*.*"))) 
        if f == ():
            return

        if not self.omgr.import_from_dbc(f):
            self.log("DBC load cancelled")
            return
        self.log("Loaded " + str(len(self.omgr.messages)) + " messages from DBC file")
        self.reload_internal_from_omgr()

    
    def clean(self):
        self.omgr.clean()
        self.reload_internal_from_omgr()

    
    def reload_internal_from_omgr(self):
        '''
        Regenerate combo boxes and internal message
        table based on contents of OMGR
        '''
        self.message_names = []
        self.message_ids = []
        self.message_ints = []

        for message in self.omgr.messages:
            self.message_ids.append(self.omgr.to_hex(message, 3))
            self.message_ints.append(message)
            self.message_names.append(self.omgr.messages[message].name)

        if len(self.message_names) > 0:
            self.messageType['values'] = self.message_names
            self.messageID['values'] = self.message_ids
        else:
            self.messageType['values'] = ["Choose..."]
            self.messageID['values'] = ["Choose..."]
            
        self.messageType.current(0)
        self.messageID.current(0)

        if len(self.message_names) > 0:
            self.CANChangeMsgType()
            self.CANChangeFields()
        else:
            self.CANChangeFields()

    
    def bit_display_toggle(self, new_mode):
        self.bit_display_mode = new_mode
        self.reload_signal_ui()
        

    # Init window
    def __init__(self, master):
        self.omgr = oleomgr()
        self.bit_display_mode = self.omgr.MODE_OLEO

        self.active_message = 0
        self.active_message_index = 0
        self.active_message_old = 0

        self.port = None
        self.master = master
        self.CAN_list = []
        self.serial_connex = False
        self.can_connex = False
        self.IDcurrent = 0
        self.hexIDcurrent = 0
        self.simDelayMs =  1
        self.sim_ok = False
        self.reading_thread = None

        self.win_msg_editor = None
        self.win_sig_editor = None

        master.title("OpenLEO CAN database manager")

        self.winView = None
        self.menubar = Menu(master)
        filemenu = Menu(self.menubar)

        filemenu.add_command(label="Import DBC", command=self.importDBC)
        filemenu.add_separator()
        filemenu.add_command(label="Import YAML (file)", command=self.importYAMLfile)
        filemenu.add_command(label="Import YAML (folder)", command=self.importYAMLfolder)
        filemenu.add_command(label="Export YAML (multiple)", command=self.saveYAMLall)
        filemenu.add_command(label="Export YAML (only selected)", command=self.saveYAMLselected)
        
        filemenu.add_command(label="Export C Code...", command=self.exportCoptions)
        self.menubar.add_cascade(label= "File", underline=0, menu= filemenu)

        createWin = master.register(self.createOverview)
 
        self.menubar.add_command(label="Overview", command=createWin)
        master.config(menu=self.menubar)
    
        self.bus_conf = BooleanVar()
        self.bus_is = BooleanVar()
        self.bus_car = BooleanVar()


        toolsmenu = Menu(self.menubar)
        #self.menubar.add_command(label="Load CAN Map", command=self.loadCSV)  
        toolsmenu.add_command(label="Clear loaded messages", command=self.clean)  
        toolsmenu.add_command(label="Load CAN Sim", command=self.loadSim)
        toolsmenu.add_separator()
        self.bit_type = IntVar(master)
        self.bit_type.set(self.omgr.MODE_OLEO)
        toolsmenu.add_radiobutton(label="OpenLEO bit numbering", var=self.bit_type, value=self.omgr.MODE_OLEO, command=partial(self.bit_display_toggle, self.omgr.MODE_OLEO))
        toolsmenu.add_radiobutton(label="Logical bit numbering", var=self.bit_type, value=self.omgr.MODE_CANT, command=partial(self.bit_display_toggle, self.omgr.MODE_CANT))

        #self.menubar.add_command(label="Save CAN Map", command=self.saveCSV)
        self.menubar.add_cascade(label= "Tools", underline=0, menu= toolsmenu)


        self.com_type = Menu(self.menubar)
        self.contype = IntVar(master)
        self.contype.set(self.USE_CAN)
        self.com_type.add_radiobutton(label="Serial", var=self.contype, value=self.USE_SERIAL, command=self.SerialEnable)
        self.com_type.add_radiobutton(label="SocketCAN", var=self.contype, value=self.USE_CAN, command=self.CANEnable)
        self.menubar.add_cascade(label="Comms", menu=self.com_type)

        ################# ROW 1 ###########################

        self.label = Label(master, text="COM Port:")
        self.label.grid(column=1, row=1, columnspan=1)

        self.serial_frame = Frame(master)

        self.serialBus = Entry(self.serial_frame, text="500kbps", width=10)
        self.serialBus.grid(column=2,row=1)

        lis = serial.tools.list_ports.comports()
        self.com_ports = []
        opts = []
        for item in lis:
            self.com_ports.append(item[0])
            opts.append(str(item[0]) + " - " + str(item[1]))

        self.serialPort = Combobox(self.serial_frame, values = opts)
        self.serialPort.grid(column=1,row=1)
        self.serialPort.current(0)
        self.serialPort.bind("<<ComboboxSelected>>", self.COMPortChange)
        self.serialPort['state'] = DISABLED

        self.serial_frame.grid(column=2, row=1, columnspan=2)
        self.connex = Button(self.serial_frame, text=">", command=self.connexion)
        self.connex.grid(column=4, row=1, columnspan=1)

        # Hex converter utility
        self.label = Label(master, text="Hex Convert:")
        self.label.grid(column=4, row=1, columnspan=1)
        self.calc_frame = Frame(master)
        hexcal = master.register(self.hexcal)
        self.calc_frame.grid(column=5, row=1, columnspan=1)
        self.calc = Entry(self.calc_frame, validate="key", validatecommand=(hexcal, '%P'), width=5)
        self.calc.grid(column=1, row=1, columnspan=1)
        self.calc_out = StringVar()
        self.calc_outb = StringVar()
        self.calc_res = Entry(self.calc_frame, textvariable=self.calc_out, state='readonly', width=5)
        self.calc_res.grid(column=2, row=1, columnspan=1)
        self.calc_bin = Entry(master, textvariable=self.calc_outb, state='readonly', width=8)
        self.calc_bin.grid(column=6, row=1, columnspan=1)

        # note the delay is applied inside the Sim source_handler
        # so is totally ignored in Serial mode
        scmd = master.register(self.simDelayTime)
        self.simFrame = Frame(master)
        self.simLabel = Label(self.simFrame, text="Sim Speed:")
        self.simLabel.grid(column=1, row=1, columnspan=1)
        self.simFrame.grid(column=7, row=1, columnspan=1)
        self.simDelay = Entry(self.simFrame, validate="focusout", validatecommand=(scmd, '%P'), width=5)
        self.simDelay.insert(0, str(self.simDelayMs))
        self.simDelay.grid(column=2, row=1, columnspan=1)

        self.simStart = Button(master, text=">", command=self.startSim)
        self.simStart.grid(column=8, row=1, columnspan=1)

        ############### ROW 2 #############################

        # choose message names & IDs boxes
        messageDefault = StringVar(master)
        messageDefault.set("Choose...") # default value
        self.lbl_msg = Label(master, text="Choose message:")
        self.lbl_msg.grid(column=1, row=2, columnspan=1)
        self.messageType = Combobox(master, values = ["Choose..."])
        self.messageType.grid(column=2, row=2, columnspan=1)
        self.messageID = Combobox(master, values = ["Choose..."])
        self.messageID.grid(column=3, row=2, columnspan=1)
        self.messageType.bind("<<ComboboxSelected>>", self.CANChangeMsgType)
        self.messageID.bind("<<ComboboxSelected>>", self.CANChangeMsgID)

        self.addDef = Button(master, text="New Def", command=self.addDefinition)
        self.addDef.grid(column=5, row=2, columnspan=1)
        self.addDef['state'] = DISABLED

        self.addMsg = Button(master, text="New Msg", command=self.addMessage)
        self.addMsg.grid(column=6, row=2, columnspan = 1)
        #self.addMsg['state'] = DISABLED

        self.renameMsg = Button(master, text="Edit Msg", command=self.editMessage)
        self.renameMsg.grid(column=7, row=2, columnspan=1)
        #self.renameMsg['state'] = DISABLED

        self.delMsg = Button(master, text="Delete Msg", command=self.deleteMessage)
        self.delMsg.grid(column=8, row=2, columnspan=1)
        #self.delMsg['state'] = DISABLED

        self.lab_hex = []
        self.lab_bin = []
        for x in range(0,8):
            self.lab_hex.append(Label(master, text="----", fg="white", bg="blue"))
            self.lab_hex[x].grid(row=3,column=x+1)
            self.lab_hex[x].config(font=("Monospace", 14))
            self.lab_bin.append(Label(master, text="--------"))
            self.lab_bin[x].grid(row=4,column=x+1)
            self.lab_bin[x].config(font=("Monospace", 12))

        self.canFields = []
        self.canLabels = ["Bit Pos", "Name", "Name (EN)", "Calc Value", "Unit", "Min", "Max", "Edit", "Delete" ]
        self.cl = []
        y = 1

        container = Frame(master)
        canvas = Canvas(container)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = Frame(canvas)
        self.scrollable_frame.bind(
                        "<Configure>",
                        lambda e: canvas.configure(
                            scrollregion=canvas.bbox("all")
                        )
                    )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for x in self.canLabels:
            self.cl.append(Label(self.scrollable_frame, text=x, state=DISABLED))
            self.cl[-1].grid(row=0, column=y)
            y = y + 1

        for x in range(1, 9):
            self.scrollable_frame.grid_columnconfigure(x, minsize=90)

        
        container.grid(row=5, column=1, columnspan=10, sticky='nesw')
        canvas.grid(row=0, column=0, sticky='nesw')
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        scrollbar.grid(row=0, column=1, sticky="ns")

        master.rowconfigure(5, weight=1)
        master.columnconfigure(1, weight=1)

        #print("Columns" + str(y-1))
        self.frame = Frame(master)
        self.status = Label(self.frame, text="Ready.", bd=1, relief=SUNKEN, anchor=W)
        self.status.pack(fill="both", expand=True)
        self.frame.grid(row=6, column=0, columnspan=10, sticky="sew")


    def COMPortChange(self, *largs):
        self.port = self.com_ports[self.serialPort.current()]


    def editMessage(self):
        '''
        Show window to let user edit message properties
        '''
        if len(self.omgr.messages) == 0 or self.active_message == 0:
            return

        if self.win_msg_editor is None:
            self.win_msg_editor = message_editor(self.master, self, self.omgr.messages[self.active_message].name, self.active_message)
        else:
            if self.win_msg_editor.created == 0:
                self.win_msg_editor = message_editor(self.master, self, self.omgr.messages[self.active_message].name, self.active_message)


    def deleteMessage(self):
        '''
        Delete a whole message
        '''
        if self.active_message == 0:
            return

        # don't allow deleting a message open in the editor (or a signal open in editor)
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                if self.win_sig_editor.mid == self.active_message:
                    return False
        
        if self.win_msg_editor is not None:
            if self.win_msg_editor.created == 1:
                if self.win_sig_editor.mid == self.active_message:
                    return False

        self.omgr.messages.pop(self.active_message, 0)
        self.active_message -= 1
        if self.active_message < 0:
            self.active_message = 0
        
        self.CANChangeMsgType()


    def deleteSignal(self, ref):
        '''
        Delete a signal
        '''
        if self.active_message == 0:
            return

        # don't allow deleting a signal which is open in the editor
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                if self.win_sig_editor.mid == self.active_message and self.win_sig_editor.sid == ref:
                    return False

        self.omgr.messages[self.active_message].signals.pop(ref)
        self.CANChangeFields(False)



    def SerialEnable(self):
        self.serialPort['state'] = NORMAL
        self.conn = self.USE_SERIAL

    def CANEnable(self):
        self.serialPort['state'] = DISABLED
        self.conn = self.USE_CAN

    # Connect/Disconnect from Arduino
    def connexion(self):
        if self.conn == self.USE_SERIAL:
            if not self.serial_connex: 
                try:        
                    self.port = self.com_ports[self.serialPort.current()]
                    print("[SER] Connect to " + self.port)
                    baud = 115200
                    self.source_handler = SerialHandler(self.port, baudrate=baud, bus=self.serialBus.get(), veh=self.serialVeh.get())
                    # If reading from a serial device, it will be opened with timeout=0 (non-blocking read())
                    self.source_handler.open()

                    self.connex.configure(text="Disconnexion")
                    
                    self.startThread()
                    self.serial_connex = True
                    self.serialBus['state'] = 'readonly'
                    self.serialPort['state'] = 'readonly'
                except:
                    print("[SER] Connexion failed")
                    self.status['text'] = "Connexion to serial port failed"
            else:
                self.serialBus['state'] = 'normal'
                self.serialPort['state'] = 'normal'

        elif self.conn == self.USE_CAN:
            if not self.can_connex:
                try:
                    
                    self.source_handler = CANHandler(bus=self.serialBus.get(), veh=self.serialVeh.get())
                    self.source_handler.open()
                    print("[CAN] Interface can0 initialised successfully")
                    self.can_connex = True
                    self.startThread()
                    
                except:
                    print("[CAN] Unable to initialise CAN interface - offline operation only")
                    return False

        else:
            print("[APP] No communication configured")

    def parse_can_data(self):
        #try:
        if self.serial_connex or self.can_connex:
            if not self.reading_thread.is_alive():
                self.status['text'] = "Processing of data crashed. See logfile"
                self.serial_connex = False
                self.can_connex = False
                self.connex.configure(text="Connexion")
                self.simStart.configure(text=">")
                self.master.after(2, self.parse_can_data)
                return

            with can_messages_lock:
                if not self.winView == None:
                    self.winViewUpdateFields()

                for x in can_flags:
                    if x == self.active_message_hex:
                        if can_flags[self.active_message_hex]:

                            msg = can_messages[self.active_message_hex]
                            for p in self.canFields:
                                p.update(msg)

                            can_flags[self.active_message_hex] = False

                            # Update binary and hex representations
                            z = 0
                            b = 0
                            buf = ""
                            buf2 = ""
                            for x in msg:
                                buf = buf + str(x)
                                buf2 = buf2 + str(x)
                                z = z + 1
                                if z == 8:
                                    self.lab_bin[b]["text"] = buf
                                    self.lab_hex[b]["text"] = str(hex(int(buf2, 2)))
                                    buf = ""
                                    buf2 = ""
                                    z = 0
                                    b = b+1
                    else:
                        can_flags[x] = False
        self.master.after(500, self.parse_can_data)
        #except Exception as e:
        #    print("[CRD] Exception in update loop: " + str(e))
        #    self.master.after(2, self.readSerial)


    def resetStatus(self):
        self.status['text'] = "Ready."
        self.master.after(5000, self.resetStatus)


    def simDelayTime(self, val):
        self.simDelayMs = int(val)


    def loadSim(self):
        try:
            filename = filedialog.askopenfilename(initialdir = "/home/rob/Software/car_projects/CAN Dumps", 
                                          title = "Select a CAN message LOG", 
                                          filetypes = (("CAN Dumps", 
                                                       "*.csv*"), 
                                                       ("all files", 
                                                        "*.*"))) 
            if not filename:
                return
            else:
                self.sim_ok = True
                self.source_handler = ArdLogHandler(filename, self) # pass self to allow access to simDelayMs
                self.status['text'] = "Simulation file loaded"
        except:
            print("[SIM] No file loaded")
            self.status['text'] = "Failed to load simulation file"


    def startSim(self):
        if self.can_connex and self.sim_ok:
            stop_reading.set()         
            self.simStart.configure(text=">")
            self.status['text'] = "SIM paused"
            self.can_connex = False
            self.log("Simulation paused")
            return

        if self.sim_ok:
            print("[SIM] Start CAN simulation")

            if self.reading_thread != None:
                stop_reading.clear()
                self.can_connex = True
                self.simStart.configure(text="||")
                self.status['text'] = "Simulation from " + self.source_handler.filename + " resumed"
                self.log("Resumed simulation")
                return

            self.log("Starting new thread")
            self.source_handler.open(bus=self.serialBus.get())
            self.simStart.configure(text="||")
            self.startThread()
            stop_reading.clear()
            self.can_connex = True
            self.log("Started new simulation")
            self.status['text'] = "Simulation from " + self.source_handler.filename + " started anew"
        else:
            self.status['text'] = "SIM not ready. Choose file first"
 
 
    def startThread(self):
        '''
        Start the reading background thread
        '''
        self.reading_thread = None
        self.reading_thread = threading.Thread(target=reading_loop, args=(self.source_handler,), daemon=True)
        self.reading_thread.start()
        print("[THR] Started reading thread")


    def CANChangeMsgType(self, *largs):
        '''
        Called when the user changes the message NAME box
        '''
        self.active_message_old = self.active_message
        self.active_message_index =  int(self.messageType.current())
        self.active_message_hex = self.message_ids[ self.active_message_index ]
        self.active_message = self.message_ints[ self.active_message_index ]
        self.messageID.current(self.messageType.current())

        self.CANChangeFields()
        print("[GUI] New message analysis: " + str(self.messageType.current()))
 

    def CANChangeMsgID(self, *largs):
        '''
        Called when the user changes the combobox of message IDs
        '''
        self.active_message_old = self.active_message
        self.active_message_index =  int(self.messageID.current())
        self.active_message_hex = self.message_ids[ self.active_message_index ]
        self.active_message = self.message_ints [ self.active_message_index ]
        self.messageType.current(self.messageID.current())

        self.CANChangeFields()
        print("[GUI] New message analysis: " + str(self.messageID.current()))


    def CANChangeFields(self, saveold=True):
        '''
        Clear the list of fields and create new ones
        '''

        # close editor windows if open
        if self.win_msg_editor is not None:
            if self.win_msg_editor.created == 1:
                self.win_msg_editor.win.destroy()
        
        # this will close the choice editor if needed by itself
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                self.win_sig_editor.win.destroy()

        # blank out the binary viewer
        for x in range(0,8):
                    self.lab_hex[x]['text'] = "----"
                    self.lab_bin[x]['text'] = "--------"

        for candef in self.canFields:
            candef.destroy()
        self.canFields = []

        # make & render the new fields
        signal_id = 0
        if self.omgr.messages == [] or self.omgr.messages == {} or self.omgr.messages == OrderedDict():
            return

        for signal in self.omgr.messages[self.active_message].signals:
            self.canFields.append(CANDef(self.master, self, signal_id, self.active_message))
            signal_id += 1


    def reload_msg_list(self):
        '''
        Generate the list of comboboxes from the internal databases
        '''
        self.reload_internal_from_omgr()
        self.winViewUpdateCmbMessages()
        self.reload_signal_ui()


    def reload_signal_ui(self):
        '''
        '''
        self.CANChangeFields()
    

    def addMessage(self):
        '''
        Open window to add new message
        '''
        result = askstring("New message ID", "Enter the hex ID of the new message to continue")

        try:
            id = int(result, 16)
        except:
            return False

        if id in self.omgr.messages:
            messagebox.showerror("Sacre bleu", "The ID " + str(result) + " already exists, please edit that instead")
            return
        
        self.omgr.messages[id] = cantools.database.can.Message(frame_id = id)
        self.reload_msg_list()
        # TODO: save changes if the window is open?
        if self.win_msg_editor is not None:
            if self.win_msg_editor.created == 1:
                self.win_msg_editor.win.destroy()
        self.win_msg_editor = message_editor(self.master, self, "new message", id)


    def addDefinition(self):
        '''
        Create a new parameter (byte postions) definition
        # bits, message_name[s], description, [type], [value pairs] OR [offset,min,max,unit] 
        '''
        result = askstring("New signal", "Enter the bit position of the new signal to continue")

        try:
            start, lng = self.omgr.yml_bits_decode(result, input_mode = self.bit_display_mode)
        except:
            return False
      
        self.messages[self.active_message].signals.append(cantools.database.can.Signal(start=start, length=lng))
        self.reload_signal_ui()

        # TODO: save changes if the window is open?
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                self.win_sig_editor.win.destroy()
        self.win_sig_editor = signal_editor(self.master, self, "new message", id, len(self.messages[self.active_message].signals) - 1)
    
    def edit_signal(self, mid, sid):
        
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                if self.win_sig_editor.mid == mid and self.win_sig_editor.sid == sid:
                    return
                else:
                    self.win_sig_editor.win.destroy()
        
        self.win_sig_editor = signal_editor(self.master, self, self.omgr.messages[mid].signals[sid].name, mid, sid)


    def delete_signal(self, mid, sid):
        pass


    # get an integer value
    def can_to_int(self, can, start, length):
        start = self.omgr.endian_translate(start)
        f = ""
        for x in range(start, start+length):
            #print(x, len(can))
            f = f + str(can[x])
        return int(f, 2)


    # convert to ASCII of each byte
    def can_to_str(self, can, offset, length):
        # First adjust length to within the limits of can
        # This is because sometimes ECU will send a shorter
        # message than 8 bytes for some text strings
        if offset + length > (len(can) - 1):
            length = len(can) - offset

        # Convert bits to bytes (only multiples of 8)
        if length % 8 != 0:
            print("[CNV] Invalid value supplied for string conversion")

        data_str = ''
        for x in range(offset, offset+ length):
            data_str = data_str + str(can[x])
        
        # got str'1111000011110000'
        no_str = int(data_str, 2)
        # got int'480'
        byte_str = no_str.to_bytes(int(length / 8), byteorder='big')
        # got '0x1 0xE0'
       
        # Try to make an ASCII representation of the bytes.
        msg_str = ''
        for byte in byte_str:
            msg_str = msg_str + self.byte2ascii(byte)
        return msg_str

    
    def ref_to_offset(self, row):
        '''
        Convert our preferred 1.3-1.4 byte format into an offset and length
        '''
        offset = 0
        length = 0
        if "-" in row:
            # multiple bits
            keys = row.split("-")
            start = keys[0].split(".")
            end = keys[1].split(".")
            start = ((8 * (int(start[0])-1)) + int(start[1])) - 1   # zero indexed
            end = ((8 * (int(end[0])-1)) + int(end[1])) - 1
            offset = start
            length = end - start
        else:
            # just one bit
            start = row.split(".")
            if len(start) != 2:
                return False
            start = ((8 * (int(start[0])-1)) + int(start[1])) - 1   # zero indexed
            offset = start
            length = 0
        return (offset, length)


    def saveCSV(self):
        '''
        Save a CSV of the message dict
        '''

        if self.messageMap == None or self.messageMap == "":
            f = filedialog.asksaveasfilename(initialdir = "/home/rob/Software/diagnostique/def", 
                                             title = "Select filename to save as...", 
                                             filetypes = (("CAN Descriptors", 
                                                            "*.csv*"), 
                                                           ("all files", 
                                                            "*.*"))) 
            if f == ():                                                
                return
            else:
                fname = f
                self.messageMap = f
        else:
            fname = self.messageMap
        
        csvfile = open(fname, 'w', newline='')
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        row = []
        y = 0
        writer.writerow(["CANALYZER",self.serialBus.get(),self.serialVeh.get()])

        for message in self.messages:
            row.append(message["id"])
            row.append(message["name"])
            row.append(message["label_en"])
            row.append(message["label_fr"])
            row.append(message["tx"])
            row.append(message["rx"])
            
            for sig in message["signals"]:
                for key in sig:
                    row.append(sig[key])

            writer.writerow(row)
            row = []
            y = y + 1

        self.status['text'] = "Saved CAN map of " + str(y) + " rows"
        print("[CDE] Saved " + str(y) + " rows to " + fname)
        

    def loadCSV(self):
        '''
        Load a CSV file containing the message definitions
        '''
        try:
            f = filedialog.askopenfilename(initialdir = "/home/rob/Software/CANbus", 
                                              title = "Select a CAN message map", 
                                              filetypes = (("CAN Descriptors", 
                                                            "*.csv*"), 
                                                           ("all files", 
                                                            "*.*"))) 
            if f == ():
                return
            else:
                self.messageMap = f

            csvfile = open(self.messageMap, newline='')
            reader = csv.reader(csvfile, delimiter=',', quotechar='"')

            self.ids = []
            self.types = []
            self.messageType['values'] = ["Choose..."]
            self.messageID['values'] = ["Choose..."]
            self.messages = []

            cline = 1

            for row in reader:     
                if row[0] == "CANALYZER":
                    p = 0
                    self.serialBus.text = row[1]
       
                mdef = make_dict(msg_def)

                # Load basic message info
                mdef["id"] = row[0]
                mdef["name"] = row[1]
                #mdef["label_en"] = row[2]
                #mdef["label_fr"] = row[3]
                #mdef["tx"] = row[4]
                #mdef["rx"] = row[5]
                mdef["signals"] = []

                # Add message to combo boxes
                self.ids.append(row[0])
                self.types.append(row[1])

                # now we interpret the rest as we go along
                i = 2

                while i < len(row):   
                    can_def = make_dict(sig_def)

                    # if new definition, turn "1.3-1.4" into an offset and len
                    can_def["hex"] = row[0]
                    f = self.ref_to_offset(row[i])
                    if not not f:
                        can_def["offset"], can_def["lenbi"] = f
                    can_def["ref"] = row[i]
                    i = i+1
                    can_def["name"] = row[i]
                    i = i+1
                    can_def["formula"] = row[i]
                    i = i+1
                    can_def["unit"] = row[i]
                    i = i+1
                    can_def["min"] = row[i]
                    i = i+1
                    can_def["max"] = row[i]
                    i = i+1

                    mdef["signals"].append(can_def)


                self.messages.append(mdef)
                cline = cline + 1

            self.messageType['values'] = self.types
            self.messageID['values'] = self.ids
            self.messageType.current(0)
            self.messageID.current(0)

            self.IDcurrent = 0
            self.hexIDcurrent = self.messageID.get()

            self.status['text'] = "CAN definition file loaded. " + str(len(self.messages)) + " entries"
            csvfile.close()
            self.CANChangeFields(saveold=False)

            self.addDef['state'] = NORMAL
        except Exception as e:
            self.status['text'] = "CAN definition file was not loaded."
            print("[CSV] The file couldn't be loaded from line " + str(cline) + " because: " + str(e))
            traceback.print_exc()

    # Strip out anything but real letters
    def byte2ascii(self, byte):
        char = chr(byte)
        if char == '\0':
            return ""            
            #msg_str = msg_str + '.'
        elif ord(char) < 32 or ord(char) > 126:
            return "" #msg_str = msg_str + '?'
        else:
            return char

    # Convert input to decimal
    def hexcal(self, inp):
        try:
            val = int(inp, 16)
            self.calc_out.set(str(val))    
            self.calc_outb.set(format(val, '08b'))
            return True
        except:
            self.calc_out.set("0")
            self.calc_outb.set("00000000")
            return True

    def can_to_formatted(self, msg, mid, sid):
        # Blank => Dump the binary
        '''
        if self.omgr.messages[mid].signals[sid].scale == "":
            f = ""
            for x in range(self.messages[dic]["signals"][ref]["offset"], self.messages[dic]["signals"][ref]["offset"]+self.messages[dic]["signals"][ref]["lenbi"]+1):
                f = f + str(msg[x])
            return f
        elif self.omgr.messages[mid].signals[sid].scale == "str":
            # make bytes from the bits and render
            f = self.can_to_str(msg, self.messages[dic]["signals"][ref]["offset"], self.messages[dic]["signals"][ref]["lenbi"]+1)
            return f
        elif self.messages[dic]["signals"][ref]["formula"] == "bool":
            # On or Off
            if self.messages[dic]["signals"][ref]["lenbi"] == 0:
                if str(msg[self.messages[dic]["signals"][ref]["offset"]]) == "1":
                    return "On"
                    self.value.configure(bg="green")
                else:
                    return "Off"
                    self.value.configure(bg="red")
            else:
                # if more than one bit just dump the binary for now
                f = ""
                for x in range(self.messages[dic]["signals"][ref]["offset"], self.messages[dic]["signals"][ref]["offset"]+self.messages[dic]["signals"][ref]["lenbi"]+1):
                    f = f + str(msg[x])
                return f
        elif "opt/" in self.messages[dic]["signals"][ref]["formula"]:
            # opt/011=Off/010=On/111=In Progress
            z = self.messages[dic]["signals"][ref]["formula"].split("/")
            self.valz = {}
            for x in z:
                y = x.split("=")
                if len(y) != 2:
                    continue
                self.valz[y[0]] = y[1]
            f = ""
            # do this otherwise we get 2 bytes when we only ask for 1
            if self.messages[dic]["signals"][ref]["lenbi"] == 0:
                lengz = self.messages[dic]["signals"][ref]["offset"] + 1
            else:
                lengz = self.messages[dic]["signals"][ref]["offset"] + self.messages[dic]["signals"][ref]["lenbi"] + 1
            for x in range(self.messages[dic]["signals"][ref]["offset"], lengz):
                f = f + str(msg[x])
            if f in self.valz:
                return self.valz[f]
            else:
                print("[OPT] Invalid parameter for " + str(f))
        elif "e." in self.messages[dic]["signals"][ref]["formula"]:
            # inbuilt existing special formula (e.g. navi multi-message)
            if hasattr(self, self.messages[dic]["signals"][ref]["formula"].replace("e.","e_")):
                c = getattr(self, self.messages[dic]["signals"][ref]["formula"].replace("e.","e_"))
                return str(c(msg, self.messages[dic]["signals"][ref]["offset"], self.messages[dic]["signals"][ref]["lenbi"]+1))
        '''
            # math equation 
        f = self.can_to_int(msg, self.omgr.messages[mid].signals[sid].start, self.omgr.messages[mid].signals[sid].length)
        calculation = self.omgr.messages[mid].signals[sid].scale * f + self.omgr.messages[mid].signals[sid].offset

        if self.omgr.messages[mid].signals[sid].choices is not None:
            if calculation in self.omgr.messages[mid].signals[sid].choices:
                return str(self.omgr.messages[mid].signals[sid].choices[calculation])
        
        return calculation


################### E_ SPECIAL FUNCTIONS ############################

# Certain CAN parameters need more advanced parsing than simple int/opt
# etc., so here we can define custom python functions to run on them
# Also used for opt tables that would otherwise be unwieldy

    def e_torque(self, raw, offset, length):
        x = self.can_to_int(raw, offset, length -1)
        # 0x00 to 0xFF => 

    def e_climTemp(self, raw, offset, length):
        clim_prop = {  0: "LO", 2: "15", 3: "16", 4: "17", 5: "18",
                       6: "18.5", 7:"19", 8:"19.5", 9:"20", 10:"20.5",
                       11: "21", 12: "21.5", 13: "22", 14: "22.5", 15: "23",
                       16: "23.5", 17: "24", 18: "25", 19: "26", 20: "27",
                       22: "HI", 21: "HI" } 
        x = self.can_to_int(raw, offset, length - 1)
        if x in clim_prop:
            return clim_prop[x]
        else:
            return 0

    def e_balance(self, raw, offset, length):
        balance_prop = { "0110110": -9, "0110111": -8, "0111000": -7, "0111001": -6, "0111010": -5,
                         "0111011": -4, "0111100": -3, "0111101": -2, "0111110": -1, "0111111": 0,
                         "1000000": 1, "1000001": 2, "1000010": 3, "1000011": 4, "1000100": 5,
                         "1000101": 6, "1000110": 7, "1000111": 8, "1001000": 9 }
        search = ""
        for x in range(offset, offset + length):
            search = search + raw[x]
        if search in balance_prop:
            return balance_prop[search]
        else:
            return "0"

    def e_navi(self, raw, offset, length):
        #if offset + length > (len(raw) - 1):
        #            length = len(raw) - offset
        #            print("[CNV] Warn only: shortened string message")
        #if length % 8 != 0:
        #            print("[CNV] Invalid value supplied for string conversion")
        rex = "".join(raw)
        datai = int(str(rex),2)
        msg_a = datai.to_bytes(8, byteorder='big')
        msg = []        

        for x in range(0, len(msg_a)):
            # throw away anything blank
            if msg_a[x] != 0:
                msg.append(msg_a[x])

        if not hasattr(self, "e_navi_data"):
            self.e_navi_data = []

        if 0x20 <= msg[0] < 0x29:
            for x in range(1, len(msg)):
                self.e_navi_data.append(self.byte2ascii(msg[x]))
                
        elif msg[0] == 0x10:
            self.e_navi_data = []      
            for x in range(3, 8):
                if x < len(msg):
                    self.e_navi_data.append(self.byte2ascii(msg[x]))

        elif msg[0] == 0x04:
            self.e_navi_data = []      
            for x in range(2, 8):
                if x < len(msg):
                    self.e_navi_data.append(self.byte2ascii(msg[x]))

        elif msg[0] == 0x07:
            self.e_navi_data = []
            self.e_navi_data = list("CALCULATING ROUTE")

        print(self.e_navi_data)
        e_navi_str = "".join(self.e_navi_data)
        return e_navi_str

################### OVERVIEW  ############################
    
    def addwinViewRow(self):
        if len(self.omgr.messages) == 0:
            return

        z = len(self.overview_cmbs_messages)
        cmb = Combobox(self.winView, values=['Choose...'], width=35)
        cmb.grid(row=z+2, column=0)

        self.overview_cmbs_messages.append(cmb)

        cmb_sig = Combobox(self.winView, values=['Choose...'], width=35)
        cmb_sig.grid(row=z+2, column=1)

        self.overview_selected_signal.append(-1)

        self.overview_cmbs_signals.append(cmb_sig)
        self.overview_output_svars.append(StringVar())
        self.overview_unit_svars.append(StringVar())

        self.overview_output_textboxs.append(Entry(self.winView, textvariable=self.overview_output_svars[z], state='readonly', width=30))
        self.overview_unit_textboxs.append(Entry(self.winView, textvariable=self.overview_unit_svars[z], state='readonly', width=10))

        self.overview_output_textboxs[z].grid(column=2, row=z+2)
        self.overview_unit_textboxs[z].grid(column=3, row=z+2)
        self.overview_cmbs_messages[z].current(0)
        self.overview_cmbs_signals[z].current(0)

        self.overview_cmbs_messages[z].bind("<<ComboboxSelected>>", partial(self.overview_update_cmbs_signals, z))
        self.overview_cmbs_signals[z].bind("<<ComboboxSelected>>", partial(self.winViewUpdateSignals, z))
        self.overview_messages_subscribed.append(-1)
    
        for x in range(1, z + 2):
            self.winView.grid_rowconfigure(x, minsize=25)
        
        self.winViewUpdateCmbMessages()
        self.overview_update_cmbs_signals(z)


    def winViewUpdateCmbMessages(self):
        '''
        Update the combo boxes to reflect contents
        of main window combo boxes
        '''
        items = []
        i = 0
        offset = -1
        j = 0
        for cmb in self.overview_cmbs_messages:
            # save the user selection
            active_index = cmb.current()
            current_frame_id = self.message_ids[active_index]

            j = 0
            offset = -1

            if len(self.omgr.messages) > 0:
                for message in self.omgr.messages:
                    # the index will match with message index in the main view, so we don't need to store separately here
                    if current_frame_id == message:
                        offset = j
                    items.append(self.omgr.to_hex(message) + " - " + self.omgr.messages[message].name)
                    j += 1

            if len(items) > 0:    
                cmb['values'] = items
            else:
                cmb['values'] = ["Choose..."]
            
            # restore the users selection
            if offset != -1:
                # this will trigger the signal update 
                cmb.current(offset)
            else:
                # deleted message
                cmb.current(0)

            i += 1

    
    def overview_update_cmbs_signals(self, row, *largs):
        '''
        Update the signal list of combobox row
        because the chosen message changed
        '''
        
        if row > len(self.overview_cmbs_signals):
            return
        
        active_index = self.overview_cmbs_messages[row].current()
        current_frame_id = self.message_ints[active_index]

        if current_frame_id not in self.omgr.messages:
            self.log("Invalid frame ID for overview - d" + str(current_frame_id))
            return
        
        items = []
        for signal in self.omgr.messages[current_frame_id].signals:
            items.append(signal.name)
        
        if len(items) > 0:
            self.overview_cmbs_signals[row]["values"] = items
        else:
            self.overview_cmbs_signals[row]['values'] = ["Choose..."]

        self.overview_cmbs_signals[row].current(0)
        self.overview_messages_subscribed[row] = self.message_ids[active_index]

        self.winViewUpdateSignals(row)

    
    def winViewUpdateSignals(self, row, *largs):
        '''
        Handle the user changing the dropdown for which signal to view
        '''
        self.overview_selected_signal[row] = self.overview_cmbs_signals[row].current()
        self.overview_output_svars[row].set("")

        self.active_message = self.message_ints [ self.overview_cmbs_messages[row].current() ]
        signal = self.omgr.messages[self.active_message].signals[self.overview_selected_signal[row]]
        self.overview_unit_svars[row].set(str(signal.unit))


    def winViewUpdateFields(self):   
        '''
        Update all the values displayed in the window
        '''
        ctr = 0
        for row in self.overview_messages_subscribed:
            if row == -1:
                # message not been set yet
                continue
            
            if row in can_messages:
                msg = can_messages[row]
                self.overview_output_svars[ctr].set(self.can_to_formatted(msg, int(row, 16), self.overview_selected_signal[ctr]))
            
            ctr += 1


    def overViewDestroyed(self, x):
        self.winView = None


    def createOverview(self):
        if not isinstance(self.winView, Toplevel):             
            self.winView = Toplevel(self.master)
            self.winView.wm_title("CANerview")
            self.winView.bind("<Destroy>",self.overViewDestroyed)

    
            info = Label(self.winView, text="Combined signal view - choose message and then from available signals")
            info.grid(row=1, column=0, columnspan=2)

            addCmb = self.winView.register(self.addwinViewRow)
            create = Button(self.winView, text="Add +", command=addCmb)
            create.grid(row=1, column=2, columnspan=1)
            self.winView.grid_columnconfigure(1, minsize=120)
            self.winView.grid_columnconfigure(2, minsize=120)
            self.addwinViewRow()


################### THREADING ############################

should_redraw = threading.Event()
stop_reading = threading.Event()

can_messages = {}
can_flags = {}
can_messages_lock = threading.Lock()

thread_exception = None
thread_crashed = False

# Convert [ 8E, 7F ] to [ 0 1 1 0 1 0 ] etc
def can_to_bin(data):
    out = []
    for x in data:
        out.append("{0:08b}".format(int(x)))
    binstr = "".join(out)
    
    return list(binstr)

def reading_loop(source_handler):
    """Background thread for reading."""
    #try:
    while 1:
        while not stop_reading.is_set():
            try:
                frame_id, data = source_handler.get_message()
                #print(frame_id)
            except InvalidFrame:
                print("[CAN] Invalid frame encountered")
                continue
            except EOFError:
                break

            # Add the frame to the can_messages dict and tell the main thread to refresh its content
            with can_messages_lock:
                can_messages[frame_id] = can_to_bin(data)
                #print("[CAN] Send " + str(frame_id))
                #if frame_id in can_flags:
                #    if can_flags[frame_id]:
                #        print("[CAN] Block on ID: " + str(frame_id))
                #        while can_flags[frame_id]:
                #            time.sleep(0.025)
                can_flags[frame_id] = True
        time.sleep(0.2)

    #except:
    #    thread_crashed = True
     #   print("[CAN] Reading thread exited")

    

############## MAIN LOOP ####################################


root = Tk()
my_gui = oleomux(root)
for x in range(1,9):
    root.grid_columnconfigure(x, minsize=110)


root.grid_rowconfigure(1, minsize=30)
root.grid_rowconfigure(2, minsize=30)
root.grid_rowconfigure(3, minsize=45)
root.grid_rowconfigure(4, minsize=45)
root.grid_rowconfigure(5, minsize=30)

root.after(5, my_gui.parse_can_data)
root.after(5000, my_gui.resetStatus)
root.mainloop()
