from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentConnectionError, EquipmentTimeoutError
from colosseum_equipment.transports.base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0) -> None:
        import serial

        try:
            self._ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        except Exception as exc:
            raise EquipmentConnectionError(f"Failed to open serial port `{port}`: {exc}") from exc

    def write_bytes(self, payload: bytes) -> None:
        self._ser.write(payload)

    def read_line(self) -> str:
        try:
            raw = self._ser.readline()
            return raw.decode("ascii", errors="replace").strip()
        except Exception as exc:
            raise EquipmentTimeoutError(str(exc)) from exc

    def read_until(self, terminator: str | bytes) -> str:
        try:
            term_bytes = terminator.encode("ascii") if isinstance(terminator, str) else terminator
            raw = self._ser.read_until(term_bytes)
            return raw.decode("ascii", errors="replace")
        except Exception as exc:
            raise EquipmentTimeoutError(str(exc)) from exc

    def write(self, data: str) -> None:
        payload = data if data.endswith("\n") else f"{data}\n"
        self.write_bytes(payload.encode("ascii"))

    def read(self) -> str:
        return self.read_line()

    def query(self, data: str) -> str:
        self.write(data)
        return self.read()

    def close(self) -> None:
        if self._ser.is_open:
            self._ser.close()
