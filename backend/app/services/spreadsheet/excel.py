from __future__ import annotations

from pathlib import Path
import pandas as pd

from .base import SpreadsheetClient


class ExcelLikeClient(SpreadsheetClient):
    def __init__(self, file_path: str, worksheet_name: str):
        self.file_path = Path(file_path)
        self.worksheet_name = worksheet_name
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def read_dataframe(self) -> pd.DataFrame:
        if not self.file_path.exists():
            return pd.DataFrame()
        if self.file_path.suffix.lower() == ".csv":
            return pd.read_csv(self.file_path)
        # Excel fallback
        try:
            df = pd.read_excel(self.file_path, sheet_name=self.worksheet_name)
        except ValueError:
            df = pd.read_excel(self.file_path)
        return df

    def write_dataframe(self, df: pd.DataFrame) -> None:
        if self.file_path.suffix.lower() == ".csv":
            df.to_csv(self.file_path, index=False)
            return
        with pd.ExcelWriter(self.file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=self.worksheet_name, index=False)


