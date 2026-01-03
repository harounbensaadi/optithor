# src/optithor/errors.py

class OptithorError(Exception):
    """Base exception for optithor."""
    pass


class DataError(OptithorError):
    """Raised when input data or dataset is invalid."""
    pass


class OptimizationError(OptithorError):
    """Raised when optimization fails in an unexpected way."""
    pass
