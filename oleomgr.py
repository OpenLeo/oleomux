from typing import OrderedDict
import yaml, sys, math, cantools, pprint, copy, traceback
from cantools.database.can.signal import NamedSignalValue

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
    TAB = ""
    MODE_OLEO = 1           # 1.7 1.6 1.5
    MODE_CANT = 2           # 1.0 1.1 1.2

    def __init__(self, owner, config):
        self.messages = OrderedDict()
        self.configuration = config
        self.owner = owner

        for i in range(self.configuration["tab_space_num"]):
            self.TAB = self.TAB + " "


    def log(self, hdr, msg = None):
        if self.owner is not None:
            if msg is None:
                msg = hdr
                hdr = "OMG"
                
            self.owner.log(hdr, msg)


    def to_hex(self, raw_val, lng=3):
        return "{0:0{1}x}".format(raw_val, lng).upper()


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

                if input_mode == self.MODE_CANT:
                    start_bit = 7 - start_bit
                    end_bit = 7 - end_bit
            except:
                self.log("Error splitting yml_bits - " + str(bits_str))
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
        output = {}

        if type(signal) is dict:
            if src is not None:
                signal["src"] = src
            
            output = signal

            if "name_en" not in output:
                output["name_en"] = ""
            if "comment_en" not in output:
                output["comment_en"] = ""
            if "comment_fr" not in output:
                output["comment_fr"] = ""
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
                    csplit = comment.split(":")
                    output[csplit[0]] = csplit[1]

                if src is not None:
                    output["src"] = src
            else:
                output["comment_fr"] = signal
        except:
            pass

        if "name_en" not in output:
            output["name_en"] = ""
        if "comment_en" not in output:
            output["comment_en"] = ""
        if "comment_fr" not in output:
            output["comment_fr"] = ""
        if "src" not in output:
            output["src"] = ""

        return output

    def yml_comment_decode(self, comment):
        out = ""

        if type(comment) is str or comment is None:
            return comment

        else:
            for key in comment:
                out = out + key + ":" + comment[key] + ";"
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

        for message in db.messages:
            if message.frame_id not in self.messages:
                self.messages[message.frame_id] = message

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
        # todo - check endianness
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
                        choices_clean[choice] = str(signal.choices[choice])
                yaml_tree[id]["signals"][signal.name] = {
                    "bits": self.yml_bits_encode(signal),
                    #"byte_order": 'big_endian',
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


    def import_from_yaml(self, file_list, callback = None):
        '''
        Import from YAML to internal cantools data structure
        '''
        tree = {}
        ctr = 1

        for file_name in file_list:
            try:
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
                result = self.yml_bits_decode(msg["signals"][signal]["bits"])
                if not result:
                    continue

                bit_start, bit_length = result

                msg_signals.append(
                    cantools.database.can.Signal(
                        name = signal,
                        byte_order = 'big_endian', 
                        start = bit_start,
                        length = bit_length,
                        scale = msg["signals"][signal]["factor"],
                        offset = msg["signals"][signal]["offset"],
                        minimum = msg["signals"][signal]["min"],
                        maximum = msg["signals"][signal]["max"],
                        unit = msg["signals"][signal]["units"],
                        choices = msg["signals"][signal]["values"],
                        receivers = msg["receivers"],
                        comment = self.yml_comment_decode(msg["signals"][signal]["comment"])
                    )
                )

            tree[int(msg["id"], 16)] = cantools.database.can.Message(
                strict = False,
                frame_id = int(msg["id"], 16),
                is_extended_frame = False,
                name = msg["name"],
                length = msg["length"],
                signals = msg_signals,
                comment = self.yml_comment_decode(msg["comment"]),
                senders = msg["senders"],
                cycle_time = msg["periodicity"]
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
            return False


    def export_to_struct(self, fname, include_list):
        '''
        Write the structure definitions for a given database

        TODO:
        - defines need to exclude special characters / be less rubbish
        '''

        out = []
        defines = []
        
        for message in self.messages:
            if include_list is not None:
                if self.messages[message].frame_id not in include_list:
                    continue

            out.append("typedef struct " + self.configuration['STRUCT_PREFIX'] + self.messages[message].name.lower() + "{")

            signal_offset = 0
            for signal in self.messages[message].signals:
                if include_list is not None:
                    if self.messages[message].frame_id not in include_list:
                        continue
                    elif signal_offset not in include_list[self.messages[message].frame_id]:
                        continue
                signal_offset += 1

                if signal.choices is not None:
                    for choice in signal.choices:
                        defines.append("#define " + signal.name + "_" + str(signal.choices[choice]).upper().replace(" ", "_") + "    " + str(choice))

                if signal.length < 8:
                    if signal.is_signed:
                        out.append(self.TAB + self.configuration['TYPE_S8'] + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.configuration['TYPE_U8'] + " " + signal.name + ";")
                
                elif signal.length > 8 and signal.length <= 16:
                    if signal.is_signed:
                        out.append(self.TAB + self.configuration['TYPE_S16'] + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.configuration['TYPE_U16'] + " " + signal.name + ";")

                elif signal.length > 16 and signal.length <= 32:
                    if signal.is_signed:
                        out.append(self.TAB + self.configuration['TYPE_S32'] + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.configuration['TYPE_U32'] + " " + signal.name + ";")

            out.append("} " + self.configuration['STRUCT_PREFIX'] + self.messages[message].name.lower() + "; ")
            out.append("")

        for line in defines:
            print(line)

        print()
        print()
        
        with open(fname + '_messages.h', 'w') as f:
            for line in out:
                f.write("%s\n" % line)


    def export_parser_c(self, fname, include_list):
        '''
        Export automatic parsing functions for OLE databases

        TODO
        - Restrict to limits
        '''

        out = []
        out_h = []

        out_h.append('#include "' + fname + '_messages.h"')
        out_h.append("")

        out.append('#include "' + fname + '.h"')
        out.append("")
        
        for message in self.messages:
            if include_list is not None:
                if self.messages[message].frame_id not in include_list:
                    continue

            out_h.append("void " + self.configuration['FUNC_PARSE_PREFIX'] + self.messages[message].name.lower() + "(can_msg* msg, " + self.configuration['STRUCT_PREFIX'] + self.messages[message].name.lower() + "* ptr);")

            out.append("void " + self.configuration['FUNC_PARSE_PREFIX'] + self.messages[message].name.lower() + "(can_msg* msg, " + self.configuration['STRUCT_PREFIX'] + self.messages[message].name.lower() + "* ptr) {")
            out.append("")

            signal_offset = 0
            for signal in self.messages[message].signals:
                if include_list is not None:
                    if self.messages[message].frame_id not in include_list:
                        continue
                    elif signal_offset not in include_list[self.messages[message].frame_id]:
                        continue
                signal_offset += 1

                bitlen = signal.length
                start = self.endian_translate(signal.start)
                byte_start = math.trunc(start / 8)
                byte_end   = math.floor((start + (signal.length - 1)) / 8)
                bit_in_byte_start = start - (byte_start * 8)
                print(signal.name, str(bitlen), str(start), str(bit_in_byte_start))

                data_assemble = ""
                byte_this = byte_start
                bits_left = bitlen
                
                while(bits_left > 8):
                    data_assemble = data_assemble + "msg->data[" + str(byte_this) + "] << " + str(bits_left - 8) + " | "
                    bits_left -= 8
                    byte_this += 1
                data_assemble = data_assemble + "msg->data[" + str(byte_end) + "]"

                if bitlen == 8 or bitlen == 16 or bitlen == 24 or bitlen == 32:
                    bitmask = ")"
                else:
                    bitmask = " & " + self.bitmask(bit_in_byte_start, bitlen)
                    if (8 - (bit_in_byte_start + bitlen)) != 0:
                        bitmask = bitmask + ") >> " + str(8 - (bit_in_byte_start + bitlen))
                if signal.scale != 1:
                    bitmask = bitmask + ") * " + str(signal.scale)
                else:
                    bitmask = bitmask + ")"
                if signal.offset != 0:
                    if signal.offset < 0:
                        bitmask = bitmask + " - " + str(signal.offset * -1)
                    else:
                        bitmask = bitmask + " + " + str(signal.offset)
                out.append(self.TAB + "ptr->" + signal.name + " = (((" + data_assemble + ")" + bitmask + ";")        


            out.append("}")
            out.append("")
        
        with open(fname + '.h', 'w') as f:
            for line in out_h:
                f.write("%s\n" % line)
        
        with open(fname + '.c', 'w') as f:
            for line in out:
                f.write("%s\n" % line)


    def get_translation_list(self, tree):
        '''
        Dump a list of CAN signal names for translation
        '''
        for message in tree:
            for signal in message.signals:
                print(self.to_hex(message.frame_id) + "," + message.name + "," + signal.name)

