from dataclasses import dataclass
from datetime import datetime

from src.schemas import GoogleNotificationType, SubscriptionStatus
from src.utils.logs import Logger


# Maps RTDN notificationType → SubscriptionStatus.
# None means the notification is informational and doesn't change status.
_NOTIFICATION_STATUS_MAP: dict[GoogleNotificationType, SubscriptionStatus | None] = {
    GoogleNotificationType.SUBSCRIPTION_RECOVERED: SubscriptionStatus.ACTIVE,
    GoogleNotificationType.SUBSCRIPTION_RENEWED: SubscriptionStatus.ACTIVE,
    GoogleNotificationType.SUBSCRIPTION_CANCELED: SubscriptionStatus.CANCELED,
    GoogleNotificationType.SUBSCRIPTION_PURCHASED: SubscriptionStatus.ACTIVE,
    GoogleNotificationType.SUBSCRIPTION_ON_HOLD: SubscriptionStatus.ON_HOLD,
    GoogleNotificationType.SUBSCRIPTION_IN_GRACE_PERIOD: SubscriptionStatus.IN_GRACE_PERIOD,
    GoogleNotificationType.SUBSCRIPTION_RESTARTED: SubscriptionStatus.ACTIVE,
    GoogleNotificationType.SUBSCRIPTION_PRICE_CHANGE_CONFIRMED: None,
    GoogleNotificationType.SUBSCRIPTION_DEFERRED: SubscriptionStatus.ACTIVE,
    GoogleNotificationType.SUBSCRIPTION_PAUSED: SubscriptionStatus.PAUSED,
    GoogleNotificationType.SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED: None,
    GoogleNotificationType.SUBSCRIPTION_REVOKED: SubscriptionStatus.REVOKED,
    GoogleNotificationType.SUBSCRIPTION_EXPIRED: SubscriptionStatus.EXPIRED,
}


@dataclass(frozen=True)
class SubscriptionData:
    product_id: str
    platform: str
    status: SubscriptionStatus
    starts_at: datetime | None
    expires_at: datetime | None


def extract_notification_type(notification_payload: dict) -> GoogleNotificationType | None:
    notification_type_int = notification_payload.get("notificationType")
    if notification_type_int is None:
        return None
    try:
        return GoogleNotificationType(notification_type_int)
    except ValueError:
        Logger.warning(f"Unknown Google notification type: {notification_type_int}")
        return None


def map_notification_to_status(
        notification_type: GoogleNotificationType,
) -> SubscriptionStatus | None:
    return _NOTIFICATION_STATUS_MAP.get(notification_type)


# Google subscriptionsv2 API subscriptionState → SubscriptionStatus
_GOOGLE_STATE_MAP: dict[int, SubscriptionStatus] = {
    0: SubscriptionStatus.ACTIVE,       # SUBSCRIPTION_STATE_UNSPECIFIED
    1: SubscriptionStatus.ACTIVE,       # SUBSCRIPTION_STATE_ACTIVE
    2: SubscriptionStatus.CANCELED,     # SUBSCRIPTION_STATE_CANCELED
    3: SubscriptionStatus.IN_GRACE_PERIOD,  # SUBSCRIPTION_STATE_IN_GRACE_PERIOD
    4: SubscriptionStatus.ON_HOLD,      # SUBSCRIPTION_STATE_ON_HOLD
    5: SubscriptionStatus.PAUSED,       # SUBSCRIPTION_STATE_PAUSED
    6: SubscriptionStatus.EXPIRED,      # SUBSCRIPTION_STATE_EXPIRED
}


def extract_subscription_data(
        verified_purchase: dict, product_id: str
) -> SubscriptionData:
    google_state = verified_purchase.get("subscriptionState", 6)
    status = _GOOGLE_STATE_MAP.get(google_state, SubscriptionStatus.EXPIRED)

    start_time_str = verified_purchase.get("startTime")
    expiry_time_str = verified_purchase.get("expiryTime")

    starts_at = datetime.fromisoformat(start_time_str) if start_time_str else None
    expires_at = datetime.fromisoformat(expiry_time_str) if expiry_time_str else None

    return SubscriptionData(
        product_id=product_id,
        platform="GOOGLE",
        status=status,
        starts_at=starts_at,
        expires_at=expires_at,
    )
