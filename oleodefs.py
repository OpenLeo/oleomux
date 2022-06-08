from cantools.database.can.signal import NamedSignalValue
from tkinter import Button, Entry, StringVar
from functools import partial


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
        self.label_en.insert(0, comment_fields["en"])
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
        self.max = Entry(self.owner.scrollable_frame, width=8)

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