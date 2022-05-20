from tkinter import END, Canvas, Scrollbar, Spinbox, Tk, Text, Label, Button, Entry, filedialog, StringVar, Menu, Frame, SUNKEN, W, DISABLED, NORMAL, Toplevel, BooleanVar, IntVar, messagebox
from tkinter.simpledialog import askstring
from tkinter.ttk import Combobox, Treeview
from typing import OrderedDict



from source_handler import CanPrintHandler, InvalidFrame, CANHandler, SerialHandlerNew, ArdLogHandler
from recordclass import recordclass

from functools import partial
import cantools, pprint, serial, can, csv, numexpr, threading, sys, traceback, time, serial.tools.list_ports, yaml, os, datetime
from os import listdir
from os.path import isfile, join

from oleomgr import oleomgr
from oleotree import oleotree
from oleodefs import CANDef
from oleomsgeditor import message_editor
from oleosigeditor import signal_editor, choice_editor

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
#   - own research
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


class oleomux:
    version = "1.001"

    USE_CAN = 1
    USE_SERIAL = 2

    last_can_speed = 0

    cfg_file = "config.yml"

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
    source_handler = None

    overview_cmbs_messages = []
    overview_cmbs_signals = []
    overview_output_textboxs = []
    overview_output_svars = []
    overview_unit_svars = []
    overview_messages_subscribed = []
    overview_selected_signal = []
    overview_unit_textboxs = []

    configuration = {
        "logs_dir": "logs/",     # logs/
        "adapter_type": 2,       # use serial
        "can_speed": 250,        # 250 kbps
        "bit_ordering": 2,       # mode CANT
        "uart_baud": 115200,     # for serial adapter
        "can_interface": "can0", # for can
        "tab_space_num": 4,
        "STRUCT_PREFIX": "ole07_",
        "FUNC_PARSE_PREFIX": "ole07_parse_",
        "TYPE_S8": "int8_t ",
        "TYPE_U8": "uint8_t",
        "TYPE_S16": "int16_t ",
        "TYPE_U16": "uint16_t",
        "TYPE_U32": "uint32_t",
        "TYPE_S32": "int32_t "
    }

    active_message = 0
    active_message_hex = 0

    filter_senders : list = None
    filter_receivers : list = None
    log_filter = None


    def log(self, ma, msg = None):
        '''
        Log to the console, and to file
        '''
        if msg is None:
            msg = ma
            ma = "OMG"

        print("[" + str(ma) + "] " + str(msg))

        try:
            if self.log_fh is not None:
                self.log_fh.write("[" + str(ma) + "] " + str(msg) + "\n")
                self.log_fh.flush()
        except:
            #print("[LOG] No file handle available")
            pass


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
        '''
        Update the status bar with how many (index) of item_count have been processed
        '''
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
        Actually do the export to YAML folder/files
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
        Actually do the export of C files
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
        if f == () or f == None:
            return

        if not self.omgr.import_from_dbc(f):
            self.log("DBC load cancelled")
            return
        self.log("Loaded " + str(len(self.omgr.messages)) + " messages from DBC file")
        self.reload_internal_from_omgr()


    def exportDBC(self):
        '''
        Export a DBC
        '''
        olt = oleotree(self.master, self, self.exportDBCchosen, "Choose messages or signals to export to DBC", selection=1)

    
    def exportDBCchosen(self, results):
        '''
        Actually do the export to DBC file
        '''
        if len(results) > 0:
            fname = filedialog.asksaveasfile(title = "Choose filename for export to DBC...",
                                        filetypes = (("CAN database format", "*.dbc*"), 
                                                     ("all files", "*.*"))) 
            if fname == ():
                return

            result = self.omgr.export_to_dbc(fname.name, results)
            if result:
                messagebox.showinfo(title="OK", message="Export to DBC done!")
            else:
                messagebox.showerror(title="Oh no!", message="The export to DBC could not be completed.")

        else:
            messagebox.showwarning(title="Nope", message="No messages selected for export!")
            return

    
    def clean(self):
        '''
        Clean the messages stored in the internal DB and UI
        '''
        self.omgr.clean()
        self.reload_internal_from_omgr()


    def filter_by_sender(self, *largs):
        '''
        Let user choose from a list of sender ECUs
        '''
        olt = oleotree(self.master, self, self.filter_sender_apply, title="Choose SENDERS to filter by", tree_type="ecu_tx", selection=self.filter_senders)


    def filter_sender_apply(self, results, *largs):
        '''
        Apply the filter of senders
        '''
        if len(results) == 0:
            return

        self.filter_senders = results
        self.log("Filter by sender: " + str(results))
        self.reload_msg_list()


    def filter_receiver_apply(self, results, *largs):
        '''
        Filter by the chosen receivers
        '''
        if len(results) == 0:
            return
        self.filter_receivers = results
        self.reload_msg_list()
        self.log("Filter by receiver: " + str(results))


    def filter_by_receiver(self, *largs):
        '''
        Let user choose from a list of receiver ECUs
        '''
        olt = oleotree(self.master, self, self.filter_receiver_apply, title="Choose RECEIVERS to filter by", tree_type="ecu_rx", selection=self.filter_receivers)


    def clear_filters(self, *largs):
        '''
        Clear any filters that have been set, show everything
        '''
        self.filter_receiver = None
        self.filter_sender = None
        self.reload_msg_list()

    
    def reload_internal_from_omgr(self):
        '''
        Regenerate combo boxes and internal message
        table based on contents of OMGR
        '''
        self.message_names = []
        self.message_ids = []
        self.message_ints = []

        include_filter = True
        for message in self.omgr.messages:
            if self.filter_senders is not None:
                include_filter = False
                if self.omgr.messages[message].senders is None:
                    continue

                for sender in self.omgr.messages[message].senders:
                    if sender in self.filter_senders:
                        include_filter = True
                        break
                
            if self.filter_receivers is not None:
                include_filter = False
                for signal in self.omgr.messages[message].signals:
                    if signal.receivers == None:
                        continue
                    
                    for receiver in signal.receivers:
                        if receiver in self.filter_receivers:
                            include_filter = True
                            break
            
            if include_filter:
                self.message_ids.append(self.omgr.to_hex(message, 3))
                self.message_ints.append(message)
                self.message_names.append(self.omgr.messages[message].name)
            else:
                continue

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
        '''
        Swap bit ordering (1.7 -> 1.0 to 1.0 -> 1.7) according to user preference
        '''
        self.bit_display_mode = new_mode
        self.configuration["bit_ordering"] = new_mode
        self.reload_signal_ui()


    def log_filter_apply(self, results):
        '''
        Actually apply result of message filter for logging
        '''
        if len(results) == 0:
            self.log("User chose nothing to store in log > invalid > ignored")
            return
        self.log_filter = results.keys()

        if self.source_handler is not None:
            self.source_handler.filter_log = self.log_filter

        self.log("Log filter applied")


    def log_filter_cfg(self):
        '''
        Show treeview to let user choose which messages to log
        '''
        if self.log_filter == None:
            olt = oleotree(self.master, self, self.log_filter_apply, title="Choose which messages to include in log", tree_type = "msg", selection=1)
        else:
            olt = oleotree(self.master, self, self.log_filter_apply, title="Choose which messages to include in log", tree_type = "msg", selection=self.log_filter)


    def setcanspeed(self, speed):
        '''
        Set users new CAN speed
        '''
        if self.source_handler is not None:
            if self.source_handler.adapter_type == "serial":
                self.log("Request CAN speed to " + str(speed))
                if not self.source_handler.adapter_configure(speed):
                    self.configuration["can_speed"] = speed
                    self.canspeed.set(self.last_can_speed)
                else:
                    self.last_can_speed = speed
            else:
                self.log("Unknown adapter type: " + str(self.source_handler.adapter_type))
                self.canspeed.set(self.last_can_speed)
        else:
            self.log("Set CAN speed not done - not connected")
            self.canspeed.set(self.last_can_speed)
        

    def config_load(self):
        '''
        Try to load configuration from file, or use default
        '''
        try:
            f = open(self.cfg_file)
            f_contents = f.readlines()
            f_contents = "".join(f_contents)
            cfg = yaml.safe_load(f_contents)
            bad_cfg = False

            for key in self.configuration:
                if key not in cfg:
                    bad_cfg = True
            
            if not bad_cfg:
                self.configuration = cfg
                self.last_can_speed = self.configuration["can_speed"]
                self.log("Load configuration file OK")
            else:
                self.log("Failed to load configuration file - using defaults")
        except:
            self.log("Configuration file unavailable - using defaults")


    def destroyed(self, *largs):
        '''
        Called on exit, use to save config file
        '''
        try:
            f = open(self.cfg_file, "w")
            yaml.dump(self.configuration, f)
            f.close()
        except:
            self.log("Configuration file could not be saved.")


    # Init window
    def __init__(self, master):

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

        self.master.bind("<Destroy>",self.destroyed)
        self.config_load()

        self.omgr = oleomgr(self, self.configuration)
        self.bit_display_mode = self.configuration["bit_ordering"]
        self.log_fh = None

        # open the log file
        try:
            directory = os.path.dirname(self.configuration["logs_dir"])
            if not os.path.exists(directory):
                os.makedirs(directory)
            fn = "oleomux-" + str(datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")) + ".log"
            self.log_fh = open(self.configuration["logs_dir"] + str(fn), "w")

            output = "OLEOMUX CAN MANAGER " + str(self.version) + "\n"
            output = output + "Software: " + str(self.version) + "\n"
            output = output + "Date    : " + str(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")) + "\n\n"
            self.log_fh.write(output)
        except:
            print("[LOG] Error create logfile")
            self.log_fh = None

        pprint.pprint(self.configuration, self.log_fh)

        master.title("OpenLEO CAN database manager")

        self.winView = None
        self.menubar = Menu(master)
        filemenu = Menu(self.menubar)

        filemenu.add_command(label="Import DBC", command=self.importDBC)
        # Removed until the MANY bugs in dbc exporting are dealt with
        #filemenu.add_command(label="Export DBC", command=self.exportDBC)
        filemenu.add_separator()
        filemenu.add_command(label="Import YAML (file)", command=self.importYAMLfile)
        filemenu.add_command(label="Import YAML (folder)", command=self.importYAMLfolder)
        filemenu.add_command(label="Export YAML (multiple)", command=self.saveYAMLall)
        filemenu.add_command(label="Export YAML (only selected)", command=self.saveYAMLselected)
        
        filemenu.add_command(label="Export C Code", command=self.exportCoptions)
        self.menubar.add_cascade(label= "File", underline=0, menu= filemenu)

        createWin = master.register(self.createOverview)
 
        self.menubar.add_command(label="Overview", command=createWin)
        master.config(menu=self.menubar)
    
        self.bus_conf = BooleanVar()
        self.bus_is = BooleanVar()
        self.bus_car = BooleanVar()


        toolsmenu = Menu(self.menubar)
        toolsmenu.add_command(label="Filter by sender...", command=self.filter_by_sender)
        toolsmenu.add_command(label="Filter by receiver...", command=self.filter_by_receiver)
        toolsmenu.add_command(label="Clear filters", command=self.clear_filters)
        toolsmenu.add_separator()
        #self.menubar.add_command(label="Load CAN Map", command=self.loadCSV)  
        toolsmenu.add_command(label="Clear loaded messages", command=self.clean)  
        toolsmenu.add_command(label="Load Oleomux CAN log", command=self.loadSim)
        toolsmenu.add_command(label="Load candump console log", command=self.loadSimCanDump)
        toolsmenu.add_separator()
        self.bit_type = IntVar(master)
        self.bit_type.set(self.configuration["bit_ordering"])
        toolsmenu.add_radiobutton(label="OpenLEO bit numbering", var=self.bit_type, value=self.omgr.MODE_OLEO, command=partial(self.bit_display_toggle, self.omgr.MODE_OLEO))
        toolsmenu.add_radiobutton(label="Logical bit numbering", var=self.bit_type, value=self.omgr.MODE_CANT, command=partial(self.bit_display_toggle, self.omgr.MODE_CANT))

        #self.menubar.add_command(label="Save CAN Map", command=self.saveCSV)
        self.menubar.add_cascade(label= "Tools", underline=0, menu= toolsmenu)


        self.com_type = Menu(self.menubar)
        self.contype = IntVar(master)
        self.contype.set(self.configuration["adapter_type"])
        
        self.canspeed = IntVar(master)
        self.canspeed.set(self.configuration["can_speed"])

        self.com_type.add_radiobutton(label="Serial", var=self.contype, value=self.USE_SERIAL, command=self.SerialEnable)
        self.com_type.add_radiobutton(label="SocketCAN", var=self.contype, value=self.USE_CAN, command=self.CANEnable)
        self.com_type.add_separator()
        self.com_type.add_radiobutton(label="CAN 125kbps", var=self.canspeed, value=125, command=partial(self.setcanspeed, 125))
        self.com_type.add_radiobutton(label="CAN 250kbps", var=self.canspeed, value=250, command=partial(self.setcanspeed, 250))
        self.com_type.add_radiobutton(label="CAN 500kbps", var=self.canspeed, value=500, command=partial(self.setcanspeed, 500))
        self.com_type.add_separator()
        self.com_type.add_command(label="Filter messages to log", command=self.log_filter_cfg)
        self.menubar.add_cascade(label="Comms", menu=self.com_type)

        ################# ROW 1 ###########################

        self.label = Label(master, text="COM Port:")
        self.label.grid(column=1, row=1, columnspan=1)

        self.serial_frame = Frame(master)

        lis = serial.tools.list_ports.comports()
        self.com_ports = []
        opts = []
        for item in lis:
            self.com_ports.append(item[0])
            opts.append(str(item[0]) + " - " + str(item[1]))

        self.serialPort = Combobox(self.serial_frame, values = opts, width=25)
        self.serialPort.grid(column=1,row=1)
        self.serialPort.current(0)
        self.serialPort.bind("<<ComboboxSelected>>", self.COMPortChange)
        if self.configuration["adapter_type"] != self.USE_SERIAL:
            self.serialPort['state'] = DISABLED

        self.serial_frame.grid(column=2, row=1, columnspan=2)
        self.connex = Button(self.serial_frame, text="Connect", command=self.connexion)
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
        self.simLabel = Label(self.simFrame, text="Sim Delay:")
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
        self.hexbin_frame = Frame(master)
        self.hexbin_frame.grid(row=3, column=1, columnspan = 8, rowspan=2)

        for x in range(0,8):
            self.lab_hex.append(Label(self.hexbin_frame, text="----", fg="white", bg="blue"))
            self.lab_hex[x].grid(row=1,column=x+1)
            self.lab_hex[x].config(font=("Monospace", 14))
            self.lab_bin.append(Label(self.hexbin_frame, text="--------"))
            self.lab_bin[x].grid(row=2,column=x+1)
            self.lab_bin[x].config(font=("Monospace", 12))
            self.hexbin_frame.grid_columnconfigure(x+1, minsize=110)

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

        self.log("Initialisation complete - ready for work")


    def COMPortChange(self, *largs):
        '''
        Update internally when user changes the com port
        '''
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
        '''
        Use Serial adapter type
        '''
        self.serialPort['state'] = NORMAL
        self.conn = self.USE_SERIAL
        self.configuration['adapter_type'] = self.USE_SERIAL


    def CANEnable(self):
        '''
        Use CAN adapter type
        '''
        self.serialPort['state'] = DISABLED
        self.conn = self.USE_CAN
        self.configuration['adapter_type'] = self.USE_CAN


    def connexion(self):
        '''
        Manage connection to different adapter types
        '''
        if self.conn == self.USE_SERIAL:
            if not self.serial_connex: 
                try:        
                    self.port = self.com_ports[self.serialPort.current()]
                    print("[SER] Connect to " + self.port)
                    self.source_handler = SerialHandlerNew(self.port, baudrate = self.configuration["uart_baud"], bus="", veh="")
                    self.source_handler.open()
                    self.source_handler.start()

                    self.connex.configure(text="Disconnexion")
                    
                    self.startThread()
                    self.serial_connex = True
                    self.serialPort['state'] = 'readonly'
                except:
                    print("[SER] Connexion failed")
                    self.status['text'] = "Connexion to serial port failed"
            else:
                self.serialPort['state'] = 'normal'

        elif self.conn == self.USE_CAN:
            if not self.can_connex:
                try:
                    
                    self.source_handler = CANHandler(channel = self.configuration["can_interface"], bus="", veh="")
                    self.source_handler.open()
                    print("[CAN] Interface " + self.configuration["can_interface"] + " initialised successfully")
                    self.can_connex = True
                    self.startThread()
                    
                except:
                    print("[CAN] Unable to initialise CAN interface - offline operation only")
                    return False

        else:
            print("[APP] No communication configured")


    def parse_can_data(self):
        '''
        Check for messages flagged as having changed
        and if its the one we have on screen, update + render it
        
        Also prompt the overview UI to update
        '''
        try:
            if self.serial_connex or self.can_connex:
                if eof_data.is_set():
                    self.status['text'] = "Simulation finished, reload file to start again"
                    stop_reading.clear()
                    eof_data.clear()
                    self.simStart.configure(text=">")
                    self.can_connex = False
                    self.reading_thread = None
                    self.log("Simulation end of file. Reload to start again")
                    self.master.after(50, self.parse_can_data)
                    return


                if not self.reading_thread.is_alive():
                    self.status['text'] = "Processing of data crashed. See logfile"
                    self.serial_connex = False
                    self.can_connex = False
                    self.connex.configure(text="Connexion")
                    self.simStart.configure(text=">")
                    self.master.after(50, self.parse_can_data)
                    return

                with can_messages_lock:
                    # update the overview window if needed
                    #if not self.winView == None:
                        # todo needs a separate can_flags
                        #self.winViewUpdateFields()

                    if self.active_message_hex in can_flags:
                        if can_flags[self.active_message_hex]:

                            msg = can_messages[self.active_message_hex]
                            self.log("Update: " + str(self.active_message_hex))
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

            self.master.after(50, self.parse_can_data)
        except Exception as e:
            self.log("CRD", "Exception in update loop")
            self.log("DMP", str(traceback.format_exc()))
            self.master.after(1000, self.parse_can_data)


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

    
    def loadSimCanDump(self):
        try:
            filename = filedialog.askopenfilename(initialdir = "/home/rob/Software/car_projects/CAN Dumps", 
                                          title = "Select a candump log file", 
                                          filetypes = (("CAN Dumps", 
                                                       "*.dmp*"), 
                                                       ("all files", 
                                                        "*.*"))) 
            if not filename:
                return
            else:
                self.sim_ok = True
                self.source_handler = CanPrintHandler(filename, self)
                self.status['text'] = "Simulation file loaded"
        except:
            print("[SIM] No file loaded")
            self.status['text'] = "Failed to load simulation file"


    def startSim(self):
        if self.serial_connex:
            if self.source_handler.is_running():
                self.status['text'] = "Receiving from adapter paused"
                stop_reading.set()         
                self.source_handler.stop()
                self.simStart.configure(text=">")
                self.log("Reception from serial adapter paused")
                return

            else:
                self.status['text'] = "Receiving from adapter resumed"
                self.source_handler.start()
                stop_reading.clear()
                self.simStart.configure(text=">")
                self.log("Reception from serial adapter resumed")
                return
            
        if self.can_connex and self.sim_ok:
            stop_reading.set()         
            self.source_handler.stop()
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
                self.source_handler.start()
                self.simStart.configure(text="||")
                self.status['text'] = "Simulation from " + self.source_handler.filename + " resumed"
                self.log("Resumed simulation")
                return

            self.log("Starting new thread")
            self.source_handler.open()
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
        if self.reading_thread is None:
            self.reading_thread = None
            self.reading_thread = threading.Thread(target=reading_loop, args=(self, self.source_handler), daemon=True)
            self.reading_thread.start()
            print("[THR] Started reading thread")

        if self.reading_thread.is_alive():
            print("[THR] Reading thread is already running, no action taken")
        else:
            self.reading_thread = None
            self.reading_thread = threading.Thread(target=reading_loop, args=(self,self.source_handler), daemon=True)
            self.reading_thread.start()
            print("[THR] Re-created reading thread")


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

        if len(self.omgr.messages) > 0:
            self.addDef['state'] = NORMAL
        else:
            self.addDef['state'] = DISABLED

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
        
        self.omgr.messages[id] = cantools.database.can.Message(frame_id = id, name="Unspecified " + str(result), length=8, signals=[])
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
      
        self.omgr.messages[self.active_message].signals.append(cantools.database.can.Signal(start=start, name="New signal " + str(result), length=lng))
        self.reload_signal_ui()

        # TODO: save changes if the window is open?
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                self.win_sig_editor.win.destroy()
        self.win_sig_editor = signal_editor(self.master, self, "new message", self.active_message, len(self.omgr.messages[self.active_message].signals) - 1)
    
    
    def edit_signal(self, mid, sid):
        '''
        Open signal editor window
        '''
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                if self.win_sig_editor.mid == mid and self.win_sig_editor.sid == sid:
                    return
                else:
                    self.win_sig_editor.win.destroy()
        
        self.win_sig_editor = signal_editor(self.master, self, self.omgr.messages[mid].signals[sid].name, mid, sid)


    def delete_signal(self, mid, sid):
        '''
        Remove signal from db
        '''
        if self.win_sig_editor is not None:
            if self.win_sig_editor.created == 1:
                if self.win_sig_editor.mid == mid and self.win_sig_editor.sid == sid:
                    self.win_sig_editor.win.destroy()
        
        try:
            self.omgr.messages[mid].signals.pop(sid)
        except:
            self.log("Could not delete signal " + str(mid) + " , " + str(sid))
            messagebox.showerror(title="Sacre bleu", message="Failed to delete signal")


    # get an integer value
    def can_to_int(self, can, start, length):
        try:
            start = self.omgr.endian_translate(start)
            f = ""
            for x in range(start, start+length):
                #print(x, len(can))
                if x >= len(can):
                    return 0
                f = f + str(can[x])
            return int(f, 2)
        except:
            self.log("DMP", str(traceback.format_exc()))
            self.log("can = " + str(can) + ", x = " + str(x) + ", str = " + str(start) + ", len = " + str(length))


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
        lenby = self.omgr.messages[mid].signals[sid].length / 8

        # handle signed values
        if self.omgr.messages[mid].signals[sid].is_signed:
            if lenby == 1:
                if f > 127:
                    f = f - 256
            elif lenby == 2:
                if f > 32767:
                    f = f - 65536
                    
        calculation = self.omgr.messages[mid].signals[sid].scale * f + self.omgr.messages[mid].signals[sid].offset
        calculation = round(calculation, 2)

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
eof_data = threading.Event()

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
    
    return binstr

def reading_loop(parent, source_handler):
    """Background thread for reading."""
    try:
        eof_data.clear()

        while 1:
            while not stop_reading.is_set():
                try:
                    result = source_handler.get_message()
                    if not result:
                        continue
                    if result == -1:
                        # end of file
                        eof_data.set()
                        return

                    frame_id, data = result
                    print(frame_id)
                except InvalidFrame:
                    print("[CAN] Invalid frame encountered")
                    print("[DMP]", str(traceback.format_exc()))
                    continue
                except EOFError:
                    break

                # Add the frame to the can_messages dict and flag that it changed
                with can_messages_lock:
                    can_messages[frame_id] = can_to_bin(data)
                    can_flags[frame_id] = True

            time.sleep(0.2)

    except:
        eof_data.set()
        parent.log("CAN", str(traceback.format_exc()))
        parent.log("CAN", "Reading thread exited")

    

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
