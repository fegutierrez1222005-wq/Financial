import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.config import get_settings


def create_admin() -> None:
    settings = get_settings()
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.admin_email).first()
        if existing:
            # update password if different
            existing.hashed_password = get_password_hash(settings.admin_password)
            db.commit()
            return
        user = User(
            email=settings.admin_email,
            hashed_password=get_password_hash(settings.admin_password),
            full_name="Admin",
            is_superuser=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()

