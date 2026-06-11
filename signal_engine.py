"""IF-THEN 신호 판별 엔진.

규칙 (Dalio 『변화하는 세계 질서』 프레임):
  R1. IF 금 전월 대비 +5%↑ AND 달러인덱스 < 100  → 인플레헤지 강화 (HIGH)
  R2. IF 미국 10년 실질금리 ≤ 0%                → 금·실물 비중 확대 (HIGH)
  R3. IF 미국 부채/GDP > 120%                   → 달러 장기 리스크 (WARNING)
  R4. IF 금 전월 대비 ±5% 이상 변동             → 포지션·헤지 점검 (INFO)
  R5. IF 금/구리 비율 전월 대비 +10% 이상       → 리스크오프 경계 (WARNING)
  R6. IF 미 10Y-2Y 금리차 ≤ 0 (역전)            → 침체 선행 경고 (WARNING)
  R7. IF 원/달러 ≥ 1,450                        → 원화 약세 경고 (WARNING)
  R8. IF 한국 가계부채/GDP > 95%                → 한국 가계부채 위험 (WARNING)

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
    put("yield_spread", "yield_spread", lambda s: float(s.iloc[-1]))
    put("krw", "krw", lambda s: float(s.iloc[-1]))
    put("kr_household_debt", "kr_household_debt", lambda s: float(s.iloc[-1]))

    # 금/구리 비율 — 두 시계열이 모두 있어야 계산 가능
    gold_s, copper_s = data.get("gold"), data.get("copper")
    if gold_s is not None and copper_s is not None and not gold_s.empty and not copper_s.empty:
        ratio = (gold_s / copper_s).dropna()
        out["gold_copper"] = float(ratio.iloc[-1])
        out["gold_copper_change_1m"] = _monthly_change_pct(ratio)
        out["gold_copper_date"] = ratio.index[-1].date().isoformat()
    else:
        out["gold_copper"] = out["gold_copper_change_1m"] = None
        out["gold_copper_date"] = None
    return out


def evaluate(indicators: dict) -> list[Signal]:
    """IF-THEN 규칙을 모두 평가해 Signal 리스트 반환 (발동 여부 무관 전체 반환)."""
    g_chg = indicators.get("gold_change_1m")
    dxy = indicators.get("dxy")
    rr = indicators.get("real_rate")
    debt = indicators.get("debt_gdp")
    gc_chg = indicators.get("gold_copper_change_1m")
    spread = indicators.get("yield_spread")
    krw = indicators.get("krw")
    kr_debt = indicators.get("kr_household_debt")

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
        Signal(
            rule_id="R5",
            name="리스크오프 경계",
            condition=f"금/구리 비율 전월 대비 +{config.GOLD_COPPER_CHANGE_THRESHOLD:.0f}% 이상 상승",
            action="안전자산 선호 급증 — 경기둔화 대비, 방어 포지션 점검",
            severity="WARNING",
            triggered=bool(gc_chg is not None and gc_chg >= config.GOLD_COPPER_CHANGE_THRESHOLD),
            detail=(
                f"금/구리 비율 1개월 변동 {_fmt(gc_chg, '{:+.2f}%')}"
                f" (현재 {_fmt(indicators.get('gold_copper'), '{:,.0f}')})"
            ),
        ),
        Signal(
            rule_id="R6",
            name="침체 선행 경고",
            condition=f"미 10Y-2Y 금리차 ≤ {config.YIELD_SPREAD_THRESHOLD:.0f}%p (역전)",
            action="수익률곡선 역전 — 향후 12~18개월 침체 가능성, 듀레이션·방어자산 점검",
            severity="WARNING",
            triggered=bool(spread is not None and spread <= config.YIELD_SPREAD_THRESHOLD),
            detail=f"10Y-2Y {_fmt(spread, '{:+.2f}%p')} ({indicators.get('yield_spread_date') or '-'})",
        ),
        Signal(
            rule_id="R7",
            name="원화 약세 경고",
            condition=f"원/달러 ≥ {config.KRW_THRESHOLD:,.0f}원",
            action="수입물가발 인플레 압력 — 환헤지·달러 표시 자산 분산 점검",
            severity="WARNING",
            triggered=bool(krw is not None and krw >= config.KRW_THRESHOLD),
            detail=f"원/달러 {_fmt(krw, '{:,.1f}원')} ({indicators.get('krw_date') or '-'})",
        ),
        Signal(
            rule_id="R8",
            name="한국 가계부채 위험",
            condition=f"한국 가계부채/GDP > {config.KR_HOUSEHOLD_DEBT_THRESHOLD:.0f}% (BIS 기준)",
            action="가계 디레버리징발 내수 위축 압력 — 한국 내수자산 비중 점검",
            severity="WARNING",
            triggered=bool(kr_debt is not None and kr_debt > config.KR_HOUSEHOLD_DEBT_THRESHOLD),
            detail=(
                f"가계부채/GDP {_fmt(kr_debt, '{:.1f}%')}"
                f" ({indicators.get('kr_household_debt_date') or '-'})"
            ),
        ),
    ]


def run_engine(data: dict[str, pd.Series]) -> tuple[dict, list[Signal]]:
    indicators = compute_indicators(data)
    return indicators, evaluate(indicators)
