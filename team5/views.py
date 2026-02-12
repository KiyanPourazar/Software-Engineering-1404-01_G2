import json
from uuid import UUID
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import get_user_model

from core.auth import api_login_required
from .models import Team5RecommendationFeedback
from .serializers import Team5Serializer
from .services.contracts import DEFAULT_LIMIT
from .services.db_provider import DatabaseProvider
from .services.location_service import get_client_ip, resolve_client_city
from .services.occasions_catalog import ensure_occasion_media_seeded
from .services.recommendation_service import RecommendationService

# Constants
TEAM_NAME = "team5"
FEEDBACK_ACTIONS = {"popular", "personalized", "nearest", "weather", "occasions"}
User = get_user_model()
provider = DatabaseProvider()
recommendation_service = RecommendationService(provider)


@api_login_required
def ping(request):
    return JsonResponse({"team": TEAM_NAME, "ok": True})


def base(request):
    return render(request, f"{TEAM_NAME}/index.html")


@require_GET
def get_cities(request):
    return JsonResponse(provider.get_cities(), safe=False)


@require_GET
def get_city_places(request, city_id: str):
    return JsonResponse(provider.get_city_places(city_id), safe=False)


@require_GET
def get_media(request):
    user_id = request.GET.get("userId")
    feed = recommendation_service.get_media_feed(user_id=user_id)
    return JsonResponse(feed)


@require_GET
def get_popular_recommendations(request):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="popular")
    items = recommendation_service.get_popular(limit=limit, excluded_media_ids=excluded)
    return JsonResponse({
        "kind": "popular", "userId": user_id, "limit": limit, "count": len(items), "items": items
    })


@require_GET
def get_nearest_recommendations(request):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="nearest")

    client_ip = get_client_ip(request, ip_override=request.GET.get("ip"))
    resolved = resolve_client_city(
        cities=provider.get_cities(), client_ip=client_ip, preferred_city_id=request.GET.get("cityId")
    )

    if not resolved:
        return JsonResponse({"kind": "nearest", "source": "unresolved", "clientIp": client_ip, "items": []}, status=400)

    items = recommendation_service.get_nearest_by_city(
        city_id=resolved["city"]["cityId"], limit=limit, excluded_media_ids=excluded, user_id=user_id
    )
    return JsonResponse(Team5Serializer.serialize_nearest(items, resolved, client_ip, limit, user_id))


@require_GET
def get_personalized_recommendations(request):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId") or (
        str(request.user.id) if getattr(request.user, "is_authenticated", False) else None)

    if not user_id:
        return JsonResponse({"detail": "userId query param is required"}, status=400)

    excluded = _load_excluded_media_ids(user_id=user_id, action="personalized")
    items = recommendation_service.get_personalized(user_id=user_id, limit=limit, excluded_media_ids=excluded)

    source = "personalized"
    if not items:
        items = recommendation_service.get_popular(limit=limit, excluded_media_ids=excluded)
        source = "fallback_popular"

    return JsonResponse(Team5Serializer.serialize_personalized(items, user_id, source, limit))


@require_GET
def get_weather_recommendations(request):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded_media_ids = _load_excluded_media_ids(user_id=user_id, action="weather")
    payload = recommendation_service.get_weather_recommendations(
        limit=limit,
        user_id=user_id,
        excluded_media_ids=excluded_media_ids,
    )
    payload["limit"] = limit
    payload["userId"] = user_id
    payload["count"] = sum(len(section.get("items") or []) for section in payload.get("sections") or [])
    return JsonResponse(payload)


@require_GET
def get_occasion_recommendations(request):
    ensure_occasion_media_seeded()
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded_media_ids = _load_excluded_media_ids(user_id=user_id, action="occasions")
    payload = recommendation_service.get_occasion_recommendations(
        limit=limit,
        user_id=user_id,
        excluded_media_ids=excluded_media_ids,
    )
    payload["limit"] = limit
    payload["userId"] = user_id
    payload["count"] = sum(len(section.get("items") or []) for section in payload.get("sections") or [])
    return JsonResponse(payload)


# @csrf_exempt
# @require_POST
# def submit_recommendation_feedback(request):
#     try:
#         payload = json.loads(request.body or "{}")
#         user_uuid = _parse_uuid(payload.get("userId"))
#         action = str(payload.get("action") or "").strip().lower()
#         liked = payload.get("liked")
#
#         if not user_uuid or action not in FEEDBACK_ACTIONS or not isinstance(liked, bool):
#             raise ValueError("Invalid payload data")
#
#         Team5RecommendationFeedback.objects.create(
#             user_id=user_uuid, action=action, liked=liked,
#             shown_media_ids=list(
#                 dict.fromkeys([str(m).strip() for m in payload.get("shownMediaIds", []) if str(m).strip()]))
#         )
#         return JsonResponse({"ok": True, "detail": "Feedback saved"})
#     except (json.JSONDecodeError, ValueError) as e:
#         return JsonResponse({"detail": str(e)}, status=400)
@csrf_exempt
@require_POST
def submit_recommendation_feedback(request):
    """
    Captures user interaction (likes/dislikes) for specific recommendation results.
    Crucial for evaluating A/B test performance and refining ML models.
    """
    try:
        payload = json.loads(request.body or "{}")
        user_uuid = _parse_uuid(payload.get("userId"))
        action = str(payload.get("action") or "").strip().lower()
        liked = payload.get("liked")

        # Capture the A/B version to analyze conversion rates per group
        ab_version = payload.get("version", "A").upper()

        if not user_uuid or action not in FEEDBACK_ACTIONS or not isinstance(liked, bool):
            raise ValueError("Invalid payload data provided.")

        # Save feedback specifically to the 'team5' database
        Team5RecommendationFeedback.objects.using('team5').create(
            user_id=user_uuid,
            action=action,
            liked=liked,
            ab_version=ab_version,
            shown_media_ids=list(
                dict.fromkeys([str(m).strip() for m in payload.get("shownMediaIds", []) if str(m).strip()])
            )
        )
        return JsonResponse({
            "ok": True,
            "detail": f"Feedback successfully saved for version {ab_version}"
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({"detail": str(e)}, status=400)

@require_GET
def get_user_interests(request, user_id: str):
    return JsonResponse(recommendation_service.get_user_interest_distribution(user_id=user_id))


@require_GET
def get_registered_users(request):
    users = User.objects.filter(is_active=True).order_by("-date_joined")
    payload = [Team5Serializer.serialize_user(u) for u in users]
    return JsonResponse({"count": len(payload), "items": payload})


@require_GET
def get_user_ratings(request, user_id: str):
    ratings = recommendation_service.get_user_ratings(user_id=user_id)
    return JsonResponse({"userId": user_id, "count": len(ratings), "items": ratings})


@csrf_exempt
@require_POST
def train(request):
    return JsonResponse({"trained": bool(recommendation_service.train())})


@require_GET
def ml_status(request):
    return JsonResponse(recommendation_service.get_ml_status())


# Helper functions
def _parse_limit(request) -> int:
    try:
        return max(1, min(int(request.GET.get("limit", DEFAULT_LIMIT)), 100))
    except (ValueError, TypeError):
        return DEFAULT_LIMIT


def _parse_uuid(value: str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except:
        return None


def _load_excluded_media_ids(*, user_id: str | None, action: str) -> set[str]:
    user_uuid = _parse_uuid(user_id)
    if not user_uuid: return set()
    latest = Team5RecommendationFeedback.objects.filter(user_id=user_uuid, action=action).order_by("-created_at",
                                                                                                   "-id").first()
    if not latest or latest.liked: return set()
    return {str(m).strip() for m in latest.shown_media_ids or [] if str(m).strip()}


@require_GET
def get_recommendations_api(request):
    """
    Official API endpoint for external teams to fetch recommendations.
    Supports: A/B Testing, Strategy Selection, and Result Limiting.
    """
    user_id = request.GET.get("userId")
    limit = _parse_limit(request)

    # Manage A/B Testing versions (Default is 'A')
    # Use version='B' as a query param to trigger the test variant
    version = request.GET.get("version", "A").upper()

    # Strategy pattern: client can choose between 'personalized', 'weather', or 'popular'
    strategy = request.GET.get("strategy", "personalized")

    if not user_id:
        return JsonResponse({
            "status": "error",
            "message": "userId is required as a query parameter."
        }, status=400)

    # Logic for A/B Testing: version 'B' triggers a specific test algorithm
    if version == "B":
        # Variant B: Testing recommendations based on specific occasions
        items = recommendation_service.get_occasion_recommendations(user_id=user_id, limit=limit)
        applied_method = "occasion_test_v2"
    else:
        # Variant A (Control): Follow the requested strategy
        if strategy == "weather":
            items = recommendation_service.get_weather_recommendations(user_id=user_id, limit=limit)
        elif strategy == "popular":
            items = recommendation_service.get_popular(limit=limit)
        elif strategy == "nearest":
            # Fetches location-based content (Tehran used as default fallback)
            items = recommendation_service.get_nearest_by_city(city_id="tehran", limit=limit)
        else:
            # Default strategy: Collaborative filtering / Personalization
            items = recommendation_service.get_personalized(user_id=user_id, limit=limit)
        applied_method = strategy

    # Return a structured JSON response with metadata for transparency
    return JsonResponse({
        "status": "success",
        "metadata": {
            "team": "team5",
            "api_version": "v2.0",
            "ab_test_group": version,
            "applied_strategy": applied_method,
            "limit": limit
        },
        "data": {
            "userId": user_id,
            "count": len(items),
            "items": items
        }
    })

@require_GET
def get_random_media_recommendations(request):
    limit = _parse_limit(request)
    items = provider.get_random_media(limit=limit)
    return JsonResponse({
        "status": "success",
        "count": len(items),
        "items": items
    })