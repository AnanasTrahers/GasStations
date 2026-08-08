from fastapi import APIRouter, Depends

from src.dependencies import get_current_user_id, get_db_repo
from src.repositories import DBRepository
from src.schemas import SubscriptionStatusResponse

router = APIRouter(tags=["Subscriptions"])

@router.get(
    "/users/me/subscription",
    response_model=SubscriptionStatusResponse
)
async def get_subscription_status(
        user_id: str = Depends(get_current_user_id),
        db_repo: DBRepository = Depends(get_db_repo)
):
    subscription = await db_repo.subscriptions.get_by_user_id(user_id)

    return SubscriptionStatusResponse(is_premium=subscription.is_premium)
