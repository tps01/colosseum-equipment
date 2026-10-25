Config reference
================

A config row is one TOML table. One row uses ``[dotted.path]``. Use
``[[dotted.path]]`` only when the sample shows two or more rows of that same
section. When the section is present, ``normalize_sections`` requires the
integer id field. ``require_item`` rejects a row that omits a required key or
sets it to an empty string or ``None``.

Comments on each line come from the code that reads the key: the transport
factory, ``VISATransport``, and the instrument or I/O backend. A key that is
registered but not read says so on that line.

Each instrument block in :doc:`config_instruments` repeats the common keys so
the block stands alone. I/O blocks are in :doc:`config_io`.

Common VISA keys
----------------

VISA kinds require ``resource``. ``address="either"`` kinds (``serial``,
``gnss``, ``rfswitch``, ``attn``) accept ``port`` or ``resource`` and require
neither. ``open_transport`` accepts an explicit ``driver`` of ``sim``,
``visa``, ``serial``, or ``http``. With no driver, kind ``serial`` or a
``port`` without ``resource`` selects serial; an HTTP kind or an ``http://``
or ``https://`` resource selects HTTP; otherwise the driver is ``visa``.
``driver = "serial"`` still opens through pyVISA.

.. code-block:: toml

   # Shared lines for a VISA-backed equipment.* row. Not itself a section.
   # The integer id is the kind name plus _id, for example psu_id.
   resource = "TCPIP0::192.0.2.10::INSTR"     # required on VISA kinds
   driver = "visa"                            # optional; sim, visa, serial, or http; else inferred
   model = "generic"                          # optional; default generic; non-empty skips *IDN?
   interface = "usb"                          # optional; open_transport and instruments do not read it
   timeout = 5.0                              # optional; seconds; default 5.0
   visa_backend = "sim"                       # optional; "sim" requires sim_definition; any other value keeps the default manager
   visa_library = "visa32.dll"                # optional; ResourceManager argument when visa_backend is not sim
   sim_definition = "sim.yaml"                # optional YAML path; required when visa_backend is sim

``visa_backend = "sim"`` opens a resource manager on the resolved YAML path
with ``@sim`` appended. ``resolve_sim_definition`` uses the path when it is
already a file, otherwise the path under the current directory or the
equipment checkout. An empty ``visa_library`` calls
``ResourceManager()`` with no argument. ``COM5`` in ``resource`` or ``port``
becomes ``ASRL5::INSTR``. Line mode (serial driver or a ``COM`` address) sets
the baud rate from ``baudrate``, default ``115200``, or ``9600`` for kind
``gnss``. An ``ASRL`` resource that is not line mode sets the baud only when
``baudrate`` is present.

HTTP relay keys
---------------

Kind ``relay`` is ``address="http"``. ``resource`` is required.
``HttpTransport`` reads ``timeout`` (default ``5.0`` seconds), ``username``,
and ``password`` (both default to an empty string). The instrument page
repeats this row with ``channel`` and ``relay_count``.

.. code-block:: toml

   [equipment.relay]
   relay_id = 1                    # required integer id
   resource = "http://192.0.2.20/" # required; missing resource fails the open
   driver = "http"                 # optional; explicit driver, else http for this kind
   timeout = 5.0                   # optional; seconds; default 5.0
   username = ""                   # optional; HTTP basic user; default empty
   password = ""                   # optional; HTTP basic password; default empty
   channel = 1                     # optional; GenericRelay default channel; default 1
   relay_count = 8                 # optional; GenericRelay relay count; default 8
