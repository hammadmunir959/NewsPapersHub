from datetime import date

def validate_date(date_str: str) -> None:
    """Validate date format and business rules."""
    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format")

    if parsed > date.today():
        raise ValueError("Date must not be in the future")
    if (date.today() - parsed).days > 30:
        raise ValueError("Date must be within the last 30 days")
