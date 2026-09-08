"""
Supermarket Operations Agent — Single Command All-in-One Runner
Runs PostgreSQL check/start, database migrations, FastAPI server,
and Telegram bot long poller concurrently with graceful Ctrl+C shutdown.
"""
import asyncio
import logging
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SupermarketRunner")

ROOT_DIR = Path(__file__).resolve().parent
PG_BIN = ROOT_DIR / "pgsql" / "bin" / "pg_ctl.exe"
PG_DATA = ROOT_DIR / "pgdata"


def check_and_start_postgres():
    """Ensure PostgreSQL is running locally."""
    if PG_BIN.exists() and PG_DATA.exists():
        logger.info("🐘 Checking PostgreSQL database status...")
        try:
            status_res = subprocess.run(
                [str(PG_BIN), "status", "-D", str(PG_DATA)],
                capture_output=True,
                text=True,
            )
            if "server is running" not in status_res.stdout.lower():
                pid_file = PG_DATA / "postmaster.pid"
                if pid_file.exists():
                    try:
                        pid_file.unlink()
                    except Exception:
                        pass
                logger.info("🚀 Starting PostgreSQL server...")
                subprocess.run(
                    [str(PG_BIN), "start", "-D", str(PG_DATA), "-w"],
                    check=False,
                )
            else:
                logger.info("✅ PostgreSQL is already running.")
        except Exception as e:
            logger.warning(f"Note: Could not check pg_ctl: {e}")
    else:
        logger.info("PostgreSQL binary folder not found locally, assuming system postgres service is active.")


def run_migrations_and_seed():
    """Run alembic migrations and seed base products/customers."""
    logger.info("📦 Verifying database schema & migrations...")
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=str(ROOT_DIR), check=True)
    except Exception as e:
        logger.warning(f"Migration note: {e}")

    try:
        subprocess.run([sys.executable, "scripts/seed_data.py"], cwd=str(ROOT_DIR), check=False)
    except Exception as e:
        logger.warning(f"Seed note: {e}")


async def run_uvicorn():
    """Run FastAPI Uvicorn web server."""
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    logger.info("🌐 Launching Web Operations Dashboard on http://localhost:8000 ...")
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(ROOT_DIR))
    return proc


async def run_telegram_poller():
    """Run Telegram bot poller."""
    cmd = [sys.executable, "-m", "scripts.poll_telegram"]
    logger.info("🤖 Launching Telegram Bot Poller (@mykiranastore_bot) ...")
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(ROOT_DIR))
    return proc


async def main():
    print("""
========================================================================
   🏪  SUPERMARKETBOT — AI-POWERED STORE OPERATIONS AGENT  🏪
========================================================================
   • Web Dashboard : http://localhost:8000
   • Telegram Bot  : @mykiranastore_bot
   • Database      : PostgreSQL 16
========================================================================
    """)

    # 1. Start Postgres & migrate
    check_and_start_postgres()
    run_migrations_and_seed()

    # 2. Launch processes concurrently
    uvicorn_proc = await run_uvicorn()
    await asyncio.sleep(1.5)

    # 3. Open browser
    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass

    telegram_proc = await run_telegram_poller()

    logger.info("✅ All services are LIVE! Press Ctrl+C to stop.\n")

    try:
        await asyncio.gather(
            uvicorn_proc.wait(),
            telegram_proc.wait(),
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("\n🛑 Shutting down SupermarketBot services...")
        try:
            uvicorn_proc.terminate()
        except Exception:
            pass
        try:
            telegram_proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
