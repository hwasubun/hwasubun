"""데이터 수집 — yfinance(금, 달러인덱스) + FRED(실질금리, 부채/GDP).

FRED 수집 순서:
  1) FRED_API_KEY가 있으면 fredapi (api.stlouisfed.org)
  2) FRED 공개 CSV (fred.stlouisfed.org — 키 불필요, 일부 네트워크에서 차단됨)
  3) DFII10(실질금리)에 한해 미 재무부 실질수익률 CSV로 폴백
"""
import io
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

import config

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_real_yield_curve&_format=csv"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (dalio-signal-app)"}


def fetch_market(tickers: list[str], period: str = "2y") -> pd.Series:
    """yfinance 종가 시계열. 첫 티커 실패 시 대체 티커를 순서대로 시도."""
    last_err = None
    for ticker in tickers:
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df.empty:
                continue
            close = df["Close"]
            if isinstance(close, pd.DataFrame):  # 멀티인덱스 컬럼 대응
                close = close.iloc[:, 0]
            close = close.dropna()
            if not close.empty:
                close.name = ticker
                return close
        except Exception as e:  # noqa: BLE001 — 다음 티커로 폴백
            last_err = e
    raise RuntimeError(f"yfinance 데이터 수집 실패: {tickers} ({last_err})")


def _fetch_fred_csv(series_id: str) -> pd.Series:
    resp = requests.get(FRED_CSV_URL.format(sid=series_id), headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), na_values=".")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["value"].dropna()
    s.name = series_id
    return s


def fetch_treasury_real_10y() -> pd.Series:
    """미 재무부 일별 실질수익률 곡선에서 10년 실질금리 (DFII10 대체)."""
    year = datetime.now().year
    frames = []
    for y in (year - 1, year):
        resp = requests.get(TREASURY_CSV_URL.format(year=y), headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df["Date"] = pd.to_datetime(df["Date"])
        frames.append(df.set_index("Date")["10 YR"])
    s = pd.concat(frames).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s.name = "TREASURY_REAL_10Y"
    return s


def fetch_fred(series_id: str) -> pd.Series:
    if config.FRED_API_KEY:
        from fredapi import Fred

        s = Fred(api_key=config.FRED_API_KEY).get_series(series_id)
        s = s.dropna()
        s.name = series_id
        return s

    try:
        return _fetch_fred_csv(series_id)
    except requests.RequestException as e:
        if series_id == config.FRED_REAL_RATE:
            return fetch_treasury_real_10y()
        raise RuntimeError(
            f"FRED({series_id}) 수집 실패 — .env에 FRED_API_KEY를 설정하면 해결됩니다. ({e})"
        ) from e


def get_all_data() -> tuple[dict[str, pd.Series], dict[str, str]]:
    """전체 시계열 수집. 실패한 시리즈는 건너뛰고 (데이터, 오류) 튜플로 반환."""
    fetchers = {
        "gold": lambda: fetch_market(config.GOLD_TICKERS),
        "dxy": lambda: fetch_market(config.DXY_TICKERS),
        "real_rate": lambda: fetch_fred(config.FRED_REAL_RATE),
        "debt_gdp": lambda: fetch_fred(config.FRED_DEBT_GDP),
    }
    data, errors = {}, {}
    for name, fn in fetchers.items():
        try:
            data[name] = fn()
        except Exception as e:  # noqa: BLE001 — 시리즈 단위로 격리
            errors[name] = str(e)
    return data, errors


if __name__ == "__main__":
    data, errors = get_all_data()
    for name, series in data.items():
        print(f"{name}: {len(series)}개 ({series.index[-1].date()} = {series.iloc[-1]:.2f})")
    for name, err in errors.items():
        print(f"{name}: 실패 — {err}")
