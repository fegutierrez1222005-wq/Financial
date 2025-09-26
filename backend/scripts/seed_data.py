from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company
from app.models.data_source import DataSource
from app.models.financial_data import FinancialData


def seed() -> None:
    db: Session = SessionLocal()
    try:
        # Data sources
        sources = [
            ("pitchbook", "https://sandbox.api.pitchbook.com"),
            ("capiq", "https://sandbox.api.spglobal.com"),
            ("factset", "https://sandbox.api.factset.com"),
            ("axial", "https://sandbox.api.axial.net"),
            ("grata", "https://sandbox.api.grata.com"),
            ("sec_edgar", "https://data.sec.gov"),
            ("web_scraper", None),
            ("deal_books", None),
        ]
        for name, base_url in sources:
            if not db.query(DataSource).filter(DataSource.name == name).first():
                db.add(DataSource(name=name, base_url=base_url))

        # Companies
        acme = Company(name="Acme Corp", website="https://acme.example", industry="Industrials", country="US")
        if not db.query(Company).filter(Company.name == acme.name).first():
            db.add(acme)
            db.flush()

            db.add(
                FinancialData(
                    company_id=acme.id,
                    metric="revenue",
                    period="FY2023",
                    value=10000000.0,
                    currency="USD",
                    source="pitchbook",
                    as_of=datetime(2024, 3, 31),
                )
            )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()

