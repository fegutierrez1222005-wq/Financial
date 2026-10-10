"""DEMO DATA — ACME Technologies, Inc. and peers.

Everything here is **synthetic and fictional**. It exists so the platform is usable
end-to-end without external credentials.

Design rules that make the demo honest and useful:

1. `is_demo=True` / `source="demo"` on every record; the API and UI badge it ``DEMO``.
2. Filing prose is *generated from the same numbers* as the statement tables, so citation
   verification and numeric recomputation work against internally consistent data rather
   than being trivially satisfied.
3. Every document has a realistic filing timestamp, so the historical information lock is
   demonstrable (an FY2023 10-K filed 2024-02-14 is invisible at a 2024-01-01 cutoff).
4. Prices come from a seeded random walk — reproducible for any (symbol, date) pair and
   never presented as real market history.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np

DEMO_SOURCE = "demo"
DEMO_DISCLAIMER = (
    "DEMO DATA — ACME Technologies, Inc. is a fictional issuer. All figures are synthetic "
    "and must not be used for investment decisions."
)

MILLION = 1_000_000.0


def _utc(year: int, month: int, day: int, hour: int = 21) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- profiles

COMPANY_PROFILES: dict[str, dict[str, Any]] = {
    "ACME": {
        "name": "ACME Technologies, Inc.",
        "sector": "Information Technology",
        "industry": "Industrial Automation Software & Hardware",
        "cik": "0009999991",
        "exchange": "DEMO-EX",
        "employees": 11_400,
        "description": (
            "ACME Technologies, Inc. (fictional demo issuer) designs industrial automation "
            "controllers and subscription software for discrete manufacturing. Revenue is split "
            "between hardware systems and a recurring software platform."
        ),
        "shares_outstanding": 128.4,  # millions
    },
    "BLTA": {
        "name": "Beltane Semiconductor Corp.",
        "sector": "Information Technology",
        "industry": "Semiconductors",
        "employees": 6_200,
        "description": "Fictional demo issuer: analog semiconductors for factory automation.",
        "shares_outstanding": 92.5,
    },
    "CRUX": {
        "name": "Crux Software Holdings",
        "sector": "Information Technology",
        "industry": "Application Software",
        "employees": 2_800,
        "description": "Fictional demo issuer: MES/quality software for regulated manufacturing.",
        "shares_outstanding": 61.3,
    },
    "DELP": {
        "name": "Delphi Precision Works",
        "sector": "Industrials",
        "industry": "Machinery",
        "employees": 14_900,
        "description": "Fictional demo issuer: precision machining and tooling.",
        "shares_outstanding": 154.0,
    },
    "EVRG": {
        "name": "Evergreen Logistics Group",
        "sector": "Industrials",
        "industry": "Freight & Logistics",
        "employees": 33_500,
        "description": "Fictional demo issuer: regional freight and warehousing.",
        "shares_outstanding": 210.7,
    },
    "FALC": {
        "name": "Falcon Materials PLC",
        "sector": "Materials",
        "industry": "Specialty Chemicals",
        "employees": 8_100,
        "description": "Fictional demo issuer: specialty coatings and adhesives.",
        "shares_outstanding": 118.2,
    },
    "GLDN": {
        "name": "Golden Harbor Bancorp",
        "sector": "Financials",
        "industry": "Regional Banks",
        "employees": 4_400,
        "description": "Fictional demo issuer: commercial bank serving industrial clients.",
        "shares_outstanding": 88.9,
    },
    "HELX": {
        "name": "Helix Biosystems",
        "sector": "Health Care",
        "industry": "Life Science Tools",
        "employees": 3_150,
        "description": "Fictional demo issuer: laboratory automation instruments.",
        "shares_outstanding": 47.6,
    },
}

DEMO_UNIVERSE: tuple[str, ...] = tuple(COMPANY_PROFILES)

#: symbol → (start_price, annual_drift, annual_vol, seed)
_PRICE_PARAMS: dict[str, tuple[float, float, float, int]] = {
    "ACME": (58.0, 0.17, 0.31, 11),
    "BLTA": (34.5, 0.21, 0.42, 22),
    "CRUX": (71.0, 0.13, 0.36, 33),
    "DELP": (22.4, 0.06, 0.27, 44),
    "EVRG": (41.8, 0.04, 0.24, 55),
    "FALC": (65.2, 0.08, 0.29, 66),
    "GLDN": (28.9, 0.05, 0.22, 77),
    "HELX": (96.4, 0.11, 0.38, 88),
}


# ------------------------------------------------------------------- ACME statements
# USD millions. Internal consistency is asserted by tests/unit/test_core_primitives.py.

ACME_ANNUAL_INCOME: dict[str, dict[str, float]] = {
    "FY2021": {
        "revenue": 3402.1, "cost_of_revenue": 2187.4, "gross_profit": 1214.7,
        "operating_expenses": 900.3, "operating_income": 314.4, "interest_expense": 41.2,
        "other_income": 5.1, "pretax_income": 278.3, "income_tax_expense": 58.4,
        "net_income": 219.9, "diluted_shares": 131.8, "diluted_eps": 1.67,
    },
    "FY2022": {
        "revenue": 4084.7, "cost_of_revenue": 2574.8, "gross_profit": 1509.9,
        "operating_expenses": 1081.8, "operating_income": 428.1, "interest_expense": 45.7,
        "other_income": 6.3, "pretax_income": 388.7, "income_tax_expense": 86.1,
        "net_income": 302.6, "diluted_shares": 130.4, "diluted_eps": 2.32,
    },
    "FY2023": {
        "revenue": 4820.0, "cost_of_revenue": 2989.0, "gross_profit": 1831.0,
        "operating_expenses": 1268.0, "operating_income": 563.0, "interest_expense": 49.6,
        "other_income": 8.4, "pretax_income": 521.8, "income_tax_expense": 109.6,
        "net_income": 412.2, "diluted_shares": 129.0, "diluted_eps": 3.20,
    },
}

ACME_QUARTERLY_INCOME: dict[str, dict[str, float]] = {
    "Q1 2022": {
        "revenue": 940.2, "cost_of_revenue": 597.0, "gross_profit": 343.2,
        "operating_expenses": 258.9, "operating_income": 84.3, "interest_expense": 11.2,
        "other_income": 1.5, "pretax_income": 74.6, "income_tax_expense": 16.5,
        "net_income": 58.1, "diluted_shares": 131.0, "diluted_eps": 0.44,
    },
    "Q2 2022": {
        "revenue": 1002.5, "cost_of_revenue": 634.6, "gross_profit": 367.9,
        "operating_expenses": 265.1, "operating_income": 102.8, "interest_expense": 11.4,
        "other_income": 1.5, "pretax_income": 92.9, "income_tax_expense": 20.6,
        "net_income": 72.3, "diluted_shares": 130.6, "diluted_eps": 0.55,
    },
    "Q3 2022": {
        "revenue": 1050.0, "cost_of_revenue": 656.3, "gross_profit": 393.7,
        "operating_expenses": 269.1, "operating_income": 124.6, "interest_expense": 11.5,
        "other_income": 1.6, "pretax_income": 114.7, "income_tax_expense": 25.4,
        "net_income": 89.3, "diluted_shares": 130.2, "diluted_eps": 0.69,
    },
    "Q4 2022": {
        "revenue": 1092.0, "cost_of_revenue": 686.9, "gross_profit": 405.1,
        "operating_expenses": 288.7, "operating_income": 116.4, "interest_expense": 11.6,
        "other_income": 1.7, "pretax_income": 106.5, "income_tax_expense": 23.6,
        "net_income": 82.9, "diluted_shares": 130.0, "diluted_eps": 0.64,
    },
    "Q1 2023": {
        "revenue": 1120.0, "cost_of_revenue": 700.0, "gross_profit": 420.0,
        "operating_expenses": 310.0, "operating_income": 110.0, "interest_expense": 12.1,
        "other_income": 1.8, "pretax_income": 99.7, "income_tax_expense": 20.9,
        "net_income": 78.8, "diluted_shares": 129.6, "diluted_eps": 0.61,
    },
    "Q2 2023": {
        "revenue": 1180.0, "cost_of_revenue": 733.4, "gross_profit": 446.6,
        "operating_expenses": 316.0, "operating_income": 130.6, "interest_expense": 12.4,
        "other_income": 2.2, "pretax_income": 120.4, "income_tax_expense": 25.3,
        "net_income": 95.1, "diluted_shares": 129.3, "diluted_eps": 0.74,
    },
    "Q3 2023": {
        "revenue": 1240.0, "cost_of_revenue": 768.4, "gross_profit": 471.6,
        "operating_expenses": 307.9, "operating_income": 163.7, "interest_expense": 12.7,
        "other_income": 2.3, "pretax_income": 153.3, "income_tax_expense": 32.2,
        "net_income": 121.1, "diluted_shares": 129.0, "diluted_eps": 0.94,
    },
    "Q4 2023": {
        "revenue": 1280.0, "cost_of_revenue": 787.2, "gross_profit": 492.8,
        "operating_expenses": 334.1, "operating_income": 158.7, "interest_expense": 12.4,
        "other_income": 2.1, "pretax_income": 148.4, "income_tax_expense": 31.2,
        "net_income": 117.2, "diluted_shares": 128.4, "diluted_eps": 0.91,
    },
}

ACME_ANNUAL_BALANCE: dict[str, dict[str, float]] = {
    "FY2021": {
        "cash_and_equivalents": 402.6, "accounts_receivable": 470.1, "inventory": 296.4,
        "other_current_assets": 92.0, "total_current_assets": 1261.1,
        "property_plant_equipment": 972.4, "goodwill": 902.3, "intangible_assets": 386.9,
        "other_assets": 121.3, "total_assets": 3644.0, "accounts_payable": 310.2,
        "accrued_liabilities": 226.4, "deferred_revenue": 262.0, "current_debt": 80.0,
        "total_current_liabilities": 878.6, "long_term_debt": 1190.0,
        "other_long_term_liabilities": 180.4, "total_liabilities": 2249.0, "total_equity": 1395.0,
    },
    "FY2022": {
        "cash_and_equivalents": 484.4, "accounts_receivable": 556.8, "inventory": 341.2,
        "other_current_assets": 104.9, "total_current_assets": 1487.3,
        "property_plant_equipment": 1046.2, "goodwill": 902.3, "intangible_assets": 352.4,
        "other_assets": 138.8, "total_assets": 3927.0, "accounts_payable": 355.6,
        "accrued_liabilities": 251.7, "deferred_revenue": 302.4, "current_debt": 90.0,
        "total_current_liabilities": 999.7, "long_term_debt": 1120.0,
        "other_long_term_liabilities": 195.3, "total_liabilities": 2315.0, "total_equity": 1612.0,
    },
    "FY2023": {
        "cash_and_equivalents": 812.4, "accounts_receivable": 640.2, "inventory": 388.9,
        "other_current_assets": 120.5, "total_current_assets": 1962.0,
        "property_plant_equipment": 1140.6, "goodwill": 902.3, "intangible_assets": 318.7,
        "other_assets": 145.4, "total_assets": 4469.0, "accounts_payable": 402.1,
        "accrued_liabilities": 288.4, "deferred_revenue": 356.9, "current_debt": 120.0,
        "total_current_liabilities": 1167.4, "long_term_debt": 1050.0,
        "other_long_term_liabilities": 210.6, "total_liabilities": 2428.0, "total_equity": 2041.0,
    },
}

ACME_ANNUAL_CASH_FLOW: dict[str, dict[str, float]] = {
    "FY2021": {
        "net_income": 219.9, "depreciation_amortization": 228.7, "stock_based_compensation": 110.4,
        "change_in_working_capital": -70.2, "cash_from_operations": 488.8,
        "capital_expenditures": -240.0, "acquisitions": 0.0, "cash_from_investing": -240.0,
        "share_repurchases": -120.0, "dividends_paid": -92.0, "net_debt_change": -10.0,
        "cash_from_financing": -222.0, "free_cash_flow": 248.8, "net_change_in_cash": 26.8,
    },
    "FY2022": {
        "net_income": 302.6, "depreciation_amortization": 244.1, "stock_based_compensation": 132.6,
        "change_in_working_capital": -85.5, "cash_from_operations": 593.8,
        "capital_expenditures": -262.0, "acquisitions": 0.0, "cash_from_investing": -262.0,
        "share_repurchases": -150.0, "dividends_paid": -98.0, "net_debt_change": -2.0,
        "cash_from_financing": -250.0, "free_cash_flow": 331.8, "net_change_in_cash": 81.8,
    },
    "FY2023": {
        "net_income": 412.2, "depreciation_amortization": 268.4, "stock_based_compensation": 156.2,
        "change_in_working_capital": -94.6, "cash_from_operations": 942.2,
        "capital_expenditures": -286.0, "acquisitions": -45.0, "cash_from_investing": -331.0,
        "share_repurchases": -180.0, "dividends_paid": -103.2, "net_debt_change": 0.0,
        "cash_from_financing": -283.2, "free_cash_flow": 656.2, "net_change_in_cash": 328.0,
    },
}

PERIOD_ENDS: dict[str, date] = {
    "FY2021": date(2021, 12, 31),
    "FY2022": date(2022, 12, 31),
    "FY2023": date(2023, 12, 31),
    "Q1 2022": date(2022, 3, 31),
    "Q2 2022": date(2022, 6, 30),
    "Q3 2022": date(2022, 9, 30),
    "Q4 2022": date(2022, 12, 31),
    "Q1 2023": date(2023, 3, 31),
    "Q2 2023": date(2023, 6, 30),
    "Q3 2023": date(2023, 9, 30),
    "Q4 2023": date(2023, 12, 31),
}

#: When each period's figures became public (filing / press-release timestamps).
PERIOD_PUBLICATION: dict[str, datetime] = {
    "FY2021": _utc(2022, 2, 16),
    "FY2022": _utc(2023, 2, 15),
    "FY2023": _utc(2024, 2, 14),
    "Q1 2022": _utc(2022, 5, 5),
    "Q2 2022": _utc(2022, 8, 4),
    "Q3 2022": _utc(2022, 11, 3),
    "Q4 2022": _utc(2023, 1, 31),
    "Q1 2023": _utc(2023, 5, 4),
    "Q2 2023": _utc(2023, 8, 3),
    "Q3 2023": _utc(2023, 11, 2),
    "Q4 2023": _utc(2024, 1, 30),
}


@dataclass(frozen=True)
class DemoDocumentPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class DemoDocument:
    key: str
    title: str
    form_type: str
    ticker: str
    filed_at: datetime
    period_label: str
    pages: tuple[DemoDocumentPage, ...]
    source_label: str

    @property
    def page_count(self) -> int:
        return max(page.page_number for page in self.pages)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)

    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _m(value: float) -> str:
    """Format a USD-millions figure the way a filing writes it."""
    return f"${value:,.1f} million"


def _pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def _growth(new: float, old: float) -> float:
    return (new - old) / old * 100.0


def _margin(numerator: float, revenue: float) -> float:
    return numerator / revenue * 100.0


def _statement_table(table: dict[str, dict[str, float]], periods: list[str]) -> str:
    keys = list(table[periods[-1]].keys())
    header = "Line item".ljust(34) + "".join(period.rjust(14) for period in periods)
    lines = [header, "-" * len(header)]
    for key in keys:
        digits = 2 if ("eps" in key or "per_share" in key) else 1
        label = key.replace("_", " ").title().ljust(34)
        values = "".join(f"{table[period].get(key, float('nan')):>14,.{digits}f}" for period in periods)
        lines.append(label + values)
    return "\n".join(lines)


def _annual_report_pages(fy: str, prior_fy: str) -> tuple[DemoDocumentPage, ...]:
    income, prior = ACME_ANNUAL_INCOME[fy], ACME_ANNUAL_INCOME[prior_fy]
    balance, prior_balance = ACME_ANNUAL_BALANCE[fy], ACME_ANNUAL_BALANCE[prior_fy]
    cash_flow = ACME_ANNUAL_CASH_FLOW[fy]
    year, prior_year = fy[2:], prior_fy[2:]

    revenue_growth = _growth(income["revenue"], prior["revenue"])
    gross_margin = _margin(income["gross_profit"], income["revenue"])
    prior_gross_margin = _margin(prior["gross_profit"], prior["revenue"])
    operating_margin = _margin(income["operating_income"], income["revenue"])
    prior_operating_margin = _margin(prior["operating_income"], prior["revenue"])
    total_debt = balance["current_debt"] + balance["long_term_debt"]
    net_debt = total_debt - balance["cash_and_equivalents"]
    tax_rate = income["income_tax_expense"] / income["pretax_income"]
    nopat = income["operating_income"] * (1 - tax_rate)
    invested_capital = total_debt + balance["total_equity"] - balance["cash_and_equivalents"]
    roic = nopat / invested_capital * 100.0

    return (
        DemoDocumentPage(
            1,
            "ACME TECHNOLOGIES, INC.\nANNUAL REPORT ON FORM 10-K\nFor the fiscal year ended "
            f"{PERIOD_ENDS[fy].strftime('%B %d, %Y')}\n\n{DEMO_DISCLAIMER}",
        ),
        DemoDocumentPage(
            4,
            "Item 1. Business.\n\n"
            "ACME Technologies, Inc. designs, manufactures and supports industrial automation "
            "controllers, and sells a subscription software platform for discrete manufacturing "
            f"operations. In fiscal {year} the Company employed approximately 11,400 people across "
            "three reportable segments: Automation Systems, Software Platform and Services. "
            "Software Platform revenue is recognised ratably over the subscription term, while "
            "Automation Systems revenue is recognised on delivery.",
        ),
        DemoDocumentPage(
            24,
            "Item 1A. Risk Factors.\n\n"
            "Our results depend on capital spending by industrial customers, which has historically "
            "declined during economic downturns. Component shortages have previously increased our "
            "cost of revenue and lengthened lead times, and a recurrence would pressure gross "
            f"margin. Competitive pricing pressure in Automation Systems increased during fiscal "
            f"{year} and may continue. A single distributor accounted for 11.2% of revenue in "
            f"fiscal {year}; loss of that relationship would reduce revenue. We are subject to "
            "ongoing patent litigation in the Software Platform segment, the outcome of which is "
            "uncertain and could result in a material loss.",
        ),
        DemoDocumentPage(
            41,
            "Item 7. Management's Discussion and Analysis of Financial Condition and Results of "
            "Operations.\n\nOverview.\n\n"
            f"Revenue for fiscal {year} was {_m(income['revenue'])}, compared with "
            f"{_m(prior['revenue'])} for fiscal {prior_year}. Demand for the Software Platform "
            "continued to outpace Automation Systems, shifting revenue mix toward higher-margin "
            "subscription revenue.",
        ),
        DemoDocumentPage(
            42,
            "Results of Operations — Revenue.\n\n"
            f"Revenue increased {_pct(revenue_growth)} to {_m(income['revenue'])} in fiscal {year} "
            f"from {_m(prior['revenue'])} in fiscal {prior_year}. The increase was driven by "
            "subscription growth in the Software Platform segment and higher volumes in Automation "
            f"Systems. Cost of revenue was {_m(income['cost_of_revenue'])} in fiscal {year} "
            f"compared with {_m(prior['cost_of_revenue'])} in fiscal {prior_year}.",
        ),
        DemoDocumentPage(
            43,
            "Results of Operations — Margins and Operating Expenses.\n\n"
            f"Gross profit was {_m(income['gross_profit'])} in fiscal {year}, representing a gross "
            f"margin of {_pct(gross_margin)}, compared with {_pct(prior_gross_margin)} in fiscal "
            f"{prior_year}. Operating expenses were {_m(income['operating_expenses'])}. Operating "
            f"income was {_m(income['operating_income'])}, or {_pct(operating_margin)} of revenue, "
            f"compared with {_m(prior['operating_income'])}, or {_pct(prior_operating_margin)} of "
            f"revenue, in fiscal {prior_year}. The effective tax rate was {_pct(tax_rate * 100)}. "
            f"Diluted earnings per share were ${income['diluted_eps']:.2f} on "
            f"{income['diluted_shares']:.1f} million diluted shares.",
        ),
        DemoDocumentPage(
            44,
            "Liquidity and Capital Resources.\n\n"
            f"Cash provided by operating activities was {_m(cash_flow['cash_from_operations'])} in "
            f"fiscal {year}. Capital expenditures were {_m(abs(cash_flow['capital_expenditures']))}, "
            f"resulting in free cash flow of {_m(cash_flow['free_cash_flow'])}. Stock-based "
            f"compensation was {_m(cash_flow['stock_based_compensation'])}. Cash and cash "
            f"equivalents were {_m(balance['cash_and_equivalents'])} at fiscal year end, compared "
            f"with {_m(prior_balance['cash_and_equivalents'])} in the prior year. Total debt was "
            f"{_m(total_debt)} and net debt was {_m(net_debt)}. Working capital, defined as total "
            "current assets less total current liabilities, was "
            f"{_m(balance['total_current_assets'] - balance['total_current_liabilities'])}. Return "
            "on invested capital, calculated as after-tax operating income divided by the sum of "
            f"total debt and equity less cash, was {_pct(roic)}.",
        ),
        DemoDocumentPage(
            58,
            "Consolidated Statements of Operations (in millions, except per share amounts)\n\n"
            + _statement_table(ACME_ANNUAL_INCOME, [prior_fy, fy]),
        ),
        DemoDocumentPage(
            59,
            "Consolidated Balance Sheets (in millions)\n\n"
            + _statement_table(ACME_ANNUAL_BALANCE, [prior_fy, fy]),
        ),
        DemoDocumentPage(
            60,
            "Consolidated Statements of Cash Flows (in millions)\n\n"
            + _statement_table(ACME_ANNUAL_CASH_FLOW, [prior_fy, fy]),
        ),
    )


def _quarterly_release_pages(quarter: str, prior_quarter: str) -> tuple[DemoDocumentPage, ...]:
    current, prior = ACME_QUARTERLY_INCOME[quarter], ACME_QUARTERLY_INCOME[prior_quarter]
    revenue_growth = _growth(current["revenue"], prior["revenue"])
    gross_margin = _margin(current["gross_profit"], current["revenue"])
    operating_margin = _margin(current["operating_income"], current["revenue"])
    prior_operating_margin = _margin(prior["operating_income"], prior["revenue"])

    return (
        DemoDocumentPage(
            1,
            f"ACME Technologies, Inc. Reports {quarter} Results\n\n{DEMO_DISCLAIMER}\n\n"
            f"{quarter} revenue of {_m(current['revenue'])} increased {_pct(revenue_growth)} year "
            f"over year from {_m(prior['revenue'])}. Gross profit was "
            f"{_m(current['gross_profit'])}, a gross margin of {_pct(gross_margin)}. Operating "
            f"income of {_m(current['operating_income'])} represented an operating margin of "
            f"{_pct(operating_margin)}, compared with {_pct(prior_operating_margin)} in "
            f"{prior_quarter}. Diluted earnings per share were ${current['diluted_eps']:.2f}, "
            f"compared with ${prior['diluted_eps']:.2f} in {prior_quarter}.",
        ),
        DemoDocumentPage(
            2,
            "Outlook.\n\n"
            "For fiscal 2024 the Company expects revenue of $5,500.0 million to $5,650.0 million, "
            "representing growth of 14.1% to 17.2%, and expects full-year operating margin of "
            "11.5% to 12.5%. Guidance assumes no material deterioration in industrial capital "
            "spending and continued easing of component costs.",
        ),
        DemoDocumentPage(
            3,
            "Condensed Consolidated Statements of Operations (unaudited, in millions)\n\n"
            + _statement_table(ACME_QUARTERLY_INCOME, [prior_quarter, quarter]),
        ),
    )


def _transcript_pages(quarter: str) -> tuple[DemoDocumentPage, ...]:
    current = ACME_QUARTERLY_INCOME[quarter]
    operating_margin = _margin(current["operating_income"], current["revenue"])
    return (
        DemoDocumentPage(
            1,
            f"ACME Technologies {quarter} Earnings Call — Prepared Remarks\n\n{DEMO_DISCLAIMER}\n\n"
            "Dana Ruiz, Chief Executive Officer: Software Platform annual recurring revenue grew "
            "26.0% year over year and now represents 34.0% of total revenue. Automation Systems "
            "orders were flat sequentially as several customers deferred capital projects into the "
            "first half of fiscal 2024.\n\n"
            "Priya Anand, Chief Financial Officer: "
            f"{quarter} revenue was {_m(current['revenue'])} and operating margin was "
            f"{_pct(operating_margin)}. Free cash flow conversion improved as inventory normalised.",
        ),
        DemoDocumentPage(
            2,
            "Question and Answer Session.\n\n"
            "Analyst: How should we think about the pricing environment in Automation Systems?\n\n"
            "Dana Ruiz: Pricing is more competitive than a year ago. We expect low single digit "
            "price erosion in Automation Systems in fiscal 2024, offset by software mix.\n\n"
            "Analyst: Any update on the patent litigation?\n\n"
            "Priya Anand: The matter remains in discovery. We have not recorded a loss accrual "
            "because a loss is not currently probable or estimable.",
        ),
    )


def _memo_pages() -> tuple[DemoDocumentPage, ...]:
    return (
        DemoDocumentPage(
            1,
            "INTERNAL — INVESTMENT COMMITTEE MEMORANDUM (DEMO)\n\n"
            f"{DEMO_DISCLAIMER}\n\n"
            "Subject: ACME Technologies (ACME) — initiation review, December 2023.\n\n"
            "Recommendation: build a 150 basis point position, subject to confirmation of Software "
            "Platform gross margin. Base case assumes fiscal 2024 revenue growth of 15.0% and "
            "operating margin of 12.0%. Position limit set at 3.0% of NAV given single-distributor "
            "concentration of 11.2% of revenue.",
        ),
        DemoDocumentPage(
            2,
            "Bear considerations raised by the committee.\n\n"
            "1. Automation Systems is cyclical; a 10.0% decline in industrial capital spending has "
            "historically translated to a 6.0% revenue decline for comparable issuers.\n"
            "2. Goodwill of $902.3 million has not been retested since the 2020 acquisition; an "
            "impairment would reduce reported equity.\n"
            "3. Patent litigation in the Software Platform segment is unresolved and unaccrued.",
        ),
    )


def demo_documents() -> list[DemoDocument]:
    """The demo corpus. Filing timestamps are what make cutoff demonstrations meaningful."""
    return [
        DemoDocument(
            key="ACME_FY2022_10K",
            title="ACME Technologies FY2022 Form 10-K (DEMO)",
            form_type="10-K",
            ticker="ACME",
            filed_at=PERIOD_PUBLICATION["FY2022"],
            period_label="FY2022",
            pages=_annual_report_pages("FY2022", "FY2021"),
            source_label="ACME FY2022 10-K",
        ),
        DemoDocument(
            key="ACME_FY2023_10K",
            title="ACME Technologies FY2023 Form 10-K (DEMO)",
            form_type="10-K",
            ticker="ACME",
            filed_at=PERIOD_PUBLICATION["FY2023"],
            period_label="FY2023",
            pages=_annual_report_pages("FY2023", "FY2022"),
            source_label="ACME FY2023 10-K",
        ),
        DemoDocument(
            key="ACME_Q3_2023_10Q",
            title="ACME Technologies Q3 2023 Form 10-Q (DEMO)",
            form_type="10-Q",
            ticker="ACME",
            filed_at=PERIOD_PUBLICATION["Q3 2023"],
            period_label="Q3 2023",
            pages=_quarterly_release_pages("Q3 2023", "Q3 2022"),
            source_label="ACME Q3 2023 10-Q",
        ),
        DemoDocument(
            key="ACME_Q4_2023_EARNINGS",
            title="ACME Technologies Q4 2023 earnings release (DEMO)",
            form_type="8-K",
            ticker="ACME",
            filed_at=PERIOD_PUBLICATION["Q4 2023"],
            period_label="Q4 2023",
            pages=_quarterly_release_pages("Q4 2023", "Q4 2022"),
            source_label="ACME Q4 2023 earnings release",
        ),
        DemoDocument(
            key="ACME_Q4_2023_TRANSCRIPT",
            title="ACME Technologies Q4 2023 earnings call transcript (DEMO)",
            form_type="TRANSCRIPT",
            ticker="ACME",
            filed_at=_utc(2024, 1, 30, 22),
            period_label="Q4 2023",
            pages=_transcript_pages("Q4 2023"),
            source_label="ACME Q4 2023 earnings call",
        ),
        DemoDocument(
            key="ACME_IC_MEMO_2023",
            title="Internal investment committee memo — ACME (DEMO)",
            form_type="INTERNAL_MEMO",
            ticker="ACME",
            filed_at=_utc(2023, 12, 5, 18),
            period_label="FY2023",
            pages=_memo_pages(),
            source_label="Internal IC memo (Dec 2023)",
        ),
    ]


# ------------------------------------------------------------------------- prices


def _trading_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def generate_price_series(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    """Deterministic synthetic price history.

    The walk is generated from a fixed anchor date, so any window is a consistent slice of
    one series — which is what makes demo backtests reproducible.
    """
    if symbol not in _PRICE_PARAMS:
        raise KeyError(f"unknown demo symbol: {symbol}")
    start_price, drift, vol, seed = _PRICE_PARAMS[symbol]
    anchor = date(2018, 1, 1)
    horizon_end = max(end, date(2024, 12, 31))
    days = _trading_days(anchor, horizon_end)
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    shocks = rng.normal((drift - 0.5 * vol**2) * dt, vol * (dt**0.5), size=len(days))
    closes = start_price * np.exp(np.cumsum(shocks))
    ranges = np.abs(rng.normal(0.0, vol * (dt**0.5), size=len(days))) * closes

    bars: list[dict[str, Any]] = []
    for index, day in enumerate(days):
        if day < start or day > end:
            continue
        close = float(closes[index])
        spread = float(ranges[index])
        open_price = float(closes[index - 1]) if index else close
        bars.append(
            {
                "symbol": symbol,
                "bar_date": day,
                "open": round(open_price, 4),
                "high": round(max(open_price, close) + spread / 2, 4),
                "low": round(max(0.01, min(open_price, close) - spread / 2), 4),
                "close": round(close, 4),
                "adj_close": round(close, 4),
                "volume": float(int(rng.integers(200_000, 3_000_000))),
                # A daily bar is public after that session closes.
                "publication_timestamp": datetime(day.year, day.month, day.day, 21, 0, tzinfo=timezone.utc),
            }
        )
    return bars


def demo_fundamental_factors() -> list[dict[str, Any]]:
    """Quarterly factor rows with an explicit reporting lag.

    ``period_end`` is when the quarter ended; ``publication_timestamp`` is 45 days later,
    modelling the filing lag. A backtest that trades on ``period_end`` is committing
    look-ahead bias — the validator checks for exactly that.
    """
    rows: list[dict[str, Any]] = []
    quarter_ends = [
        date(year, month, day)
        for year in range(2018, 2025)
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31))
    ]
    for symbol in DEMO_UNIVERSE:
        seed = _PRICE_PARAMS[symbol][3]
        rng = np.random.default_rng(seed + 900)
        base_quality = float(rng.uniform(0.05, 0.25))
        for period_end in quarter_ends:
            drift = rng.normal(0.0, 0.02)
            rows.append(
                {
                    "symbol": symbol,
                    "period_end": period_end,
                    "publication_timestamp": datetime(
                        period_end.year, period_end.month, period_end.day, 21, 0, tzinfo=timezone.utc
                    )
                    + timedelta(days=45),
                    "earnings_yield": round(max(0.005, base_quality * 0.35 + drift), 4),
                    "gross_margin": round(min(0.75, max(0.15, base_quality * 2.2 + drift)), 4),
                    "accruals": round(drift, 4),
                    "is_demo": True,
                    "source": DEMO_SOURCE,
                }
            )
    return rows
