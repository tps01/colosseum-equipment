"""SCPI digital I/O backend (VISA/serial fallback when no vendor GPIO driver)."""
from colosseum_equipment.io.backends.scpi.dio import ScpiDioBackend

__all__ = ["ScpiDioBackend"]
