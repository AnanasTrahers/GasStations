import hashlib


def generate_etag(data: list) -> str:
    return hashlib.md5(str(data).encode("utf-8")).hexdigest()  # type: ignore


def check_etag_match(if_none_match: str | None, etag: str) -> bool:
    return if_none_match == etag
