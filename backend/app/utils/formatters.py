from decimal import Decimal, ROUND_HALF_UP


def format_currency(value: float | int, currency: str = "USD") -> str:
    q = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {q:,.2f}"


def normalize_domain(url: str) -> str:
    url = url.lower().strip()
    if url.startswith("http://"):
        url = url[len("http://") :]
    if url.startswith("https://"):
        url = url[len("https://") :]
    return url.strip("/")


