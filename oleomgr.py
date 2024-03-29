from typing import OrderedDict
import yaml, sys, math, cantools, pprint, copy, traceback, csv
from cantools.database.can.signal import NamedSignalValue
from os import listdir
from os.path import isfile, join

'''
OpenLEO database and CAN message generation scripts
Copyright (c) 2022 - OpenLEO.org / lorddevereux

- Import DBC
- Import/Export yaml message definitions 
- Export C code
- Import/merge message and signal translations
- Export database information for manual use
'''


class oleomgr:

    configuration = {}
    TAB = " "
    TAB2 = "  "
    TAB3 = "   "
    TAB4 = "    "
    MODE_OLEO = 1           # 1.7 1.6 1.5
    MODE_CANT = 2           # 1.0 1.1 1.2

    def __init__(self, owner, config):
        self.messages = OrderedDict()

        if config is not None:
            self.configuration = config
            for i in range(self.configuration["tab_space_num"]):
                self.TAB = self.TAB + " "
            self.TAB2 = self.TAB + self.TAB
            self.TAB3 = self.TAB2 + self.TAB
            self.TAB4 = self.TAB2 + self.TAB2

        self.owner = owner
        self.vehicle_networks = {}

        


    def log(self, hdr, msg = None):
        if self.owner is not None:
            if msg is None:
                msg = hdr
                hdr = "OMG"
                
            self.owner.log(hdr, msg)
        else:
            print(hdr, msg)


    def to_hex(self, raw_val, lng=3):
        return "{0:0{1}x}".format(raw_val, lng).upper()


    def dget(self, dic, key, default = 0):
        '''
        Safely get a given key from a dictionary
        or else return a default value
        '''
        if type(dic) is not dict:
            return default

        if key in dic:
            return dic[key]
        else:
            return default


    def bitmask(self, bit, length = 1, lng = 8):
        '''
        Generate a bitmask for a bit at position bit
        '''
        out = "0b"
        end = bit + (length - 1)

        for i in range(lng):
            if i >= bit and i <= end:
                out = out + "1"
            else:
                out = out + "0"

        return out


    def endian_translate(self, start):
        '''
        Convert from the strange bit numbering (endian-ified)
        to something we can use in code
        '''
        start_byte = math.ceil((start + 1) / 8)
        start_bit  = start % 8

        return ((start_byte - 1) * 8) + (7-start_bit)


    def yml_bits_encode(self, signal: cantools.database.can.Signal, output_mode=1):
        '''
        Convert DBC start + length to OpenLEO byte.bit format

        1.7 1.6 1.5 1.4 1.3 1.2 1.1 1.0 2.7 2.6 2.5
        '''

        # the start position is actually the left most bit
        # + 1 so the division works properly with non zero indexed bytes
        start_byte = math.ceil((signal.start + 1) / 8)
        start_bit  = signal.start % 8

        if signal.length == 1:
            if output_mode == self.MODE_OLEO:
                return str(start_byte) + "." + str(start_bit)
            elif output_mode == self.MODE_CANT:
                return str(start_byte) + "." + str(7 - start_bit)    

        this_bit = start_bit
        this_byte = start_byte
        length_left = signal.length - 1

        while (length_left > 0):
            this_bit -= 1
            if this_bit == -1:
                this_byte += 1
                this_bit = 7
            length_left -= 1

        if output_mode == self.MODE_OLEO:
            return str(start_byte) + "." + str(start_bit) + "-" + str(this_byte) + "." + str(this_bit)
        elif output_mode == self.MODE_CANT:
            return str(start_byte) + "." + str(7 - start_bit) + "-" + str(this_byte) + "." + str(7 - this_bit)


    def yml_bits_decode(self, bits_str, input_mode = 1):
        '''
        Invert the operation above
        '''
        bit_start = 0
        bit_length = 0


        if "-" in bits_str:
            try:
                start_pos, end_pos = bits_str.split("-")
                start_byte, start_bit = start_pos.split(".")
                end_byte, end_bit = end_pos.split(".")

                start_byte = int(start_byte)
                end_byte = int(end_byte)
                start_bit = int(start_bit)
                end_bit = int(end_bit)

                if input_mode == self.MODE_CANT:
                    start_bit = 7 - start_bit
                    end_bit = 7 - end_bit
            except:
                self.log("Error splitting yml_bits - " + str(bits_str))
                self.log("DMP", str(traceback.format_exc()))
                return False

            start_byte = int(start_byte)
            end_byte = int(end_byte)
            start_bit = int(start_bit)
            end_bit = int(end_bit)
            bit_start = ((start_byte - 1) * 8) + (start_bit)

            this_byte = start_byte
            this_bit = start_bit
            length_so_far = 1
            
            while not (this_byte == end_byte and this_bit == end_bit):
                this_bit -= 1
                if this_bit == -1:
                    this_byte += 1
                    this_bit = 7
                length_so_far += 1

                if (this_byte > 8):
                    self.log("Error calculating length for yml_bits " + str(bits_str))
                    return False
            
            bit_length = length_so_far

        else:
            start_byte, start_bit = bits_str.split(".")
            start_byte = int(start_byte)
            start_bit = int(start_bit)

            if input_mode == self.MODE_CANT:
                start_bit = 7 - start_bit
            
            bit_start = ((start_byte - 1) * 8) + (start_bit)
            bit_length = 1

        return bit_start, bit_length


    def yml_comment_encode(self, signal, src = None):
        '''
        Extract a string to a comment dict
        '''
        output = {}

        if type(signal) is dict:
            if src is not None:
                signal["src"] = src
            
            output = signal
            #if "alt_name" not in output:
            #    output["alt_name"] = ""
            if "en" not in output:
                output["en"] = ""
            if "fr" not in output:
                output["fr"] = ""
            if "src" not in output:
                output["src"] = ""

            return output

        if signal is None:
            if src is not None:
                output["src"] = src

        try:
            if ";" in signal:
                comments = signal.split(";")
                for comment in comments:
                    csplit = comment.split("=")
                    output[csplit[0]] = csplit[1]

                if src is not None:
                    output["src"] = src
            else:
                output["fr"] = signal
        except:
            pass

        #if "alt_name" not in output:
        #    output["alt_name"] = ""
        if "en" not in output:
            output["en"] = ""
        if "fr" not in output:
            output["fr"] = ""
        if "src" not in output:
            output["src"] = ""

        return output


    def yml_comment_decode(self, comment):
        out = ""

        if type(comment) is str or comment is None:
            return comment

        else:
            for key in comment:
                if "comment_" in key:
                    key_new = key.replace("comment_", "")
                else:
                    key_new = key
                out = out + key_new + "=" + comment[key] + ";"
            return out[:-1]


    def txt_choices_encode(self, choices):
        '''
        Choices is a cantools choices object
        '''
        out = ""
        if choices == None:
            return ""

        return str(choices)

    
    def clean(self):
        '''
        Clear the internal db
        '''
        self.messages = OrderedDict()


    def get_comment(self, comment, lang):
        db = self.yml_comment_encode(comment)

        if type(db) is dict:
            if lang in db:
                return db[lang]

        return ""


    def import_from_dbc(self, fname):
        '''
        Import DBC
        '''
        db = None
        
        try:
            db = cantools.database.load_file(fname, encoding = 'utf-8')
        except:
            self.log("Failed in strict mode - trying tolerant mode")
            try:
                db = cantools.database.load_file(fname, strict=False, encoding = 'utf-8')
            except:
                self.log("Failed in normal mode - check the file and try again")
                self.log("DMP", str(traceback.format_exc()))
                return False
        self.log("Loaded " + str(len(db.messages)) + " messages")

        added = 0
        for message in db.messages:
            if message.frame_id not in self.messages:
                print(message.frame_id, type(message.frame_id))
                added += 1
                self.messages[message.frame_id] = message
        
        self.log("Actually added " + str(added) + " messages")

        self.check_message_structure()
        
        return True


    def export_to_dbc(self, fname, include_list):
        '''
        Export messages as DBC database to fname
        filter messages/signals as given by chosen
        '''
        messages_export = []
        ctr = 0

        fname = str(fname)
        try:
            if fname.split(".")[-1] != "dbc":
                fname = fname + ".dbc"
        except:
            fname = fname + ".dbc"

        for mid in self.messages:
            message = self.messages[mid]

            if message.frame_id not in include_list:
                ctr += 1
                continue
            
            signal_export = []
            signal_offset = 0
            for signal in message.signals:
                if type(include_list[message.frame_id]) == list:
                    if signal_offset in include_list[message.frame_id]:
                        signal_export.append(signal)
                else:
                    signal_export.append(signal)
                signal_offset += 1
            
            messages_export.append(message)
            messages_export[-1].signals = signal_export
        
        db = cantools.database.can.Database(messages = messages_export, strict=False)
        # todo - check endianness, update is_signed and is_decimal from datatype
        cantools.database.dump_file(db, fname, 'dbc', encoding = 'utf-8')

        return True


    def check_message_structure(self):
        '''
        Do standard checks on the database after import to make sure it conforms to spec

        # re-order to sort by frame ID
        # force all signal choices to be NamedSignalValue
        '''
        self.messages = OrderedDict(sorted(self.messages.items()))

        for message in self.messages:
            for signal in self.messages[message].signals:
                if signal.choices != None:
                    for choice in signal.choices:
                        if type(signal.choices[choice]) != NamedSignalValue:
                            signal.choices[choice] = NamedSignalValue(choice, signal.choices[choice], "")

    
    def export_all_signals(self, fname, include_list, comment_src = None, callback = None):
        '''
        Export all selected signals to CSV
        '''
        ctr = 0

        csvfile = open(fname, 'w', newline='')
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        row = []
 
        for mid in self.messages:
            message = self.messages[mid]
            yaml_tree = {}

            if message.frame_id not in include_list:
                ctr += 1
                continue

            receivers = []

            signal_offset = 0
            for signal in message.signals:
                if include_list is not None:
                    if message.frame_id not in include_list:
                        continue
                    else:
                        if type(include_list[message.frame_id]) == list:
                            if signal_offset not in include_list[message.frame_id]:
                                continue
                signal_offset += 1

                row.append(self.to_hex(message.frame_id))
                row.append(message.name)
                row.append(",".join(message.senders))
                row.append(signal.name)
                row.append(self.yml_comment_encode(signal.comment)["name_en"])
                row.append(self.yml_comment_encode(signal.comment)["comment_en"])
                writer.writerow(row)
                row = []        

            ctr += 1
        
        csvfile.close()  
        
        return True


    def export_to_yaml_oleo(self, fname, include_list, comment_src = None, callback = None):
        '''
        Export from internal cantools data structure
        to YAML file format
        '''

        mode = 0

        if type(include_list) == int:
            # fname is a full file path
            # if a given message ID is set to 1 instead of a list, it will 
            # export every signal in the message
            include_list = { include_list : 1 }
            mode = 0

            fname = str(fname)

            try:
                if fname.split(".")[-1] != "yml":
                    fname = fname + ".yml"
            except:
                fname = fname + ".yml"
        else:
            # fname is a FOLDER path
            mode = 1

        ctr = 1
 
        for mid in self.messages:
            message = self.messages[mid]
            yaml_tree = {}

            if message.frame_id not in include_list:
                ctr += 1
                continue

            receivers = []

            yaml_tree[message.frame_id] = {
                "id": "0x" + self.to_hex(message.frame_id),
                "name": message.name,
                "length": message.length,
                "type": message.mtype,
                "comment": self.yml_comment_encode(message.comment, comment_src),
                "periodicity": message.cycle_time,
                "senders": message.senders,
                "signals": {}
            }

            id = message.frame_id

            signal_offset = 0
            for signal in message.signals:
                if include_list is not None:
                    if message.frame_id not in include_list:
                        continue
                    else:
                        if type(include_list[message.frame_id]) == list:
                            if signal_offset not in include_list[message.frame_id]:
                                continue
                signal_offset += 1

                choices_clean = None
                if signal.choices is not None:
                    choices_clean = {}
                    for choice in signal.choices:
                        comment_enc = {}
                        comment_enc["comment"] = self.yml_comment_encode(signal.choices[choice].comments)
                        comment_enc["name"] = str(signal.choices[choice])
                        choices_clean[choice] = comment_enc


                yaml_tree[id]["signals"][signal.name] = {
                    "bits": self.yml_bits_encode(signal),
                    #"byte_order": 'big_endian',
                    "type": signal.dtype,
                    "comment": self.yml_comment_encode(signal.comment),
                    "min": signal.minimum,
                    "max": signal.maximum,
                    "factor": signal.scale,
                    "offset": signal.offset,
                    "units": signal.unit,
                    "values": choices_clean
                }

                # add only if relevant to the signal type
                if "bool" in signal.dtype:
                    yaml_tree[id]["signals"][signal.name]["inverted"] = signal.inverted

                # cantools uses receivers by signal, rather than
                # by frame
                for receiver in signal.receivers:
                    if receiver not in receivers:
                        receivers.append(receiver)
            
            yaml_tree[id]["receivers"] = receivers

            #pprint.pprint(yaml.dump(yaml_tree[0xF6]))
            if mode == 0:
                f = open(fname, "w")
                self.log("Exporting yaml " + str(self.to_hex(message.frame_id)))
                yaml.dump(yaml_tree[message.frame_id], f)
                f.close()
                return True
            
            else:
                self.log("Exporting yaml " + str(self.to_hex(message.frame_id)))
                f = open(fname + "/" + self.to_hex(message.frame_id) + ".yml", "w")
                yaml.dump(yaml_tree[message.frame_id], f)
                f.close()

            if callback is not None:
                callback(ctr)

            ctr += 1
        
        return True


    def export_to_yaml(self, fname, include_list, comment_src = None, callback = None):
        '''
        Export from internal cantools data structure
        to YAML file format
        '''

        mode = 0

        if type(include_list) == int:
            # fname is a full file path
            # if a given message ID is set to 1 instead of a list, it will 
            # export every signal in the message
            include_list = { include_list : 1 }
            mode = 0

            fname = str(fname)

            try:
                if fname.split(".")[-1] != "yml":
                    fname = fname + ".yml"
            except:
                fname = fname + ".yml"
        else:
            # fname is a FOLDER path
            mode = 1

        ctr = 1
 
        for mid in self.messages:
            message = self.messages[mid]
            yaml_tree = {}

            if message.frame_id not in include_list:
                ctr += 1
                continue

            receivers = []

            yaml_tree[message.frame_id] = {
                "id": "0x" + self.to_hex(message.frame_id),
                "name": message.name,
                "length": message.length,
                "type": "can",
                "comment": self.yml_comment_encode(message.comment, comment_src),
                "periodicity": message.cycle_time,
                "senders": message.senders,
                "signals": {}
            }

            id = message.frame_id

            signal_offset = 0
            for signal in message.signals:
                if include_list is not None:
                    if message.frame_id not in include_list:
                        continue
                    else:
                        if type(include_list[message.frame_id]) == list:
                            if signal_offset not in include_list[message.frame_id]:
                                continue
                signal_offset += 1

                choices_clean = None
                if signal.choices is not None:
                    choices_clean = {}
                    for choice in signal.choices:
                        comment_enc = {}
                        comment_enc["comment"] = self.yml_comment_encode(signal.choices[choice].comments)
                        comment_enc["name"] = str(signal.choices[choice])
                        choices_clean[choice] = comment_enc

                yaml_tree[id]["signals"][signal.name] = {
                    "bits": self.yml_bits_encode(signal),
                    #"byte_order": 'big_endian',
                    "is_signed": signal.is_signed,
                    "comment": self.yml_comment_encode(signal.comment),
                    "min": signal.minimum,
                    "max": signal.maximum,
                    "factor": signal.scale,
                    "offset": signal.offset,
                    "units": signal.unit,
                    "values": choices_clean
                }

                # cantools uses receivers by signal, rather than
                # by frame
                for receiver in signal.receivers:
                    if receiver not in receivers:
                        receivers.append(receiver)
            
            yaml_tree[id]["receivers"] = receivers

            #pprint.pprint(yaml.dump(yaml_tree[0xF6]))
            if mode == 0:
                f = open(fname, "w")
                self.log("Exporting yaml " + str(self.to_hex(message.frame_id)))
                yaml.dump(yaml_tree[message.frame_id], f)
                f.close()
                return True
            
            else:
                self.log("Exporting yaml " + str(self.to_hex(message.frame_id)))
                f = open(fname + "/" + self.to_hex(message.frame_id) + ".yml", "w")
                yaml.dump(yaml_tree[message.frame_id], f)
                f.close()

            if callback is not None:
                callback(ctr)

            ctr += 1
        
        return True

    def load_vehicle_def(self, fname):
        '''
        Load a vehicle description file
        WIP - only "IS" network supported currently
        '''
        try:
            f = open(fname)
            f_contents = f.readlines()
            f_contents = "".join(f_contents)
            veh = yaml.safe_load(f_contents)

            if "networks" in veh:
                for network in veh["networks"]:
                    if network not in veh:
                        return False
                    
                    else:
                        self.vehicle_networks[network] = []
                        for msg in veh[network]:
                            self.vehicle_networks[network].append(msg)

            self.log("Successfully loaded vehicle file " + str(fname))
            return True
        except:
            self.log("Failed loading vehicle file " + str(fname))
            self.log("DMP", str(traceback.format_exc()))
            return False


    def import_from_yaml_oleo(self, file_list, callback = None):
        '''
        Import from oleo YAML to internal cantools data structure
        '''
        tree = {}
        ctr = 1

        for file_name in file_list:
            try:
                #if self.owner.configuration["debug"] == 1:
                #    self.log("Opening " + str(file_name))
                f = open(file_name)
                f_contents = f.readlines()
                f_contents = "".join(f_contents)
                msg = yaml.safe_load(f_contents)
            except:
                msg = None
                self.log("DMP", str(traceback.format_exc()))

            msg_signals = []

            if msg is None:
                self.log("Failed to load " + str(file_name))
                continue

            if "signals" not in msg:
                self.log("Missing SIGNAL definitions for message " + str(file_name))
            
            for signal in msg["signals"]:
                if self.owner.configuration["debug"] == 1:
                    print(signal)
                result = self.yml_bits_decode(msg["signals"][signal]["bits"])
                if not result:
                    continue

                bit_start, bit_length = result

                # decode comment fields of choices
                choices = self.dget(msg["signals"][signal], "values", {})
                choices_loaded = {}
                if choices is not None:
                    for choice in choices:
                        if type(choices[choice]) == dict:
                            # new format
                            if "comment" in choices[choice] and "name" in choices[choice]:
                                choices_loaded[choice] = NamedSignalValue(value=choice, name=choices[choice]["name"], comments=self.yml_comment_decode(choices[choice]["comment"]))
                                #print("New: ", choices[choice]["name"])
                            # legacy format
                            elif "en" in choices[choice]:
                                choices_loaded[choice] = NamedSignalValue(value=choice, name=choices[choice]["en"], comments=self.yml_comment_decode(choices[choice]))
                                #print("Old: ", choices[choice["en"]])
                            else:
                                pass
                                #print("SHOULDNT GET HERE, INVALID FILES")
                        else:
                            choices_loaded[choice] = NamedSignalValue(value=choice, name=choices[choice])
                            #print("Other type ", type(choice))
                stype = self.dget(msg["signals"][signal], "type", "uint")
                is_signed = False
                is_decimal = False

                if stype == "uint":
                    is_signed = False
                    is_decimal = False
                if stype == "sint":
                    is_signed = True
                    is_decimal = False
                if stype == "float" or stype == "double":
                    is_signed = True
                    is_decimal = True
                
                if "is_signed" in msg["signals"][signal]:
                    if msg["signals"][signal]["is_signed"]:
                        stype = "sint"

                msg_signals.append(
                    cantools.database.can.Signal(
                        name = signal,
                        byte_order = self.dget(msg["signals"][signal], "endian", "big_endian"), 
                        start = bit_start,
                        length = bit_length,
                        scale = self.dget(msg["signals"][signal], "factor", 1),
                        offset = self.dget(msg["signals"][signal], "offset", 0),
                        is_signed = is_signed,
                        is_float = is_decimal,
                        dtype = stype,
                        inverted = self.dget(msg["signals"][signal], "inverted", False),
                        minimum = self.dget(msg["signals"][signal], "min", None),
                        maximum = self.dget(msg["signals"][signal], "max", None),
                        unit = self.dget(msg["signals"][signal], "units", ""),
                        choices = choices_loaded,
                        receivers = self.dget(msg, "receivers", None),
                        comment = self.yml_comment_decode(self.dget(msg["signals"][signal], "comment", ""))
                    )
                )

            frame_id = msg["id"]
            if type(frame_id) is not int:
                frame_id = int(frame_id, 16)

            periodicity = self.dget(msg, "periodicity", None)
            if type(periodicity) == str:
                periodicity.replace("ms", "")

            tree[frame_id] = cantools.database.can.Message(
                strict = False,
                frame_id = frame_id,
                is_extended_frame = False,
                name = msg["name"],
                length = self.dget(msg, "length", 8),
                signals = msg_signals,
                mtype = self.dget(msg, "type", "can"),
                comment = self.yml_comment_decode(self.dget(msg, "comment", "")),
                senders = self.dget(msg, "senders", 8),
                cycle_time = periodicity
            )

            if callback is not None:
                callback(ctr)

            ctr += 1

        self.ignored_messages = 0
        self.added_messages = 0

        for message in tree:
            if message not in self.messages:
                self.added_messages += 1
                self.messages[message] = tree[message]
            else:
                self.ignored_messages += 1
        
        self.log("Imported " + str(self.added_messages) + " messages, " + str(self.ignored_messages) + " messages already exist and were skipped")

        if len(self.messages) > 0:
            self.check_message_structure()
            return True
        else:
            self.log("No messages loaded")
            return False


    def import_from_yaml(self, file_list, callback = None):
        '''
        Import from YAML to internal cantools data structure
        '''
        tree = {}
        ctr = 1

        try:

            for file_name in file_list:
                try:
                    self.log("Opening " + str(file_name))
                    f = open(file_name)
                    f_contents = f.readlines()
                    f_contents = "".join(f_contents)
                    msg = yaml.safe_load(f_contents)
                except:
                    msg = None
                    self.log("DMP", str(traceback.format_exc()))

                msg_signals = []

                if msg is None:
                    self.log("Failed to load " + str(file_name))
                    continue

                if "signals" not in msg:
                    self.log("Missing SIGNAL definitions for message " + str(file_name))
                
                for signal in msg["signals"]:
                    print(signal)
                    result = self.yml_bits_decode(msg["signals"][signal]["bits"])
                    if not result:
                        continue

                    bit_start, bit_length = result

                    # decode comment fields of choices
                    choices = self.dget(msg["signals"][signal], "values", {})
                    choices_loaded = {}
                    if choices is not None:
                        for choice in choices:
                            if type(choices[choice]) == dict:
                                # new format
                                if "comment" in choices[choice] and "name" in choices[choice]:
                                    choices_loaded[choice] = NamedSignalValue(value=choice, name=choices[choice]["name"], comments=self.yml_comment_decode(choices[choice]["comment"]))
                                # legacy format
                                if "en" in choices[choice]:
                                    choices_loaded[choice] = NamedSignalValue(value=choice, name=choices[choice]["en"], comments=self.yml_comment_decode(choices[choice]))
                            else:
                                choices_loaded[choice] = choices[choice]

                    msg_signals.append(
                        cantools.database.can.Signal(
                            name = signal,
                            byte_order = self.dget(msg["signals"][signal], "endian", "big_endian"), 
                            start = bit_start,
                            length = bit_length,
                            scale = self.dget(msg["signals"][signal], "factor", 1),
                            offset = self.dget(msg["signals"][signal], "offset", 0),
                            is_signed = self.dget(msg["signals"][signal], "is_signed", 0),
                            minimum = self.dget(msg["signals"][signal], "min", None),
                            maximum = self.dget(msg["signals"][signal], "max", None),
                            unit = self.dget(msg["signals"][signal], "units", ""),
                            choices = choices_loaded,
                            receivers = self.dget(msg, "receivers", None),
                            comment = self.yml_comment_decode(self.dget(msg["signals"][signal], "comment", ""))
                        )
                    )

                frame_id = msg["id"]
                if type(frame_id) is not int:
                    frame_id = int(frame_id, 16)

                tree[frame_id] = cantools.database.can.Message(
                    strict = False,
                    frame_id = frame_id,
                    is_extended_frame = False,
                    name = msg["name"],
                    length = self.dget(msg, "length", 8),
                    signals = msg_signals,
                    comment = self.yml_comment_decode(self.dget(msg, "comment", "")),
                    senders = self.dget(msg, "senders", 8),
                    cycle_time = self.dget(msg, "periodicity", None)
                )

                if callback is not None:
                    callback(ctr)

                ctr += 1

            self.ignored_messages = 0
            self.added_messages = 0

            for message in tree:
                if message not in self.messages:
                    self.added_messages += 1
                    self.messages[message] = tree[message]
                else:
                    self.ignored_messages += 1
            
            self.log("Imported " + str(self.added_messages) + " messages, " + str(self.ignored_messages) + " messages already exist and were skipped")

            if len(self.messages) > 0:
                self.check_message_structure()
                return True
            else:
                self.log("No messages loaded")
                return False
        except:
            self.log("DMP", traceback.format_exc())
            return False


    def merge_names_to_existing_yaml(self, base_tree_fldr, trans_tree_fldr, out_fldr):
        '''
        This will copy comments and name fields from trans_tree to base_tree
        Used when bugs are found which have damaged data in base_tree
        '''
        file_list = [(base_tree_fldr + "/" + f) for f in listdir(base_tree_fldr) if isfile(join(base_tree_fldr, f))]
        rslt = self.import_from_yaml(file_list)
        base = copy.deepcopy(self.messages)
        self.messages = {}
        file_list = [(trans_tree_fldr + "/" + f) for f in listdir(trans_tree_fldr) if isfile(join(trans_tree_fldr, f))]
        rslt = self.import_from_yaml(file_list)
        trans = copy.deepcopy(self.messages)
        self.messages = {}

        for msg in base:
            if msg not in trans:
                self.log("Message " + str(msg) + " missing from trans tree")
                continue

            base[msg].name = trans[msg].name
            base[msg].comment = trans[msg].comment

            if base[msg].signals == None:
                self.log("Message " + str(msg) + " no signals")
                continue

            if len(base[msg].signals) != len(trans[msg].signals):
                self.log("Message " + str(msg) + " signals count mismatch")
                continue

            sid = 0
            for signal in base[msg].signals:
                base[msg].signals[sid].name = trans[msg].signals[sid].name
                base[msg].signals[sid].comment = trans[msg].signals[sid].comment

                sid += 1

        self.messages = base
        inc_list = {}
        for key in base.keys():
            inc_list[key] = 1

        rslt = self.export_to_yaml(out_fldr, inc_list)
        self.log("Write result: " + str(rslt))


    def export_to_struct(self, fname, include_list):
        '''
        Write the structure definitions for a given database

        TODO:
        - defines need to exclude special characters / be less rubbish

        - use NAME_EN if it exists for signal + message names, else NAME
        - use NAME if it exists for signal choices and doesn't have spaces, else signal NAME_VALUE
        '''

        out = []
        defines = []
        errors = 0

        defined = {}

        self.log("Exporting " + str(include_list.keys()))

        #out.append("typedef unsigned long int uint32_t;")
        #out.append("typedef unsigned char uint8_t;")
        out.append("")
        
        for message in self.messages:
            if include_list is not None:
                if self.messages[message].frame_id not in include_list:
                    continue

            message_name = self.messages[message].name.upper()
            cmt = self.yml_comment_encode(self.messages[message].comment)
            if cmt["name_en"] is not None and " " not in cmt["name_en"] and len(cmt["name_en"]) > 1:
                message_name = cmt["name_en"].upper()

            out.append("struct " + self.configuration['STRUCT_PREFIX'] + message_name + "{")

            mid = self.to_hex(message)

            signal_offset = 0
            for signal in self.messages[message].signals:
                if include_list is not None:
                    if self.messages[message].frame_id not in include_list:
                        continue
                    elif signal_offset not in include_list[self.messages[message].frame_id]:
                        continue
                signal_offset += 1

                chosen_name = signal.name
                cmt = self.yml_comment_encode(signal.comment)
                if cmt["name_en"] is not None and " " not in cmt["name_en"] and len(cmt["name_en"]) > 1:
                    chosen_name = cmt["name_en"].upper()

                

                if signal.choices is not None:
                    for choice in signal.choices:
                        if " " not in signal.choices[choice].name:
                            chc_name = ("M_" + mid + "_" + signal.choices[choice].name).upper()
                            if chc_name not in defined:
                                defines.append("#define " + chc_name + "    " + str(choice))
                                defined[chc_name] = choice
                            elif defined[chc_name] != choice:
                                self.log("WARNING: Signal choice value define mismatch: " + str(signal.name) + " - " + str(chc_name) + " does not match " + str(choice))
                                errors += 1
                        else:
                            chc_name = ("M_" + mid + "_" + chosen_name + "_" + str(choice)).upper()
                            if chc_name not in defined:
                                defines.append("#define " + chc_name + "    " + str(choice))
                                defined[chc_name] = choice
                            elif defined[chc_name] != choice:
                                self.log("WARNING: Signal choice value define mismatch: " + str(signal.name) + " - " + str(defined[chc_name]) + " does not match " + str(choice))
                                errors += 1

                if signal.length <= 8:
                    max_val = signal.scale * 255
                elif signal.length <= 16:
                    max_val = signal.scale * 65535
                elif signal.length <= 32:
                    max_val = signal.scale * 1000000
                
                if max_val <= 128 and signal.is_signed:
                    df_type = self.configuration['TYPE_S8']
                elif max_val <= 255 and not signal.is_signed:
                    df_type = self.configuration['TYPE_U8']
                elif max_val <= 32767 and signal.is_signed:
                    df_type = self.configuration['TYPE_S16']
                elif max_val <= 65535 and not signal.is_signed:
                    df_type = self.configuration['TYPE_U16']
                elif signal.is_signed:
                    df_type = self.configuration['TYPE_S32']
                else:
                    df_type = self.configuration['TYPE_U32']

                out.append(self.TAB + df_type + " " + chosen_name + ";")

            out.append("} " + self.configuration['STRUCT_PREFIX'] + message_name + "; ")
            out.append("")

        if errors > 0:
            return errors
        

        print()
        print()
        
        with open(fname + '_messages.h', 'w') as f:
            for line in defines:
                f.write("%s\n" % line)
            f.write("\n\n")
            for line in out:
                f.write("%s\n" % line)

        return 0


    def export_parser_c(self, fname, include_list):
        '''
        Export automatic parsing functions for OLE databases

        TODO
        - Restrict to limits
        '''

        out = []
        out_h = []
        defines = []
        out_sw = []

        file_only = fname.split("/")[-1]

        out_h.append('#include "' + file_only + '_messages.h"')
        out_h.append("")
        out_h.append("uint8_t " + self.configuration['FUNC_PARSE_PREFIX'] + "RAW_CAN(uint32_t id, uint8_t len, uint8_t* ptr);")

        out.append('#include "' + file_only + '.h"')
        out.append("")

        out_sw.append("uint8_t " + self.configuration['FUNC_PARSE_PREFIX'] + "RAW_CAN(uint32_t id, uint8_t len, uint8_t* ptr){")
        out_sw.append(self.TAB + "switch(id){")
        
        
        for message in self.messages:
            if include_list is not None:
                if self.messages[message].frame_id not in include_list:
                    continue
            
            message_name = self.messages[message].name.upper()
            cmt = self.yml_comment_encode(self.messages[message].comment)
            if cmt["name_en"] is not None and " " not in cmt["name_en"] and len(cmt["name_en"]) > 1:
                message_name = cmt["name_en"].upper()

            defines.append("#define MSG_" + message_name + self.TAB + str(message))

            out_h.append("void " + self.configuration['FUNC_PARSE_PREFIX'] + message_name + "(uint8_t* data, struct " + self.configuration['STRUCT_PREFIX'] + message_name + "* ptr);")

            out.append("void " + self.configuration['FUNC_PARSE_PREFIX'] + message_name + "(uint8_t* data, struct " + self.configuration['STRUCT_PREFIX'] + message_name + "* ptr) {")
            out.append("")

            signal_offset = 0
            for signal in self.messages[message].signals:
                if include_list is not None:
                    if self.messages[message].frame_id not in include_list:
                        continue
                    elif signal_offset not in include_list[self.messages[message].frame_id]:
                        continue
                signal_offset += 1

                chosen_name = signal.name
                cmt = self.yml_comment_encode(signal.comment)
                if cmt["name_en"] is not None and " " not in cmt["name_en"] and len(cmt["name_en"]) > 1:
                    chosen_name = cmt["name_en"].upper()

                bitlen = signal.length
                start = self.endian_translate(signal.start)
                byte_start = math.trunc(start / 8)
                byte_end   = math.floor((start + (signal.length - 1)) / 8)
                bit_in_byte_start = start - (byte_start * 8)
                print(chosen_name, str(bitlen), str(start), str(bit_in_byte_start))

                data_assemble = ""
                byte_this = byte_start
                bits_left = bitlen
                
                while(bits_left > 8):
                    data_assemble = data_assemble + "data[" + str(byte_this) + "] << " + str(bits_left - 8) + " | "
                    bits_left -= 8
                    byte_this += 1
                data_assemble = data_assemble + "data[" + str(byte_end) + "]"

                if bitlen == 8 or bitlen == 16 or bitlen == 24 or bitlen == 32:
                    bitmask = ")"
                else:
                    bitmask = " & " + self.bitmask(bit_in_byte_start, bitlen)
                    if (8 - (bit_in_byte_start + bitlen)) != 0:
                        bitmask = bitmask + ") >> " + str(8 - (bit_in_byte_start + bitlen))
                    else:
                        bitmask = bitmask + ")"

                if signal.scale != 1:
                    bitmask = bitmask + ") * " + str(signal.scale)
                else:
                    bitmask = bitmask + ")"

                if signal.offset != 0:
                    if signal.offset < 0:
                        bitmask = bitmask + " - " + str(signal.offset * -1)
                    else:
                        bitmask = bitmask + " + " + str(signal.offset)
                out.append(self.TAB + "ptr->" + chosen_name + " = (((" + data_assemble + ")" + bitmask + ";")        


            out.append("}")
            out.append("")

            out_sw.append(self.TAB2 + "case MSG_" + message_name + ":")
            out_sw.append(self.TAB3 + "if (" + str(self.messages[message].length) + " == len)")
            out_sw.append(self.TAB4 + self.configuration['FUNC_PARSE_PREFIX'] + message_name + "(ptr, &" + self.configuration['STRUCT_PREFIX'] + message_name + ");")
            out_sw.append(self.TAB3 + "else")
            out_sw.append(self.TAB4 + "return 2;")
            out_sw.append(self.TAB3 + "return 1;")
        
        out_sw.append(self.TAB2 + "default:")
        out_sw.append(self.TAB3 + "return 0;")
        out_sw.append(self.TAB + "}")
        out_sw.append("}")
        
        with open(fname + '.h', 'w') as f:
            for line in defines:
                f.write("%s\n" % line)
            f.write("\n\n")
            for line in out_h:
                f.write("%s\n" % line)
        
        with open(fname + '.c', 'w') as f:
            for line in out:
                f.write("%s\n" % line)
            f.write("\n\n")
            for line in out_sw:
                f.write("%s\n" % line)



    def get_translation_list(self, tree):
        '''
        Dump a list of CAN signal names for translation
        '''
        for message in tree:
            for signal in message.signals:
                print(self.to_hex(message.frame_id) + "," + message.name + "," + signal.name)

'''

inst = oleomgr(None, None)
fd = "../database/04conf"
file_list = [(fd + "/" + f) for f in listdir(fd) if isfile(join(fd, f))]
inst.import_from_yaml_oleo(file_list)
lis = {}
for key in inst.messages:
    lis[key] = 1

inst.export_to_yaml_oleo("../database/04conf_new", lis)
'''
#inst.merge_names_to_existing_yaml("../database/04_conf_clean", "../database/04_conf_trans", "../database/04_conf_out")
