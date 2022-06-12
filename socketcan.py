import serial, time, can

'''
This is a script to test and develop the socketcan implementation
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

serial_device = can.interface.Bus(channel = "can0", bustype = 'socketcan')


packets = []


while True:
    this_packet = []
    b = 0
    crc = 0
    d = []

    msg = serial_device.recv(1.0) 

    if msg is None:
        continue
    
    for i in msg.data:
        d.append(int(i))
    print(hex(msg.arbitration_id), d)


