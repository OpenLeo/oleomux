from binascii import unhexlify
from tkinter import E
import can, csv, os, serial, time, re, datetime, traceback, threading


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
    filter_log = None
    owner = None

    def __init__(self, *largs):
        self.adapter_type = "raw"

    def log(self, str):
        if self.owner is not None:
            self.owner.log(str)
        else:
            print("[SRC] " + str)

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def log_open(self):
        try: 
            directory = os.path.dirname("can_logs/")

            if not os.path.exists(directory):
                os.makedirs(directory)
            fname = "can_logs/" + str(datetime.datetime.now().strftime("%d-%m-%Y-%H-%M-%S")) + ".log"

            csvfile = open(fname, 'w', newline='')
            self.cs = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        except:
            print("[DMP]", str(traceback.format_exc()))
            print("[CAN] Logging not available.")


    def get_message(self):
        """Get CAN id and CAN data.

        Returns:
            A tuple containing the id (int) and data (bytes)

        Raises:
            InvalidFrame
        """
        raise NotImplementedError

    
    def adapter_configure(self):
        self.log("This adapter can not be configured")
        return False

    
    def start(self):
        self.log("Nothing to do to start")

    def stop(self):
        self.log("Nothing to do to stop")


class CANHandler(SourceHandler):

    def __init__(self, channel="can0", bus = "", veh=""):
        self.adapter_type = "socketcan"
        self.bus = bus
        self.veh = veh
        self.channel = channel


    def open(self):
        self.log_open()
        self.can0 = can.interface.Bus(channel = self.channel, bustype = 'socketcan_ctypes')


    def close(self):
        self.can0.shutdown()


    def adapter_configure(self, baud_rate):
        '''
        Set the CAN speed
        '''
        pass


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


class SerialHandlerNew(SourceHandler):
    def __init__(self, device_name, baudrate=115200, bus="", veh=""):
        self.adapter_type = "serial"
        self.device_name = device_name
        self.baudrate = baudrate
        self.serial_device = None
        self.bus = bus      
        self.veh = veh
        self.can_speed = 250
        self.connected = False
        self.packets = []
        self.serial_thread = None
        self.thread_event = threading.Event()
        self.serial_thread = threading.Thread(target=self.serial_thread_loop, args=(self.thread_event,), daemon=True)


    def open(self):
        '''
        Open the connection to the serial port
        '''
        self.log_open()
        self.serial_device = serial.Serial(self.device_name, self.baudrate)
        self.connected = True
        self.thread_event.clear()


    def start(self):
        '''
        Start receiving messages and load them into the buffer
        '''
        if not self.connected:
            return False

        self.adapter_configure(self.can_speed)

        self.thread_event.clear()

        if not self.serial_thread.is_alive():
            self.serial_thread.start()

    
    def stop(self):
        '''
        Stop receiving messages
        '''
        if not self.connected:
            return False

        self.thread_event.set()

    
    def adapter_configure(self, baud_rate):
        '''
        Set the CAN speed of the connected arduino
        '''
        self.can_speed = baud_rate
        if self.connected:
            self.log("Change CAN speed to " + str(baud_rate))
            if baud_rate == 125:
                self.serial_device.write(bytearray([ord('a')]))
            elif baud_rate == 250:
                self.serial_device.write(bytearray([ord('f')]))
            elif baud_rate == 500:
                self.serial_device.write(bytearray([ord('m')]))
            else:
                return False
            
            return True
        else:
            return False


    def close(self):
        '''
        Stop receiving messages (and load them into the buffer)
        '''
        if self.serial_device and self.connected:
            self.thread_event.set()
            self.serial_device.close()
            self.connected = False

    
    def crc8(self, crc, extract):
        sum = 0
        for i in range(8):
            sum = (crc ^ extract) & 0x01
            crc >>= 1
            if (sum):
                crc ^= 0x8C
            extract >>= 1     
        return crc

    
    def serial_thread_loop(self, stop_event):
        '''
        Daemon to read from serial bus and stuff in packet
        record
        '''
        while True:
            while not stop_event.is_set():
                this_packet = []
                b = 0
                crc = 0

                for i in range(0, 19):
                    b = int.from_bytes(self.serial_device.read(1), "big")
                    if i < 18:
                        crc = self.crc8(crc, b)
                    this_packet.append(b)
                
                if crc == this_packet[-1]:
                    # message integrity OK
                    print(this_packet)
                    self.packets.append(this_packet)
                else:
                    # resync
                    self.serial_device.write(bytearray([ord('s')]))
                    self.serial_device.flush()
                    self.serial_device.flushInput()
                
            
            while stop_event.is_set():
                time.sleep(0.2)

            # resync before resume
            self.serial_device.write(bytearray([ord('s')]))
            self.serial_device.flush()
            self.serial_device.flushInput()


    def get_message(self):
        '''
        Get the oldest message from the FIFO
        '''
        if len(self.packets) == 0:
            return False

        inp = self.packets.pop(0)

        msg_data = []
        id = inp[0] << 24 | inp[1] << 16 | inp[2] << 8 | inp[3]

        for i in range(0, inp[4]):
            msg_data.append(inp[5 + i])
        timestamp = inp[14] << 24 | inp[15] << 16 | inp[16] << 8 | inp[17]

        if self.filter_log is not None:
            if id not in self.filter_log:
                # skip logging only if we explicitly filtered it out
                return id, msg_data
        
        self.cs.writerow([timestamp, id, inp[4], *msg_data])
        
        return id, msg_data


class SerialHandler(SourceHandler):

    def __init__(self, device_name, baudrate=115200, bus="", veh=""):
        self.adapter_type = "serial_old"
        self.device_name = device_name
        self.baudrate = baudrate
        self.serial_device = None
        self.bus = bus      
        self.veh = veh


    def open(self):
        self.log_open()
        self.serial_device = serial.Serial(self.device_name, self.baudrate, timeout=0)

    
    def adapter_configure(self, baud_rate):
        '''
        Set the CAN speed of the connected arduino
        '''
        print("The adapter does not support changing CAN speed")
        return False


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
        self.adapter_type = "log"
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
        
        try:
            line = next(self.f)
        except:
            return -1

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

    def __init__(self, file_path, owner):
        self.file_path = file_path
        self.file_object = None
        self.owner = owner

    def open(self, bus = ""):
        # interface name in candump file may contain non-ascii chars so we need utf-8
        self.file_object = open(self.file_path, 'rt', encoding='utf-8')

    def close(self):
        if self.file_object:
            self.file_object.close()

    def get_message(self):
        time.sleep(self.owner.simDelayMs/1000.0)
        line = self.file_object.readline()
        if line == '':
            return -1
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

        print(can_id, can_data)

        return can_id, can_data


class CanPrintHandler(SourceHandler):
    """
    Parser for text files generated by candump copied from console
    """

    MSG_RE = r".* ([0-9A-F]+)\#([0-9A-F]*)"
    MSG_RGX = re.compile(MSG_RE)

    def __init__(self, file_path, owner):
        self.filename = file_path
        self.file_object = None
        self.owner = owner

    def open(self, bus = ""):
        # interface name in candump file may contain non-ascii chars so we need utf-8
        self.file_object = open(self.filename, 'rt', encoding='utf-8')

    def close(self):
        if self.file_object:
            self.file_object.close()

    def get_message(self):
        time.sleep(self.owner.simDelayMs/1000.0)
        line = self.file_object.readline()
        if line == '':
            return -1
        return self._parse_from_candump(line)

    @classmethod
    def _parse_from_candump(cls, line):
        hex_can_data = []
        line = line.strip('\n')

        groups = line.split("   ")
        id_group = groups[0].split("  ")
        hex_can_id = id_group[-1]
        data_group = groups[1].split("  ")
        can_data = data_group[1].split(" ")

        for d in can_data:
            hex_can_data.append(int(d, 16))

        print(hex_can_id, hex_can_data)

        return hex_can_id, hex_can_data