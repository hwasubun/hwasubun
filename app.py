"""Streamlit 대시보드 — Dalio '변화하는 세계 질서' IF-THEN 신호 모니터.

실행: streamlit run app.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import database
import notifier
from data_fetcher import get_all_data
from signal_engine import run_engine

st.set_page_config(page_title="Dalio 신호 모니터", page_icon="🌍", layout="wide")

_SEVERITY_STYLE = {
    "HIGH": ("🚨", "#ff4b4b"),
    "WARNING": ("⚠️", "#ffa726"),
    "INFO": ("ℹ️", "#42a5f5"),
}


@st.cache_data(ttl=3600, show_spinner="시장 데이터 수집 중...")
def load_data() -> tuple[dict[str, pd.Series], dict[str, str]]:
    return get_all_data()


def fmt(value, pattern: str, missing: str = "—") -> str:
    return pattern.format(value) if value is not None else missing


def threshold_chart(series: pd.Series, title: str, threshold: float,
                    threshold_label: str) -> go.Figure:
    s = series.loc[series.index >= series.index[-1] - pd.DateOffset(years=2)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=title,
                             line=dict(color="#e0c060", width=2)))
    fig.add_hline(y=threshold, line_dash="dash", line_color="#ff4b4b",
                  annotation_text=threshold_label, annotation_position="top left")
    fig.update_layout(title=title, height=320, margin=dict(l=10, r=10, t=45, b=10),
                      template="plotly_dark", showlegend=False)
    return fig


def signal_card(col, s) -> None:
    emoji, color = _SEVERITY_STYLE.get(s.severity, ("", "#888"))
    status = "발동" if s.triggered else "정상"
    border = color if s.triggered else "#444"
    bg = f"{color}22" if s.triggered else "transparent"
    col.markdown(
        f"""
        <div style="border:2px solid {border}; border-radius:12px; padding:14px; background:{bg}; min-height:185px">
          <div style="font-size:0.8rem; color:{color}; font-weight:700">{emoji} {s.severity} · {s.rule_id} · {status}</div>
          <div style="font-size:1.15rem; font-weight:700; margin:6px 0">{s.name}</div>
          <div style="font-size:0.85rem; color:#aaa"><b>IF</b> {s.condition}</div>
          <div style="font-size:0.85rem; color:#aaa"><b>THEN</b> {s.action}</div>
          <div style="font-size:0.85rem; margin-top:8px">{s.detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── 사이드바 ─────────────────────────────────────────────
with st.sidebar:
    st.title("🌍 Dalio 신호 모니터")
    st.caption("『변화하는 세계 질서』 IF-THEN 프레임")

    if st.button("🔄 데이터 새로고침"):
        load_data.clear()
        st.rerun()

    st.divider()
    st.subheader("임계값")
    st.markdown(
        f"- 금 변동: ±{config.GOLD_CHANGE_THRESHOLD:.0f}% / 1개월\n"
        f"- 달러인덱스: {config.DXY_THRESHOLD:.0f} 이하\n"
        f"- 실질금리: {config.REAL_RATE_THRESHOLD:.0f}% 이하\n"
        f"- 부채/GDP: {config.DEBT_GDP_THRESHOLD:.0f}% 이상"
    )

    st.divider()
    st.subheader("데이터 소스")
    if config.FRED_API_KEY:
        st.success("FRED API 키 로드됨")
    else:
        st.info("FRED 키 없음 — 공개 CSV 폴백 사용 중. "
                "Cloud에서는 Settings → Secrets에 FRED_API_KEY를 설정하세요.")

    st.divider()
    st.subheader("텔레그램")
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        st.success("봇 설정됨")
        if st.button("테스트 메시지 발송"):
            ok = notifier.send_message("✅ Dalio 신호 모니터 테스트 메시지입니다.")
            st.toast("발송 완료" if ok else "발송 실패")
    else:
        st.info(".env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 설정하면 알림이 활성화됩니다.")

# ── 데이터 + 신호 평가 ───────────────────────────────────
data, errors = load_data()
if not data:
    st.error("모든 데이터 수집에 실패했습니다. 네트워크 또는 FRED_API_KEY 설정을 확인하세요.")
    st.stop()

_SERIES_LABEL = {"gold": "금", "dxy": "달러인덱스", "real_rate": "실질금리", "debt_gdp": "부채/GDP"}
for name, err in errors.items():
    label = _SERIES_LABEL.get(name, name)
    if name in data:  # 캐시된 마지막 값으로 폴백한 경우 — 평가는 계속됨
        st.info(f"ℹ️ {label}: {err}")
    else:
        st.warning(f"{label} 데이터 수집 실패 — 해당 규칙은 평가에서 제외됩니다. ({err})")

indicators, signals = run_engine(data)
database.save_triggered(signals)
triggered = [s for s in signals if s.triggered]

# ── 헤더 지표 ────────────────────────────────────────────
st.title("Ray Dalio — 변화하는 세계 질서 신호 대시보드")
st.caption("부채 · 패권 · 내부갈등 사이클 기반 거시 IF-THEN 모니터링")

m1, m2, m3, m4 = st.columns(4)
m1.metric("🥇 금 (1개월 변동)", fmt(indicators["gold_price"], "{:,.1f}"),
          fmt(indicators["gold_change_1m"], "{:+.2f}%", None))
m2.metric("💵 달러인덱스", fmt(indicators["dxy"], "{:.2f}"),
          f"기준 {config.DXY_THRESHOLD:.0f}", delta_color="off")
m3.metric("📉 미 10Y 실질금리", fmt(indicators["real_rate"], "{:.2f}%"),
          f"기준 {config.REAL_RATE_THRESHOLD:.0f}%", delta_color="off")
m4.metric("🏛️ 미 부채/GDP", fmt(indicators["debt_gdp"], "{:.1f}%"),
          f"기준 {config.DEBT_GDP_THRESHOLD:.0f}%", delta_color="off")

if triggered:
    st.error(f"🚨 현재 발동 중인 신호 {len(triggered)}건: " + " · ".join(s.name for s in triggered))
else:
    st.success("✅ 현재 발동 중인 신호가 없습니다.")

# ── 신호 카드 ────────────────────────────────────────────
st.subheader("IF-THEN 신호")
cols = st.columns(len(signals))
for col, s in zip(cols, signals):
    signal_card(col, s)

# ── 차트 ─────────────────────────────────────────────────
st.subheader("지표 차트 (최근 2년)")
# (시리즈 키, 제목, 기준선 값, 기준선 라벨) — 금은 변동률 기준이라 현재가를 기준선으로 표시
chart_specs = [
    ("gold", lambda s: f"금 ({s.name})", indicators["gold_price"], "현재가"),
    ("dxy", lambda s: f"달러인덱스 ({s.name})", config.DXY_THRESHOLD, f"임계 {config.DXY_THRESHOLD:.0f}"),
    ("real_rate", lambda s: f"미국 10년 실질금리 ({s.name})", config.REAL_RATE_THRESHOLD, "임계 0%"),
    ("debt_gdp", lambda s: f"미국 연방부채/GDP ({s.name})", config.DEBT_GDP_THRESHOLD,
     f"임계 {config.DEBT_GDP_THRESHOLD:.0f}%"),
]
available = [spec for spec in chart_specs if spec[0] in data]
for i in range(0, len(available), 2):
    for col, (key, title_fn, thr, thr_label) in zip(st.columns(2), available[i:i + 2]):
        col.plotly_chart(threshold_chart(data[key], title_fn(data[key]), thr, thr_label),
                         width="stretch")

# ── 국가별 빅사이클 ──────────────────────────────────────
st.subheader("국가별 빅사이클 위치 (15개국 · 정성 평가 · 참고용)")
st.caption("『변화하는 세계 질서』의 부채 사이클 · 내부 갈등 · 패권 프레임 기반. "
           "점수 0 = 상승초기(양호), 100 = 쇠퇴 말기(위험).")

_STAGE_EMOJI = {"상승초기": "🟢", "횡보/중립": "⚪", "조정/경고": "🟠", "위험/쇠퇴": "🔴"}
_by_score_asc = sorted(config.COUNTRY_CYCLES.items(), key=lambda kv: kv[1]["score"])

# 1) 사이클 포지션 바 차트 — 단계별 색상, 점수 오름차순 (위 = 위험)
fig = go.Figure()
for stage, color in config.CYCLE_STAGES.items():
    group = [(name, c) for name, c in _by_score_asc if c["stage"] == stage]
    if not group:
        continue
    fig.add_trace(go.Bar(
        y=[name for name, _ in group],
        x=[c["score"] for _, c in group],
        orientation="h",
        name=stage,
        marker_color=color,
        text=[f"{c['score']} · {c['action']}" for _, c in group],
        textposition="outside",
        hovertext=[f"{c['summary']}<br>권고: {c['action']}" for _, c in group],
        hoverinfo="text",
    ))
fig.update_layout(
    height=520, template="plotly_dark", barmode="overlay",
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(range=[0, 108], title="사이클 포지션 (0=상승초기 · 100=쇠퇴 말기)"),
    yaxis=dict(categoryorder="array", categoryarray=[name for name, _ in _by_score_asc]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, width="stretch")

# 2) 국가별 상세 분석 — 클릭해서 펼치기 (점수 높은 순)
st.markdown("##### 국가별 상세 분석 (클릭해서 펼치기)")
detail_cols = st.columns(3)
for i, (name, c) in enumerate(sorted(config.COUNTRY_CYCLES.items(),
                                     key=lambda kv: -kv[1]["score"])):
    with detail_cols[i % 3], st.expander(
            f"{_STAGE_EMOJI[c['stage']]} {name} · {c['score']}점 · 권고: {c['action']}"):
        stage_color = config.CYCLE_STAGES[c["stage"]]
        action_color = config.ACTION_COLORS[c["action"]]
        st.markdown(
            f"<span style='background:{stage_color}33;color:{stage_color};padding:2px 10px;"
            f"border-radius:10px;font-size:0.8rem;font-weight:700'>{c['stage']}</span>&nbsp;"
            f"<span style='background:{action_color}33;color:{action_color};padding:2px 10px;"
            f"border-radius:10px;font-size:0.8rem;font-weight:700'>Dalio 권고: {c['action']}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**핵심 지표 요약** — {c['summary']}")
        for metric, v in c["details"].items():
            st.progress(v / 100, text=f"{metric} {v}")
        st.markdown("**IF-THEN 리스크 요인**")
        for risk in c["risks"]:
            st.markdown(f"- {risk}")

# ── 포트폴리오 배분 시뮬레이터 ───────────────────────────
st.subheader("포트폴리오 배분 시뮬레이터")
st.caption("국가별 사이클 신호·거시 IF-THEN 신호와 연동된 자산 배분 도구. 합계 100%를 맞춰 보세요.")

DALIO_DEFAULTS = {  # Dalio 올웨더 변형 기본값 (합계 100%)
    "금·원자재": 15, "미국주식": 20, "인도주식": 10, "기타신흥국": 5,
    "물가연동채": 20, "실물자산": 10, "현금·단기채": 20,
}
_ASSET_COLORS = {
    "금·원자재": "#e0c060", "미국주식": "#42a5f5", "인도주식": "#22c55e",
    "기타신흥국": "#ab47bc", "물가연동채": "#26c6da", "실물자산": "#8d6e63",
    "현금·단기채": "#9e9e9e",
}
_ASSET_COUNTRY = {  # 자산군 → 연동 국가 (사이클 권고를 슬라이더 힌트로 표시)
    "미국주식": ["미국"],
    "인도주식": ["인도"],
    "기타신흥국": ["중국", "브라질", "멕시코", "러시아"],
}
_INFLATION_ASSETS = {"금·원자재", "물가연동채", "실물자산"}  # R1/R2 거시 신호 연동
_ACTION_BADGE = {"확대": ("🟢", "#22c55e"), "유지": ("🔵", "#42a5f5"),
                 "축소": ("🟠", "#ffa726"), "회피": ("🔴", "#ff4b4b")}
_ACTION_SEVERITY = {"확대": 0, "유지": 1, "축소": 2, "회피": 3}


def asset_hint(asset: str, triggered_ids: set[str]) -> tuple[str, str] | None:
    """자산군별 연동 힌트 (텍스트, 색상). 연동 신호 없으면 None."""
    nations = _ASSET_COUNTRY.get(asset)
    if nations:
        actions = [(n, config.COUNTRY_CYCLES[n]["action"]) for n in nations]
        worst = max(actions, key=lambda na: _ACTION_SEVERITY[na[1]])[1]
        text = " · ".join(f"{_ACTION_BADGE[a][0]} {n} {a}" for n, a in actions)
        return text, _ACTION_BADGE[worst][1]
    if asset in _INFLATION_ASSETS and triggered_ids & {"R1", "R2"}:
        return "🟢 거시 신호 발동 — 인플레헤지·실물 비중 확대 권고", "#22c55e"
    return None


for _asset, _default in DALIO_DEFAULTS.items():
    st.session_state.setdefault(f"alloc_{_asset}", _default)

if st.button("⚖️ Dalio 기본값 자동 설정"):
    for _asset, _default in DALIO_DEFAULTS.items():
        st.session_state[f"alloc_{_asset}"] = _default

_triggered_ids = {s.rule_id for s in signals if s.triggered}
slider_col, pie_col = st.columns([3, 2])

with slider_col:
    for _asset in DALIO_DEFAULTS:
        st.slider(_asset, min_value=0, max_value=40, step=1,
                  format="%d%%", key=f"alloc_{_asset}")
        hint = asset_hint(_asset, _triggered_ids)
        if hint:
            text, color = hint
            st.markdown(
                f"<div style='margin-top:-12px;margin-bottom:6px;font-size:0.78rem;"
                f"color:{color}'>{text}</div>",
                unsafe_allow_html=True,
            )

allocation = {a: st.session_state[f"alloc_{a}"] for a in DALIO_DEFAULTS}
total = sum(allocation.values())

with pie_col:
    if total == 100:
        st.success(f"✅ 합계 {total}%")
    elif total > 100:
        st.error(f"🚨 합계 {total}% — 100%를 {total - 100}%p 초과했습니다!")
    else:
        st.warning(f"합계 {total}% — {100 - total}%p 미배분 상태입니다.")

    nonzero = {a: v for a, v in allocation.items() if v > 0}
    if nonzero:
        pie = go.Figure(go.Pie(
            labels=list(nonzero.keys()),
            values=list(nonzero.values()),
            hole=0.45,
            marker=dict(colors=[_ASSET_COLORS[a] for a in nonzero]),
            textinfo="label+percent",
        ))
        pie.update_layout(height=380, template="plotly_dark", showlegend=False,
                          margin=dict(l=10, r=10, t=10, b=10),
                          annotations=[dict(text=f"{total}%", x=0.5, y=0.5,
                                            font_size=22, showarrow=False)])
        pie_col.plotly_chart(pie, width="stretch")
    else:
        st.info("배분된 자산이 없습니다. 슬라이더를 조정하거나 기본값 버튼을 누르세요.")

# ── 신호 이력 ────────────────────────────────────────────
st.subheader("신호 이력 (SQLite)")
history = database.load_history()
if history.empty:
    st.info("저장된 신호 이력이 없습니다.")
else:
    st.dataframe(history, width="stretch", hide_index=True)

st.caption("⚠️ 본 대시보드는 정보 제공용이며 투자 권유가 아닙니다. 데이터: Yahoo Finance, FRED.")
