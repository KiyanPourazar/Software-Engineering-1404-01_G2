import json
import hashlib
from uuid import UUID
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.auth import api_login_required
from .models import Team5MediaComment, Team5RecommendationFeedback
from .serializers import Team5Serializer
from .services.contracts import DEFAULT_LIMIT
from .services.db_provider import DatabaseProvider
from .services.location_service import get_client_ip, resolve_client_city
from .services.occasions_catalog import ensure_occasion_media_seeded
from .services.recommendation_service import RecommendationService

# Constants
TEAM_NAME = "team5"
FEEDBACK_ACTIONS = {"popular", "personalized", "nearest", "weather", "occasions", "random"}
AB_ALLOWED_STRATEGIES = {"personalized", "popular", "nearest", "weather", "occasions", "random"}
AB_ALLOWED_GROUPS = {"A", "B"}
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
def get_media_comments(request, media_id: str):
    comments = list(
        Team5MediaComment.objects.filter(media_id=str(media_id))
        .order_by("-created_at")
        .only("user_id", "user_email", "body", "sentiment_label", "sentiment_score", "created_at")
    )
    user_ids = [comment.user_id for comment in comments]
    users = User.objects.filter(id__in=user_ids).only("id", "first_name", "last_name", "email")
    users_by_id = {user.id: user for user in users}

    def _display_name_for_comment(comment: Team5MediaComment) -> str:
        user = users_by_id.get(comment.user_id)
        if user:
            first_name = (user.first_name or "").strip()
            last_name = (user.last_name or "").strip()
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                return full_name
            if (user.email or "").strip():
                return user.email.split("@")[0]
        if (comment.user_email or "").strip():
            return comment.user_email.split("@")[0]
        return str(comment.user_id)

    payload = [
        {
            "userId": str(comment.user_id),
            "userEmail": comment.user_email,
            "userDisplayName": _display_name_for_comment(comment),
            "body": comment.body,
            "sentimentLabel": comment.sentiment_label,
            "sentimentScore": round(float(comment.sentiment_score), 3),
            "createdAt": comment.created_at.isoformat(),
        }
        for comment in comments
    ]
    return JsonResponse({"mediaId": media_id, "count": len(payload), "items": payload})


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
def get_random_recommendations(request):
    # Curious mode: intentionally random, regardless of user preferences.
    limit = _parse_limit(request)
    limit = max(10, limit)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="random")
    items = recommendation_service.get_random(
        limit=limit,
        user_id=user_id,
        excluded_media_ids=excluded,
    )
    return JsonResponse({
        "kind": "random",
        "title": "For Curious Users",
        "userId": user_id,
        "limit": limit,
        "count": len(items),
        "items": items,
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
        fallback_user_id = str(request.user.id) if getattr(request.user, "is_authenticated", False) else None
        user_uuid = _parse_uuid(payload.get("userId")) or _parse_uuid(fallback_user_id)
        action = str(payload.get("action") or "").strip().lower()
        liked = payload.get("liked")

        # Capture requested A/B version for API response/debugging.
        # Group assignment for analytics is deterministic by user_id.
        ab_version = _normalize_ab_version(payload.get("version"))
        assigned_group = _resolve_ab_group(user_id=str(user_uuid), requested_version=ab_version)

        if not user_uuid or action not in FEEDBACK_ACTIONS or not isinstance(liked, bool):
            raise ValueError("Invalid payload data provided.")

        # Save feedback specifically to the 'team5' database
        Team5RecommendationFeedback.objects.using("team5").create(
            user_id=user_uuid,
            action=action,
            liked=liked,
            shown_media_ids=list(
                dict.fromkeys([str(m).strip() for m in payload.get("shownMediaIds", []) if str(m).strip()])
            )
        )
        return JsonResponse({
            "ok": True,
            "detail": f"Feedback successfully saved for version {assigned_group}",
            "abTest": {
                "requestedVersion": ab_version,
                "assignedGroup": assigned_group,
            },
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

    requested_version = _normalize_ab_version(request.GET.get("version"))
    strategy = str(request.GET.get("strategy", "personalized") or "personalized").strip().lower()
    if strategy not in AB_ALLOWED_STRATEGIES:
        strategy = "personalized"

    if not user_id:
        return JsonResponse({
            "status": "error",
            "message": "userId is required as a query parameter."
        }, status=400)

    assigned_group = _resolve_ab_group(user_id=user_id, requested_version=requested_version)
    excluded = _load_excluded_media_ids(user_id=user_id, action=strategy)

    if assigned_group == "B":
        items = _build_variant_b_items(
            strategy=strategy,
            user_id=user_id,
            limit=limit,
            excluded_media_ids=excluded,
        )
        applied_method = f"{strategy}_variant_b_mixed"
    else:
        items = _get_items_for_strategy(
            strategy=strategy,
            user_id=user_id,
            limit=limit,
            excluded_media_ids=excluded,
        )
        applied_method = strategy

    # Return a structured JSON response with metadata for transparency
    return JsonResponse({
        "status": "success",
        "metadata": {
            "team": "team5",
            "api_version": "v2.0",
            "ab_test_group": assigned_group,
            "requested_version": requested_version,
            "applied_strategy": applied_method,
            "requested_strategy": strategy,
            "limit": limit,
        },
        "data": {
            "userId": user_id,
            "count": len(items),
            "items": items,
        }
    })


@require_GET
def get_ab_test_summary(request):
    """
    Aggregate A/B feedback metrics from Team5 feedback logs.
    Group assignment is deterministic by user_id, so we can evaluate past data
    even if clients did not always send version explicitly.
    """
    action_filter = str(request.GET.get("action", "") or "").strip().lower()

    try:
        days = int(request.GET.get("days", 30))
        days = max(1, min(days, 365))
    except (TypeError, ValueError):
        days = 30

    since = timezone.now() - timezone.timedelta(days=days)

    # Optimization: Use select_related/only and iterator to save memory on large datasets
    feedback_qs = Team5RecommendationFeedback.objects.using("team5").filter(
        created_at__gte=since
    ).only("user_id", "action", "liked", "created_at")

    if action_filter:
        feedback_qs = feedback_qs.filter(action=action_filter)

    # Use iterator() instead of list() to handle large datasets efficiently
    rows = feedback_qs.iterator()

    summary = {
        "A": {"impressions": 0, "likes": 0, "dislikes": 0, "users": set()},
        "B": {"impressions": 0, "likes": 0, "dislikes": 0, "users": set()},
    }
    by_action: dict[str, dict[str, dict[str, int | float]]] = {}

    for row in rows:
        user_id_str = str(row.user_id)
        group = _resolve_ab_group(user_id=user_id_str, requested_version="AUTO")
        action = str(row.action or "").strip().lower() or "unknown"
        liked_int = 1 if row.liked else 0

        # Update Main Summary
        bucket = summary[group]
        bucket["impressions"] += 1
        bucket["likes"] += liked_int
        bucket["dislikes"] += 0 if row.liked else 1
        bucket["users"].add(user_id_str)

        # Update By-Action Summary using setdefault for cleaner logic
        if action not in by_action:
            by_action[action] = {
                "A": {"impressions": 0, "likes": 0, "likeRate": 0.0},
                "B": {"impressions": 0, "likes": 0, "likeRate": 0.0},
            }

        action_bucket = by_action[action][group]
        action_bucket["impressions"] += 1
        action_bucket["likes"] += liked_int

    def _finalize_group_stats(data: dict) -> dict:
        impressions = int(data["impressions"])
        likes = int(data["likes"])
        dislikes = int(data["dislikes"])
        users_count = len(data["users"])
        like_rate = round((likes / impressions) * 100, 2) if impressions else 0.0
        return {
            "impressions": impressions,
            "likes": likes,
            "dislikes": dislikes,
            "uniqueUsers": users_count,
            "likeRatePercent": like_rate,
        }

    group_a = _finalize_group_stats(summary["A"])
    group_b = _finalize_group_stats(summary["B"])

    # Finalize per-action stats
    for action_data in by_action.values():
        for group in ("A", "B"):
            g_data = action_data[group]
            imp = int(g_data["impressions"])
            likes = int(g_data["likes"])
            g_data["likeRate"] = round((likes / imp) * 100, 2) if imp else 0.0

    return JsonResponse({
        "status": "success",
        "windowDays": days,
        "appliedActionFilter": action_filter or None,
        "groups": {"A": group_a, "B": group_b},
        "deltaLikeRatePercent": round(group_b["likeRatePercent"] - group_a["likeRatePercent"], 2),
        "byAction": by_action,
    })


def _normalize_ab_version(raw_value) -> str:
    value = str(raw_value or "AUTO").strip().upper()
    return value if value in AB_ALLOWED_GROUPS else "AUTO"


def _resolve_ab_group(*, user_id: str, requested_version: str) -> str:
    if requested_version in AB_ALLOWED_GROUPS:
        return requested_version

    # Standardizing logic for readability
    digest = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()
    return "A" if int(digest[:2], 16) % 2 == 0 else "B"


def _get_items_for_strategy(
        *,
        strategy: str,
        user_id: str,
        limit: int,
        excluded_media_ids: set[str],
) -> list[dict]:
    # Using elif to prevent unnecessary checks
    if strategy == "popular":
        return recommendation_service.get_popular(
            limit=limit, excluded_media_ids=excluded_media_ids
        )
    elif strategy == "nearest":
        return recommendation_service.get_nearest_by_city(
            city_id="tehran",
            limit=limit,
            user_id=user_id,
            excluded_media_ids=excluded_media_ids,
        )
    elif strategy == "weather":
        payload = recommendation_service.get_weather_recommendations(
            limit=limit,
            user_id=user_id,
            excluded_media_ids=excluded_media_ids,
        )
        return _extract_items_from_payload(payload)
    elif strategy == "occasions":
        ensure_occasion_media_seeded()
        payload = recommendation_service.get_occasion_recommendations(
            limit=limit,
            user_id=user_id,
            excluded_media_ids=excluded_media_ids,
        )
        return _extract_items_from_payload(payload)
    elif strategy == "random":
        return recommendation_service.get_random(
            limit=limit,
            user_id=user_id,
            excluded_media_ids=excluded_media_ids,
        )

    # Default fallback
    items = recommendation_service.get_personalized(
        user_id=user_id,
        limit=limit,
        excluded_media_ids=excluded_media_ids,
    )
    return items if items else recommendation_service.get_popular(
        limit=limit, excluded_media_ids=excluded_media_ids
    )


def _build_variant_b_items(
        *,
        strategy: str,
        user_id: str,
        limit: int,
        excluded_media_ids: set[str],
) -> list[dict]:
    """
    Variant B mixes baseline strategy with random exploration.
    """
    half = max(1, limit // 2)
    baseline = _get_items_for_strategy(
        strategy=strategy,
        user_id=user_id,
        limit=max(1, limit - half),
        excluded_media_ids=excluded_media_ids,
    )

    baseline_ids = {str(item.get("mediaId")) for item in baseline if item.get("mediaId")}

    exploratory = recommendation_service.get_random(
        limit=max(1, half),
        user_id=user_id,
        excluded_media_ids=excluded_media_ids.union(baseline_ids),
    )

    # Tag items for tracking
    for item in baseline:
        item.update({"abVariant": "B", "abBucket": "baseline"})
    for item in exploratory:
        item.update({"abVariant": "B", "abBucket": "explore"})

    # Interleave items (A, B, A, B...)
    merged: list[dict] = []
    left, right = list(baseline), list(exploratory)

    while (left or right) and len(merged) < limit:
        if left:
            merged.append(left.pop(0))
            if len(merged) >= limit: break
        if right:
            merged.append(right.pop(0))

    return merged[:limit]


def _extract_items_from_payload(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    # Check for direct items list
    if isinstance(payload.get("items"), list):
        return payload["items"]

    sections = payload.get("sections")
    if not isinstance(sections, list):
        return []

    items: list[dict] = []
    seen_ids: set[str] = set()

    for section in sections:
        if not isinstance(section, dict):
            continue

        section_items = section.get("items")
        if not section_items:
            continue

        for item in section_items:
            media_id = str(item.get("mediaId") or "").strip()

            if media_id:
                if media_id in seen_ids:
                    continue
                seen_ids.add(media_id)

            items.append(item)

    return items