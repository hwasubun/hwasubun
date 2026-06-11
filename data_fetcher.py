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
WORLDBANK_DEBT_URL = (
    "https://api.worldbank.org/v2/country/{country}/indicator/"
    "GC.DOD.TOTL.GD.ZS?format=json&per_page=200"
)
TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_real_yield_curve&_format=csv"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (dalio-signal-app)"}
_TIMEOUT = 60  # FRED 공개 엔드포인트가 느릴 때가 많아 넉넉하게

# 성공한 수집 결과를 저장해 두는 로컬 캐시 — 실시간 수집 실패 시 마지막 값으로 폴백
CACHE_DIR = config.BASE_DIR / "data_cache"


def _save_cache(name: str, series: pd.Series) -> None:
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        series.to_csv(CACHE_DIR / f"{name}.csv")
    except OSError:
        pass  # 캐시 저장 실패는 치명적이지 않음


def _load_cache(name: str) -> pd.Series | None:
    path = CACHE_DIR / f"{name}.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        s = df.iloc[:, 0].dropna()
        s.name = df.columns[0]
        return s if not s.empty else None
    except Exception:  # noqa: BLE001 — 캐시가 깨졌으면 없는 것으로 취급
        return None


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
    resp = requests.get(FRED_CSV_URL.format(sid=series_id), headers=_HEADERS, timeout=_TIMEOUT)
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
        resp = requests.get(TREASURY_CSV_URL.format(year=y), headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df["Date"] = pd.to_datetime(df["Date"])
        frames.append(df.set_index("Date")["10 YR"])
    s = pd.concat(frames).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s.name = "TREASURY_REAL_10Y"
    return s


def fetch_worldbank_debt_gdp(country: str = "US") -> pd.Series:
    """World Bank 중앙정부부채/GDP (GC.DOD.TOTL.GD.ZS, 연간)."""
    resp = requests.get(WORLDBANK_DEBT_URL.format(country=country),
                        headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        raise RuntimeError(f"World Bank 응답 형식 오류: {str(payload)[:200]}")
    records = sorted(
        (int(row["date"]), float(row["value"]))
        for row in payload[1] if row.get("value") is not None
    )
    if not records:
        raise RuntimeError("World Bank 부채/GDP 데이터 없음")
    s = pd.Series(
        [value for _, value in records],
        index=pd.to_datetime([f"{year}-12-31" for year, _ in records]),
        name="WB GC.DOD.TOTL.GD.ZS",
    )
    return s


def fetch_debt_gdp() -> pd.Series:
    """부채/GDP — World Bank 우선, 실패 시 FRED 폴백."""
    try:
        return fetch_worldbank_debt_gdp()
    except Exception:  # noqa: BLE001 — FRED로 폴백
        return fetch_fred(config.FRED_DEBT_GDP)


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
    """전체 시계열 수집 후 (데이터, 오류) 튜플 반환.

    성공한 시리즈는 data_cache/에 저장된다. 실시간 수집이 실패하면 캐시된
    마지막 값으로 폴백한다(data에 포함 + errors에 사유 기록). 캐시도 없으면
    해당 시리즈는 data에서 빠지고 errors에만 남는다.
    """
    fetchers = {
        "gold": lambda: fetch_market(config.GOLD_TICKERS),
        "dxy": lambda: fetch_market(config.DXY_TICKERS),
        "real_rate": lambda: fetch_fred(config.FRED_REAL_RATE),
        "debt_gdp": fetch_debt_gdp,
    }
    data, errors = {}, {}
    for name, fn in fetchers.items():
        try:
            data[name] = fn()
            _save_cache(name, data[name])
        except Exception as e:  # noqa: BLE001 — 시리즈 단위로 격리
            cached = _load_cache(name)
            if cached is not None:
                data[name] = cached
                errors[name] = (
                    f"실시간 수집 실패 — 캐시된 마지막 값 사용"
                    f" (기준일 {cached.index[-1].date()}): {e}"
                )
            else:
                errors[name] = str(e)
    return data, errors


if __name__ == "__main__":
    data, errors = get_all_data()
    for name, series in data.items():
        print(f"{name}: {len(series)}개 ({series.index[-1].date()} = {series.iloc[-1]:.2f})")
    for name, err in errors.items():
        print(f"{name}: 실패 — {err}")
