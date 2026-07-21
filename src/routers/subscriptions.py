from fastapi import APIRouter, Depends, HTTPException, status, Request

from src.billing import (
    extract_notification_type,
    extract_subscription_data,
    map_notification_to_status,
)
from src.clients.google_play import GooglePlayClient
from src.dependencies import get_db_repo, get_current_user_id, get_httpx_client
from src.repositories import DBRepository
from src.schemas import (
    VerifyPurchaseRequest,
    VerifyPurchaseResponse,
    SubscriptionStatusResponse,
    Platform,
)
from src.utils.billing import _verify_pubsub_signature, _decode_pubsub_payload
from src.utils.logs import Logger

router = APIRouter(tags=["Subscriptions"])


@router.get(
    "/users/me/subscription",
    response_model=SubscriptionStatusResponse,
)
async def get_subscription_status(
        user_id: str = Depends(get_current_user_id),
        db_repo: DBRepository = Depends(get_db_repo),
):
    subscription = await db_repo.subscriptions.get_by_user_id(user_id)

    if subscription is None:
        return SubscriptionStatusResponse(is_premium=False)

    return SubscriptionStatusResponse(
        is_premium=subscription.is_premium,
        expires_at=subscription.expires_at,
    )


@router.post("/billing/verify/google", response_model=VerifyPurchaseResponse)
async def verify_purchase(
        data: VerifyPurchaseRequest,
        user_id: str = Depends(get_current_user_id),
        db_repo: DBRepository = Depends(get_db_repo),
        httpx_client=Depends(get_httpx_client),
):
    Logger.info(f"Verifying purchase for user {user_id}")

    existing = await db_repo.subscriptions.get_by_purchase_token(data.purchase_token)
    if existing is not None:
        if existing.user_id == user_id:
            Logger.info(f"Purchase token already processed for user {user_id}")
            return VerifyPurchaseResponse(
                is_premium=existing.is_premium,
                expires_at=existing.expires_at,
            )
        Logger.warning(
            f"Purchase token belongs to a different user "
            f"(existing={existing.user_id}, requested={user_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Purchase token does not belong to this user",
        )

    google_play = GooglePlayClient(httpx_client)

    # 1. Verify the purchase token with Google
    verified_purchase = await google_play.verify_purchase_token(
        data.product_id, data.purchase_token
    )

    # 2. Acknowledge the purchase
    await google_play.acknowledge_purchase(data.purchase_token)

    # 3. Extract typed subscription data
    sub_data = extract_subscription_data(verified_purchase, data.product_id)

    # 4. Create or update subscription in DB + log history (single transaction)
    try:
        await db_repo.subscriptions.create_or_update(
            user_id=user_id,
            purchase_token=data.purchase_token,
            product_id=sub_data.product_id,
            platform=sub_data.platform,
            starts_at=sub_data.starts_at,
            expires_at=sub_data.expires_at,
            status=sub_data.status.value,
            is_premium=sub_data.status.grants_premium,
        )

        await db_repo.subscriptions.log_history(
            user_id=user_id,
            event_type="PURCHASED",
            platform=Platform.GOOGLE.value,
            purchase_token=data.purchase_token,
            product_id=data.product_id,
            raw_payload=verified_purchase,
        )

        await db_repo.subscriptions.commit()
    except Exception:
        await db_repo.subscriptions.rollback()
        raise

    Logger.info(
        f"Purchase verified for user {user_id} – premium={sub_data.status.grants_premium}"
    )

    return VerifyPurchaseResponse(
        is_premium=sub_data.status.grants_premium,
        expires_at=sub_data.expires_at,
    )


@router.post("/billing/webhook/google")
async def google_play_webhook(
        request: Request,
        db_repo: DBRepository = Depends(get_db_repo),
):
    # 1. Verify signature
    signature = request.headers.get("x-goog-signature")
    if not signature:
        Logger.warning("Missing x-goog-signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature",
        )

    body_bytes = await request.body()
    _verify_pubsub_signature(signature, body_bytes)

    # 2. Decode Pub/Sub envelope
    body = await request.json()
    notification_payload = _decode_pubsub_payload(body)

    # 3. Extract and validate notification type
    notification_type = extract_notification_type(notification_payload)
    if notification_type is None:
        Logger.warning("Notification type not found in payload")
        return {"status": "ignored", "reason": "unknown_notification_type"}

    Logger.info(f"Processing notification: {notification_type.name}")

    # 4. Extract subscription notification data
    subscription_data = notification_payload.get("subscriptionNotification")
    if subscription_data is None:
        Logger.warning("No subscriptionNotification in payload")
        return {"status": "ignored", "reason": "no_subscription_data"}

    purchase_token = subscription_data.get("purchaseToken")
    if purchase_token is None:
        Logger.warning("No purchaseToken in notification")
        return {"status": "ignored", "reason": "no_purchase_token"}

    # 5. Look up subscription
    subscription = await db_repo.subscriptions.get_by_purchase_token(purchase_token)
    if subscription is None:
        Logger.error(
            f"No subscription found for purchase_token: {purchase_token[:20]}..."
        )
        return {"status": "ignored", "reason": "unknown_purchase_token"}

    # 6. Validate product_id matches
    notification_product_id = subscription_data.get("subscriptionId")
    if notification_product_id and notification_product_id != subscription.product_id:
        Logger.warning(
            f"Product ID mismatch: notification={notification_product_id}, "
            f"stored={subscription.product_id}"
        )
        return {"status": "ignored", "reason": "product_id_mismatch"}

    # 7. Map notification to status
    new_status = map_notification_to_status(notification_type)
    if new_status is None:
        Logger.info(f"Informational notification {notification_type.name}, no status change")
        return {"status": "ignored", "reason": "informational_notification"}

    # 8. Update subscription + log history (single transaction)
    try:
        subscription.status = new_status.value
        subscription.is_premium = new_status.grants_premium
        await db_repo.subscriptions.update(subscription)

        await db_repo.subscriptions.log_history(
            user_id=subscription.user_id,
            event_type=notification_type.name,
            platform=Platform.GOOGLE.value,
            purchase_token=purchase_token,
            product_id=subscription.product_id,
            raw_payload=notification_payload,
        )

        await db_repo.subscriptions.commit()
    except Exception:
        await db_repo.subscriptions.rollback()
        raise

    return {"status": "processed", "notification_type": notification_type.name}
