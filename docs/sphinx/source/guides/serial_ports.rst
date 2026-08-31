Serial ports (``col.equipment.serial``)
========================================

Each ``[equipment.serial]`` row defines a COM or TTY port. Use ``col.equipment.serial`` for raw line and block I/O on that port (DUT console, debug header, USB-serial adapters, etc.).

SCPI-over-serial uses the **same config rows**: pass ``serial_id=`` to ``col.equipment.scpi`` instead of ``psu_id=`` or ``dmm_id=``.

Configuration
-------------

DUT console on one port; SCPI instrument on another::

   [equipment.serial]
   serial_id = 1
   port = "COM5"
   baudrate = 115200
   driver = serial

   [equipment.serial]
   serial_id = 2
   port = "COM3"
   baudrate = 9600
   driver = serial

Simulated port for CI (``driver = sim``)::

   [equipment.serial]
   serial_id = 1
   driver = sim
   port = SIM4
   sim_read = "BOOT OK\r\nREADY\r\n"

Raw serial I/O
----------------

::

   col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
   col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot", strip_ansi=True)
   col.shared.regex.verify_match(key="boot", pattern=r"OK")

SCPI on a serial port
---------------------

::

   col.equipment.scpi.query(serial_id=2, command="*IDN?")

See also the generated ``api/serial`` and ``api/scpi`` reference chapters in the equipment PDF.
