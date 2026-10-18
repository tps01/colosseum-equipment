"""NI USB-6501 static DIO via NI-DAQmx."""

from __future__ import annotations

from ctypes import byref, c_int32, c_uint8
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.io.backends.ni import daqmx as api
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_PORT_LINES = 24
_MASK = (1 << _PORT_LINES) - 1


def _line_channel(device: str, line: int) -> str:
    port = line // 8
    bit = line % 8
    return f"{device}/port{port}/line{bit}"


def _channels_csv(device: str, lines: list[int]) -> str:
    return ",".join(_line_channel(device, line) for line in lines)


class Ni6501DioBackend:
    """USB-6501: 24 software-timed lines mapped as P0.0..P2.7 → lines 0..23."""

    def __init__(
        self,
        *,
        resource: str,
        direction: int,
        drive: str = "open-drain",
        library: str | None = None,
    ) -> None:
        if not resource:
            raise IoConfigError("ni-6501 requires resource= (DAQmx device name, e.g. Dev1)")
        drive_key = drive.strip().lower().replace("_", "-")
        if drive_key in ("open-drain", "open-collector", "opendrain"):
            self._drive_type = api.DAQmx_Val_OpenCollector
            self._drive_name = "open-drain"
        elif drive_key in ("push-pull", "active-drive", "pushpull"):
            self._drive_type = api.DAQmx_Val_ActiveDrive
            self._drive_name = "push-pull"
        else:
            raise IoConfigError(
                f"ni-6501 drive must be open-drain or push-pull; got {drive!r}",
            )
        self._device = resource
        self._lib = api.load_daqmx(library=library)
        self._mask = _MASK
        self._direction = direction & self._mask
        self._output = 0
        self._di_task: Any = None
        self._do_task: Any = None
        self._di_lines: list[int] = []
        self._do_lines: list[int] = []
        try:
            self._rebuild_tasks()
        except Exception:
            self.close()
            raise

    def _line_list(self, *, outputs: bool) -> list[int]:
        lines: list[int] = []
        for line in range(_PORT_LINES):
            is_out = bool(self._direction & (1 << line))
            if is_out == outputs:
                lines.append(line)
        return lines

    def _clear_tasks(self) -> None:
        if self._do_task is not None:
            api.clear_task(self._lib, self._do_task)
            self._do_task = None
            self._do_lines = []
        if self._di_task is not None:
            api.clear_task(self._lib, self._di_task)
            self._di_task = None
            self._di_lines = []

    def _rebuild_tasks(self) -> None:
        self._clear_tasks()
        do_lines = self._line_list(outputs=True)
        di_lines = self._line_list(outputs=False)
        if do_lines:
            task = api.create_task(self._lib, "col_dio_do")
            channels = _channels_csv(self._device, do_lines)
            api.check_status(
                self._lib,
                self._lib.DAQmxCreateDOChan(
                    task,
                    channels.encode("ascii"),
                    None,
                    api.DAQmx_Val_ChanPerLine,
                ),
                action="CreateDOChan",
            )
            api.check_status(
                self._lib,
                self._lib.DAQmxSetDOOutputDriveType(
                    task,
                    channels.encode("ascii"),
                    self._drive_type,
                ),
                action="SetDOOutputDriveType",
            )
            api.check_status(self._lib, self._lib.DAQmxStartTask(task), action="StartTask(DO)")
            self._do_task = task
            self._do_lines = do_lines
            self._write_do_lines()
        if di_lines:
            task = api.create_task(self._lib, "col_dio_di")
            channels = _channels_csv(self._device, di_lines)
            api.check_status(
                self._lib,
                self._lib.DAQmxCreateDIChan(
                    task,
                    channels.encode("ascii"),
                    None,
                    api.DAQmx_Val_ChanPerLine,
                ),
                action="CreateDIChan",
            )
            api.check_status(self._lib, self._lib.DAQmxStartTask(task), action="StartTask(DI)")
            self._di_task = task
            self._di_lines = di_lines

    def _write_do_lines(self) -> None:
        if self._do_task is None or not self._do_lines:
            return
        n = len(self._do_lines)
        array_type = c_uint8 * n
        data = array_type(*[1 if self._output & (1 << line) else 0 for line in self._do_lines])
        written = c_int32(0)
        api.check_status(
            self._lib,
            self._lib.DAQmxWriteDigitalLines(
                self._do_task,
                1,
                1,
                10.0,
                api.DAQmx_Val_GroupByChannel,
                data,
                byref(written),
                None,
            ),
            action="WriteDigitalLines",
        )

    def _read_di_lines(self) -> int:
        if self._di_task is None or not self._di_lines:
            return 0
        n = len(self._di_lines)
        array_type = c_uint8 * n
        data = array_type()
        read = c_int32(0)
        bytes_per = c_int32(0)
        api.check_status(
            self._lib,
            self._lib.DAQmxReadDigitalLines(
                self._di_task,
                1,
                10.0,
                api.DAQmx_Val_GroupByChannel,
                data,
                n,
                byref(read),
                byref(bytes_per),
                None,
            ),
            action="ReadDigitalLines",
        )
        result = 0
        for index, line in enumerate(self._di_lines):
            if data[index]:
                result |= 1 << line
        return result

    def configure(self, direction: int) -> None:
        self._direction = direction & self._mask
        self._output &= self._direction
        self._rebuild_tasks()

    def configure_pin(self, line: int, output: bool) -> None:
        if line < 0 or line >= _PORT_LINES:
            raise IoConfigError(f"line {line} out of range for port_lines={_PORT_LINES}")
        bit = 1 << line
        if output:
            self._direction |= bit
        else:
            self._direction &= ~bit
            self._output &= ~bit
        self._rebuild_tasks()

    def set_pull(self, line: int, pull: str) -> None:
        _ = line, pull
        raise EquipmentCapabilityError(
            "set_pull is not supported on ni-6501 "
            "(fixed onboard 4.7 kΩ pull-up in open-drain mode)",
        )

    def write_port(self, value: int) -> None:
        self._output = value & self._direction & self._mask
        self._write_do_lines()

    def read_port(self) -> int:
        inputs = self._read_di_lines()
        return ((self._output & self._direction) | (inputs & ~self._direction)) & self._mask

    def write_pin(self, line: int, value: bool) -> None:
        if line < 0 or line >= _PORT_LINES:
            raise IoConfigError(f"line {line} out of range for port_lines={_PORT_LINES}")
        bit = 1 << line
        if not (self._direction & bit):
            raise IoConfigError(f"line {line} is not configured as output")
        if value:
            self._output |= bit
        else:
            self._output &= ~bit
        self._write_do_lines()

    def read_pin(self, line: int) -> bool:
        if line < 0 or line >= _PORT_LINES:
            raise IoConfigError(f"line {line} out of range for port_lines={_PORT_LINES}")
        return bool(self.read_port() & (1 << line))

    def close(self) -> None:
        # Power-on state is all inputs: clear DO/DI tasks without leaving outputs driven.
        try:
            self._direction = 0
            self._output = 0
            self._clear_tasks()
        except Exception as exc:  # noqa: BLE001
            raise IoConnectionError(f"ni-6501 close failed: {exc}") from exc
