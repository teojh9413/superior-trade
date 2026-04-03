from services.pair_mapper import PairMapper, normalize_asset


def test_resolve_known_crypto_alias() -> None:
    mapper = PairMapper()

    result = mapper.resolve("btc")

    assert result.found is True
    assert result.pair == "BTC/USDC:USDC"
    assert result.market_type == "crypto perp"


def test_resolve_known_hip3_alias() -> None:
    mapper = PairMapper()

    result = mapper.resolve("gold")

    assert result.found is True
    assert result.pair == "XYZ-GOLD/USDC:USDC"
    assert result.market_type == "HIP3 perp"


def test_resolve_oil_uses_curated_proxy() -> None:
    mapper = PairMapper()

    result = mapper.resolve("oil")

    assert result.found is True
    assert result.pair == "XYZ-BRENTOIL/USDC:USDC"
    assert "proxy" in result.explanation.lower()


def test_explicit_pair_is_preserved() -> None:
    mapper = PairMapper()

    result = mapper.resolve("btc/usdc:usdc")

    assert result.found is True
    assert result.pair == "BTC/USDC:USDC"
    assert result.market_type == "explicit pair"


def test_unknown_alias_does_not_invent_pair() -> None:
    mapper = PairMapper()

    result = mapper.resolve("mystery-asset")

    assert result.found is False
    assert result.pair is None


def test_normalize_asset_removes_separators() -> None:
    assert normalize_asset("S&P-500 / USDC:USDC") == "s&p500usdcusdc"
