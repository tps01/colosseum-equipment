class IoError(Exception):
    """Base error for ``col.io`` operations."""


class IoConfigError(IoError):
    """Raised when bench IO configuration is invalid or incomplete."""


class IoConnectionError(IoError):
    """Raised when an IO backend cannot open or communicate with hardware."""
