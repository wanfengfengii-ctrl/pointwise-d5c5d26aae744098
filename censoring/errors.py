class ValidationError(ValueError):
    """The request is invalid; no partial publication is allowed."""


class FitError(RuntimeError):
    """A fit did not meet the numerical publication criteria."""
