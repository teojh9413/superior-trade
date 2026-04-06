class SuperiorBotError(Exception):
    """Base exception for the bot."""


class ConfigurationError(SuperiorBotError):
    """Raised when required configuration is missing."""


class MarketResolutionError(SuperiorBotError):
    """Raised when an official Hyperliquid market cannot be resolved."""
