"""utils/helpers.py — Shared utility functions used across the project"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def generate_id(prefix: str = "") -> str:
    """Generate a short unique ID with optional prefix"""
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}_{uid}" if prefix else uid


def now_iso() -> str:
    """Current UTC time as ISO 8601 string"""
    return datetime.now(timezone.utc).isoformat()


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate a string to max_len with ellipsis"""
    if not text:
        return ""
    return text[:max_len] + ("..." if len(text) > max_len else "")


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON without raising — returns default on failure"""
    if not text:
        return default
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """Flatten a nested dict: {'a': {'b': 1}} → {'a.b': 1}"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def hash_content(content: str) -> str:
    """Return SHA-256 hash of content string (for deduplication)"""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def clean_email(email: str) -> str:
    """Normalise an email address"""
    return email.strip().lower() if email else ""


def extract_emails(text: str) -> List[str]:
    """Extract all email addresses from a string"""
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return list(set(re.findall(pattern, text)))


def minutes_between(iso_start: str, iso_end: Optional[str] = None) -> float:
    """Calculate minutes between two ISO timestamps"""
    try:
        start = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
        end_str = iso_end or now_iso()
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        return (end - start).total_seconds() / 60
    except (ValueError, AttributeError):
        return 0.0


def format_duration(seconds: float) -> str:
    """Human-readable duration: 125 → '2m 5s'"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def sanitise_filename(name: str) -> str:
    """Strip unsafe characters from a filename"""
    return re.sub(r"[^\w\-_\. ]", "_", name).strip()