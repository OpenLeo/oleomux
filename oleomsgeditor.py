from tkinter import END, Canvas, Scrollbar, Spinbox, Tk, Text, Label, Button, Entry, filedialog, StringVar, Menu, Frame, SUNKEN, W, DISABLED, NORMAL, Toplevel, BooleanVar, IntVar, messagebox
import cantools

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
            #self.svs["name_en"] =  StringVar(value=comment_fields["name_en"])
            self.svs["en"] = comment_fields["en"]
            self.svs["fr"] = comment_fields["fr"]
            self.svs["src"] = StringVar(value=comment_fields["src"])

            #self.lbl.append(Label(self.win, text="Name (EN)"))
            #self.field.append(Entry(self.win, text = self.svs["name_en"]))

            self.lbl.append(Label(self.win, text="Comment (EN)"))
            self.comment_field_en = Text(self.win, height=2, width=30)
            self.field.append(self.comment_field_en)
            self.field[-1].insert(END, str(self.svs["en"]))

            self.lbl.append(Label(self.win, text="Comment (FR)"))
            self.comment_field_fr = Text(self.win, height=2, width=30)
            self.field.append(self.comment_field_fr)
            self.field[-1].insert(END, str(self.svs["fr"]))

            self.lbl.append(Label(self.win, text="Periodicity"))
            self.field.append(Spinbox(self.win, text = self.svs["periodicity"]))

            self.lbl.append(Label(self.win, text="Senders"))
            self.field.append(Entry(self.win, text = self.svs["senders"]))

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
        comments_collection["en"] = self.comment_field_en.get("1.0", "end-1c")
        comments_collection["fr"] = self.comment_field_fr.get("1.0", "end-1c")
        #comments_collection["name_en"] = self.svs["name_en"].get()
        comments_collection["src"] = self.svs["src"].get()       # not user editable, atm

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