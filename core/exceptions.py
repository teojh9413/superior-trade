class SuperiorBotError(Exception):
    """Base exception for the bot."""


class ConfigurationError(SuperiorBotError):
    """Raised when required configuration is missing."""


class PairMappingError(SuperiorBotError):
    """Raised when a pair cannot be safely mapped."""
