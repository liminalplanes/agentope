"""Exceptions raised by agentope."""


class AgentopeError(Exception):
    """Base class for agentope errors."""


class DataError(AgentopeError):
    """Input data or arguments are invalid. The CLI exits with code 2."""


class RefusedError(AgentopeError):
    """A guard refused to run the evaluation. The CLI exits with code 1."""
