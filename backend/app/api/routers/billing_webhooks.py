import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.stripe_billing import handle_stripe_event, init_stripe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])


@router.post("/billing/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhooks not configured")
    payload = await request.body()
    sig = request.headers.get("stripe-signature") or ""
    init_stripe()
    import stripe

    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except ValueError as e:
        logger.warning("stripe webhook invalid payload: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload") from e
    except stripe.error.SignatureVerificationError as e:
        logger.warning("stripe webhook bad signature: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature") from e

    ev: dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)  # type: ignore[arg-type]

    db = SessionLocal()
    try:
        handle_stripe_event(db, ev)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("stripe webhook handler failed")
        raise HTTPException(status_code=500, detail="Webhook processing failed") from None
    finally:
        db.close()
    return {"received": "true"}
