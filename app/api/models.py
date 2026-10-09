"""Veritabanı görüntüsünü ortak API cevabına dönüştürür."""

from datetime import datetime, timedelta

from app.api.schemas import ProductResponse
from app.database.read import ProductSnapshot
from app.price_statistics import calculate_statistics


def product_response(
    snapshot: ProductSnapshot, generated_at: datetime
) -> ProductResponse:
    checked_at = snapshot.best_offer.checked_at if snapshot.best_offer else None
    age = generated_at - checked_at if checked_at is not None else None
    return ProductResponse.model_validate(
        {
            "product": snapshot.product,
            "state": snapshot.state,
            "current": snapshot.current,
            "checks": snapshot.checks,
            "best_offer": snapshot.best_offer,
            "last_successful_offer": snapshot.last_successful_offer,
            "history": snapshot.history,
            "cimri_history": snapshot.cimri_history,
            "statistics": calculate_statistics(snapshot),
            "generated_at": generated_at,
            "price_age_seconds": (
                max(0.0, age.total_seconds()) if age is not None else None
            ),
            "is_stale": age >= timedelta(hours=18) if age is not None else None,
        }
    )
