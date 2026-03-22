"""
Helpers Module - Utility functions for time, data manipulation, and system operations.

Provides:
- ISO 8601 compliant datetime generation
- Timezone-aware operations
- Data transformation helpers
- Workflow state helpers
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union
import json
from pathlib import Path


# ==================== Time Helpers ====================

def get_utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def get_iso_now() -> str:
    """
    Get current UTC time as ISO 8601 string.
    
    Returns:
        ISO formatted timestamp
    """
    return get_utc_now().isoformat()


def get_timestamp_seconds() -> float:
    """
    Get current Unix timestamp in seconds.
    
    Returns:
        Current Unix timestamp
    """
    return datetime.now(timezone.utc).timestamp()


def iso_to_datetime(iso_string: str) -> datetime:
    """
    Convert ISO 8601 string to datetime.
    
    Args:
        iso_string: ISO formatted datetime string
        
    Returns:
        datetime object
    """
    return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def datetime_to_iso(dt: datetime) -> str:
    """
    Convert datetime to ISO 8601 string.
    
    Args:
        dt: datetime object
        
    Returns:
        ISO formatted string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def add_hours_to_iso(iso_string: str, hours: float) -> str:
    """
    Add hours to ISO datetime string.
    
    Args:
        iso_string: ISO formatted datetime
        hours: Hours to add
        
    Returns:
        New ISO formatted datetime
    """
    dt = iso_to_datetime(iso_string)
    new_dt = dt + timedelta(hours=hours)
    return datetime_to_iso(new_dt)


def is_past_iso(iso_string: str) -> bool:
    """
    Check if ISO datetime is in the past.
    
    Args:
        iso_string: ISO formatted datetime
        
    Returns:
        True if datetime is before now
    """
    dt = iso_to_datetime(iso_string)
    return dt < get_utc_now()


def seconds_until_iso(iso_string: str) -> float:
    """
    Calculate seconds until ISO datetime.
    
    Args:
        iso_string: ISO formatted datetime
        
    Returns:
        Seconds remaining (negative if past)
    """
    dt = iso_to_datetime(iso_string)
    delta = dt - get_utc_now()
    return delta.total_seconds()


def parse_iso_safely(value: str) -> Optional[datetime]:
    """
    Safely parse ISO string handling naive/aware datetimes.
    
    Args:
        value: ISO datetime string
        
    Returns:
        datetime object or None if parsing fails
    """
    try:
        # Try standard ISO parsing
        return iso_to_datetime(value)
    except (ValueError, AttributeError):
        try:
            # Try alternative formats
            return datetime.fromisoformat(value)
        except (ValueError, AttributeError):
            return None


# ==================== Duration Helpers ====================

def format_duration_seconds(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


def sla_status(elapsed_seconds: float, sla_seconds: float) -> tuple[str, float]:
    """
    Calculate SLA status and remaining percentage.
    
    Args:
        elapsed_seconds: Time elapsed
        sla_seconds: Total SLA time
        
    Returns:
        Tuple of (status, percentage_remaining)
        - status: "on_track", "warning", "breached"
        - percentage_remaining: 0-100%
    """
    percentage_used = (elapsed_seconds / sla_seconds) * 100
    percentage_remaining = max(0, 100 - percentage_used)
    
    if percentage_used <= 75:
        status = "on_track"
    elif percentage_used <= 95:
        status = "warning"
    else:
        status = "breached"
    
    return status, percentage_remaining


# ==================== Data Helpers ====================

def deep_merge_dicts(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        update: Updates to merge in
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def filter_dict_keys(data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """
    Filter dictionary to only include specified keys.
    
    Args:
        data: Source dictionary
        keys: Keys to include
        
    Returns:
        Filtered dictionary
    """
    return {k: v for k, v in data.items() if k in keys}


def flatten_dict(data: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """
    Flatten nested dictionary.
    
    Args:
        data: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep).items())
        else:
            items.append((new_key, value))
    
    return dict(items)


# ==================== State Helpers ====================

def load_json_file(file_path: str) -> Dict[str, Any]:
    """
    Load JSON file safely.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Loaded JSON data or empty dict on error
    """
    try:
        path = Path(file_path)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    
    return {}


def save_json_file(file_path: str, data: Dict[str, Any], pretty: bool = True) -> bool:
    """
    Save dictionary to JSON file.
    
    Args:
        file_path: Path to save to
        data: Data to save
        pretty: Whether to pretty-print
        
    Returns:
        Success status
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            if pretty:
                json.dump(data, f, indent=2, default=str)
            else:
                json.dump(data, f, default=str)
        
        return True
    except IOError:
        return False


def load_jsonl_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load JSONL file (one JSON object per line).
    
    Args:
        file_path: Path to JSONL file
        
    Returns:
        List of JSON objects
    """
    lines = []
    
    try:
        path = Path(file_path)
        if path.exists():
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
    except IOError:
        pass
    
    return lines


def append_jsonl_file(file_path: str, data: Dict[str, Any]) -> bool:
    """
    Append JSON object to JSONL file.
    
    Args:
        file_path: Path to JSONL file
        data: Data to append
        
    Returns:
        Success status
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")
        
        return True
    except IOError:
        return False


# ==================== Validation Helpers ====================

def is_valid_uuid(value: str) -> bool:
    """
    Check if string is valid UUID.
    
    Args:
        value: String to check
        
    Returns:
        True if valid UUID
    """
    try:
        import uuid
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def is_valid_email(email: str) -> bool:
    """
    Check if string is valid email format.
    
    Args:
        email: Email to validate
        
    Returns:
        True if valid email format
    """
    import re
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None
