import yaml, sys, math, cantools, pprint

'''
OpenLEO database and CAN message generation scripts

- Import DBC
- Import/Export yaml message definitions 
- Export C code
- Import/merge message and signal translations
- Export database information for manual use
'''

help_text = '''
OPENLEO CAN standards management utility v1.0
----------------------------------------------
Copyright (c) 2022 - OpenLEO.org

usage:  openleo-mgr NETWORK_FOLDER <options> -m=MESSAGE_LIST

-c      generate C parsing code
-s      generate structs
-m      generate only the messages in MESSAGE_LIST file
        see docs for syntax

'''


class oleomgr:

    STRUCT_PREFIX = "ole07_"
    FUNC_PARSE_PREFIX = "ole07_parse_"
    TYPE_S8 = "int8_t "
    TYPE_U8 = "uint8_t"
    TYPE_S16 = "int16_t "
    TYPE_U16 = "uint16_t"
    TYPE_U32 = "uint32_t"
    TYPE_S32 = "int32_t "
    TAB = "    "

    def __init__(self):
        self.messages = {}

    def log(self, msg):
        print("[LOG] " + str(msg))

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
        byte = math.floor(start / 8)
        rem = start - (byte * 8) + 1

        return (byte * 8) + (8 - rem)

    def yml_bits_encode(self, signal: cantools.database.can.Signal):
        '''
        Encode the bits position as 1.0-1.2 etc
        NOTE: Bytes are NOT zero indexed, but BITS are

        1.7 1.6 1.5 1.4 1.3 1.2 1.1 1.0 2.7 2.6 2.5
        '''
        byte = math.floor(signal.start / 8)
        bit = (8 - (signal.start - (byte * 8)) - 1)
        end_byte = byte

        if signal.length == 1:
            return str(byte + 1) + "." + str(bit)
        
        else:
            lng = signal.length - 1
            if bit + lng < 8:
                end_byte = byte
                end_bit = bit + lng
            else:
                while(bit + lng >= 8):
                    end_byte += 1
                    lng -= 8
                end_bit = lng
            
            return str(byte + 1) + "." + str(bit) + "-" + str(end_byte + 1) + "." + str(end_bit)


    def yml_bits_decode(self, bits_str):
        '''
        Invert the operation above
        '''
        bit_start = 0
        bit_length = 0

        if "-" in bits_str:
            start_pos, end_pos = bits_str.split("-")
            start_byte, start_bit = start_pos.split(".")
            end_byte, end_bit = end_pos.split(".")
            start_byte = int(start_byte)
            end_byte = int(end_byte)
            start_bit = int(start_bit)
            end_bit = int(end_bit)
            bit_start = start_byte * 8 - (start_bit + 1)
            bit_length = ((end_byte - start_byte) * 8) + (end_bit - start_bit) + 1

        else:
            start_byte, start_bit = bits_str.split(".")
            start_byte = int(start_byte)
            start_bit = int(start_bit)
            bit_start = ((start_byte * 8) - (start_bit + 1))
            bit_length = 1

        return bit_start, bit_length


    def yml_comment_encode(self, signal, src = None):
        output = {}

        if type(signal) is dict:
            if src is not None:
                signal["src"] = src
            return signal

        if signal is None:
            if src is not None:
                signal = { "src": src }
                return signal

        try:
            if ";" in signal.comment:
                comments = signal.split(";")
                for comment in comments:
                    csplit = comment.split(":")
                    output[csplit[0]] = csplit[1]

                if src is not None:
                    output["src"] = src
                return output
        except:
            pass

        return signal

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
                return False
        self.log("Loaded " + str(len(db.messages)) + " messages")

        for message in db.messages:
            if message.frame_id not in self.messages:
                self.messages[message.frame_id] = message
        
        return True


    def export_to_yaml(self, tree, include_list, comment_src = None):
        '''
        Export from internal cantools data structure
        to YAML file format
        '''

        yaml_tree = {}

        for message in tree:
            if message.frame_id not in include_list:
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

            for signal in message.signals:
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
            f = open("messages/" + self.to_hex(message.frame_id) + ".yml", "w")
            yaml.dump(yaml_tree[message.frame_id], f)
            f.close()


    def import_from_yaml(self, file_list):
        '''
        Import from YAML to internal cantools data structure
        '''
        tree = {}

        for file_name in file_list:
            try:
                f = open(file_name)
                f_contents = f.readlines()
                f_contents = "".join(f_contents)
                msg = yaml.safe_load(f_contents)
            except:
                msg = None

            msg_signals = []

            if msg is None:
                self.log("Failed to load " + str(file_name))
                continue

            if "signals" not in msg:
                self.log("Missing SIGNAL definitions for message " + str(file_name))
            
            for signal in msg["signals"]:
                bit_start, bit_length = self.yml_bits_decode(msg["signals"][signal]["bits"])
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
                        choices = msg["signals"][signal]["choices"],
                        receivers = msg["receivers"],
                        comment = self.yml_comment_decode(msg["signals"][signal]["comment"])
                    )
                )

            tree[int(msg["id"], 16)] = cantools.database.can.Message(
                #strict = False,
                frame_id = int(msg["id"], 16),
                is_extended_frame = False,
                name = msg["name"],
                length = msg["length"],
                signals = msg_signals,
                comment = self.yml_comment_decode(msg["comment"]),
                senders = msg["senders"],
                cycle_time = msg["periodicity"]
            )

        for message in tree:
            if message not in self.messages:
                self.messages[message] = tree[message]

        if len(self.messages) > 0:
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

            out.append("typedef struct " + self.STRUCT_PREFIX + self.messages[message].name.lower() + "{")

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
                        out.append(self.TAB + self.TYPE_S8 + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.TYPE_U8 + " " + signal.name + ";")
                
                elif signal.length > 8 and signal.length <= 16:
                    if signal.is_signed:
                        out.append(self.TAB + self.TYPE_S16 + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.TYPE_U16 + " " + signal.name + ";")

                elif signal.length > 16 and signal.length <= 32:
                    if signal.is_signed:
                        out.append(self.TAB + self.TYPE_S32 + " " + signal.name + ";")
                    else:
                        out.append(self.TAB + self.TYPE_U32 + " " + signal.name + ";")

            out.append("} " + self.STRUCT_PREFIX + self.messages[message].name.lower() + "; ")
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

            out_h.append("void " + self.FUNC_PARSE_PREFIX + self.messages[message].name.lower() + "(can_msg* msg, " + self.STRUCT_PREFIX + self.messages[message].name.lower() + "* ptr);")

            out.append("void " + self.FUNC_PARSE_PREFIX + self.messages[message].name.lower() + "(can_msg* msg, " + self.STRUCT_PREFIX + self.messages[message].name.lower() + "* ptr) {")
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


# when running as a CLI app:

if __name__ == "__main__":

    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print(help_text)
            sys.exit()

    db = cantools.database.load_file('B9R_CONF_AEE07.dbc', strict=False, encoding = 'utf-8')

    inc_list = [ 0x36, 0xF6, 268, 296 ]
    #cmr.export_to_struct(db.messages, inc_list)

    #cmr.export_parser_c(db.messages, inc_list)

    #pprint.pprint(db.messages[0].signals)

    cmr.export_to_yaml(db.messages, inc_list, comment_src="AEE07-B9R")
    #cmr.import_from_yaml(file_list)

