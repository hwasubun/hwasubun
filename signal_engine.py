"""IF-THEN 신호 판별 엔진.

규칙 (Dalio 『변화하는 세계 질서』 프레임):
  R1. IF 금 전월 대비 +5%↑ AND 달러인덱스 < 100  → 인플레헤지 강화 (HIGH)
  R2. IF 미국 10년 실질금리 ≤ 0%                → 금·실물 비중 확대 (HIGH)
  R3. IF 미국 부채/GDP > 120%                   → 달러 장기 리스크 (WARNING)
  R4. IF 금 전월 대비 ±5% 이상 변동             → 포지션·헤지 점검 (INFO)

데이터가 누락된 지표의 규칙은 발동하지 않고 '데이터 없음'으로 표시한다.
"""
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

import config


@dataclass
class Signal:
    rule_id: str
    name: str
    condition: str       # IF 조건 설명
    action: str          # THEN 권고 행동
    severity: str        # HIGH | WARNING | INFO
    triggered: bool
    detail: str          # 현재 값 기반 상세 설명
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))


def _monthly_change_pct(series: pd.Series, trading_days: int = 21) -> float:
    """전월(약 21거래일 전) 대비 변동률(%)."""
    if len(series) <= trading_days:
        return 0.0
    prev, last = series.iloc[-1 - trading_days], series.iloc[-1]
    return (last / prev - 1) * 100


def _fmt(value, pattern: str, missing: str = "데이터 없음") -> str:
    return pattern.format(value) if value is not None else missing


def compute_indicators(data: dict[str, pd.Series]) -> dict:
    """원시 시계열 → 신호 판별에 쓰는 현재 지표값. 누락 시리즈는 None."""
    out = {}

    def put(key: str, series_name: str, value_fn):
        series = data.get(series_name)
        if series is None or series.empty:
            out[key], out[f"{key}_date"] = None, None
        else:
            out[key] = value_fn(series)
            out[f"{key}_date"] = series.index[-1].date().isoformat()

    put("gold_price", "gold", lambda s: float(s.iloc[-1]))
    put("gold_change_1m", "gold", _monthly_change_pct)
    put("dxy", "dxy", lambda s: float(s.iloc[-1]))
    put("real_rate", "real_rate", lambda s: float(s.iloc[-1]))
    put("debt_gdp", "debt_gdp", lambda s: float(s.iloc[-1]))
    return out


def evaluate(indicators: dict) -> list[Signal]:
    """IF-THEN 규칙을 모두 평가해 Signal 리스트 반환 (발동 여부 무관 전체 반환)."""
    g_chg = indicators.get("gold_change_1m")
    dxy = indicators.get("dxy")
    rr = indicators.get("real_rate")
    debt = indicators.get("debt_gdp")

    return [
        Signal(
            rule_id="R1",
            name="인플레헤지 강화",
            condition=f"금 전월 대비 +{config.GOLD_CHANGE_THRESHOLD:.0f}% 이상 AND 달러인덱스 < {config.DXY_THRESHOLD:.0f}",
            action="금·원자재 등 인플레이션 헤지 자산 비중을 강화",
            severity="HIGH",
            triggered=bool(
                g_chg is not None and dxy is not None
                and g_chg >= config.GOLD_CHANGE_THRESHOLD and dxy < config.DXY_THRESHOLD
            ),
            detail=f"금 1개월 변동 {_fmt(g_chg, '{:+.2f}%')}, 달러인덱스 {_fmt(dxy, '{:.2f}')}",
        ),
        Signal(
            rule_id="R2",
            name="금·실물 비중 확대",
            condition=f"미국 10년 실질금리 ≤ {config.REAL_RATE_THRESHOLD:.0f}%",
            action="실질금리 마이너스 → 금·실물자산 비중 확대",
            severity="HIGH",
            triggered=bool(rr is not None and rr <= config.REAL_RATE_THRESHOLD),
            detail=f"실질금리 {_fmt(rr, '{:.2f}%')} ({indicators.get('real_rate_date') or '-'})",
        ),
        Signal(
            rule_id="R3",
            name="달러 장기 리스크",
            condition=f"미국 부채/GDP > {config.DEBT_GDP_THRESHOLD:.0f}%",
            action="기축통화 약화 장기 리스크 — 달러 외 통화·실물 분산 점검",
            severity="WARNING",
            triggered=bool(debt is not None and debt > config.DEBT_GDP_THRESHOLD),
            detail=f"부채/GDP {_fmt(debt, '{:.1f}%')} ({indicators.get('debt_gdp_date') or '-'})",
        ),
        Signal(
            rule_id="R4",
            name="금 가격 급변동",
            condition=f"금 전월 대비 ±{config.GOLD_CHANGE_THRESHOLD:.0f}% 이상 변동",
            action="변동성 확대 — 포지션·헤지 점검",
            severity="INFO",
            triggered=bool(g_chg is not None and abs(g_chg) >= config.GOLD_CHANGE_THRESHOLD),
            detail=(
                f"금 1개월 변동 {_fmt(g_chg, '{:+.2f}%')}"
                f" (현재가 {_fmt(indicators.get('gold_price'), '{:,.1f}')})"
            ),
        ),
    ]


def run_engine(data: dict[str, pd.Series]) -> tuple[dict, list[Signal]]:
    indicators = compute_indicators(data)
    return indicators, evaluate(indicators)
