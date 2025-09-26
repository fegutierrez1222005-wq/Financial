from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.financial_data import FinancialData
from app.models.outreach import Outreach


def summary(db: Session) -> dict:
    companies = db.query(Company).count()
    data_points = db.query(FinancialData).count()
    outreach_sent = db.query(Outreach).count()
    return {
        "companies": companies,
        "data_points": data_points,
        "outreach_sent": outreach_sent,
    }


