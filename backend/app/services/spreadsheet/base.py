from __future__ import annotations

from typing import Protocol

import pandas as pd


class SpreadsheetClient(Protocol):
    def read_dataframe(self) -> pd.DataFrame:  # pragma: no cover - protocol
        ...

    def write_dataframe(self, df: pd.DataFrame) -> None:  # pragma: no cover - protocol
        ...


