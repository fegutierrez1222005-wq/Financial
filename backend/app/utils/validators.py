from pydantic import EmailStr, HttpUrl


def is_valid_email(value: str) -> bool:
    try:
        EmailStr(value)
        return True
    except Exception:
        return False


def is_valid_url(value: str) -> bool:
    try:
        HttpUrl(value)
        return True
    except Exception:
        return False


