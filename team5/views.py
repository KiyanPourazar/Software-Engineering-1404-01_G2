from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model

from core.auth import api_login_required
from .serializers import Team5Serializer
from .services.contracts import DEFAULT_LIMIT
from .services.db_provider import DatabaseProvider
from .services.location_service import get_client_ip, resolve_client_city
from .services.recommendation_service import RecommendationService

TEAM_NAME = "team5"
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
def get_registered_users(request):
    users = User.objects.filter(is_active=True).order_by("-date_joined")
    payload = [Team5Serializer.serialize_user(user) for user in users]
    return JsonResponse({"count": len(payload), "items": payload})


@require_GET
def get_user_ratings(request, user_id: str):
    ratings = recommendation_service.get_user_ratings(user_id=user_id)
    return JsonResponse({"userId": user_id, "count": len(ratings), "items": ratings})


@require_GET
def get_user_interests(request, user_id: str):
    interests = recommendation_service.get_user_interest_distribution(user_id=user_id)
    return JsonResponse(interests)


@require_GET
def get_popular_recommendations(request):
    limit = _parse_limit(request)
    items = recommendation_service.get_popular(limit=limit)
    return JsonResponse({
        "kind": "popular",
        "limit": limit,
        "count": len(items),
        "items": items,
    })


@require_GET
def get_nearest_recommendations(request):
    limit = _parse_limit(request)
    city_override = request.GET.get("cityId")
    ip_override = request.GET.get("ip")
    client_ip = get_client_ip(request, ip_override=ip_override)

    resolved = resolve_client_city(
        cities=provider.get_cities(),
        client_ip=client_ip,
        preferred_city_id=city_override,
    )

    if not resolved:
        return JsonResponse({
            "kind": "nearest", "source": "unresolved", "clientIp": client_ip,
            "items": [], "count": 0, "limit": limit
        }, status=400)

    items = recommendation_service.get_nearest_by_city(city_id=resolved["city"]["cityId"], limit=limit)
    return JsonResponse(Team5Serializer.serialize_nearest_response(resolved, items, client_ip, limit))


@require_GET
def get_personalized_recommendations(request):
    limit = _parse_limit(request)
    user_id = request.GET.get("userId") or (str(request.user.id) if request.user.is_authenticated else None)

    if not user_id:
        return JsonResponse({"detail": "userId query param is required"}, status=400)

    items = recommendation_service.get_personalized(user_id=user_id, limit=limit)
    source = "personalized"
    if not items:
        items = recommendation_service.get_popular(limit=limit)
        source = "fallback_popular"

    return JsonResponse(Team5Serializer.serialize_personalized_response(items, user_id, source, limit))


def _parse_limit(request) -> int:
    try:
        return max(1, min(int(request.GET.get("limit", DEFAULT_LIMIT)), 100))
    except (ValueError, TypeError):
        return DEFAULT_LIMIT