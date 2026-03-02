"""Utility functions for brain."""

import re
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various formats.

    Args:
        date_str: Date string (e.g., "tomorrow", "in 2 days", "next week")

    Returns:
        Parsed datetime or None
    """
    date_str = date_str.lower().strip()
    now = datetime.now()
    
    # Common mappings
    if date_str == "today":
        return now.replace(hour=23, minute=59, second=59)
    elif date_str == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif date_str == "next week":
        return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=59)
    elif date_str == "next month":
        return (now + relativedelta(months=1)).replace(hour=23, minute=59, second=59)

    # Regex patterns for relative dates
    # "in 3 days", "after 5 days", "2 weeks", "after 1 month"
    patterns = [
        (r"(?:in|after)?\s*(\d+)\s*days?", "days"),
        (r"(?:in|after)?\s*(\d+)\s*weeks?", "weeks"),
        (r"(?:in|after)?\s*(\d+)\s*months?", "months"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, date_str)
        if match:
            amount = int(match.group(1))
            if unit == "days":
                return (now + timedelta(days=amount)).replace(hour=23, minute=59, second=59)
            elif unit == "weeks":
                return (now + timedelta(weeks=amount)).replace(hour=23, minute=59, second=59)
            elif unit == "months":
                return (now + relativedelta(months=amount)).replace(hour=23, minute=59, second=59)

    # Fallback to fuzzy parsing
    try:
        dt = date_parser.parse(date_str, fuzzy=True)
        # If the parsed date is in the past (and no year specified), usually assume future
        return dt.replace(hour=23, minute=59, second=59)
    except:
        return None
