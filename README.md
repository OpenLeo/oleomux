CAN Logger, Visualiser and Property Editor 
------------------------------------------

(c) 2020 - 2022 OpenLeo.org / lorddevereux

- Parses custom CSV-based file format to store message properties
- Visualise live CAN data or process a historic log file

Other software / derivatives:
- canmonitor by alexandreblin (MIT)
- uses cantools (MIT)
- UI based on Tkinter

Uses CAN message data compiled from:
- 207 project by alexandreblin 
- OpenLEO databases
- contributors to autowp.github.io documentation
- own research

Functionality
-------------
- Import DBC format
- Import and Export YAML format (single message per file, according to OpenLEO standards)
- Export/generate C structures and parsing code for integration to microcontroller projects
- Create/edit/delete signals and messages
- Show live CAN data/calculated values via an Arduino adapter or SocketCAN (on Linux platforms) for debugging and research
- Play back CAN log files and render calculated values/parameters

Building
--------
You'll need some dependencies

> pip3 install cantools pyserial ttkwidgets

For ttkwidgets to work on linux you may need to install

> python3-pil python3-pil.imagetk

On linux you'll also need "python-can" for SocketCAN to work

To use the Arduino (Serial) adaptor you need an Arduino with a CAN shield attached. An example sketch for MCP2515-based hardware is included in the repository here, but you'll need to adjust the CS/INTERRUPT/SPI pins according to your own board configuration. This software is developed & tested using a Hobbytronics Arduino Leonardo CANBus shield.

Usage
-----
> python3 oleomux.py

Databases
---------
Databases included in the repository are compiled from publicly available information, including clean-room reverse engineered signal definitions. As such, there may be errors or inconsistencies in the data and it is YOUR responsibility as the end user to ensure the information gathered is accurate, correct or otherwise suitable for the purpose you will use it for. NO WARRANTY IS PROVIDED WITH THIS SOFTWARE, AND WE DISCLAIM ALL RESPONSIBILITY FOR ANY LOSS OR DAMAGE INCURRED AS A RESULT OF USING THE SOFTWARE AND/OR ASSOCIATED DATA!

Issues
------
This software is still under development, and you may find issues. Please report them using the issue tracker with as much information as possible (log file included please!)

The software will accept either raw serial input from the accompanying
Arduino sketch, or a dump file previously created from that sketch

The timestamp and bus are optional, but you cannot have bus without timestamp

Sim/Dump Format: timestamp bus can_id bytes ...