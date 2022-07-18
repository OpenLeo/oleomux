Naming conventions (WIP)
------------------------

- NAME and NAME_EN are likely to be used in C struct/variable type names, so should
  - not have spaces or special characters (except underscores)
  - be in all-capitals
  - be as short as possible whilst still conveying the meaning

- Include a prefix (e.g. IND_ or VMF_) for signals which have common names, if it is not clear in the context of the message
  - e.g. VMF_BUTTON_STATES.BACK_BUTTON is clear and does not need a prefix

- EN and FR should be used to explain what the signal does, if it is not trivial or obvious

- Leave NAME_EN blank if NAME is clear enough in both languages e.g. DIAG_MUX_ON

- NAME in French is not known, put the English name in NAME and leave NAME_EN blank

- Use STATUS not STATE, and always at the end e.g. HEAD_LIGHTS_STATUS

- If you don't know, DON'T GUESS.


Acronyms
--------
- Warning lights should be named as IND_XXXXX
- Faults (defaut) should be named FAULT_XXXX
- Requests to do something should be CMD_XXXX
- Alerts (displayed as messages usually) should be ALERT_XXX

AAS = Parking assistance
MPD = Parking space measurement
VMF = Steering wheel controls
DSG = Tyre pressure monitoring
EASYMOVE = Hill assist function (PSA named this, not us!)
IAE = ?
RVV = Cruise control
LVV = Speed limiter
ACC = Radar cruise control
ADC = ADML/ADC3/ADC2/ADCQ keyless system
PIU = B9R Power Information Unit?


Datatypes
----------
This list must match with oleomux/oleosigeditor.py
- uint          (integer which is always positive)
- sint          (integer which can be negative)
- float         (decimal, can be positive or negative)
- bool_pressed  (1 = PRESSED / 0 = NOT_PRESSED)
- bool_active   (1 = ACTIVE  / 0 = NOT ACTIVE )
- bool_present  (1 = PRESENT / 0 = NOT PRESENT)
- bool_on       (1 = ON      / 0 = OFF)
- bool_enabled  (1 = ENABLED / 0 = DISABLED)

These data types are the standard ones. ALWAYS CHECK, sometimes 0 = present and 1 = active on some signals. The "inverted" key indicates this.

File format
-----------

The following example format explains how this database works:

Signal Choices/Values
---------------------

Note that although this example shows values, it would not have them in reality because it is of type "bool_pressed".

```
    comment:
      en: 'This is an english comment'
      fr: "Le comment de francais"
      src: 'original data source, if relevant'
    id: '0x0A2'
    length: 5   (bytes)
    name: VMF_DSGN
    periodicity: 200 (in milliseconds)
    receivers:
    - PASS_BSI
    senders:
    - HDC
    signals:
      CDE_TEL_KML:
        bits: '3.7'
        comment:
          en: 'This is an english comment'
          fr: "Comment de francais"
          src: ''
        factor: 1
        type: bool_pressed
        inverted: False
        max: null
        min: null
        offset: 0
        units: null
        values:
          0: 
            name: NOT_PRESSED
            comment:
              en: "Button not pressed"
              fr: "Bouton non presse"
          1: 
            name: PRESSED
            comment:
              en: "Button pressed"
              fr: "Bouton presse"
```