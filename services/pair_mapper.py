from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PairMappingResult:
    requested: str
    found: bool
    pair: str | None
    market_type: str | None
    explanation: str


@dataclass(frozen=True, slots=True)
class PairDefinition:
    pair: str
    market_type: str
    explanation: str


class PairMapper:
    def __init__(self) -> None:
        self._map = self._build_map()

    def resolve(self, asset_or_market: str) -> PairMappingResult:
        if is_explicit_pair(asset_or_market):
            return PairMappingResult(
                requested=asset_or_market,
                found=True,
                pair=asset_or_market.strip().upper(),
                market_type="explicit pair",
                explanation="Using the pair exactly as provided.",
            )

        normalized = normalize_asset(asset_or_market)
        definition = self._map.get(normalized)
        if definition is None:
            return PairMappingResult(
                requested=asset_or_market,
                found=False,
                pair=None,
                market_type=None,
                explanation="No safe static mapping was found in the curated Phase 1 map.",
            )

        return PairMappingResult(
            requested=asset_or_market,
            found=True,
            pair=definition.pair,
            market_type=definition.market_type,
            explanation=definition.explanation,
        )

    def list_supported_aliases(self) -> list[str]:
        return sorted(self._map.keys())

    @staticmethod
    def _build_map() -> dict[str, PairDefinition]:
        return {
            "btc": PairDefinition(
                pair="BTC/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid BTC perp pair.",
            ),
            "bitcoin": PairDefinition(
                pair="BTC/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid BTC perp pair.",
            ),
            "eth": PairDefinition(
                pair="ETH/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid ETH perp pair.",
            ),
            "ethereum": PairDefinition(
                pair="ETH/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid ETH perp pair.",
            ),
            "sol": PairDefinition(
                pair="SOL/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid SOL perp pair.",
            ),
            "solana": PairDefinition(
                pair="SOL/USDC:USDC",
                market_type="crypto perp",
                explanation="Mapped to the standard Hyperliquid SOL perp pair.",
            ),
            "gold": PairDefinition(
                pair="XYZ-GOLD/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped using the `XYZ-` HIP3 convention documented in SKILL.md for metals.",
            ),
            "silver": PairDefinition(
                pair="XYZ-SILVER/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped using the `XYZ-` HIP3 convention documented in SKILL.md for metals.",
            ),
            "oil": PairDefinition(
                pair="XYZ-BRENTOIL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to Brent oil as the broad oil proxy in the curated HIP3 list. `XYZ-CL/USDC:USDC` can be used for WTI-style exposure.",
            ),
            "brent": PairDefinition(
                pair="XYZ-BRENTOIL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the Brent oil HIP3 pair listed in SKILL.md.",
            ),
            "wti": PairDefinition(
                pair="XYZ-CL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the CL crude oil HIP3 pair listed in SKILL.md.",
            ),
            "aapl": PairDefinition(
                pair="XYZ-AAPL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ AAPL HIP3 pair listed in SKILL.md.",
            ),
            "apple": PairDefinition(
                pair="XYZ-AAPL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ AAPL HIP3 pair listed in SKILL.md.",
            ),
            "amzn": PairDefinition(
                pair="XYZ-AMZN/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ AMZN HIP3 pair listed in SKILL.md.",
            ),
            "amazon": PairDefinition(
                pair="XYZ-AMZN/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ AMZN HIP3 pair listed in SKILL.md.",
            ),
            "coin": PairDefinition(
                pair="XYZ-COIN/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ COIN HIP3 pair listed in SKILL.md.",
            ),
            "googl": PairDefinition(
                pair="XYZ-GOOGL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ GOOGL HIP3 pair listed in SKILL.md.",
            ),
            "google": PairDefinition(
                pair="XYZ-GOOGL/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ GOOGL HIP3 pair listed in SKILL.md.",
            ),
            "meta": PairDefinition(
                pair="XYZ-META/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ META HIP3 pair listed in SKILL.md.",
            ),
            "dxy": PairDefinition(
                pair="XYZ-DXY/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ DXY HIP3 pair listed in SKILL.md.",
            ),
            "dollar": PairDefinition(
                pair="XYZ-DXY/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the DXY dollar index proxy listed in SKILL.md.",
            ),
            "eurusd": PairDefinition(
                pair="XYZ-EUR/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ EUR HIP3 pair listed in SKILL.md.",
            ),
            "euro": PairDefinition(
                pair="XYZ-EUR/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ EUR HIP3 pair listed in SKILL.md.",
            ),
            "jpy": PairDefinition(
                pair="XYZ-JPY/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ JPY HIP3 pair listed in SKILL.md.",
            ),
            "yen": PairDefinition(
                pair="XYZ-JPY/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ JPY HIP3 pair listed in SKILL.md.",
            ),
            "microsoft": PairDefinition(
                pair="XYZ-MSFT/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ MSFT HIP3 pair listed in SKILL.md.",
            ),
            "msft": PairDefinition(
                pair="XYZ-MSFT/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ MSFT HIP3 pair listed in SKILL.md.",
            ),
            "nvda": PairDefinition(
                pair="XYZ-NVDA/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ NVDA HIP3 pair listed in SKILL.md.",
            ),
            "sp500": PairDefinition(
                pair="XYZ-SP500/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ SP500 HIP3 pair listed in SKILL.md.",
            ),
            "s&p500": PairDefinition(
                pair="XYZ-SP500/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ SP500 HIP3 pair listed in SKILL.md.",
            ),
            "vix": PairDefinition(
                pair="XYZ-VIX/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ VIX HIP3 pair listed in SKILL.md.",
            ),
            "natgas": PairDefinition(
                pair="XYZ-NATGAS/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ NATGAS HIP3 pair listed in SKILL.md.",
            ),
            "naturalgas": PairDefinition(
                pair="XYZ-NATGAS/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ NATGAS HIP3 pair listed in SKILL.md.",
            ),
            "tesla": PairDefinition(
                pair="XYZ-TSLA/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ TSLA HIP3 pair listed in SKILL.md.",
            ),
            "tsla": PairDefinition(
                pair="XYZ-TSLA/USDC:USDC",
                market_type="HIP3 perp",
                explanation="Mapped to the XYZ TSLA HIP3 pair listed in SKILL.md.",
            ),
        }


def normalize_asset(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
        .replace(":", "")
    )


def is_explicit_pair(value: str) -> bool:
    stripped = value.strip()
    return "/" in stripped
