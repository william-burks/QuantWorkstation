"""
APScheduler entry point for crypto data collection and risk management.

Jobs:
  - 00:00 UTC daily  — risk day reset (new starting balance, lift daily halts)
  - 00:15 UTC daily  — crypto bar collection (all configured symbols, all timeframes)
  - heartbeat        — periodic risk state update from broker (every 60s while running)

Run standalone:
    python3 -m execution.scheduler

The execution trigger (strategy → OMS → broker) is wired in when strategies exist (T006).
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from data.collectors.alpaca_crypto import collect_all as collect_all_crypto
from data.collectors.ibkr_futures import collect_all as collect_all_futures
from data.config import get_settings
from execution.brokers.alpaca import AlpacaBroker
from execution.risk import RiskEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)

_broker: AlpacaBroker | None = None
_risk: RiskEngine | None = None


def _get_broker() -> AlpacaBroker:
    global _broker
    if _broker is None:
        _broker = AlpacaBroker()
    return _broker


def _get_risk() -> RiskEngine:
    global _risk
    if _risk is None:
        s = get_settings()
        _risk = RiskEngine(eval_profit_target=s.eval_profit_target)
    return _risk


# --- Jobs ---


def job_risk_day_reset() -> None:
    """00:00 UTC — lock in new starting balance, lift daily halts."""
    try:
        acct = _get_broker().get_account()
        _get_risk().reset_day(acct.equity)
        log.info("Day reset complete: equity=%.2f", acct.equity)
    except Exception:
        log.exception("job_risk_day_reset failed")


_CRYPTO_TIMEFRAMES = ["1Min", "5Min", "15Min", "1Hour", "4Hour", "1Day", "1Week"]
_FUTURES_TIMEFRAMES = ["1min", "5min", "15min", "1H", "4H", "1D", "1W"]


def job_collect_crypto() -> None:
    """00:15 UTC — incremental bar collection for all configured crypto symbols."""
    try:
        s = get_settings()
        for tf in _CRYPTO_TIMEFRAMES:
            collect_all_crypto(tf)
        log.info(
            "Crypto collection complete: %d symbols × %d timeframes",
            len(s.crypto_symbols),
            len(_CRYPTO_TIMEFRAMES),
        )
    except Exception:
        log.exception("job_collect_crypto failed")


def job_collect_futures() -> None:
    """23:20 UTC — incremental bar collection after CME settlement (~17:15 CT)."""
    try:
        s = get_settings()
        for tf in _FUTURES_TIMEFRAMES:
            collect_all_futures(tf)
        log.info(
            "Futures collection complete: %d symbols × %d timeframes",
            len(s.futures_symbols),
            len(_FUTURES_TIMEFRAMES),
        )
    except Exception:
        log.exception("job_collect_futures failed")


def job_export_parquet() -> None:
    """Export all ArcticDB bars to parquet for the quant sandbox."""
    try:
        from data.parquet_export import export_all

        log.info("Exporting parquet snapshots")
        export_all()
    except Exception:
        log.exception("job_export_parquet failed")


def job_risk_heartbeat() -> None:
    """Every 60s — update risk state from live account equity."""
    try:
        risk = _get_risk()
        if risk.is_halted():
            return  # already halted, nothing to do until day reset
        acct = _get_broker().get_account()
        state = risk.update(acct.equity)
        if risk.is_halted():
            log.warning("HALT triggered by heartbeat: state=%s equity=%.2f", state, acct.equity)
    except Exception:
        log.exception("job_risk_heartbeat failed")


# --- Entry point ---


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        job_risk_day_reset,
        CronTrigger(hour=0, minute=0),
        id="risk_day_reset",
        name="Risk day reset",
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_collect_crypto,
        CronTrigger(hour=0, minute=15),
        id="collect_crypto",
        name="Crypto bar collection",
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_collect_futures,
        CronTrigger(hour=23, minute=20),
        id="collect_futures",
        name="Futures bar collection",
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_export_parquet,
        CronTrigger(hour=0, minute=30),
        id="export_parquet_post_crypto",
        name="Parquet export (post-crypto)",
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_export_parquet,
        CronTrigger(hour=23, minute=35),
        id="export_parquet_post_futures",
        name="Parquet export (post-futures)",
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_risk_heartbeat,
        IntervalTrigger(seconds=60),
        id="risk_heartbeat",
        name="Risk heartbeat",
    )

    return scheduler


def main() -> None:
    # Seed risk engine with current equity on startup
    try:
        acct = _get_broker().get_account()
        _get_risk().seed(acct.equity)
        log.info("Startup: equity=%.2f risk_state=%s", acct.equity, _get_risk().state.value)
    except Exception:
        log.exception("Failed to seed risk engine — check Alpaca credentials")
        sys.exit(1)

    scheduler = build_scheduler()

    def _shutdown(signum: int, frame: object) -> None:
        log.info("Shutdown signal received, stopping scheduler")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Scheduler started — jobs: %s", [j.name for j in scheduler.get_jobs()])
    scheduler.start()


if __name__ == "__main__":
    main()
