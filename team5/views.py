import json
import hashlib
from uuid import UUID
from typing import List, Dict, Set, Optional, Any

from django.http import JsonResponse, HttpRequest
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

# --- Configuration & Constants ---
TEAM_NAME = "team5"
User = get_user_model()

# Dependency Injection
provider = DatabaseProvider()
recommendation_service = RecommendationService(provider)

# A/B Testing Constants
FEEDBACK_ACTIONS = {"popular", "personalized", "nearest", "weather", "occasions", "random", "click", "view", "like",
                    "dislike"}
AB_ALLOWED_STRATEGIES = {"personalized", "popular", "nearest", "weather", "occasions", "random"}
AB_ALLOWED_GROUPS = {"A", "B"}


# --- Section 1: General & Utility Views ---

@api_login_required
def ping(request: HttpRequest):
    """Health check endpoint."""
    return JsonResponse({"team": TEAM_NAME, "ok": True})


def base(request: HttpRequest):
    """Renders the main entry point (HTML)."""
    return render(request, f"{TEAM_NAME}/index.html")


@require_GET
def get_cities(request: HttpRequest):
    """Returns list of supported cities."""
    return JsonResponse(provider.get_cities(), safe=False)


@require_GET
def get_city_places(request: HttpRequest, city_id: str):
    """Returns places for a specific city."""
    return JsonResponse(provider.get_city_places(city_id), safe=False)


# --- Section 2: Media & Comments ---

@require_GET
def get_media(request: HttpRequest):
    """Fetches the general media feed."""
    user_id = request.GET.get("userId")
    feed = recommendation_service.get_media_feed(user_id=user_id)
    return JsonResponse(feed)


@require_GET
def get_media_comments(request: HttpRequest, media_id: str):
    """
    Fetches comments for a media item with user details enriched.
    Optimized to prevent N+1 queries.
    """
    comments = list(
        Team5MediaComment.objects.filter(media_id=str(media_id))
        .order_by("-created_at")
        .only("user_id", "user_email", "body", "sentiment_label", "sentiment_score", "created_at")
    )

    if not comments:
        return JsonResponse({"mediaId": media_id, "count": 0, "items": []})

    # Bulk fetch users to avoid N+1
    user_ids = {comment.user_id for comment in comments}
    users = User.objects.filter(id__in=user_ids).only("id", "first_name", "last_name", "email")
    users_by_id = {user.id: user for user in users}

    def _resolve_display_name(comment_obj, user_obj):
        """Helper to determine the best display name."""
        if user_obj:
            full_name = f"{user_obj.first_name or ''} {user_obj.last_name or ''}".strip()
            if full_name:
                return full_name
            if user_obj.email:
                return user_obj.email.split("@")[0]

        if comment_obj.user_email:
            return comment_obj.user_email.split("@")[0]
        return str(comment_obj.user_id)

    payload = []
    for comment in comments:
        user_obj = users_by_id.get(comment.user_id)
        payload.append({
            "userId": str(comment.user_id),
            "userEmail": comment.user_email,
            "userDisplayName": _resolve_display_name(comment, user_obj),
            "body": comment.body,
            "sentimentLabel": comment.sentiment_label,
            "sentimentScore": round(float(comment.sentiment_score), 3),
            "createdAt": comment.created_at.isoformat(),
        })

    return JsonResponse({"mediaId": media_id, "count": len(payload), "items": payload})


# --- Section 3: Specific Strategy Endpoints ---

@require_GET
def get_popular_recommendations(request: HttpRequest):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="popular")

    items = recommendation_service.get_popular(limit=limit, excluded_media_ids=excluded)

    return JsonResponse({
        "kind": "popular",
        "userId": user_id,
        "limit": limit,
        "count": len(items),
        "items": items
    })


@require_GET
def get_random_recommendations(request: HttpRequest):
    """Curious mode: intentionally random."""
    limit = max(10, _parse_limit(request))
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
def get_nearest_recommendations(request: HttpRequest):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="nearest")

    client_ip = get_client_ip(request, ip_override=request.GET.get("ip"))
    resolved = resolve_client_city(
        cities=provider.get_cities(),
        client_ip=client_ip,
        preferred_city_id=request.GET.get("cityId")
    )

    if not resolved:
        return JsonResponse({
            "kind": "nearest",
            "source": "unresolved",
            "clientIp": client_ip,
            "items": []
        }, status=400)

    items = recommendation_service.get_nearest_by_city(
        city_id=resolved["city"]["cityId"],
        limit=limit,
        excluded_media_ids=excluded,
        user_id=user_id
    )
    return JsonResponse(Team5Serializer.serialize_nearest(items, resolved, client_ip, limit, user_id))


@require_GET
def get_personalized_recommendations(request: HttpRequest):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")

    # Fallback to authenticated user ID if not provided in query params
    if not user_id and getattr(request.user, "is_authenticated", False):
        user_id = str(request.user.id)

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
def get_weather_recommendations(request: HttpRequest):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="weather")

    payload = recommendation_service.get_weather_recommendations(
        limit=limit,
        user_id=user_id,
        excluded_media_ids=excluded,
    )

    # Enrich payload
    payload.update({
        "limit": limit,
        "userId": user_id,
        "count": sum(len(section.get("items") or []) for section in payload.get("sections") or [])
    })
    return JsonResponse(payload)


@require_GET
def get_occasion_recommendations(request: HttpRequest):
    ensure_occasion_media_seeded()
    limit = _parse_limit(request)
    user_id = request.GET.get("userId")
    excluded = _load_excluded_media_ids(user_id=user_id, action="occasions")

    payload = recommendation_service.get_occasion_recommendations(
        limit=limit,
        user_id=user_id,
        excluded_media_ids=excluded,
    )

    payload.update({
        "limit": limit,
        "userId": user_id,
        "count": sum(len(section.get("items") or []) for section in payload.get("sections") or [])
    })
    return JsonResponse(payload)


# --- Section 4: Main API & A/B Testing ---

@require_GET
def get_recommendations_api(request: HttpRequest):
    """
    Official API endpoint for external teams.
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


@csrf_exempt
@require_POST
def submit_recommendation_feedback(request: HttpRequest):
    """
    Captures user interaction (likes/dislikes) for A/B testing and training.
    """
    try:
        payload = json.loads(request.body or "{}")

        # Determine User ID
        fallback_user_id = str(request.user.id) if getattr(request.user, "is_authenticated", False) else None
        user_uuid = _parse_uuid(payload.get("userId")) or _parse_uuid(fallback_user_id)

        action = str(payload.get("action") or "").strip().lower()
        liked = payload.get("liked")

        # Validate
        if not user_uuid or not isinstance(liked, bool):
            raise ValueError("Invalid payload: userId and liked status are required.")
        if action not in FEEDBACK_ACTIONS and "action" in payload:
            # Relaxed check: if action is missing/wrong, we might still want to log,
            # but keeping strict for now as per previous logic.
            pass

            # A/B Logic
        ab_version = _normalize_ab_version(payload.get("version"))
        assigned_group = _resolve_ab_group(user_id=str(user_uuid), requested_version=ab_version)

        # Parse Shown Media IDs uniquely
        shown_ids = list(dict.fromkeys([
            str(m).strip() for m in payload.get("shownMediaIds", []) if str(m).strip()
        ]))

        Team5RecommendationFeedback.objects.using("team5").create(
            user_id=user_uuid,
            action=action,
            liked=liked,
            shown_media_ids=shown_ids
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
def get_ab_test_summary(request: HttpRequest):
    """
    Analytics endpoint to evaluate A/B test performance.
    """
    action_filter = str(request.GET.get("action", "") or "").strip().lower()

    try:
        days = max(1, min(int(request.GET.get("days", 30)), 365))
    except (TypeError, ValueError):
        days = 30

    since = timezone.now() - timezone.timedelta(days=days)

    feedback_qs = Team5RecommendationFeedback.objects.using("team5").filter(
        created_at__gte=since
    ).only("user_id", "action", "liked", "created_at")

    if action_filter:
        feedback_qs = feedback_qs.filter(action=action_filter)

    # Use iterator for memory efficiency
    rows = feedback_qs.iterator()

    summary = {
        "A": {"impressions": 0, "likes": 0, "dislikes": 0, "users": set()},
        "B": {"impressions": 0, "likes": 0, "dislikes": 0, "users": set()},
    }
    by_action: dict = {}

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

        # Update By-Action Summary
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


# --- Section 5: Admin & ML Views ---

@require_GET
def get_user_interests(request: HttpRequest, user_id: str):
    return JsonResponse(recommendation_service.get_user_interest_distribution(user_id=user_id))


@require_GET
def get_registered_users(request: HttpRequest):
    users = User.objects.filter(is_active=True).order_by("-date_joined")
    payload = [Team5Serializer.serialize_user(u) for u in users]
    return JsonResponse({"count": len(payload), "items": payload})


@require_GET
def get_user_ratings(request: HttpRequest, user_id: str):
    ratings = recommendation_service.get_user_ratings(user_id=user_id)
    return JsonResponse({"userId": user_id, "count": len(ratings), "items": ratings})


@csrf_exempt
@require_POST
def train(request: HttpRequest):
    return JsonResponse({"trained": bool(recommendation_service.train())})


@require_GET
def ml_status(request: HttpRequest):
    return JsonResponse(recommendation_service.get_ml_status())


# --- Section 6: Helper Functions (Internal Logic) ---

def _parse_limit(request: HttpRequest) -> int:
    try:
        return max(1, min(int(request.GET.get("limit", DEFAULT_LIMIT)), 100))
    except (ValueError, TypeError):
        return DEFAULT_LIMIT


def _parse_uuid(value: Optional[str]) -> Optional[UUID]:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _load_excluded_media_ids(*, user_id: Optional[str], action: str) -> Set[str]:
    user_uuid = _parse_uuid(user_id)
    if not user_uuid:
        return set()

    # Check only the most recent feedback to avoid staleness
    latest = Team5RecommendationFeedback.objects.filter(
        user_id=user_uuid, action=action
    ).order_by("-created_at", "-id").first()

    # If the user liked the last batch, we generally don't exclude them (let them see it again),
    # unless logic dictates otherwise. Here we strictly follow existing logic.
    if not latest or latest.liked:
        return set()

    return {str(m).strip() for m in latest.shown_media_ids or [] if str(m).strip()}


def _normalize_ab_version(raw_value: Any) -> str:
    value = str(raw_value or "AUTO").strip().upper()
    return value if value in AB_ALLOWED_GROUPS else "AUTO"


def _resolve_ab_group(*, user_id: str, requested_version: str) -> str:
    if requested_version in AB_ALLOWED_GROUPS:
        return requested_version

    # Deterministic assignment: MD5(userId) % 2
    # This ensures the same user always gets the same version
    digest = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()
    return "A" if int(digest[:2], 16) % 2 == 0 else "B"


def _get_items_for_strategy(
        *, strategy: str, user_id: str, limit: int, excluded_media_ids: Set[str]
) -> List[Dict]:
    """Router to fetch data based on strategy name."""
    if strategy == "popular":
        return recommendation_service.get_popular(limit=limit, excluded_media_ids=excluded_media_ids)
    elif strategy == "nearest":
        return recommendation_service.get_nearest_by_city(
            city_id="tehran", limit=limit, user_id=user_id, excluded_media_ids=excluded_media_ids
        )
    elif strategy == "weather":
        payload = recommendation_service.get_weather_recommendations(
            limit=limit, user_id=user_id, excluded_media_ids=excluded_media_ids
        )
        return _extract_items_from_payload(payload)
    elif strategy == "occasions":
        ensure_occasion_media_seeded()
        payload = recommendation_service.get_occasion_recommendations(
            limit=limit, user_id=user_id, excluded_media_ids=excluded_media_ids
        )
        return _extract_items_from_payload(payload)
    elif strategy == "random":
        return recommendation_service.get_random(
            limit=limit, user_id=user_id, excluded_media_ids=excluded_media_ids
        )

    # Default fallback
    items = recommendation_service.get_personalized(
        user_id=user_id, limit=limit, excluded_media_ids=excluded_media_ids
    )
    if items:
        return items
    return recommendation_service.get_popular(limit=limit, excluded_media_ids=excluded_media_ids)


def _build_variant_b_items(
        *, strategy: str, user_id: str, limit: int, excluded_media_ids: Set[str]
) -> List[Dict]:
    """
    Variant B Logic: Mixes the requested strategy with random exploration.
    Hypothesis: Adding variety improves user engagement.
    """
    half = max(1, limit // 2)

    # 1. Get baseline items (Strategy A)
    baseline = _get_items_for_strategy(
        strategy=strategy,
        user_id=user_id,
        limit=max(1, limit - half),
        excluded_media_ids=excluded_media_ids,
    )

    baseline_ids = {str(item.get("mediaId")) for item in baseline if item.get("mediaId")}

    # 2. Get exploratory items (Random)
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

    # 3. Interleave items (A, B, A, B...)
    merged: List[Dict] = []
    left, right = list(baseline), list(exploratory)

    while (left or right) and len(merged) < limit:
        if left:
            merged.append(left.pop(0))
            if len(merged) >= limit: break
        if right:
            merged.append(right.pop(0))

    return merged[:limit]


def _extract_items_from_payload(payload: Dict) -> List[Dict]:
    """Flattens nested payloads (like sections) into a simple list of items."""
    if not isinstance(payload, dict):
        return []

    # Check for direct items list
    if isinstance(payload.get("items"), list):
        return payload["items"]

    sections = payload.get("sections")
    if not isinstance(sections, list):
        return []

    items: List[Dict] = []
    seen_ids: Set[str] = set()

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