"""
app.py — Second Brain entry point
==================================
Run with:  streamlit run app.py

Responsibilities:
  1. Ensure ./data/ directories exist
  2. Initialise SQLite schema
  3. Start APScheduler background jobs:
       • decay_job()      — every DECAY_JOB_INTERVAL_MINUTES (default 60 min)
       • reminder_sweep() — every REMINDER_SWEEP_INTERVAL_MINUTES (default 5 min)
  4. Hand off to the Streamlit frontend (frontend/app.py)
"""

import sys
import os
import logging

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ── Ensure data directories exist ────────────────────────────────────────────
os.makedirs("./data/chroma", exist_ok=True)
os.makedirs(os.path.dirname("./data/second_brain.db"), exist_ok=True)

# ── DB init ───────────────────────────────────────────────────────────────────
from db.database import init_db
init_db()

# ── APScheduler ───────────────────────────────────────────────────────────────
from apscheduler.schedulers.background import BackgroundScheduler
from backend.config import config
from core.decay_engine import decay_job
from core.reminder_engine import reminder_sweep

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(daemon=True)

# Only start once per process (Streamlit reruns the script on every interaction)
if not _scheduler.running:
    _scheduler.add_job(
        decay_job,
        trigger="interval",
        minutes=config.DECAY_JOB_INTERVAL_MINUTES,
        id="decay_job",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.add_job(
        reminder_sweep,
        trigger="interval",
        minutes=config.REMINDER_SWEEP_INTERVAL_MINUTES,
        id="reminder_sweep",
        replace_existing=True,
        misfire_grace_time=60,
    )
    try:
        _scheduler.start()
        logger.info(
            "APScheduler started — decay every %dm, sweep every %dm",
            config.DECAY_JOB_INTERVAL_MINUTES,
            config.REMINDER_SWEEP_INTERVAL_MINUTES,
        )
    except Exception as e:
        logger.warning("APScheduler could not start: %s", e)

# ── Delegate to Streamlit frontend ────────────────────────────────────────────
# Streamlit re-executes this file on every interaction; guard the scheduler
# with a session-state flag so it only starts once per server process.
import streamlit as st

if "_scheduler_started" not in st.session_state:
    st.session_state["_scheduler_started"] = True   # mark before potential error

from frontend.app import main   # noqa: E402
main()
