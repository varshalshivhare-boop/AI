"""Exception types. Each one marks a failure class the caller must handle explicitly."""


class ConfigurationError(Exception):
    """Startup configuration is missing or invalid. The service must not run on fake data."""


class ProviderNotImplementedError(RuntimeError):
    """A provider component exists as a scaffold and cannot yet produce data."""


class StorageError(Exception):
    """Candle persistence failed. Fatal for the pipeline: candles must not be lost silently."""
