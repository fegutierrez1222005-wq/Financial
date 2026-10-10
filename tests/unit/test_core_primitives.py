"""Unit tests for the domain core: cutoff arithmetic, numerics, demo data, sandbox."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from finagent_core.cutoff import AsOfContext, LookAheadViolation, ensure_utc
from finagent_core.numeric import (
    Unit,
    cagr,
    comparable,
    extract_numbers,
    in_range,
    parse_number,
    percent_change,
    safe_div,
    values_match,
)


class TestAsOfContext:
    def test_naive_datetimes_are_treated_as_utc(self) -> None:
        assert ensure_utc(datetime(2023, 1, 1)).tzinfo is timezone.utc
        assert ensure_utc(date(2023, 1, 1)).tzinfo is timezone.utc
        assert ensure_utc("2023-01-01T00:00:00Z").tzinfo is timezone.utc

    def test_boundary_is_inclusive(self) -> None:
        cutoff = datetime(2023, 6, 30, 12, 0, tzinfo=timezone.utc)
        context = AsOfContext(cutoff=cutoff)
        assert context.allows(cutoff)
        assert not context.allows(datetime(2023, 6, 30, 12, 0, 1, tzinfo=timezone.utc))

    def test_unknown_timestamps_are_inadmissible_under_a_cutoff(self) -> None:
        assert not AsOfContext(cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc)).allows(None)
        assert AsOfContext(cutoff=None).allows(None)

    def test_strict_mode_raises_and_lenient_mode_filters(self) -> None:
        strict = AsOfContext(cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc))
        with pytest.raises(LookAheadViolation):
            strict.check(datetime(2024, 1, 1, tzinfo=timezone.utc), subject="FY2023 10-K")

        lenient = AsOfContext(cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc), strict=False)
        assert lenient.check(datetime(2024, 1, 1, tzinfo=timezone.utc), subject="FY2023 10-K") is False
        assert lenient.filtered_subjects == ["FY2023 10-K"]

    def test_filter_records_drops_unknown_and_future_timestamps(self) -> None:
        context = AsOfContext(cutoff=datetime(2023, 6, 30, tzinfo=timezone.utc))
        records = [
            {"id": "past", "publication_timestamp": datetime(2023, 1, 1, tzinfo=timezone.utc)},
            {"id": "future", "publication_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            {"id": "unknown", "publication_timestamp": None},
        ]
        assert [record["id"] for record in context.filter_records(records)] == ["past"]

    def test_describes_itself_for_the_trace(self) -> None:
        historical = AsOfContext(cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc))
        assert historical.is_historical is True
        assert AsOfContext(cutoff=None).is_historical is False


class TestNumerics:
    def test_extracts_values_with_units(self) -> None:
        mentions = extract_numbers("Revenue rose to $4,820.0 million, up 18.0% year over year.")
        by_unit = {mention.unit: mention.value for mention in mentions}
        # A scaled money figure is normalised to its base unit, so "$4,820.0 million"
        # cannot be silently compared against a raw 4820.
        assert by_unit[Unit.USD] == 4_820_000_000.0
        assert by_unit[Unit.PERCENT] == 18.0

    def test_percent_change_and_cagr(self) -> None:
        assert percent_change(4820.0, 4084.7) == pytest.approx(18.0, abs=0.05)
        assert cagr(100.0, 121.0, 2.0) == pytest.approx(10.0, abs=0.01)

    def test_safe_div_does_not_raise_on_zero(self) -> None:
        assert safe_div(1.0, 0.0) == 0.0
        assert safe_div(1.0, 0.0, default=-1.0) == -1.0

    def test_values_match_respects_tolerance(self) -> None:
        assert values_match(18.02, 18.0, tolerance_pct=0.5)
        assert not values_match(19.0, 18.0, tolerance_pct=0.5)
        assert values_match(0.0, 0.0, absolute_tolerance=0.01)

    def test_units_must_be_comparable(self) -> None:
        percent = parse_number("18.0%")
        money = parse_number("$18.0 million")
        assert percent is not None and money is not None
        assert not comparable(percent, money), "a percentage is not a dollar amount"

    def test_in_range_is_inclusive_and_tolerates_open_bounds(self) -> None:
        assert in_range(62.5, 62.0, 63.0)
        assert in_range(62.5, None, 63.0)
        assert not in_range(64.0, 62.0, 63.0)


class TestDemoDataset:
    """The demo corpus must be internally consistent, or every derived test is meaningless."""

    def test_income_statement_reconciles(self) -> None:
        from finagent_core.data.demo_dataset import ACME_ANNUAL_INCOME

        for period, row in ACME_ANNUAL_INCOME.items():
            assert row["revenue"] - row["cost_of_revenue"] == pytest.approx(
                row["gross_profit"], abs=0.2
            ), period
            assert row["gross_profit"] - row["operating_expenses"] == pytest.approx(
                row["operating_income"], abs=0.2
            ), period
            assert row["pretax_income"] - row["income_tax_expense"] == pytest.approx(
                row["net_income"], abs=0.2
            ), period

    def test_quarters_sum_to_the_annual_figure(self) -> None:
        from finagent_core.data.demo_dataset import ACME_ANNUAL_INCOME, ACME_QUARTERLY_INCOME

        for year in (2022, 2023):
            quarters = [
                row for key, row in ACME_QUARTERLY_INCOME.items() if key.endswith(str(year))
            ]
            assert len(quarters) == 4, year
            total = sum(row["revenue"] for row in quarters)
            assert total == pytest.approx(ACME_ANNUAL_INCOME[f"FY{year}"]["revenue"], abs=1.0)

    def test_balance_sheet_balances(self) -> None:
        from finagent_core.data.demo_dataset import ACME_ANNUAL_BALANCE

        for period, row in ACME_ANNUAL_BALANCE.items():
            assert row["total_assets"] == pytest.approx(
                row["total_liabilities"] + row["total_equity"], abs=0.5
            ), period

    def test_every_issuer_is_explicitly_fictional(self) -> None:
        from finagent_core.data.demo_dataset import COMPANY_PROFILES, DEMO_DISCLAIMER, demo_documents

        assert "fictional" in DEMO_DISCLAIMER.lower()
        for symbol, profile in COMPANY_PROFILES.items():
            assert "fictional" in profile["description"].lower(), symbol
        for document in demo_documents():
            body = "\n".join(page.text for page in document.pages)
            assert "DEMO DATA" in body, document.title

    def test_documents_carry_publication_timestamps(self) -> None:
        from finagent_core.data.demo_dataset import demo_documents

        for document in demo_documents():
            assert document.filed_at is not None, document.title
            assert document.filed_at.tzinfo is not None, document.title

    def test_price_series_is_deterministic(self) -> None:
        from finagent_core.data.demo_dataset import generate_price_series

        first = generate_price_series("ACME", date(2022, 1, 3), date(2022, 3, 31))
        second = generate_price_series("ACME", date(2022, 1, 3), date(2022, 3, 31))
        assert first == second, "the demo price walk must be reproducible across processes"
        assert all(bar["close"] > 0 for bar in first)

    def test_fundamental_factors_carry_a_publication_lag(self) -> None:
        from finagent_core.data.demo_dataset import demo_fundamental_factors

        rows = demo_fundamental_factors()
        assert rows
        for row in rows:
            assert row["publication_timestamp"].date() > row["period_end"], (
                "a factor must not be usable before the date it was published"
            )
            assert row["is_demo"] is True


class TestLogging:
    def test_a_log_field_cannot_crash_the_operation_it_describes(self, caplog) -> None:  # noqa: ANN001
        """``filename`` and ``module`` collide with LogRecord attributes.

        Before this guard, ingesting a document raised ``KeyError`` from inside the logging
        call that was merely reporting success.
        """
        from finagent_core.logging import get_logger

        logger = get_logger("tests.logging")
        with caplog.at_level("INFO"):
            logger.info("document_ingested", extra={"filename": "acme.pdf", "pages": 3})

        record = caplog.records[-1]
        assert record.extra_filename == "acme.pdf"
        assert record.pages == 3
        assert record.filename.endswith(".py"), "the real LogRecord attribute is preserved"

    def test_sensitive_values_are_redacted(self) -> None:
        from finagent_core.logging import redact

        payload = redact(
            {"api_key": "sk-live-secret", "nested": {"password": "hunter2"}, "model": "gpt-4o"}
        )
        assert payload["api_key"] == "[REDACTED]"
        assert payload["nested"]["password"] == "[REDACTED]"
        assert payload["model"] == "gpt-4o"


class TestSandbox:
    """The sandbox must run real analysis code and refuse everything else."""

    @pytest.fixture(scope="class")
    def sandbox(self):  # noqa: ANN201
        from finagent_agent_runner.sandbox import PythonSandbox

        return PythonSandbox(timeout_seconds=15, memory_mb=512, cpu_seconds=10)

    def test_runs_ordinary_analysis_code(self, sandbox) -> None:  # noqa: ANN001
        outcome = sandbox.run(
            "import pandas as pd\n"
            "frame = pd.DataFrame({'revenue': [4084.7, 4820.0]})\n"
            "result = {'growth_pct': round((frame.revenue.iloc[1] / frame.revenue.iloc[0] - 1) * 100, 1)}\n"
        )
        assert outcome.succeeded, outcome.error
        assert outcome.results["growth_pct"] == 18.0

    @pytest.mark.parametrize(
        "code",
        [
            "import os\nresult = {'x': os.listdir('/')}",
            "import socket\nresult = {}",
            "import subprocess\nresult = {}",
            "open('/etc/passwd').read()",
            "__import__('os').system('echo hi')",
            "import requests\nresult = {}",
        ],
    )
    def test_refuses_escapes(self, sandbox, code: str) -> None:  # noqa: ANN001
        """Refusal may happen in the static scan or at run time; either is acceptable,
        silently executing is not."""
        from finagent_core.errors import SandboxDeniedError

        try:
            outcome = sandbox.run(code)
        except SandboxDeniedError:
            return
        assert not outcome.succeeded, f"the sandbox executed forbidden code: {code}"
        assert outcome.error

    def test_enforces_the_wall_clock_timeout(self, sandbox) -> None:  # noqa: ANN001
        from finagent_core.errors import SandboxTimeoutError

        with pytest.raises(SandboxTimeoutError):
            sandbox.run("while True:\n    pass\n", timeout_seconds=3)

    def test_describes_its_own_limits(self, sandbox) -> None:  # noqa: ANN001
        described = sandbox.describe()
        assert described["network"] == "disabled"
        assert described["timeout_seconds"] > 0
        assert described["memory_mb"] > 0
