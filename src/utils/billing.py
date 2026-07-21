import base64
import hashlib
import hmac
import json

from fastapi import HTTPException, status

from src.config import project_settings
from src.utils.logs import Logger


def _verify_pubsub_signature(signature: str, body_bytes: bytes) -> None:
    expected = base64.b64encode(
        hmac.new(
            project_settings.GOOGLE_PUBSUB_VERIFICATION_TOKEN.encode(),
            body_bytes,
            hashlib.sha256,
        ).digest()
    ).decode()

    if not hmac.compare_digest(signature, expected):
        Logger.warning("Invalid Pub/Sub signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )


def _decode_pubsub_payload(body: dict) -> dict:
    message = body.get("message")
    if message is None:
        Logger.warning("Received webhook without Pub/Sub message envelope")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Pub/Sub message format",
        )

    encoded_data = message.get("data")
    if encoded_data is None:
        Logger.warning("Pub/Sub message missing data field")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing data in Pub/Sub message",
        )

    try:
        decoded = base64.b64decode(encoded_data)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as e:
        Logger.error(f"Failed to decode webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload encoding",
        )
