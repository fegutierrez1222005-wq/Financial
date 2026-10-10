"""Financial data provider abstraction."""

from finagent_core.data.base import FinancialDataProvider
from finagent_core.data.demo_provider import DemoDataProvider
from finagent_core.data.market_providers import (
    AlphaVantageProvider,
    PolygonProvider,
    UploadedCsvPriceProvider,
)
from finagent_core.data.registry import DataProviderRegistry, build_default_data_registry
from finagent_core.data.schemas import (
    CompanyProfile,
    DataQualityReport,
    DividendEvent,
    FinancialStatement,
    MarketCapPoint,
    Periodicity,
    PriceBar,
    ProviderCapability,
    SecFiling,
    StatementType,
    TranscriptSegment,
)
from finagent_core.data.sec_edgar import SecEdgarProvider

__all__ = [
    "FinancialDataProvider",
    "DemoDataProvider",
    "AlphaVantageProvider",
    "PolygonProvider",
    "UploadedCsvPriceProvider",
    "SecEdgarProvider",
    "DataProviderRegistry",
    "build_default_data_registry",
    "CompanyProfile",
    "DataQualityReport",
    "DividendEvent",
    "FinancialStatement",
    "MarketCapPoint",
    "Periodicity",
    "PriceBar",
    "ProviderCapability",
    "SecFiling",
    "StatementType",
    "TranscriptSegment",
]
