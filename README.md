# 🌍 Dalio 신호 모니터

Ray Dalio 『변화하는 세계 질서』의 사이클 프레임(부채 · 패권 · 내부갈등)을 기반으로
거시경제 지표를 수집해 **IF-THEN 투자 신호**를 자동 판별하고 알림을 보내는 대시보드.

## 프로젝트 구조

```
dalio-signal-app/
├── app.py            # Streamlit 대시보드 (메인)
├── config.py         # 지표·임계값·환경변수 설정
├── data_fetcher.py   # yfinance + FRED 데이터 수집
├── signal_engine.py  # IF-THEN 신호 판별 엔진
├── database.py       # SQLite 신호 이력 저장
├── notifier.py       # 텔레그램 알림
├── scheduler.py      # 매일 09:00 자동 실행 (APScheduler)
├── setup_scheduler.bat  # Windows 작업 스케줄러 등록 (1회 실행)
├── run_daily.bat        # 작업 스케줄러가 매일 호출하는 실행 스크립트
├── requirements.txt
└── .env.example      # 환경변수 템플릿
```

## 설치 및 실행

```powershell
# 1) 가상환경 + 의존성
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2) (선택) 환경변수 — FRED 키 없이도 동작함 (공개 CSV 폴백)
copy .env.example .env   # 토큰 입력

# 3) 대시보드 실행
.venv\Scripts\streamlit run app.py

# 4) 스케줄러 (별도 터미널, 매일 09:00 자동 점검 + 텔레그램 알림)
.venv\Scripts\python scheduler.py          # 상주 실행
.venv\Scripts\python scheduler.py --once   # 즉시 1회 테스트
```

## Windows 작업 스케줄러 자동 등록 (권장)

터미널을 계속 띄워둘 필요 없이, Windows 작업 스케줄러가 **매일 오전 09:00 (PC 로컬 시간 = Asia/Seoul)** 에 자동으로 신호 점검을 실행하게 할 수 있습니다.

```powershell
# 1회만 실행하면 등록 완료 (탐색기에서 더블클릭해도 됨)
setup_scheduler.bat
```

- 등록되는 작업 이름: **DalioSignalMonitor** — 매일 09:00에 `run_daily.bat` 실행
- `run_daily.bat`은 `scheduler.py --once`를 호출해 데이터 수집 → 신호 판별 → SQLite 저장 → HIGH 신호 텔레그램 발송을 1회 수행
- 실행 로그는 **`logs/scheduler.log`** 에 누적 저장 (UTF-8)

```powershell
# 관리 명령
schtasks /Run /TN "DalioSignalMonitor"          # 지금 즉시 1회 실행 (테스트)
schtasks /Query /TN "DalioSignalMonitor"        # 상태·다음 실행 시각 확인
schtasks /Delete /TN "DalioSignalMonitor" /F    # 등록 해제
```

> 참고: 기본 등록은 "로그온 시에만 실행" 모드라서 09:00에 PC가 켜져 있고 로그인된 상태여야 합니다.
> 잠금 화면/미로그온 상태에서도 실행하려면 작업 스케줄러 GUI(taskschd.msc)에서 해당 작업의
> "사용자의 로그온 여부에 관계없이 실행" 옵션을 켜세요.

## 모니터링 지표 & IF-THEN 규칙

| 지표 | 소스 | 임계값 |
|---|---|---|
| 금 가격 | yfinance `GC=F` | 전월 대비 ±5% |
| 달러인덱스 | yfinance `DX-Y.NYB` | 100 이하 |
| 미 10Y 실질금리 | FRED `DFII10` | 0% 이하 |
| 미 부채/GDP | World Bank `GC.DOD.TOTL.GD.ZS` (연간, FRED 폴백) | 120% 이상 |

| 규칙 | IF | THEN |
|---|---|---|
| R1 (HIGH) | 금 +5%↑ AND 달러인덱스 < 100 | 인플레헤지 강화 |
| R2 (HIGH) | 실질금리 ≤ 0% | 금·실물 비중 확대 |
| R3 (WARNING) | 부채/GDP > 120% | 달러 장기 리스크 경고 |
| R4 (INFO) | 금 ±5% 급변동 | 포지션·헤지 점검 |

- HIGH 등급 신호 발동 시 텔레그램으로 자동 발송됩니다.
- 발동된 신호는 `signals.db`(SQLite)에 날짜별로 기록되며, 대시보드 하단에서 조회할 수 있습니다.

## Streamlit Cloud 배포

### 1) GitHub에 푸시

`.gitignore`가 `.env`, `.venv`, `*.db`, `secrets.toml` 등을 제외하므로 **시크릿은 저장소에 올라가지 않습니다.**

```powershell
git init
git add .
git commit -m "Dalio signal monitor"
git remote add origin https://github.com/<계정>/dalio-signal-app.git
git push -u origin main
```

### 2) Streamlit Cloud에서 앱 생성

[share.streamlit.io](https://share.streamlit.io) → **New app** → 저장소 선택 → Main file path: `app.py` → Deploy.

### 3) Secrets 설정 (API 키 관리)

앱 대시보드 → **Settings → Secrets** 에 TOML 형식으로 입력:

```toml
FRED_API_KEY = "발급받은_FRED_키"
TELEGRAM_BOT_TOKEN = "봇_토큰"
TELEGRAM_CHAT_ID = "챗_ID"
```

`config.py`가 **환경변수(.env) → st.secrets → 기본값** 순으로 키를 찾기 때문에:
- **로컬**: `.env` 파일 사용 (기존 방식 그대로)
- **Streamlit Cloud**: 위 Secrets 설정 자동 인식
- **둘 다 없어도** 앱은 동작합니다 — FRED는 공개 CSV로 폴백하고 텔레그램 알림만 생략됩니다.

로컬에서 secrets.toml 방식을 테스트하려면 `.streamlit/secrets.toml` 파일을 같은 TOML 형식으로 만들면 됩니다 (`.gitignore`에 이미 제외되어 있음).

### 배포 시 유의사항

- **SQLite 이력(`signals.db`)은 휘발성** — Streamlit Cloud 컨테이너는 재시작 시 파일이 초기화됩니다. 영구 이력이 필요하면 외부 DB(Supabase 등)로 교체가 필요합니다.
- **스케줄러는 클라우드에서 동작하지 않음** — `scheduler.py`/작업 스케줄러는 로컬 PC 용입니다. 클라우드 앱은 접속할 때마다 최신 데이터로 신호를 평가합니다 (1시간 캐시).
- `DX-Y.NYB` 등 yfinance 티커는 Streamlit Cloud 서버에서도 정상 수집됩니다.

> ⚠️ 본 앱은 정보 제공용이며 투자 권유가 아닙니다.
