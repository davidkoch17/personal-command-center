@echo off
REM Phase B net-worth daily snapshot — schedule this in Windows Task Scheduler to
REM run ~18:00 daily. Prices held tickers (yfinance -> EUR), writes one row per
REM position to data/positions_daily.csv and one net-worth row to
REM data/networth_daily.csv. Idempotent: re-running on the same day overwrites
REM that day's rows. One-time history seed: python -m modules.finance.backfill
cd /d "%~dp0"
python -m modules.finance.daily_snapshot
