import serial, time

'''
This is a script to test and develop the arduino sketch
'''


def crc8(crc, extract):
    sum = 0;
   
    for i in range(8):
       sum = (crc ^ extract) & 0x01
       crc >>= 1
       if (sum):
          crc ^= 0x8C
       extract >>= 1
    return crc

serial_device = serial.Serial("/dev/ttyACM0", 115200, timeout=None)

serial_device.write(bytearray([ord('m')]))
serial_device.write(bytearray([ord('s')]))
serial_device.flush()
serial_device.flushInput()

packets = []


while True:
    this_packet = []
    b = 0
    crc = 0

    for i in range(0, 19):
        b = int.from_bytes(serial_device.read(1), "big")
        if i < 18:
            crc = crc8(crc, b)
        this_packet.append(b)
    
    if crc == this_packet[-1]:
        # message integrity OK
        print(this_packet)
        packets.append(this_packet)
    else:
        # resync
        self.serial_device.write(bytearray([ord('s')]))
        self.serial_device.flush()
        self.serial_device.flushInput()


