I/O config
==========

One row uses ``[io.dio]`` (and the same form for ``i2c``, ``spi``, and
``analyzer``). ``[[io.dio]]`` is for a file that shows two or more DIO rows.
The id field is required when the section is present. No I/O key other than
``io.analyzer`` ``driver`` is required.

io.dio
------

``open_dio_backend`` accepts ``sim``, ``ftdi-ft232h``, ``ni-6501``,
``ni-845x``, and ``scpi``. An omitted driver, or ``generic``, ``visa``, or
``serial``, is accepted and logged as a preference for ``driver = "scpi"``.

.. code-block:: toml

   [io.dio]
   dio_id = 1                         # required integer id
   driver = "sim"                     # optional; sim, ftdi-ft232h, ni-6501, ni-845x, or scpi
   resource = ""                      # optional address string for the selected driver
   port_lines = 8                     # optional; default 8; ni-6501 requires 24; ni-845x requires 8; FT232H allows 8 or 16; sim and SCPI allow 1..16
   direction = 0                      # optional bitmask; default 0; 0 is input and 1 is output per line
   model = ""                         # optional; ni-845x passes it; default empty
   drive = "open-drain"               # optional; ni-6501 default open-drain; ni-845x default push-pull; open-drain, open-collector, opendrain, push-pull, active-drive, or pushpull
   voltage = 3.3                      # optional; ni-845x passes a float when set
   library = ""                       # optional path; ni-6501 and ni-845x pass it when set
   pins = { enable = 0 }              # optional map of name to line
   pin_names = { enable = 0 }         # optional; alias of pins; used when pins is absent

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
   driver = "sim"                     # optional; totalphase-aardvark, ti-usb2any, sim, or ni-845x
   resource = ""                      # optional; Total Phase numeric serial, or USB2ANY ASCII serial
   model = ""                         # optional; ni-845x passes it; default empty
   voltage = 3.3                      # optional; Total Phase and USB2ANY reject a value other than 3.3; ni-845x passes a float
   clock_hz = 100000                  # optional; default 100000; Aardvark allows 1000..800000
   address = 0x50                     # optional; default 0x50; must fit address_bits
   address_bits = 7                   # optional; default 7; 7 or 10
   pullup = true                      # optional; default true
   library = "USB2ANY.dll"            # optional; USB2ANY default USB2ANY.dll; Total Phase rejects library=
   nack = false                       # optional; sim backend; default false; true raises on write and read
   read_data = ""                     # optional; sim read bytes; hex text or bytes; default empty
   target_power = false               # optional; default false
   timeout_ms = 500                   # optional; Total Phase default 500 (1..1000); USB2ANY default 25 (2..200)

io.spi
------

``open_spi_backend`` accepts ``totalphase-aardvark``, ``totalphase-cheetah``,
``ti-usb2any``, ``sim``, and ``ni-845x``.

.. code-block:: toml

   [io.spi]
   spi_id = 1                         # required integer id
   driver = "sim"                     # optional; totalphase-aardvark, totalphase-cheetah, ti-usb2any, sim, or ni-845x
   resource = ""                      # optional; Total Phase numeric serial, or USB2ANY ASCII serial
   model = ""                         # optional; ni-845x passes it; default empty
   voltage = 3.3                      # optional; Total Phase and USB2ANY reject a value other than 3.3; ni-845x passes a float
   clock_hz = 1000000                 # optional; default 1000000; Aardvark 125000..8000000; Cheetah 100000..40000000
   mode = 0                           # optional; default 0; 0..3
   chip_select = 0                    # optional; default 0; adapter chip-select index
   bits_per_word = 8                  # optional; default 8; these adapter backends require 8
   library = "USB2ANY.dll"            # optional; USB2ANY default USB2ANY.dll; Total Phase rejects library=
   read_data = ""                     # optional; sim returns these bytes; omitted sim SPI echoes the write
   target_power = false               # optional; default false
   timeout_ms = 500                   # optional; Total Phase default 500 except Cheetah, which rejects the key; USB2ANY default 25

``spi_settings`` allows chip select ``0`` only on Aardvark (``max_cs`` 0) and
``0..2`` on Cheetah.

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
