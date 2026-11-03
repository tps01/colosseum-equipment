I/O config
==========

One row uses ``[io.dio]`` (and the same form for ``i2c``, ``spi``,
``analyzer``, and ``onewire``). ``[[io.dio]]`` is for a file that shows two
or more DIO rows. The id field is required when the section is present. No
I/O key other than ``io.analyzer`` ``driver`` is required.

**Addressing defaults (first-contact):** NI adapters use USB ``resource=``
(for example ``USB0::...`` as shown by NI-VISA / MAX). Non-NI SCPI DIO and
DS9481R 1-Wire use serial ``port=`` (for example ``COM5``). Total Phase /
USB2ANY / Beagle keep vendor serial-number ``resource=``; FTDI keeps its USB
URL ``resource=``.

io.dio
------

``open_dio_backend`` accepts ``sim``, ``ftdi-ft232h``, ``ni-6501``,
``ni-845x``, and ``scpi``. An omitted driver, or ``generic``, ``visa``, or
``serial``, is accepted and logged as a preference for ``driver = "scpi"``.

.. code-block:: toml

   # NI USB DIO (preferred first-contact form)
   [io.dio]
   dio_id = 1
   driver = "ni-6501"
   resource = "USB0::0x3923::0x718A::01A12345::RAW"  # NI-VISA / MAX USB resource
   port_lines = 24
   direction = 0x0000FF
   drive = "open-drain"

   # Non-NI SCPI DIO over serial (preferred first-contact form)
   # [io.dio]
   # dio_id = 2
   # driver = "scpi"
   # port = "COM5"
   # port_lines = 8
   # direction = 0x0F

``resource`` is the USB / VISA / FTDI / MAX address for NI and USB adapters.
``port`` is the serial COM port for SCPI DIO. Prefer ``port=`` for SCPI trials;
use ``resource=`` when the box is on VISA USB/GPIB.

Other optional keys: ``port_lines`` (default 8; ni-6501 requires 24; ni-845x
requires 8; FT232H allows 8 or 16; sim and SCPI allow 1..16), ``direction``
(default 0; bit 1 = output), ``model``, ``drive``, ``voltage``, ``library``,
``initial_output``, ``pins`` / ``pin_names``.

``resolve_pin_line`` reads ``pins`` or, when that value is missing, ``pin_names``.
The value must be a table of names to line numbers.

io.i2c
------

``open_i2c_backend`` accepts ``totalphase-aardvark``, ``ti-usb2any``, ``sim``,
and ``ni-845x``. Any other driver, including an empty one, raises
``IoConfigError``.

.. code-block:: toml

   [io.i2c]
   i2c_id = 1                         # required integer id
   driver = "ni-845x"                 # totalphase-aardvark, ti-usb2any, sim, or ni-845x
   resource = "USB0::0x3923::..."     # NI: USB resource; Total Phase/USB2ANY: adapter serial
   model = "usb-8452"                 # optional; ni-845x passes it
   voltage = 3.3
   clock_hz = 100000
   address = 0x50
   address_bits = 7
   pullup = true
   timeout_ms = 500                   # NI-845x / Total Phase / USB2ANY
   # Sim-only optional keys: nack, read_data

io.spi
------

``open_spi_backend`` accepts ``totalphase-aardvark``, ``totalphase-cheetah``,
``ti-usb2any``, ``sim``, and ``ni-845x``.

.. code-block:: toml

   [io.spi]
   spi_id = 1
   driver = "ni-845x"
   resource = "USB0::0x3923::..."     # NI USB resource (or adapter serial for TP/USB2ANY)
   model = "usb-8452"
   voltage = 3.3
   clock_hz = 1000000
   mode = 0
   chip_select = 0
   bits_per_word = 8
   timeout_ms = 500
   # Sim-only optional key: read_data

``spi_settings`` allows chip select ``0`` only on Aardvark (``max_cs`` 0) and
``0..2`` on Cheetah.

io.onewire
----------

``open_onewire_backend`` accepts ``sim`` and ``maxim-ds9481r`` (aliases
``ds9481r``, ``ds2480b``). The DS9481R enumerates as a Prolific virtual COM
port and speaks the DS2480B serial protocol.

.. code-block:: toml

   [io.onewire]
   onewire_id = 1
   driver = "maxim-ds9481r"
   port = "COM5"                      # serial COM (preferred); not USB0::
   baudrate = 9600                    # DS2480B power-on default
   timeout_s = 1.0
   speed = "standard"                 # standard or overdrive
   # Sim-only optional keys: presence, roms / devices, read_data

io.analyzer
-----------

``driver`` is required. ``open_backend`` accepts ``sim`` or
``totalphase-beagle``.

.. code-block:: toml

   [io.analyzer]
   analyzer_id = 1                    # required integer id
   driver = "sim"                     # required; sim or totalphase-beagle
   resource = ""                      # optional; live Beagle numeric serial
   model = "i2c-spi"                  # optional; live Beagle must be i2c-spi, usb-12, or usb-480
   protocol = "i2c"                   # optional; default usb when model starts with usb-, else i2c; i2c, spi, or usb
   mode = 0                           # optional; default 0; SPI mode 0..3
   sample_rate_hz = 50000000          # optional; i2c-spi default 50000000 (1000..50000000); USB models default 0 and reject a non-zero rate
   pullup = false                     # optional; Beagle i2c-spi pull-up; default false
   target_power = false               # optional; default false; USB 12/480 reject true
   timeout_ms = 500                   # optional; default 500 (1..1000); live Beagle open sets bg_timeout and bg_latency
   max_duration_s = 60                # optional; default 60; must be finite and positive
   max_records = 100000               # optional; default 100000; must be positive
   max_bytes = 67108864               # optional; default 67108864; must be positive
   records = []                       # optional; sim capture packets; default empty
