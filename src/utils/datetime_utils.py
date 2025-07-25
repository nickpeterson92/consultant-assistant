"""Datetime utilities for consistent UTC/Zulu time handling across the application."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get the current time in UTC with timezone awareness.
    
    This ensures consistency with PostgreSQL's timestamptz fields
    which store timestamps in UTC.
    
    Returns:
        datetime: Current UTC time with timezone awareness
    """
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware and in UTC.
    
    Args:
        dt: A datetime object (may be naive or aware)
        
    Returns:
        datetime: Timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        # Assume naive datetimes are in UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if not already
        return dt.astimezone(timezone.utc)


def datetime_to_iso_utc(dt: datetime) -> str:
    """
    Convert datetime to ISO format string in UTC.
    
    Args:
        dt: A datetime object
        
    Returns:
        str: ISO format string with 'Z' suffix for UTC
    """
    utc_dt = ensure_utc(dt)
    return utc_dt.isoformat().replace('+00:00', 'Z')