from binascii import unhexlify
import re
import time
import serial
import csv
import can


class InvalidFrame(Exception):
    pass


class SourceHandler:
    """Base class for classes reading CAN messages.

    This serves as a kind of interface for all classes reading CAN messages,
    whatever the source of these messages: serial port, text file etc.
    """

    bus = ""
    veh = ""
    cs = None

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def log_open(self):
        try:          
            fname = "../../CAN Dumps/CANView_"
            if self.veh != "":
                fname = fname + self.veh + "_"
            if self.bus != "":
                fname = fname + self.bus + "_"

            fname = fname + str(int(time.time())) + ".csv"
            csvfile = open(fname, 'w', newline='')
            self.cs = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        except:
            print("[CAN] Logging not available.")


    def get_message(self):
        """Get CAN id and CAN data.

        Returns:
            A tuple containing the id (int) and data (bytes)

        Raises:
            InvalidFrame
        """
        raise NotImplementedError

class CANHandler(SourceHandler):

    def __init__(self, bus = "", veh=""):
        self.bus = bus
        self.veh = veh


    def open(self):
        self.log_open()
        self.can0 = can.interface.Bus(channel = 'can0', bustype = 'socketcan_ctypes')


    def close(self):
        self.can0.shutdown()


    def send_message(self, nid, msg_data):
        m = can.Message(arbitration_id=nid,
                      data=msg_data,
                      is_extended_id=False)
        x = self.can0.send(m)


    def get_message(self):
        while True:
            msg = self.can0.recv(3.0)

            if msg is None:
                continue

            if self.cs != None:
                dat = [self.bus, str(int(round(time.time() * 1000)))]
                for byt in msg.data:
                    dat.append(self.to_hex(byt))
                self.cs.writerow(dat)

            

            return self.to_hex(msg.arbitration_id,3), msg.data


    def to_hex(self, inp, ln = 2):
        return "{0:0{1}x}".format(inp, ln).upper()


class SerialHandler(SourceHandler):

    def __init__(self, device_name, baudrate=115200, bus="", veh=""):
        self.device_name = device_name
        self.baudrate = baudrate
        self.serial_device = None
        self.bus = bus      
        self.veh = veh


    def open(self):
        self.log_open()
        self.serial_device = serial.Serial(self.device_name, self.baudrate, timeout=0)


    def close(self):
        if self.serial_device:
            self.serial_device.close()


    def get_message(self):
        inp = self._read_until_newline()
        line = inp.decode("utf-8")
        try:
            b = line.split(" ")
            b.insert(0, self.bus)
            b.insert(0, str(int(round(time.time() * 1000))))
            self.cs.writerow(b)
        except:
            print("[CAN] Logging error")
        return self._parse(line)


    def _read_until_newline(self):
        """Read data from `serial_device` until the next newline character."""
        line = self.serial_device.readline()
        while not line.endswith(b'\n'):
            line = line + self.serial_device.readline()

        return line.strip()

    @staticmethod
    def _parse(line):
        # Sample frame from Arduino: 246 8E 62 1C F6 1E 63 63 20
        
        # Split it into an array
        # (e.g. [ '246', '8E 62 1C F6 1E 63 63 20'])
        frame = line.split(" ", maxsplit=1)

        #try:
        frame_id = frame[0]  # get the ID from the 'ID=246' string

        #frame_length = int(frame[2][4:])  # get the length from the 'LEN=8' string

        hex_data = frame[1].split(" ")
        bytes = []
        #print(frame_id)
        #print(hex_data)
        for x in hex_data:
            bytes.append(int(x, 16))

        #except (IndexError, ValueError) as exc:
        #    raise InvalidFrame("Invalid frame {}".format(line)) from exc

        #if len(data) != frame_length:
        #    raise InvalidFrame("Wrong frame length or invalid data: {}".format(line))

        return frame_id, bytes

class ArdLogHandler(SourceHandler):
    # Parser for custom CAN logger CSV format
    def __init__(self, file_name, owner):
        self.filename = file_name
        self.owner = owner

    def open(self, bus=""):
        self.csvfile = open(self.filename, newline='')
        self.f = csv.reader(self.csvfile, delimiter=' ', quotechar='|')
        self.is_timestamped = None
        self.is_bussed = None
        self.is_offset = 0
        self.bus = bus

    def get_message(self):
        # introduce a fake message delay
        time.sleep(self.owner.simDelayMs/1000.0)
        line = next(self.f)

        if self.is_timestamped == None:
            if len(line[0]) > 4:
                self.is_timestamped = True
                self.is_offset = self.is_offset + 1
                print("[SIM] Selected simulation includes timestamps. Speed set to " + str(self.owner.simDelayMs))               
                if len(line[1]) > 4:
                    self.is_bussed = True
                    self.is_offset = self.is_offset + 1
                    print("[SIM] Selected simulation includes bus information")
                    if self.bus != "" and self.bus != line[1]:
                        print("[SIM] WARNING: Bus definitions loaded do not match the log data")
                else:
                    self.is_bussed = False
            else:
                self.is_timestamped = False
                print("[SIM] Selected simulation has no timestamps. Delay set to " + str(self.owner.simDelayMs/1000.0))
            
        can_id = line[self.is_offset]
        
        bytes = []
        for x in line[(self.is_offset + 1):]:
            bytes.append(int(x, 16))
        return can_id, bytes
            

class CandumpHandler(SourceHandler):
    """Parser for text files generated by candump."""

    MSG_RE = r".* ([0-9A-F]+)\#([0-9A-F]*)"
    MSG_RGX = re.compile(MSG_RE)

    def __init__(self, file_path):
        self.file_path = file_path
        self.file_object = None

    def open(self):
        # interface name in candump file may contain non-ascii chars so we need utf-8
        self.file_object = open(self.file_path, 'rt', encoding='utf-8')

    def close(self):
        if self.file_object:
            self.file_object.close()

    def get_message(self):
        line = self.file_object.readline()
        if line == '':
            raise EOFError
        return self._parse_from_candump(line)

    @classmethod
    def _parse_from_candump(cls, line):
        line = line.strip('\n')

        msg_match = cls.MSG_RGX.match(line)
        if msg_match is None:
            raise InvalidFrame("Wrong format: '{}'".format(line))

        hex_can_id, hex_can_data = msg_match.group(1, 2)

        can_id = int(hex_can_id, 16)

        try:
            can_data = bytes.fromhex(hex_can_data)
        except ValueError as err:
            raise InvalidFrame("Can't decode message '{}': '{}'".format(line, err))

        return can_id, can_data
