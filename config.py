"""앱 전역 설정 — 모니터링 지표, 임계값, 환경변수."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # .env가 없으면 조용히 건너뜀


def _get_secret(name: str, default: str = "") -> str:
    """우선순위: 환경변수(.env 포함) → Streamlit secrets → 기본값.

    로컬은 .env, Streamlit Cloud는 앱 설정의 Secrets(st.secrets)로 키를 관리한다.
    secrets.toml이 없거나 streamlit 외부(scheduler.py 등)에서 호출돼도 안전하다.
    """
    value = os.getenv(name, "")
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, default))
    except Exception:  # noqa: BLE001 — secrets 미설정/비-streamlit 환경
        return default


# ── 시크릿 (모두 선택 사항 — 없어도 앱은 동작) ──────────────
FRED_API_KEY = _get_secret("FRED_API_KEY")            # 없으면 FRED 공개 CSV로 폴백
TELEGRAM_BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get_secret("TELEGRAM_CHAT_ID")

DB_PATH = BASE_DIR / "signals.db"

# ── 모니터링 지표 ─────────────────────────────────────────
# yfinance 티커 (대체 티커 포함 — 첫 번째가 실패하면 다음 시도)
GOLD_TICKERS = ["GC=F", "GLD"]
DXY_TICKERS = ["DX-Y.NYB", "DX=F"]

# FRED 시리즈
FRED_REAL_RATE = "DFII10"        # 미국 10년 실질금리 (일간)
FRED_DEBT_GDP = "GFDEGDQ188S"    # 미국 연방부채/GDP (분기)

# ── 임계값 ───────────────────────────────────────────────
GOLD_CHANGE_THRESHOLD = 5.0      # 전월 대비 변동률 (%)
DXY_THRESHOLD = 100.0            # 달러인덱스 약세 기준
REAL_RATE_THRESHOLD = 0.0        # 실질금리 (%)
DEBT_GDP_THRESHOLD = 120.0       # 부채/GDP (%)

# ── 스케줄러 ─────────────────────────────────────────────
SCHEDULE_HOUR = 9                # 매일 오전 9시
SCHEDULE_MINUTE = 0

# ── 국가별 빅사이클 (정성 평가, Dalio 『변화하는 세계 질서』 기반 참고용) ──
# score: 사이클 포지션 0(상승초기·양호) ~ 100(쇠퇴 말기·위험)
# stage: 사이클 단계 / action: Dalio식 권고 배지 (확대·유지·축소·회피)
CYCLE_STAGES = {  # 단계 → 표시 색상 (선언 순서 = 범례 순서)
    "상승초기": "#22c55e",
    "횡보/중립": "#9e9e9e",
    "조정/경고": "#ffa726",
    "위험/쇠퇴": "#ff4b4b",
}
ACTION_COLORS = {"확대": "#22c55e", "유지": "#42a5f5", "축소": "#ffa726", "회피": "#ff4b4b"}

COUNTRY_CYCLES = {
    # ── 상승초기 ──
    "인도": {
        "score": 25, "stage": "상승초기", "action": "확대",
        "summary": "고성장·낮은 부채·생산성 개혁 — 빅사이클 상승 초입",
        "details": {"부채 사이클": 35, "내부 갈등": 45, "패권 쇠퇴 압력": 15},
        "risks": [
            "IF 유가 100달러 돌파 → THEN 경상수지·인플레 압박 — 단기 변동성 유의",
            "IF 증시 고평가 조정 → THEN 단기 급락 가능 — 분할 접근",
            "IF 개혁 모멘텀 둔화 → THEN 성장 프리미엄 축소 — 정책 모니터링",
        ],
    },
    "호주": {
        "score": 35, "stage": "상승초기", "action": "확대",
        "summary": "원자재 기반 견조·낮은 정부부채 — 완만한 상승 국면",
        "details": {"부채 사이클": 45, "내부 갈등": 30, "패권 쇠퇴 압력": 30},
        "risks": [
            "IF 중국 원자재 수요 급감 → THEN 수출·교역조건 악화 — 자원 섹터 점검",
            "IF 금리 재상승 → THEN 높은 가계부채발 부동산 조정 — 은행 노출 유의",
            "IF 원자재 사이클 지연 → THEN 호주달러 약세 — 환헤지 고려",
        ],
    },
    # ── 횡보/중립 ──
    "캐나다": {
        "score": 48, "stage": "횡보/중립", "action": "유지",
        "summary": "자원·제도 견조 vs 높은 가계부채 — 중립 구간",
        "details": {"부채 사이클": 60, "내부 갈등": 35, "패권 쇠퇴 압력": 40},
        "risks": [
            "IF 금리 상승 재개 → THEN 가계부채발 부동산 경착륙 — 은행주 유의",
            "IF 유가 급락 → THEN 에너지 수출 타격 — 캐나다달러 약세",
            "IF 미국 경기 둔화 → THEN 동조 침체 — 경기민감 비중 점검",
        ],
    },
    "독일": {
        "score": 50, "stage": "횡보/중립", "action": "유지",
        "summary": "에너지 비용·중국 수요 둔화로 제조업 정체 — 횡보 국면",
        "details": {"부채 사이클": 55, "내부 갈등": 50, "패권 쇠퇴 압력": 60},
        "risks": [
            "IF 에너지 가격 재급등 → THEN 제조업 경쟁력 추가 훼손 — 산업주 신중",
            "IF 중국 수요 둔화 지속 → THEN 수출 의존 모델 타격 — 비중 확대 자제",
            "IF EU 재정준칙 갈등 심화 → THEN 유로존 불안 재점화 — 유로 노출 점검",
        ],
    },
    "스페인": {
        "score": 52, "stage": "횡보/중립", "action": "유지",
        "summary": "관광·내수 회복 vs 높은 공공부채 — 중립 구간",
        "details": {"부채 사이클": 60, "내부 갈등": 55, "패권 쇠퇴 압력": 55},
        "risks": [
            "IF 실업률 재상승 → THEN 내수 회복 둔화 — 확대 자제",
            "IF 유로존 금리 재상승 → THEN 공공부채 부담 증가 — 국채 점검",
            "IF 관광 경기 변동 확대 → THEN 성장 변동성 — 섹터 분산",
        ],
    },
    # ── 조정/경고 ──
    "멕시코": {
        "score": 58, "stage": "조정/경고", "action": "유지",
        "summary": "니어쇼어링 수혜 vs 제도·치안 리스크 — 경계 구간",
        "details": {"부채 사이클": 50, "내부 갈등": 60, "패권 쇠퇴 압력": 35},
        "risks": [
            "IF 미국 관세·통상정책 변화 → THEN 수출 타격 — 페소 변동성 유의",
            "IF 치안·제도 리스크 악화 → THEN 투자 매력 저하 — 신중 접근",
            "IF 미국 경기 둔화 → THEN 동조 둔화 — 경기민감 비중 점검",
        ],
    },
    "브라질": {
        "score": 60, "stage": "조정/경고", "action": "유지",
        "summary": "원자재 의존·재정 불확실성 — 변동성 큰 조정 국면",
        "details": {"부채 사이클": 60, "내부 갈등": 60, "패권 쇠퇴 압력": 40},
        "risks": [
            "IF 재정준칙 신뢰 훼손 → THEN 헤알화 급락 — 환헤지 필수",
            "IF 원자재 가격 하락 → THEN 수출·재정 동반 악화 — 비중 축소 검토",
            "IF 정치 불확실성 재점화 → THEN 리스크 프리미엄 급등 — 신중 접근",
        ],
    },
    "한국": {
        "score": 62, "stage": "조정/경고", "action": "축소",
        "summary": "가계부채·수출 편중·인구구조 — 구조적 조정 압력",
        "details": {"부채 사이클": 65, "내부 갈등": 55, "패권 쇠퇴 압력": 45},
        "risks": [
            "IF 가계부채/GDP 105% 상회 → THEN 소비 위축 장기화 — 내수 비중 축소",
            "IF 반도체 수출 증가율 마이너스 전환 → THEN 원화 약세·성장 둔화 — 환노출 점검",
            "IF 미·중 공급망 디커플링 심화 → THEN 수출 구조 타격 — 섹터 분산",
        ],
    },
    "프랑스": {
        "score": 65, "stage": "조정/경고", "action": "축소",
        "summary": "재정적자 확대·정치 교착 — 신용 경고 구간",
        "details": {"부채 사이클": 70, "내부 갈등": 65, "패권 쇠퇴 압력": 55},
        "risks": [
            "IF 재정적자 6% 상회 지속 → THEN 국채 스프레드 확대 — 프랑스채 축소",
            "IF 의회 분열·정치 교착 장기화 → THEN 신용등급 강등 — 신중 접근",
            "IF 연금 등 사회 갈등 재점화 → THEN 내부 갈등 심화 — 노출 축소",
        ],
    },
    "중국": {
        "score": 68, "stage": "조정/경고", "action": "축소",
        "summary": "부동산 디레버리징·지방정부 부채 — 부채 사이클 조정 국면",
        "details": {"부채 사이클": 70, "내부 갈등": 55, "패권 쇠퇴 압력": 40},
        "risks": [
            "IF 부동산 가격 추가 10% 하락 → THEN 지방부채 위기 전이 — 위안화 자산 축소",
            "IF 위안/달러 7.5 돌파 → THEN 자본유출 가속 — 환헤지 필수",
            "IF 미·중 갈등(대만 등) 격화 → THEN 지정학 프리미엄 급등 — 노출 관리",
        ],
    },
    "미국": {
        "score": 72, "stage": "조정/경고", "action": "축소",
        "summary": "부채/GDP 120%+ · 정치 양극화 — 후기 사이클 경고 구간",
        "details": {"부채 사이클": 80, "내부 갈등": 75, "패권 쇠퇴 압력": 60},
        "risks": [
            "IF 부채/GDP 130% 돌파 → THEN 달러 기축 신뢰 저하 가속 — 금·비달러 분산",
            "IF 10년 국채금리 5% 상회 → THEN 이자비용 악순환 경계 — 장기채 축소",
            "IF 선거 전후 내부갈등 격화 → THEN 정책 불확실성 — 변동성 헤지 강화",
        ],
    },
    # ── 위험/쇠퇴 ──
    "영국": {
        "score": 75, "stage": "위험/쇠퇴", "action": "축소",
        "summary": "생산성 정체·재정 취약 — 패권 쇠퇴 후기",
        "details": {"부채 사이클": 70, "내부 갈등": 65, "패권 쇠퇴 압력": 75},
        "risks": [
            "IF 길트 금리 재급등 → THEN 재정 신뢰 위기 재연 — 영국 장기채 회피",
            "IF 파운드 약세 + 인플레 재반등 → THEN 스태그플레이션 — 실물자산 선호",
            "IF 생산성 정체 지속 → THEN 장기 쇠퇴 고착 — 비중 축소 유지",
        ],
    },
    "일본": {
        "score": 78, "stage": "위험/쇠퇴", "action": "축소",
        "summary": "부채/GDP 260% · 고령화 — 부채 사이클 말기",
        "details": {"부채 사이클": 85, "내부 갈등": 30, "패권 쇠퇴 압력": 65},
        "risks": [
            "IF 금리 1%p 추가 상승 → THEN 국채 이자부담 한계 — 엔화 자산 신중",
            "IF 엔/달러 170 돌파 → THEN 수입물가 충격 — 환헤지 필수",
            "IF BOJ 국채 매입 축소 가속 → THEN 장기금리 급등 — 일본 장기채 회피",
        ],
    },
    "이탈리아": {
        "score": 80, "stage": "위험/쇠퇴", "action": "회피",
        "summary": "고부채·저성장 고착 — 쇠퇴 국면",
        "details": {"부채 사이클": 85, "내부 갈등": 60, "패권 쇠퇴 압력": 70},
        "risks": [
            "IF ECB 지원 축소 → THEN 부채/GDP 140%+에서 스프레드 급등 — 이탈리아채 회피",
            "IF 성장률 0%대 고착 → THEN 부채 동학 악화 — 회피 유지",
            "IF EU 재정 갈등 격화 → THEN 유로존 리스크 진앙지화 — 노출 최소화",
        ],
    },
    "러시아": {
        "score": 88, "stage": "위험/쇠퇴", "action": "회피",
        "summary": "제재 고립·전시경제 — 투자 접근 자체가 제한",
        "details": {"부채 사이클": 75, "내부 갈등": 70, "패권 쇠퇴 압력": 85},
        "risks": [
            "IF 제재 장기화 → THEN 자본시장 접근 불가 지속 — 투자 회피",
            "IF 에너지 수출 단가 하락 → THEN 재정 악화·루블 불안 — 회피",
            "IF 지정학 갈등 확전 → THEN 자산 동결 리스크 — 회피",
        ],
    },
}
