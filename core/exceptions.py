class SuperiorBotError(Exception):
    """Base exception for the bot."""


class ConfigurationError(SuperiorBotError):
    """Raised when required configuration is missing."""


class MarketResolutionError(SuperiorBotError):
    """Raised when an official Hyperliquid market cannot be resolved."""


class SuperiorApiError(SuperiorBotError):
    """Raised when the Superior.Trade API returns an error."""


class BacktestRunError(SuperiorBotError):
    """Raised when a deterministic backtest run cannot complete successfully."""
