class EquipmentError(RuntimeError):
    pass


class EquipmentConnectionError(EquipmentError):
    pass


class EquipmentTimeoutError(EquipmentError):
    pass


class EquipmentResponseError(EquipmentError):
    pass


class EquipmentCapabilityError(EquipmentError):
    """Raised when a high-level API is not supported by the configured model."""


class NoFixError(EquipmentError):
    """Raised when the receiver has no valid position fix."""


class StaleDataError(EquipmentError):
    """Raised when cached instrument data is older than the allowed age."""


class NoStreamError(EquipmentError):
    """Raised when no bytes have been received from the instrument recently."""
