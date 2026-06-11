"""스케줄러 — 매일 오전 9시 데이터 수집 → 신호 판별 → 저장 → 텔레그램 알림.

사용법:
  python scheduler.py          # 매일 09:00 자동 실행 (상주)
  python scheduler.py --once   # 즉시 1회 실행 (테스트용)
"""
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
import database
import notifier
from data_fetcher import get_all_data
from signal_engine import run_engine


def daily_job() -> None:
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 신호 점검 시작")
    data, errors = get_all_data()
    for name, err in errors.items():
        print(f"  [경고] {name} 수집 실패: {err}")
    if not data:
        print("  모든 데이터 수집 실패 — 점검 중단")
        return

    indicators, signals = run_engine(data)
    triggered = [s for s in signals if s.triggered]
    saved = database.save_triggered(signals)
    sent = notifier.notify_signals(signals, min_severity="HIGH")

    def fmt(key, pattern):
        v = indicators.get(key)
        return pattern.format(v) if v is not None else "없음"

    print(f"  지표: 금 {fmt('gold_price', '{:,.1f}')} ({fmt('gold_change_1m', '{:+.2f}%')}/1M), "
          f"DXY {fmt('dxy', '{:.2f}')}, 실질금리 {fmt('real_rate', '{:.2f}%')}, "
          f"부채/GDP {fmt('debt_gdp', '{:.1f}%')}, "
          f"금/구리 {fmt('gold_copper', '{:,.0f}')} ({fmt('gold_copper_change_1m', '{:+.2f}%')}/1M), "
          f"10Y-2Y {fmt('yield_spread', '{:+.2f}%p')}")
    print(f"  발동 신호 {len(triggered)}건 / 신규 저장 {saved}건 / 텔레그램 발송 {sent}건")
    for s in triggered:
        print(f"    - [{s.severity}] {s.name}: {s.detail}")


def main() -> None:
    if "--once" in sys.argv:
        daily_job()
        return

    sched = BlockingScheduler(timezone="Asia/Seoul")
    sched.add_job(daily_job, "cron", hour=config.SCHEDULE_HOUR, minute=config.SCHEDULE_MINUTE)
    print(f"스케줄러 시작 — 매일 {config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} (Asia/Seoul) 실행. Ctrl+C로 종료.")
    daily_job()  # 시작 시 1회 즉시 점검
    sched.start()


if __name__ == "__main__":
    main()
