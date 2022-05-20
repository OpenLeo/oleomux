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
- Import DBC format (export coming soon)
- Import and Export YAML format (single message per file, according to OpenLEO standards)
- Export/generate C structures and parsing code for integration to microcontroller projects
- Create/edit/delete signals and messages
- Show live CAN data/calculated values via an Arduino adapter or SocketCAN (on Linux platforms) for debugging and research
- Play back CAN log files and render calculated values/parameters

NOTE: In general, there is no user-confirmation of actions which can be quite destructive (delete message, close window without saving etc). Be careful what you click on! :)

An important note on bit ordering
---------------------------------
- All OpenLEO signals and messages are BIG ENDIAN.
- Message bytes are indexed from 1
- Message bits are indexed from 0

- The DBC format uses the bit numbering: 
> [ 7 6 5 4 3 2 1 0 ] [ 15 14 13 12 11 10 9 8 ]
- The OpenLEO / PSA notation uses the following. This is what Oleomux uses by default for display purposes, and it is the format used by the YAML data structure. Signals greater than one bit in length use the notation 1.0-2.7 (which would be 2 bits long)
> [ 1.7 1.6 1.5 1.4 1.3 1.2 1.1 1.0 ] [ 2.7 2.6 2.5 2.4 2.3 2.2 2.1 2.0 ]. 

- Oleomux ALSO offers the option to display and edit the signals using the alternative bit ordering 
> [ 1.0 1.1 1.2 1.3 1.4 1.5 1.6 1.7 ] [ 2.0 2.1 2.2 2.3 2.4 2.5 2.6 2.7 ]. 
- You can choose this at any time using Tools > Logical bit numbering and switch back to default using Tools > OpenLEO bit numbering
- This DOES NOT change the way data is stored or formatted outside of the software - all it does is make it a bit easier (for me anyway) to interpret the bits being used by a signal in the UI
- If you don't understand what this means, use the OpenLEO notation for now

Building
--------
You'll need some dependencies. NOTE: cantools is a dependency, but requires a modified version which is included in this repository (for now)

> pip3 install pyserial ttkwidgets

For ttkwidgets to work on linux you may need to install

> python3-pil python3-pil.imagetk

On linux you'll also need "python-can" for SocketCAN to work

To use the Arduino (Serial) adaptor you need an Arduino with a CAN shield attached. An example sketch for MCP2515-based hardware is included in the repository here, but you'll need to adjust the CS/INTERRUPT/SPI pins according to your own board configuration. This software is developed & tested using a Hobbytronics Arduino Leonardo CANBus shield.

Usage
-----
To launch the GUI - run from terminal:

> python3 oleomux.py

Databases
---------
Databases included in the repository are compiled from publicly available information, including clean-room reverse engineered signal definitions. As such, there may be errors or inconsistencies in the data and it is YOUR responsibility as the end user to ensure the information gathered is accurate, correct or otherwise suitable for the purpose you will use it for. NO WARRANTY IS PROVIDED WITH THIS SOFTWARE, AND WE DISCLAIM ALL RESPONSIBILITY FOR ANY LOSS OR DAMAGE INCURRED AS A RESULT OF USING THE SOFTWARE AND/OR ASSOCIATED DATA!


Main functionality todo list
----------------------------
- Fix cantools dbc output code
    - if there is no sender/receivers then it outputs illegal dbc
    - if there are spaces in signal names it outputs illegal dbc
- Check if "is_decimal" is used anywhere
- Test and fix arduino/socketcan input
- More translations and sync up with PSA-RE


Issues
------
This software is still under development, and you may find issues. Please report them using the issue tracker with as much information as possible (log file included please!)

The software will accept either raw serial input from the accompanying
Arduino sketch, or a dump file previously created from that sketch

The timestamp and bus are optional, but you cannot have bus without timestamp

Sim/Dump Format: timestamp bus can_id bytes ...