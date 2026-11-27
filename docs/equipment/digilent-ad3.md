# Digilent Analog Discovery 3

Install Digilent WaveForms and the Adept Runtime for your Windows or Linux
host. On Linux install the vendor USB rules and make sure your user can access
the device. Close the WaveForms application before running a procedure.
Colosseum loads the installed `dwf.dll` or `libdwf.so` on first use. Set
`library` to an absolute path in every configured role if your installation
needs a custom location. See the [WaveForms installer guide](https://files.digilent.com/manuals/WaveForms/3.25.1/main.html).

Copy [the AD3 bench config](https://github.com/tps01/colosseum-equipment/blob/develop/examples/configs/config.digilent-ad3.toml)
and replace the example serial with the serial in the WaveForms Device
Manager. Keep the same serial in every row for a shared board. The scope and
Wavegen use channels 1 and 2. Digital I/O uses pins 0 through 15 and 3.3 V
logic. See the [AD3 pinout and electrical limits](https://files.digilent.com/manuals/WaveForms/3.25.1/start10.html).

## Loopback check

With outputs inactive, connect W1 to 1+, connect 1− to GND, and jumper DIO 0
to DIO 1. Run the following with artifacts enabled. A successful run records
a sine wave near 1 Vpp, exports its time and voltage samples, and reads both
logic levels on DIO 1.

```python
import colosseum as col

col.config.load_config("examples/configs/config.digilent-ad3.toml")
try:
    col.equipment.asg.set_waveform(asg_id=1, waveform="sine")
    col.equipment.asg.set_frequency(asg_id=1, frequency=1000)
    col.equipment.asg.set_amplitude_vpp(asg_id=1, vpp=1.0)
    col.equipment.asg.set_offset_v(asg_id=1, offset_v=0.0)
    col.equipment.asg.set_output(asg_id=1, enabled=True)

    col.equipment.oscope.set_channel_display(oscope_id=1, channel=2, enabled=False)
    col.equipment.oscope.set_channel_scale_v(oscope_id=1, channel=1, volts_per_div=0.5)
    col.equipment.oscope.set_trigger_source(oscope_id=1, source="CHAN1")
    col.equipment.oscope.set_trigger_slope(oscope_id=1, slope="rising")
    col.equipment.oscope.set_trigger_level_v(oscope_id=1, level_v=0.0)
    col.equipment.oscope.acquire(oscope_id=1, timeout_s=5.0)
    voltage = col.equipment.oscope.measure_vpp(oscope_id=1, key="loopback_vpp")
    col.equipment.oscope.save_waveform(oscope_id=1, channel=1, path="ad3-loopback.csv")
    assert 0.9 <= voltage <= 1.1

    col.io.dio.configure(dio_id=1, direction=0b01, initial=0)
    assert col.io.dio.read_pin(dio_id=1, line=1, key="loopback_low") is False
    col.io.dio.write_pin(dio_id=1, line=0, value=True)
    assert col.io.dio.read_pin(dio_id=1, line=1, key="loopback_high") is True
finally:
    col.endex()
```

Use `source="NONE"` for an immediate single capture. Scope settings use ten
display divisions for mapping V/div and s/div to the SDK range and sample rate.
Measurements and CSV export use the last completed capture. Wavegen amplitude
is peak-to-peak, and the programmed offset plus or minus half of Vpp must stay
within ±5 V. A stopped Wavegen output sits near 0 V. The driver covers standard
Wavegen shapes, finite scope capture, and static digital I/O.

Physical Windows and Linux qualification is pending.
