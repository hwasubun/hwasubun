"""텔레그램 알림 — 고위험(HIGH) 신호 자동 발송."""
import asyncio

import config
from signal_engine import Signal

_SEVERITY_EMOJI = {"HIGH": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}


def _configured() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


async def _send_async(text: str) -> None:
    from telegram import Bot

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")


def send_message(text: str) -> bool:
    """단순 텍스트 발송. 토큰 미설정 시 False."""
    if not _configured():
        print("[notifier] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 알림 생략")
        return False
    asyncio.run(_send_async(text))
    return True


def format_signal(s: Signal) -> str:
    emoji = _SEVERITY_EMOJI.get(s.severity, "")
    return (
        f"{emoji} *[{s.severity}] {s.name}*\n"
        f"IF: {s.condition}\n"
        f"THEN: {s.action}\n"
        f"현재: {s.detail}\n"
        f"시각: {s.timestamp}"
    )


def notify_signals(signals: list[Signal], min_severity: str = "HIGH") -> int:
    """발동된 신호 중 min_severity 이상만 발송. 발송 건수 반환."""
    order = {"INFO": 0, "WARNING": 1, "HIGH": 2}
    targets = [
        s for s in signals
        if s.triggered and order.get(s.severity, 0) >= order.get(min_severity, 2)
    ]
    if not targets:
        return 0
    body = "🌍 *Dalio 신호 모니터*\n\n" + "\n\n".join(format_signal(s) for s in targets)
    return len(targets) if send_message(body) else 0
