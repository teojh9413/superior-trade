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
        MarketInfo("flx:TSLA", "FLX-TSLA", "FLX-TSLA/USDH:USDH", "TSLA", "perp", "perp:flx", "cross", ("tsla",)),
        MarketInfo("xyz:TSLA", "XYZ-TSLA", "XYZ-TSLA/USDC:USDC", "TSLA", "perp", "perp:xyz", "cross", ("tsla",)),
        MarketInfo("TSLA/USDC", "TSLA", "TSLA/USDC", "TSLA", "spot", "spot", None, ("tsla",)),
    ]

    sorted_candidates = sort_market_candidates(candidates)

    assert sorted_candidates[0].ticker == "XYZ-TSLA"
    assert sorted_candidates[-1].market_type == "spot"


def test_market_info_for_bio_core_perp_shape() -> None:
    market = MarketInfo("BIO", "BIO", "BIO/USDC:USDC", "BIO", "perp", "perp:core", "cross", ("bio",))

    assert market.ticker == "BIO"
    assert market.pair == "BIO/USDC:USDC"
