"""Recommendation scoring for popular and personalized feeds."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from .contracts import (
    DEFAULT_LIMIT,
    PERSONALIZED_MIN_USER_RATE,
    POPULAR_MIN_OVERALL_RATE,
    POPULAR_MIN_VOTES,
    MediaRecord,
    PlaceRecord,
)
from .data_provider import DataProvider
from .occasions_catalog import OCCASION_MEDIA_IDS_BY_OCCASION
from team5.models import Team5MediaRating

try:
    from .ml.recommender_model import RecommenderModel, NotTrainedYetException
except Exception:  # pragma: no cover - optional ML dependencies
    RecommenderModel = None

    class NotTrainedYetException(Exception):
        pass


class RecommendationService:
    def __init__(
        self,
        provider: DataProvider,
        *,
        popular_min_overall_rate: float = POPULAR_MIN_OVERALL_RATE,
        popular_min_votes: int = POPULAR_MIN_VOTES,
        personalized_min_user_rate: float = PERSONALIZED_MIN_USER_RATE,
    ):
        self.provider = provider
        self.popular_min_overall_rate = popular_min_overall_rate
        self.popular_min_votes = popular_min_votes
        self.personalized_min_user_rate = personalized_min_user_rate
        self._ml_enabled = RecommenderModel is not None
        self.personalized_place_recommender_model = RecommenderModel((0, 5)) if self._ml_enabled else None
        self.personalized_media_recommender_model = RecommenderModel((0, 5)) if self._ml_enabled else None
        self._models_ready = False

    def get_popular(
        self,
        limit: int = DEFAULT_LIMIT,
        excluded_media_ids: set[str] | None = None,
    ) -> list[MediaRecord]:
        media = [dict(item) for item in self.provider.get_media()]
        excluded = excluded_media_ids or set()
        filtered = [
            item
            for item in media
            if item["mediaId"] not in excluded
            and float(item["overallRate"]) >= self.popular_min_overall_rate
            and int(item["ratingsCount"]) >= self.popular_min_votes
        ]
        if filtered:
            filtered.sort(key=lambda item: (float(item["overallRate"]), int(item["ratingsCount"])), reverse=True)
            return filtered[:limit]

        fallback = [item for item in media if item["mediaId"] not in excluded]
        fallback.sort(key=lambda item: (float(item["overallRate"]), int(item["ratingsCount"])), reverse=True)
        for item in fallback:
            item["matchReason"] = "popular_fallback"
        return fallback[:limit]

    def get_nearest_by_city(
        self,
        city_id: str,
        limit: int = DEFAULT_LIMIT,
        user_id: str | None = None,
        excluded_media_ids: set[str] | None = None,
    ) -> list[MediaRecord]:
        place_by_id = {place["placeId"]: place for place in self.provider.get_all_places()}
        items: list[dict] = []
        excluded = excluded_media_ids or set()
        user_key = str(user_id).strip() if user_id else ""

        for media in self.provider.get_media():
            if media["mediaId"] in excluded:
                continue
            place = place_by_id.get(media["placeId"])
            if not place or place["cityId"] != city_id:
                continue
            item = dict(media)
            item["matchReason"] = "your_nearest"
            items.append(item)

        if items and user_key:
            ml_scores = self._get_ml_prediction_scores_for_media(
                user_id=user_key,
                media_ids=[item["mediaId"] for item in items],
            )
            for item in items:
                if item["mediaId"] in ml_scores:
                    item["mlScore"] = round(float(ml_scores[item["mediaId"]]), 3)
            items.sort(key=lambda item: (float(item["overallRate"]), int(item["ratingsCount"])), reverse=True)
            items.sort(key=lambda item: float(item.get("mlScore", -1)), reverse=True)
        else:
            items.sort(key=lambda item: (float(item["overallRate"]), int(item["ratingsCount"])), reverse=True)
        return items[:limit]

    def get_weather_recommendations(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        user_id: str | None = None,
        excluded_media_ids: set[str] | None = None,
    ) -> dict:
        now = datetime.now()
        season_name, season_key = _season_from_month(now.month)
        excluded = excluded_media_ids or set()

        # Section 1: season-aware "best now" recommendations.
        if season_key == "winter":
            now_city_ids = ["kish", "qeshm", "bandarabbas", "shiraz"]
            now_tip = "الان هوا زمستونی است؛ جنوب ایران معمولا مطبوع‌تره."
        elif season_key == "summer":
            now_city_ids = ["ardabil", "astara", "tonkabon", "tabriz"]
            now_tip = "الان هوا گرمه؛ مناطق خنک شمال و شمال‌غرب بهترن."
        elif season_key == "spring":
            now_city_ids = ["shiraz", "isfahan", "mashhad", "tehran"]
            now_tip = "بهار زمان خوبی برای شهرهای تاریخی و طبیعت‌گردیه."
        else:
            now_city_ids = ["shiraz", "isfahan", "kish", "qeshm"]
            now_tip = "پاییز برای سفرهای شهری و جنوب ایران گزینه خوبیه."

        now_items = self._rank_weather_candidates(
            self._filter_media_by_city_ids(city_ids=now_city_ids, excluded_media_ids=excluded),
            user_id=user_id,
            reason="weather_now",
            limit=limit,
        )

        # Section 2: for users who want cold/snow vibes.
        snow_city_ids = ["tabriz", "ardabil", "astara", "gorgan", "tonkabon"]
        snow_items = self._rank_weather_candidates(
            self._filter_media_by_city_ids(city_ids=snow_city_ids, excluded_media_ids=excluded),
            user_id=user_id,
            reason="weather_snow",
            limit=limit,
        )

        # Section 3: cool choices for summer.
        summer_city_ids = ["ardabil", "astara", "tonkabon", "tabriz"]
        summer_items = self._rank_weather_candidates(
            self._filter_media_by_city_ids(city_ids=summer_city_ids, excluded_media_ids=excluded),
            user_id=user_id,
            reason="weather_summer",
            limit=limit,
        )

        sections = [
            {
                "id": "go-now",
                "title": "1) الان برو...",
                "subtitle": f"امروز {now.strftime('%Y-%m-%d')} است و فصل فعلی: {season_name}. {now_tip}",
                "items": now_items,
            },
            {
                "id": "snow-cold",
                "title": "2) اگه برف و سرما میخوای...",
                "subtitle": "پیشنهادهایی از شهرهای سردتر و برفی‌تر مثل تبریز، اردبیل، آستارا و شمال.",
                "items": snow_items,
            },
            {
                "id": "summer-cool",
                "title": "3) تابستون که شد...",
                "subtitle": "برای روزهای گرم، مقصدهای خنک‌تر مثل اردبیل و آستارا انتخاب‌های خوبی هستن.",
                "items": summer_items,
            },
        ]

        return {
            "kind": "weather",
            "today": now.strftime("%Y-%m-%d"),
            "season": season_name,
            "sections": sections,
        }

    def get_occasion_recommendations(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        user_id: str | None = None,
        excluded_media_ids: set[str] | None = None,
    ) -> dict:
        now = datetime.now().date()
        excluded = excluded_media_ids or set()
        selected: list[OccasionDefinition] = []

        for definition in OCCASION_DEFINITIONS:
            if definition.always_show or _is_occasion_near_today(definition, now):
                selected.append(definition)

        # Keep stable order and avoid duplicate sections.
        deduped: list[OccasionDefinition] = []
        seen_ids: set[str] = set()
        for definition in selected:
            if definition.id in seen_ids:
                continue
            deduped.append(definition)
            seen_ids.add(definition.id)

        sections = [
            self._build_occasion_section(
                definition=definition,
                user_id=user_id,
                limit=limit,
                excluded_media_ids=excluded,
            )
            for definition in deduped
        ]
        sections = [section for section in sections if section.get("items")]

        return {
            "kind": "occasions",
            "today": now.strftime("%Y-%m-%d"),
            "sections": sections,
        }

    def get_personalized(
        self,
        user_id: str,
        limit: int = DEFAULT_LIMIT,
        excluded_media_ids: set[str] | None = None,
    ) -> list[MediaRecord]:
        media = [dict(item) for item in self.provider.get_media()]
        media_by_id = {item["mediaId"]: item for item in media}
        scored: list[tuple[float, float, int, dict]] = []
        ratings_by_media = self._get_db_ratings_by_media(user_id)
        excluded = excluded_media_ids or set()
        if not ratings_by_media:
            return []

        for item in media_by_id.values():
            if item["mediaId"] in excluded:
                continue
            user_rate = ratings_by_media.get(item["mediaId"])
            if user_rate is None or user_rate < self.personalized_min_user_rate:
                continue
            item["userRate"] = user_rate
            item["matchReason"] = "high_user_rating"
            scored.append((user_rate, float(item["overallRate"]), int(item["ratingsCount"]), item))

        scored.sort(key=lambda data: (data[0], data[1], data[2]), reverse=True)
        base_limit = max(1, int(limit * 0.6))
        base_items = [entry[3] for entry in scored[:base_limit]]

        similar_items = self.get_similar_items(
            user_id=user_id,
            based_on_items=base_items,
            excluded_media_ids={item["mediaId"] for item in base_items}.union(excluded),
            limit=max(1, min(limit, 10)),
        )

        ml_items = self._get_ml_personalized_items(
            user_id=user_id,
            media_by_id=media_by_id,
            excluded_media_ids={item["mediaId"] for item in base_items}.union(excluded),
            limit=max(1, min(limit - len(base_items), limit)),
        )

        merged = list(base_items)
        for item in ml_items:
            if len(merged) >= limit:
                break
            merged.append(item)
        for item in similar_items:
            if len(merged) >= limit:
                break
            merged.append(item)
        return merged[:limit]

    def get_user_interest_distribution(self, user_id: str) -> dict:
        place_by_id = {place["placeId"]: place for place in self.provider.get_all_places()}
        city_counts: dict[str, int] = defaultdict(int)
        place_counts: dict[str, int] = defaultdict(int)
        ratings_by_media = self._get_db_ratings_by_media(user_id)
        if not ratings_by_media:
            return {"userId": user_id, "cityInterests": [], "placeInterests": []}

        for item in self.provider.get_media():
            user_rate = ratings_by_media.get(item["mediaId"])
            if user_rate is None or user_rate < self.personalized_min_user_rate:
                continue
            place_id = item["placeId"]
            place_counts[place_id] += 1
            place = place_by_id.get(place_id)
            if place:
                city_counts[place["cityId"]] += 1

        return {
            "userId": user_id,
            "cityInterests": [
                {"cityId": city_id, "count": count}
                for city_id, count in sorted(city_counts.items(), key=lambda item: item[1], reverse=True)
            ],
            "placeInterests": [
                {"placeId": place_id, "count": count}
                for place_id, count in sorted(place_counts.items(), key=lambda item: item[1], reverse=True)
            ],
        }

    def get_place_lookup(self) -> dict[str, PlaceRecord]:
        return {place["placeId"]: place for place in self.provider.get_all_places()}

    def get_user_ratings(self, user_id: str) -> list[dict]:
        media_by_id = {item["mediaId"]: item for item in self.provider.get_media()}
        user_uuid = _parse_uuid(user_id)
        if user_uuid is None:
            return []

        ratings = Team5MediaRating.objects.filter(user_id=user_uuid).order_by("-rate", "-updated_at")
        return [
            {
                "userId": str(r.user_id),
                "userEmail": r.user_email,
                "mediaId": r.media_id,
                "rate": float(r.rate),
                "liked": bool(r.liked),
                "media": media_by_id.get(r.media_id),
                "updatedAt": r.updated_at.isoformat(),
            }
            for r in ratings
        ]

    def get_media_feed(self, user_id: str | None = None) -> dict:
        items = [dict(item) for item in self.provider.get_media()]
        rated_high: list[dict] = []
        rated_low: list[dict] = []
        user_ratings_map = self._get_db_ratings_by_media(user_id) if user_id else {}

        for item in items:
            user_rate = user_ratings_map.get(item["mediaId"]) if user_id else None
            if user_rate is not None:
                item["userRate"] = float(user_rate)
                item["liked"] = float(user_rate) >= self.personalized_min_user_rate
                if item["liked"]:
                    rated_high.append(item)
                else:
                    rated_low.append(item)

        items.sort(key=lambda data: (float(data["overallRate"]), int(data["ratingsCount"])), reverse=True)
        rated_high.sort(key=lambda data: float(data["userRate"]), reverse=True)
        rated_low.sort(key=lambda data: float(data["userRate"]))

        return {
            "userId": user_id,
            "count": len(items),
            "items": items,
            "ratedHigh": rated_high,
            "ratedLow": rated_low,
        }

    def get_similar_items(
        self,
        *,
        user_id: str,
        based_on_items: list[dict],
        excluded_media_ids: set[str],
        limit: int,
    ) -> list[dict]:
        if not based_on_items:
            return []

        all_items = [dict(item) for item in self.provider.get_media()]
        place_by_id = {place["placeId"]: place for place in self.provider.get_all_places()}
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, str] = {}

        seed_keywords = set()
        seed_city_ids = set()
        for item in based_on_items:
            seed_keywords |= _extract_keywords(item["title"] + " " + item.get("caption", ""))
            place = place_by_id.get(item["placeId"])
            if place:
                seed_city_ids.add(place["cityId"])

        for candidate in all_items:
            media_id = candidate["mediaId"]
            if media_id in excluded_media_ids:
                continue
            place = place_by_id.get(candidate["placeId"])
            candidate_keywords = _extract_keywords(candidate["title"] + " " + candidate.get("caption", ""))
            overlap = seed_keywords.intersection(candidate_keywords)
            if overlap:
                scores[media_id] += 2.5
                reasons[media_id] = "similar_topic"
            if place and place["cityId"] in seed_city_ids:
                scores[media_id] += 1.5
                reasons[media_id] = reasons.get(media_id, "same_city")
            scores[media_id] += float(candidate.get("overallRate", 0)) / 10.0

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        media_by_id = {item["mediaId"]: item for item in all_items}
        output = []
        for media_id, _ in ranked:
            item = media_by_id[media_id]
            item["matchReason"] = reasons.get(media_id, "similar")
            output.append(item)
        return output

    def _filter_media_by_city_ids(
        self,
        *,
        city_ids: list[str],
        excluded_media_ids: set[str],
    ) -> list[dict]:
        place_by_id = {place["placeId"]: place for place in self.provider.get_all_places()}
        target_city_ids = {str(city_id).strip().lower() for city_id in city_ids if str(city_id).strip()}
        output: list[dict] = []
        for media in self.provider.get_media():
            media_id = str(media["mediaId"])
            if media_id in excluded_media_ids:
                continue
            place = place_by_id.get(media["placeId"])
            if not place:
                continue
            city_id = str(place["cityId"]).strip().lower()
            if city_id in target_city_ids:
                output.append(dict(media))
        return output

    def _rank_weather_candidates(
        self,
        items: list[dict],
        *,
        user_id: str | None,
        reason: str,
        limit: int,
    ) -> list[dict]:
        if not items:
            return []

        user_key = str(user_id).strip() if user_id else ""
        if user_key:
            ml_scores = self._get_ml_prediction_scores_for_media(
                user_id=user_key,
                media_ids=[item["mediaId"] for item in items],
            )
            for item in items:
                if item["mediaId"] in ml_scores:
                    item["mlScore"] = round(float(ml_scores[item["mediaId"]]), 3)

        for item in items:
            item["matchReason"] = reason

        items.sort(key=lambda item: (float(item["overallRate"]), int(item["ratingsCount"])), reverse=True)
        if user_key:
            items.sort(key=lambda item: float(item.get("mlScore", -1)), reverse=True)
        return items[:limit]

    def _build_occasion_section(
        self,
        *,
        definition: "OccasionDefinition",
        user_id: str | None,
        limit: int,
        excluded_media_ids: set[str],
    ) -> dict:
        all_media = [dict(item) for item in self.provider.get_media()]
        media_by_id = {item["mediaId"]: item for item in all_media}
        curated_ids = OCCASION_MEDIA_IDS_BY_OCCASION.get(definition.id, [])
        curated_items: list[dict] = []
        seen_media_ids: set[str] = set()

        for media_id in curated_ids:
            item = media_by_id.get(media_id)
            if not item or media_id in excluded_media_ids:
                continue
            prepared = dict(item)
            prepared["matchReason"] = definition.reason
            curated_items.append(prepared)
            seen_media_ids.add(media_id)
            if len(curated_items) >= limit:
                break

        fallback_items: list[dict] = []
        if len(curated_items) < limit:
            filtered = self._filter_media_by_city_ids(
                city_ids=definition.city_ids,
                excluded_media_ids=excluded_media_ids.union(seen_media_ids),
            )
            fallback_items = self._rank_weather_candidates(
                filtered,
                user_id=user_id,
                reason=definition.reason,
                limit=max(0, limit - len(curated_items)),
            )

        items = (curated_items + fallback_items)[:limit]
        return {
            "id": definition.id,
            "title": definition.title,
            "subtitle": definition.subtitle,
            "items": items,
        }

    def _get_db_ratings_by_media(self, user_id: str) -> dict[str, float]:
        user_uuid = _parse_uuid(user_id)
        if user_uuid is None:
            return {}
        return {
            item.media_id: float(item.rate)
            for item in Team5MediaRating.objects.filter(user_id=user_uuid)
        }

    def train(self):
        if not self._ml_enabled:
            self._models_ready = False
            return False
        self._train_personalized_place_recommender_model()
        self._train_personalized_media_recommender_model()
        return self._models_ready

    def _train_personalized_place_recommender_model(self):
        if self.personalized_place_recommender_model is None:
            return
        try:
            user_place_ratings = self._to_training_triples(
                rows=self.provider.get_all_place_ratings(),
                user_key="userId",
                item_key="placeId",
                rating_key="rate",
            )
            if user_place_ratings:
                self.personalized_place_recommender_model.train(user_place_ratings)
        except Exception:
            return

    def _train_personalized_media_recommender_model(self):
        if self.personalized_media_recommender_model is None:
            self._models_ready = False
            return
        user_media_ratings = self._to_training_triples(
            rows=self.provider.get_all_media_ratings(),
            user_key="userId",
            item_key="mediaId",
            rating_key="rate",
        )
        if user_media_ratings:
            self.personalized_media_recommender_model.train(user_media_ratings)
            self._models_ready = True
        else:
            self._models_ready = False

    def _ensure_models_ready(self) -> bool:
        if not self._ml_enabled or self.personalized_media_recommender_model is None:
            return False
        if self._models_ready:
            return True
        try:
            return bool(self.train())
        except Exception:
            self._models_ready = False
            return False

    def _get_ml_personalized_items(
        self,
        *,
        user_id: str,
        media_by_id: dict[str, dict],
        excluded_media_ids: set[str],
        limit: int,
    ) -> list[dict]:
        if limit <= 0:
            return []
        user_key = str(user_id).strip()
        if not user_key or not self._ensure_models_ready():
            return []

        try:
            predictions = self.personalized_media_recommender_model.recommend(
                user_key,
                top_n=max(limit * 3, limit),
                show_already_seen_items=False,
            )
        except NotTrainedYetException:
            return []
        except Exception:
            return []

        output: list[dict] = []
        for media_id, pred_score in predictions:
            media_key = str(media_id)
            if media_key in excluded_media_ids:
                continue
            media = media_by_id.get(media_key)
            if not media:
                continue
            item = dict(media)
            item["matchReason"] = "ml_personalized"
            item["mlScore"] = round(float(pred_score), 3)
            output.append(item)
            if len(output) >= limit:
                break
        return output

    def _get_ml_prediction_scores_for_media(
        self,
        *,
        user_id: str,
        media_ids: list[str],
    ) -> dict[str, float]:
        if not media_ids:
            return {}
        if not user_id or not self._ensure_models_ready():
            return {}
        if self.personalized_media_recommender_model is None:
            return {}

        scores: dict[str, float] = {}
        for media_id in media_ids:
            try:
                prediction = self.personalized_media_recommender_model.predict_rating(user_id, media_id)
                scores[media_id] = float(prediction.est)
            except NotTrainedYetException:
                return {}
            except Exception:
                continue
        return scores

    def _to_training_triples(
        self,
        *,
        rows: list[dict],
        user_key: str,
        item_key: str,
        rating_key: str,
    ) -> list[tuple[str, str, float]]:
        output: list[tuple[str, str, float]] = []
        for row in rows:
            user_id = str(row.get(user_key, "")).strip()
            item_id = str(row.get(item_key, "")).strip()
            if not user_id or not item_id:
                continue
            try:
                rating = float(row.get(rating_key))
            except (TypeError, ValueError):
                continue
            output.append((user_id, item_id, rating))
        return output

    def get_ml_status(self) -> dict:
        try:
            media_samples = len(self.provider.get_all_media_ratings())
        except Exception:
            media_samples = 0
        try:
            place_samples = len(self.provider.get_all_place_ratings())
        except Exception:
            place_samples = 0

        media_model_users = 0
        media_model_items = 0
        place_model_users = 0
        place_model_items = 0

        if self.personalized_media_recommender_model is not None:
            media_model_items = len(self.personalized_media_recommender_model.items)
            media_model_users = len(self.personalized_media_recommender_model.user_item_rating_matrix.index)
        if self.personalized_place_recommender_model is not None:
            place_model_items = len(self.personalized_place_recommender_model.items)
            place_model_users = len(self.personalized_place_recommender_model.user_item_rating_matrix.index)

        return {
            "mlEnabled": bool(self._ml_enabled),
            "modelsReady": bool(self._models_ready),
            "mediaRatingsSamples": media_samples,
            "placeRatingsSamples": place_samples,
            "mediaModelUsers": media_model_users,
            "mediaModelItems": media_model_items,
            "placeModelUsers": place_model_users,
            "placeModelItems": place_model_items,
        }


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _extract_keywords(text: str) -> set[str]:
    text = text.lower()
    keywords = set()
    mapping = {
        "tower": ["tower", "برج"],
        "bridge": ["bridge", "پل"],
        "palace": ["palace", "کاخ"],
        "shrine": ["shrine", "حرم"],
        "square": ["square", "میدان"],
        "heritage": ["historical", "history", "ancient", "ruins", "historical site", "تاریخی"],
        "poetry": ["poetry", "verse", "hafez", "شعر"],
    }
    for canonical, tokens in mapping.items():
        if any(token in text for token in tokens):
            keywords.add(canonical)
    return keywords


def _season_from_month(month: int) -> tuple[str, str]:
    if month in {12, 1, 2}:
        return "زمستان", "winter"
    if month in {3, 4, 5}:
        return "بهار", "spring"
    if month in {6, 7, 8}:
        return "تابستان", "summer"
    return "پاییز", "autumn"


@dataclass(frozen=True)
class OccasionDefinition:
    id: str
    title: str
    subtitle: str
    reason: str
    city_ids: list[str]
    month: int
    day: int
    always_show: bool = False


OCCASION_DEFINITIONS: list[OccasionDefinition] = [
    OccasionDefinition(
        id="bahman22",
        title="22 بهمن",
        subtitle="حس همبستگی و حال‌وهوای ملی در جاهای شاخص تهران.",
        reason="occasion_bahman22",
        city_ids=["tehran"],
        month=2,
        day=11,
        always_show=True,
    ),
    OccasionDefinition(
        id="nowruz",
        title="نوروز",
        subtitle="پیشنهادهایی برای آغاز سال نو و حال‌وهوای بهاری در ایران.",
        reason="occasion_nowruz",
        city_ids=["shiraz", "isfahan", "tehran"],
        month=3,
        day=21,
        always_show=True,
    ),
    OccasionDefinition(
        id="yalda",
        title="شب یلدا",
        subtitle="برای بلندترین شب سال؛ حس جمع خانوادگی، شعر و خاطره.",
        reason="occasion_yalda",
        city_ids=["tehran", "isfahan", "shiraz"],
        month=12,
        day=21,
        always_show=True,
    ),
    OccasionDefinition(
        id="christmas",
        title="کریسمس",
        subtitle="پیشنهادهایی از فضاهای حال‌وهوادار کریسمس در تهران و اصفهان.",
        reason="occasion_christmas",
        city_ids=["tehran", "isfahan"],
        month=12,
        day=25,
        always_show=True,
    ),
    OccasionDefinition(
        id="imammahdi",
        title="تولد امام زمان (نیمه‌شعبان)",
        subtitle="فضاهای جشن و معنویت برای این مناسبت عزیز.",
        reason="occasion_imammahdi",
        city_ids=["mashhad", "tehran"],
        month=2,
        day=15,
        always_show=True,
    ),
    OccasionDefinition(
        id="chaharshanbe_soori",
        title="چهارشنبه‌سوری",
        subtitle="حال‌وهوای شب‌های نزدیک نوروز و شور جمعی مردم.",
        reason="occasion_chaharshanbe_soori",
        city_ids=["isfahan", "tehran", "shiraz"],
        month=3,
        day=18,
    ),
    OccasionDefinition(
        id="sizdah_bedar",
        title="سیزده‌بدر",
        subtitle="برای روز طبیعت و پیک‌نیک‌های بهاری در فضای باز.",
        reason="occasion_sizdah_bedar",
        city_ids=["tehran", "shiraz", "isfahan", "mashhad"],
        month=4,
        day=2,
    ),
    OccasionDefinition(
        id="mehregan",
        title="مهرگان",
        subtitle="یک حال‌وهوای پاییزی و فرهنگی برای سفرهای شهری.",
        reason="occasion_mehregan",
        city_ids=["tehran", "shiraz", "isfahan"],
        month=10,
        day=2,
    ),
]


def _is_occasion_near_today(definition: OccasionDefinition, today: date, window_days: int = 45) -> bool:
    candidates: list[date] = []
    for year_delta in (-1, 0, 1):
        y = today.year + year_delta
        try:
            candidates.append(date(y, definition.month, definition.day))
        except ValueError:
            continue
    return any(abs((candidate - today).days) <= window_days for candidate in candidates)
