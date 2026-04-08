from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyTemplate:
    name: str
    class_name: str
    code: str


def get_strategy_templates() -> list[StrategyTemplate]:
    return [
        build_macd_strategy(),
        build_bollinger_breakout_strategy(),
        build_rsi_reversal_strategy(),
        build_ema_crossover_strategy(name="10/20 EMA Crossover", class_name="Ema1020CrossoverStrategy", fast=10, slow=20),
        build_ema_crossover_strategy(name="20/50 EMA Crossover", class_name="Ema2050CrossoverStrategy", fast=20, slow=50),
        build_donchian_strategy(),
        build_heikin_ashi_strategy(),
    ]


def base_header(class_name: str) -> str:
    return f"""from freqtrade.strategy import IStrategy
import pandas as pd
import talib.abstract as ta


class {class_name}(IStrategy):
    minimal_roi = {{"0": 100.0}}
    stoploss = -0.99
    trailing_stop = False
    timeframe = "15m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 60

"""


def build_macd_strategy() -> StrategyTemplate:
    code = base_header("MacdCrossStrategy") + """
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        macd, macdsignal, macdhist = ta.MACD(dataframe)
        dataframe["macd"] = macd
        dataframe["macdsignal"] = macdsignal
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["macd"] > dataframe["macdsignal"]) &
            (dataframe["macd"].shift(1) <= dataframe["macdsignal"].shift(1)),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["macd"] < dataframe["macdsignal"]) &
            (dataframe["macd"].shift(1) >= dataframe["macdsignal"].shift(1)),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate("MACD", "MacdCrossStrategy", code.strip() + "\n")


def build_bollinger_breakout_strategy() -> StrategyTemplate:
    code = base_header("BollingerBandBreakoutStrategy") + """
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        upper, middle, lower = ta.BBANDS(dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        dataframe["bb_upper"] = upper
        dataframe["bb_middle"] = middle
        dataframe["bb_lower"] = lower
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["bb_upper"]) &
            (dataframe["close"].shift(1) <= dataframe["bb_upper"].shift(1)),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["bb_middle"]) &
            (dataframe["close"].shift(1) >= dataframe["bb_middle"].shift(1)),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate("Bollinger Band Breakout", "BollingerBandBreakoutStrategy", code.strip() + "\n")


def build_rsi_reversal_strategy() -> StrategyTemplate:
    code = base_header("RsiReversalStrategy") + """
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > 30) &
            (dataframe["rsi"].shift(1) <= 30),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["rsi"] > 70) &
            (dataframe["rsi"].shift(1) <= 70),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate("RSI Reversal", "RsiReversalStrategy", code.strip() + "\n")


def build_ema_crossover_strategy(*, name: str, class_name: str, fast: int, slow: int) -> StrategyTemplate:
    code = base_header(class_name) + f"""
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod={fast})
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod={slow})
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["ema_fast"] > dataframe["ema_slow"]) &
            (dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["ema_fast"] < dataframe["ema_slow"]) &
            (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate(name, class_name, code.strip() + "\n")


def build_donchian_strategy() -> StrategyTemplate:
    code = base_header("DonchianBreakoutStrategy") + """
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["donchian_upper"] = dataframe["high"].rolling(window=20).max()
        dataframe["donchian_lower"] = dataframe["low"].rolling(window=20).min()
        dataframe["donchian_mid"] = (dataframe["donchian_upper"] + dataframe["donchian_lower"]) / 2
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["donchian_upper"].shift(1)),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["donchian_mid"]) &
            (dataframe["close"].shift(1) >= dataframe["donchian_mid"].shift(1)),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate("Donchian Channel Breakout", "DonchianBreakoutStrategy", code.strip() + "\n")


def build_heikin_ashi_strategy() -> StrategyTemplate:
    code = base_header("HeikinAshiTrendFlipStrategy") + """
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        ha_close = (dataframe["open"] + dataframe["high"] + dataframe["low"] + dataframe["close"]) / 4
        ha_open = ha_close.copy()
        if len(dataframe) > 0:
            ha_open.iloc[0] = (dataframe["open"].iloc[0] + dataframe["close"].iloc[0]) / 2
        for i in range(1, len(dataframe)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
        dataframe["ha_open"] = ha_open
        dataframe["ha_close"] = ha_close
        dataframe["ha_bullish"] = (dataframe["ha_close"] > dataframe["ha_open"]).astype(int)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["ha_bullish"] == 1) &
            (dataframe["ha_bullish"].shift(1) == 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe["ha_bullish"] == 0) &
            (dataframe["ha_bullish"].shift(1) == 1),
            "exit_long"
        ] = 1
        return dataframe
"""
    return StrategyTemplate("Heikin Ashi Trend Flip", "HeikinAshiTrendFlipStrategy", code.strip() + "\n")
