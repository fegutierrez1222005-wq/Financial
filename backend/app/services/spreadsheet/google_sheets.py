from __future__ import annotations

import json
from os import getenv
from pathlib import Path

import gspread  # type: ignore
import pandas as pd
from google.oauth2.service_account import Credentials  # type: ignore

from .base import SpreadsheetClient


class GoogleSheetsClient(SpreadsheetClient):
    def __init__(self, sheet_id: str, worksheet_name: str):
        self.sheet_id = sheet_id
        self.worksheet_name = worksheet_name
        self.client = self._authorize()
        self.sheet = self.client.open_by_key(self.sheet_id)
        try:
            self.ws = self.sheet.worksheet(self.worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            self.ws = self.sheet.add_worksheet(title=self.worksheet_name, rows=1000, cols=20)

    def _authorize(self):
        info = _load_service_account_info()
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(credentials)

    def read_dataframe(self) -> pd.DataFrame:
        values = self.ws.get_all_values()
        if not values:
            return pd.DataFrame()
        headers = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=headers)

    def write_dataframe(self, df: pd.DataFrame) -> None:
        headers = [list(df.columns)]
        values = df.fillna("").astype(str).values.tolist()
        self.ws.clear()
        self.ws.update("A1", headers + values)


def _load_service_account_info() -> dict:
    json_content = getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    if json_content:
        return json.loads(json_content)
    json_path = getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_path:
        p = Path(json_path)
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError(
        "Google Sheets credentials not found. Set GOOGLE_SERVICE_ACCOUNT_INFO or GOOGLE_SERVICE_ACCOUNT_JSON"
    )


