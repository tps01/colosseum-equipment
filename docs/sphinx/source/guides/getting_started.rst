Getting started
===============

Install the ``colosseum-equipment`` wheel into the same virtual environment as
``colosseum-core`` (download both from GitHub Releases). Core discovers
the ``equipment`` and ``io`` namespaces automatically.

This page uses **sim** drivers so you can exercise the flow without instruments.
For RF, DIO, and serial detail, see the other guides in this site.

1. Config
---------

Minimal sim TOML (see also ``examples/configs/config.sim.toml``)::

   [[equipment.psu]]
   psu_id = 1
   driver = sim
   resource = SIM::PSU1
   model = generic
   interface = sim
   voltage = 3.3
   ovp = 3.6
   ocp = 1.0

   [equipment.dmm]
   dmm_id = 1
   driver = sim
   resource = SIM::DMM1
   model = generic
   interface = sim
   timeout = 5.0

2. Procedure + verification
---------------------------

::

   import colosseum as col

   def main() -> None:
       col.equipment.psu.set_voltage(psu_id=1, voltage=3.3)
       col.equipment.psu.set_current_limit(psu_id=1, current=0.5)
       col.equipment.psu.set_output(psu_id=1, enabled=True)
       col.equipment.dmm.measure_voltage(dmm_id=1, channel=1, key="rail")
       col.equipment.dmm.verify_voltage(
           key="rail",
           expected_val=3.3,
           tolerance=0.1,
       )

Many benches also verify with ``col.shared.*`` (install ``colosseum-shared``).
Copy-out stubs that already wire PSU/DMM live in the
`colosseum-library <https://github.com/tps01/colosseum-library>`__ catalog
(for example ``power/rail_voltage/``).

3. Run
------

::

   colosseum run my_rail.py -g config.sim.toml

Add ``--report wats`` or ``--report junit`` when you want those files. See the
`core hub <https://tps01.github.io/colosseum-core/>`__ for runners, parameters,
and artifacts.
