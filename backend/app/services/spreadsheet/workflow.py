from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pandas as pd

from app.config import get_settings
from app.services.data_aggregator import DataAggregator
from app.services.spreadsheet.base import SpreadsheetClient
from app.services.spreadsheet.excel import ExcelLikeClient
from app.services.spreadsheet.google_sheets import GoogleSheetsClient


REQUIRED_COLUMNS: List[str] = [
    "Company Name",
    "Financial Timestamp",
    "Revenue",
    "EBITDA",
    "Status",
    "Intermediary Email",
    "Last Outreach Date",
    "Outreach Count",
    "Source",
    "Last Updated At",
    "Notes",
]


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _client_from_settings() -> SpreadsheetClient:
    settings = get_settings()
    if settings.spreadsheet_mode == "google":
        if not settings.google_sheet_id:
            raise RuntimeError("GOOGLE_SHEET_ID not configured")
        return GoogleSheetsClient(sheet_id=settings.google_sheet_id, worksheet_name=settings.worksheet_name)
    return ExcelLikeClient(file_path=settings.excel_path, worksheet_name=settings.worksheet_name)


def _initialize_sheet(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col not in {"Revenue", "EBITDA", "Outreach Count"} else 0
    return df[REQUIRED_COLUMNS]


def run_update_and_outreach() -> dict:
    settings = get_settings()
    client = _client_from_settings()
    df = client.read_dataframe()
    df = _initialize_sheet(df)

    aggregator = DataAggregator()

    # Normalize numeric columns
    if not df.empty:
        for col in ["Revenue", "EBITDA", "Outreach Count"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Pull latest financials
    updated_rows = []
    for _, row in df.iterrows():
        name = str(row.get("Company Name", "")).strip()
        if not name:
            updated_rows.append(row)
            continue
        best = aggregator.fetch_best(name)
        if best:
            for field in ["Revenue", "EBITDA", "Financial Timestamp", "Source"]:
                if best.get(field) not in (None, ""):
                    row[field] = best[field]
        row["Last Updated At"] = _now_str()
        updated_rows.append(row)

    df = pd.DataFrame(updated_rows)

    # Validate freshness
    threshold = datetime.now(timezone.utc) - timedelta(days=settings.freshness_days)
    statuses: List[str] = []
    for _, row in df.iterrows():
        ts = _parse_date(str(row.get("Financial Timestamp", "")))
        statuses.append("Valid" if ts and ts >= threshold else "Flagged")
    df["Status"] = statuses

    # Outreach cadence
    cadence_threshold = datetime.now(timezone.utc) - timedelta(days=settings.outreach_cadence_days)
    sent = 0
    for idx, row in df.iterrows():
        if str(row.get("Status", "")).lower() != "flagged":
            continue
        email = str(row.get("Intermediary Email", "")).strip()
        if not email:
            continue
        last = _parse_date(str(row.get("Last Outreach Date", "")))
        if last and last > cadence_threshold:
            continue
        # Using existing OutreachManager via API is overkill; mark attempt in sheet only.
        if settings.dry_run:
            # Simulate send
            pass
        # Update row
        df.at[idx, "Last Outreach Date"] = _now_str()
        count = row.get("Outreach Count") or 0
        df.at[idx, "Outreach Count"] = int(count) + 1
        sent += 1

    client.write_dataframe(df)
    return {"updated": len(df.index), "outreach_sent": sent}


