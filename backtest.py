"""백테스트 — 과거 시계열로 IF-THEN 신호를 소급 계산하고 발동 후 자산 수익률 검증.

방법론:
  - 모든 시계열을 월말 기준으로 리샘플
  - 규칙별로 과거 발동 시점을 계산하되, 연속 발동 구간은 '진입 시점'(미발동→발동
    전환 월)만 채택해 자기상관을 줄임
  - 진입 시점 이후 1/3/6/12개월 자산 수익률 평균·승률을 전체 기간 평균과 비교

부채/GDP(R3)는 연간 데이터라 월 단위 백테스트에서 제외한다.
"""
import pandas as pd

import config
from data_fetcher import fetch_fred, fetch_market

HORIZONS = {"1개월": 1, "3개월": 3, "6개월": 6, "12개월": 12}

# 백테스트 대상 자산 (yfinance, 가능한 한 긴 히스토리)
ASSETS = {
    "금": ["GC=F", "GLD"],
    "미국주식": ["^GSPC"],
    "미국채(20Y+)": ["TLT"],
    "달러인덱스": ["DX-Y.NYB", "DX=F"],
}


def _monthly(series: pd.Series) -> pd.Series:
    return series.resample("ME").last().dropna()


def load_history() -> dict[str, pd.Series]:
    """백테스트용 장기 시계열 (월말 기준)."""
    out = {}
    for name, tickers in ASSETS.items():
        out[name] = _monthly(fetch_market(tickers, period="max"))
    out["_gold"] = out["금"]
    out["_dxy"] = out["달러인덱스"]
    out["_copper"] = _monthly(fetch_market(config.COPPER_TICKERS, period="max"))
    out["_real_rate"] = _monthly(fetch_fred(config.FRED_REAL_RATE))      # DFII10, 2003~
    out["_spread"] = _monthly(fetch_fred("T10Y2Y"))                      # 1976~
    return out


def _entries(triggered: pd.Series) -> pd.DatetimeIndex:
    """발동 불리언 시리즈에서 진입 시점(False→True 전환)만 추출."""
    triggered = triggered.fillna(False).astype(bool)
    return triggered.index[triggered & ~triggered.shift(1, fill_value=False)]


def build_rule_triggers(h: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """규칙별 과거 발동 여부 (월말 불리언 시리즈)."""
    gold_chg = h["_gold"].pct_change() * 100          # 월간 변동률
    ratio_chg = (h["_gold"] / h["_copper"]).dropna().pct_change() * 100
    dxy = h["_dxy"]

    return {
        "R1 인플레헤지 강화": (
            (gold_chg >= config.GOLD_CHANGE_THRESHOLD)
            & (dxy.reindex(gold_chg.index) < config.DXY_THRESHOLD)
        ),
        "R2 금·실물 비중 확대": h["_real_rate"] <= config.REAL_RATE_THRESHOLD,
        "R4 금 가격 급변동": gold_chg.abs() >= config.GOLD_CHANGE_THRESHOLD,
        "R5 리스크오프 경계": ratio_chg >= config.GOLD_COPPER_CHANGE_THRESHOLD,
        "R6 침체 선행 경고": h["_spread"] <= config.YIELD_SPREAD_THRESHOLD,
    }


def forward_returns(price: pd.Series, dates: pd.DatetimeIndex, months: int) -> pd.Series:
    """각 시점에서 N개월 뒤까지의 수익률(%)."""
    future = price.shift(-months)
    rets = (future / price - 1) * 100
    return rets.reindex(dates).dropna()


def run_backtest() -> tuple[pd.DataFrame, dict[str, int]]:
    """규칙×자산×기간 평균 수익률 표와 규칙별 진입 횟수 반환."""
    h = load_history()
    triggers = build_rule_triggers(h)

    rows = []
    counts = {}
    for rule_name, trig in triggers.items():
        entry_dates = _entries(trig)
        counts[rule_name] = len(entry_dates)
        for asset in ASSETS:
            price = h[asset]
            row = {"규칙": rule_name, "자산": asset, "진입횟수": len(entry_dates)}
            for label, months in HORIZONS.items():
                rets = forward_returns(price, entry_dates, months)
                base = forward_returns(price, price.index, months)  # 전기간 베이스라인
                row[f"{label} 평균"] = round(rets.mean(), 2) if len(rets) else None
                row[f"{label} 승률"] = (
                    round((rets > 0).mean() * 100, 0) if len(rets) else None
                )
                row[f"{label} 초과"] = (
                    round(rets.mean() - base.mean(), 2) if len(rets) else None
                )
            rows.append(row)
    return pd.DataFrame(rows), counts


if __name__ == "__main__":
    table, counts = run_backtest()
    print("규칙별 진입 횟수:", counts)
    print(table.to_string(index=False))
