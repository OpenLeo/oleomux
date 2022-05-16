/* Oleomux adapter sketch for an Arduino

    COPYRIGHT (c) OpenLEO project / lorddevereux
    All rights reserved, but you are free to use this sketch as you wish.

*/

// Change the following defines

#define PIN_CS      17              // SPI chip select pin
#define PIN_INT     7               // interrupt pin
#define MCP_CRYSTAL MCP_16MHZ       // crystal fitted to hardware
#define MQ_MAX      10              // on-chip queue size

#define SPD_125     'a'
#define SPD_250     'f'
#define SPD_500     'm'
#define QSTATUS     'q'
#define ADAPTER_ACK 'z'

#include <mcp_can0.h>
#include <SPI.h>

MCP_CAN0 CAN0(PIN_CS);     // Set CS to pin 10

struct can_frame {
    long unsigned int rxId;
    unsigned char len = 0;
    unsigned char rxBuf[8];
    unsigned long time_stamp;
};

volatile struct can_frame mq[MQ_MAX];
unsigned char can_ok = 0;
volatile unsigned char ptr_write = 0;
unsigned char ptr_read = 0;
unsigned char default_can_speed = CAN_250KBPS;

unsigned char inchar = 0;
volatile unsigned char mq_len = 0;
unsigned char output[20];
unsigned char crc = 0;

    
// calculate the transmission CRC
unsigned char crc8(unsigned char crc, unsigned char extract){
    char sum = 0;
   
    for (unsigned char tempI = 8; tempI; tempI--){
       sum = (crc ^ extract) & 0x01;
       crc >>= 1;
       if (sum)
          crc ^= 0x8C;
       extract >>= 1;
    }
    return crc;
}


void restart_can(){
    can_ok = (CAN0.begin(MCP_ANY, default_can_speed, MCP_CRYSTAL) == CAN_OK);
    CAN0.setMode(MCP_NORMAL);
    Serial.write(ADAPTER_ACK);
}


void setup()
{
  Serial.begin(115200);
  // Initialize MCP2515 running at 16MHz with a baudrate of 500kb/s and the masks and filters disabled.
  restart_can();
  attachInterrupt(digitalPinToInterrupt(PIN_INT), can_recv, FALLING);
}


void can_recv(){
  if (CAN0.checkReceive() == CAN_MSGAVAIL){
    CAN0.readMsgBuf(&mq[ptr_write].rxId, &mq[ptr_write].len, mq[ptr_write].rxBuf);
    mq[ptr_write].time_stamp = millis();
    ptr_write++;
    mq_len++;
    if (ptr_write >= MQ_MAX) ptr_write = 0;
    if (mq_len > MQ_MAX) mq_len = MQ_MAX;
  }
}

void loop(){
    if (Serial.available()){
        inchar = Serial.read();

        switch(inchar){
            case SPD_125:
                default_can_speed = CAN_125KBPS;
                restart_can();
                break;
            case SPD_250:
                default_can_speed = CAN_250KBPS;
                restart_can();
                break;
            case SPD_500:
                default_can_speed = CAN_500KBPS;
                restart_can();
                break;
            case QSTATUS:
                Serial.write(0xF0 + can_ok);
                break;
        }
    }

    if (mq_len > 0){
        crc = 0;
        output[0] = mq[ptr_read].rxId >> 24;
        output[1] = mq[ptr_read].rxId >> 16;
        output[2] = mq[ptr_read].rxId >> 8;
        output[3] = mq[ptr_read].rxId;
        output[4] = mq[ptr_read].len;
        output[5] = mq[ptr_read].rxBuf[0];
        output[6] = mq[ptr_read].rxBuf[1];
        output[7] = mq[ptr_read].rxBuf[2];
        output[8] = mq[ptr_read].rxBuf[3];
        output[9] = mq[ptr_read].rxBuf[4];
        output[10] = mq[ptr_read].rxBuf[5];
        output[11] = mq[ptr_read].rxBuf[6];
        output[12] = mq[ptr_read].rxBuf[7];
        output[13] = mq[ptr_read].rxBuf[8];
        output[14] = mq[ptr_read].time_stamp >> 24;
        output[15] = mq[ptr_read].time_stamp >> 16;
        output[16] = mq[ptr_read].time_stamp >> 8;
        output[17] = mq[ptr_read].time_stamp;

        for (i = 0; i < 18; i++){
            crc = crc8(output[i]);
            Serial.write(output[i]);
        }

        Serial.write(crc);

        ptr_read++;
        if (ptr_read >= MQ_MAX) ptr_read = 0;
        mq_len--;

    }
}