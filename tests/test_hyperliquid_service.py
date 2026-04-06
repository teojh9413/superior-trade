from services.hyperliquid_service import (
    MarketInfo,
    build_searchable_keys,
    looks_like_simple_asset,
    normalize_asset_request,
    sort_market_candidates,
    standardize_market_name,
)


def test_asset_validator_rejects_long_natural_language_input() -> None:
    assert looks_like_simple_asset("btc")
    assert not looks_like_simple_asset("should i long btc today?")


def test_normalize_asset_request_removes_punctuation() -> None:
    assert normalize_asset_request("S&P-500") == "sp500"


def test_standardize_market_name_formats_hip3_names() -> None:
    assert standardize_market_name("xyz:TSLA") == "XYZ-TSLA"
    assert standardize_market_name("BTC") == "BTC"


def test_build_searchable_keys_includes_aliases() -> None:
    keys = build_searchable_keys(ticker="XYZ-TSLA", symbol="TSLA", raw_name="xyz:TSLA")

    assert "tesla" in keys
    assert "tsla" in keys


def test_sort_market_candidates_prefers_perp_and_xyz() -> None:
    candidates = [
        MarketInfo("flx:TSLA", "FLX-TSLA", "TSLA", "perp", "perp", ("tsla",)),
        MarketInfo("xyz:TSLA", "XYZ-TSLA", "TSLA", "perp", "perp", ("tsla",)),
        MarketInfo("TSLA/USDC", "TSLA", "TSLA", "spot", "spot", ("tsla",)),
    ]

    sorted_candidates = sort_market_candidates(candidates)

    assert sorted_candidates[0].ticker == "XYZ-TSLA"
    assert sorted_candidates[-1].market_type == "spot"
