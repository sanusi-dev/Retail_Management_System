from datetime import datetime
from django.utils import timezone


def parse_backdate(date_str):
    """Parse a date string (YYYY-MM-DD) and return a timezone-aware datetime
    with the user-selected date but the current local time."""
    if not date_str:
        return None
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        now = timezone.localtime(timezone.now())
        return now.replace(year=parsed.year, month=parsed.month, day=parsed.day)
    except (ValueError, TypeError):
        return None