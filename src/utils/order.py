import uuid
from datetime import datetime, UTC

from src.config import LOG_ID
from src.utils.annotations import StrUUID


def get_datetime_with_utc() -> datetime:
    return datetime.now(UTC)


def get_uuid_str() -> StrUUID:
    return str(uuid.uuid4())


def get_log_id() -> StrUUID:
    return LOG_ID.get(get_uuid_str())
