Instrument config
=================

One instrument is one table, ``[equipment.psu]`` and the same form for every
other kind. ``[[equipment.psu]]`` is only for a file that shows two or more
rows of that same section. Each block repeats the common transport keys so it
stands alone. Shared VISA and HTTP behavior is in :doc:`config_reference`.

``address="either"`` kinds (``attn``, ``gnss``, ``rfswitch``, ``serial``) leave
both ``resource`` and ``port`` optional. Every other kind requires
``resource``.

equipment.asg
-------------

.. code-block:: toml

   [equipment.asg]
   asg_id = 1                                 # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   frequency = 1000.0                         # optional; set_frequency at connect when present
   amplitude_vpp = 1.0                        # optional; set_amplitude_vpp at connect when present
   output = true                              # optional; set_output(True) at connect when truthy
   channels = 1                               # optional; channel count; default 1; also reads channel_count

equipment.attn
--------------

Neither ``resource`` nor ``port`` is required.

.. code-block:: toml

   [equipment.attn]
   attn_id = 1                                # required integer id
   driver = "serial"                          # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   attenuation_db = 10.0                      # optional; set_attenuation_db at connect when present
   channel = 1                                # optional; integer default channel
   path = 1                                   # optional; integer channel used when channel is unset
   port = "COM5"                              # optional serial/ASRL address; used when driver is serial or resource is empty
   min_attenuation_db = 0.0                   # optional; measure_min_attenuation_db returns this float before SCPI
   max_attenuation_db = 60.0                  # optional; measure_max_attenuation_db returns this float before SCPI
   step_db = 0.5                              # optional; measure_step_db returns this float before SCPI
   settle_s = 0.05                            # optional; seconds slept after a change when the delay is > 0
   resource = "ASRL5::INSTR"                  # optional VISA resource; neither this nor port is required

equipment.dmm
-------------

.. code-block:: toml

   [equipment.dmm]
   dmm_id = 1                                 # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   channels = 1                               # optional; channel count; default 1 when channels and channel_count are empty
   channel_count = 1                          # optional; used when channels is empty; default 1
   baudrate = 115200                          # optional; line-mode default 115200; fluke-189 requires 9600 and fluke-289 requires 115200 with driver=serial

equipment.eload
---------------

.. code-block:: toml

   [equipment.eload]
   eload_id = 1                               # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   channels = 1                               # optional; channel count; default 1 when channels and channel_count are empty
   channel_count = 1                          # optional; used when channels is empty; default 1

equipment.freqcounter
---------------------

.. code-block:: toml

   [equipment.freqcounter]
   freqcounter_id = 1                         # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   channels = 2                               # optional; channel count; default 2; also reads channel_count

equipment.gnss
--------------

Neither ``resource`` nor ``port`` is required. ``resolve_instrument_model``
does not probe this kind; an omitted ``model`` stays ``generic``.

.. code-block:: toml

   [equipment.gnss]
   gnss_id = 1                                # required integer id
   driver = "serial"                          # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; this kind does not *IDN? probe
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0; also the poll cap when a fix max-age is larger
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   connection = "COM1"                        # optional; Septentrio stream port; default COM1; generic GNSS does not read it
   baudrate = 9600                            # optional; line-mode default 9600
   sim_read = "OK"                            # optional; registered here; SimTransport applies sim_read only for kind serial
   port = "COM5"                              # optional serial/ASRL address; used when driver is serial or resource is empty
   resource = "ASRL5::INSTR"                  # optional VISA resource; neither this nor port is required

equipment.oscope
----------------

.. code-block:: toml

   [equipment.oscope]
   oscope_id = 1                              # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   measurement_slot = 1                       # optional; tektronix-t3dso2000 PAVA CUST slot; default 1
   channels = 4                               # optional; channel count; default 4; also reads channel_count

equipment.phasenoiseanalyzer
----------------------------

.. code-block:: toml

   [equipment.phasenoiseanalyzer]
   phasenoiseanalyzer_id = 1                  # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim

equipment.psu
-------------

.. code-block:: toml

   [equipment.psu]
   psu_id = 1                                 # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   voltage = 3.3                              # optional; set_voltage at connect when present
   ovp = 3.6                                  # optional; set_ovp_v at connect when present
   ocp = 1.0                                  # optional; set_current_limit at connect when present
   channels = 1                               # optional; channel count; default 1 when channels and channel_count are empty
   channel_count = 1                          # optional; used when channels is empty; default 1
   baudrate = 115200                          # optional; line-mode default 115200; tdk-genesys-serial requires it with driver=serial
   device_address = 0                         # optional; tdk-genesys-serial sends ADR n when set; integer 0..30

equipment.pwrmeter
------------------

.. code-block:: toml

   [equipment.pwrmeter]
   pwrmeter_id = 1                            # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   frequency = 1000000000.0                   # optional; Hz; set_frequency at connect when present
   channels = 1                               # optional; channel count; default 1; also reads channel_count

equipment.relay
---------------

HTTP kind. ``resource`` is required. ``model`` is not a registered key;
``GenericRelay`` still defaults it to ``generic`` and refuses commands until
the row names ``controlbyweb-webrelay`` or ``controlbyweb-x410``.

.. code-block:: toml

   [equipment.relay]
   relay_id = 1                               # required integer id
   resource = "http://192.0.2.20/"            # required; missing resource fails the open
   driver = "http"                            # optional; explicit driver, else http for this kind
   timeout = 5.0                              # optional; seconds; default 5.0
   username = ""                              # optional; HTTP basic user; default empty
   password = ""                              # optional; HTTP basic password; default empty
   channel = 1                                # optional; default channel; default 1
   relay_count = 8                            # optional; default 8

equipment.rfswitch
------------------

Neither ``resource`` nor ``port`` is required. ``path`` here is the route
name passed to ``set_path``, not the serial ``port``.

.. code-block:: toml

   [equipment.rfswitch]
   rfswitch_id = 1                            # required integer id
   driver = "serial"                          # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   path = "A1-B1"                             # optional; set_path at connect when present
   port = "COM5"                              # optional serial/ASRL address; GenericRfSwitch does not read it
   settle_s = 0.05                            # optional; seconds; first settle key consulted
   wait_settle_s = 0.05                       # optional; seconds; used when settle_s is unset
   resource = "ASRL5::INSTR"                  # optional VISA resource; neither this nor port is required

``resolve_settle_s`` sleeps when the chosen delay is greater than ``0``.

equipment.rtsa
--------------

.. code-block:: toml

   [equipment.rtsa]
   rtsa_id = 1                                # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   center_freq = 1000000000.0                 # optional; Hz; set_center_freq at connect when present
   span = 1000000.0                           # optional; Hz; set_span at connect when present; signalhound spike rejects span
   rbw = 1000.0                               # optional; Hz; set_bandwidth at connect when present
   sample_rate_hz = 1000000.0                 # optional; signalhound spike writes SENS:ZS:CAP:SRAT when present
   reference_level_dbm = 0.0                  # optional; signalhound spike writes SENS:ZS:CAP:RLEV when present

equipment.serial
----------------

Neither ``resource`` nor ``port`` is required. This kind is not ``*IDN?``
probed. ``SimTransport`` returns ``sim_read`` (default ``OK``) for serial
reads.

.. code-block:: toml

   [equipment.serial]
   serial_id = 1                              # required integer id
   driver = "serial"                          # optional; sim, visa, serial, or http; kind serial infers serial
   model = "generic"                          # optional; default generic; this kind does not *IDN? probe
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   baudrate = 115200                          # optional; line-mode default 115200
   sim_read = "OK"                            # optional; sim driver reply text; default OK
   port = "COM5"                              # optional; COM5 becomes ASRL5::INSTR; serial open fails when port and resource are both empty
   resource = "ASRL5::INSTR"                  # optional VISA resource; neither this nor port is required

equipment.speca
---------------

.. code-block:: toml

   [equipment.speca]
   speca_id = 1                               # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   center_freq = 1000000000.0                 # optional; set_center_frequency at connect when present
   span = 1000000.0                           # optional; set_span at connect when present
   rbw = 1000.0                               # optional; set_rbw at connect when present

equipment.vna
-------------

.. code-block:: toml

   [equipment.vna]
   vna_id = 1                                 # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   channel = 1                                # optional; default 1; vendor SENS/CALC/INIT prefixes; generic _init ignores it
   frequency_unit = "GHz"                     # optional; anritsu-541xx; default GHz; GHz or MHz

equipment.vsg
-------------

.. code-block:: toml

   [equipment.vsg]
   vsg_id = 1                                 # required integer id
   resource = "TCPIP0::192.0.2.10::INSTR"     # required VISA resource
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim
   frequency = 1000000000.0                   # optional; set_frequency at connect when present
   power_dbm = 0.0                            # optional; set_power at connect when present
   output = true                              # optional; set_output(True) at connect when truthy
