Digital I/O and protocol adapters (``col.io``)
==============================================

Colosseum exposes bench digital I/O through ``col.io.dio``, and I2C/SPI masters
through ``col.io.i2c`` and ``col.io.spi``. Use ``driver = sim`` for offline runs
and CI. Live USB adapters use vendor runtimes loaded via ctypes (not pip packages):

* ``ftdi-ft232h`` — FT232H GPIO (pyftdi)
* ``ni-6501`` — NI USB-6501 static DIO (NI-DAQmx: ``nicaiu.dll`` / ``libnidaqmx.so``)
* ``ni-845x`` — NI USB-8451/8452 DIO, I2C, and SPI (NI-845x: ``Ni845x.dll`` / ``libni845x.so``)

Configuration
-------------

Example simulated DIO for smoke tests::

   [io.dio]
   dio_id = 1
   driver = sim
   port_lines = 8
   direction = 0xFF

Example FT232H on a lab bench::

   [io.dio]
   dio_id = 1
   driver = ftdi-ft232h
   resource = ftdi://ftdi:232h/1
   port_lines = 8
   direction = 0x0F

``port_lines`` is ``8`` for ADBUS (default) or ``16`` for ADBUS+ACBUS. ``direction`` is a bitmask where ``1`` means output and ``0`` means input.

NI USB-6501 (24 static lines)::

   [io.dio]
   dio_id = 1
   driver = ni-6501
   resource = Dev1
   port_lines = 24
   direction = 0x0000FF
   drive = open-drain

Lines map as ``P0.0..P2.7`` → ``0..23``. ``drive`` is ``open-drain`` (default,
onboard 4.7 kΩ to USB 5 V) or ``push-pull`` (active drive; keep total source
current within the device limit). ``set_pull`` is refused: the pull-up is fixed
hardware. Optional ``library`` overrides the DAQmx shared-library path.

NI USB-8452 DIO (8 lines on port 0)::

   [io.dio]
   dio_id = 2
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   port_lines = 8
   direction = 0x0F
   drive = push-pull
   voltage = 3.3

``model`` is ``usb-8451`` or ``usb-8452``. Voltage is device-wide (8451 fixed at
3.3 V; 8452 allows 1.2 / 1.5 / 1.8 / 2.5 / 3.3 V). Multiple ``io.*`` rows that
share the same ``resource`` must use the same voltage.

I2C and SPI (845x)::

   [io.i2c]
   i2c_id = 1
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   voltage = 3.3
   clock_hz = 100000
   address = 0x50
   address_bits = 7
   pullup = true

   [io.spi]
   spi_id = 1
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   voltage = 3.3
   clock_hz = 1000000
   mode = 0
   chip_select = 0
   bits_per_word = 8

8451 limits: I2C ≤ 250 kHz, SPI ≤ 12 MHz. 8452 limits: I2C ≤ 3.3 MHz, SPI ≤ 50 MHz.
Simulated protocol adapters::

   [io.i2c]
   i2c_id = 1
   driver = sim
   address = 0x50
   read_data = "aabb"

   [io.spi]
   spi_id = 1
   driver = sim
   mode = 0

API usage
---------

Configure direction, drive outputs, and record readbacks as measurements::

   col.io.dio.configure(dio_id=1, direction=0x0F)
   col.io.dio.write_port(dio_id=1, value=0b1010)
   value = col.io.dio.read_port(dio_id=1, key="port_a")
   col.io.dio.write_pin(dio_id=1, line=0, value=True)
   level = col.io.dio.read_pin(dio_id=1, line=0, key="reset")

I2C master (empty write is an address-only ACK probe)::

   col.io.i2c.configure(i2c_id=1, address=0x50, clock_hz=100000)
   col.io.i2c.write(i2c_id=1, data=b"")
   col.io.i2c.write_read(i2c_id=1, write_data=b"\x00", read_nbytes=2, key="reg0")

SPI full-duplex transfer::

   col.io.spi.configure(spi_id=1, mode=0, chip_select=0, clock_hz=1000000)
   col.io.spi.transfer(spi_id=1, data=b"\x01\x02", key="xfer")

``read_port``, ``read_pin``, ``i2c.read``, ``i2c.write_read``, and ``spi.transfer``
require ``key=`` and persist measurement rows under domain ``equipment`` in
``execution.sqlite``. Byte payloads are stored as hex. Writes and configure calls
are ``@command`` APIs.

Named pins and per-line setup
-----------------------------

Add a ``pins`` map to the selected DIO row; names resolve to zero-based lines::

   [io.dio]
   dio_id = 1
   driver = "sim"
   port_lines = 8
   direction = 0x01
   pins = { reset = 0, ready = 1 }

In a configured procedure, use either ``name`` or ``line``, not both::

   col.io.dio.configure_pin(dio_id=1, line=0, output=True)
   col.io.dio.configure_pin(dio_id=1, line=1, output=False)
   col.io.dio.set_pull(dio_id=1, line=1, pull="up")
   col.io.dio.write_pin(dio_id=1, name="reset", value=False)
   col.io.dio.read_pin(dio_id=1, name="reset", key="reset_low")
   col.shared.verify.verify_field(key="reset_low", expected_val=False)

The last line requires ``colosseum-shared``. It verifies the recorded readback;
a successful write alone does not establish the pin level. Sim supports pulls;
``ftdi-ft232h``, ``ni-6501``, and ``ni-845x`` DIO refuse ``set_pull`` (fixed or
absent per-line pull control). Use ``col.io.i2c.set_pullup`` for 845x I2C bus
pull-ups. Input pull behavior and driving a line are different operations.

Platform notes
--------------

**Linux:** install ``libusb`` (distribution package) so pyftdi can open FT232H
devices. Install NI-DAQmx and/or NI-845x from NI so the shared libraries are
on the loader path (or set ``library`` in config).

**Windows:** install the WinUSB driver for the FT232H (for example with Zadig) so
pyftdi can claim the interface. USB serial drivers alone are not sufficient for
MPSSE GPIO. Install NI-DAQmx for the USB-6501 and NI-845x software for the
USB-8451/8452; the DLLs are loaded from the system path.

See also :doc:`platform_notes` and :doc:`configuration`.
