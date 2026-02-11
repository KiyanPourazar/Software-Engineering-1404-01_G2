import random
from datetime import datetime, timedelta


class Team5Serializer:
    """Handles data transformation for Team5 responses."""

    @staticmethod
    def _enrich_media_item(item):
        """
        Helper to format media data as social posts, generating fake user info if missing.
        """
        # Fake usernames for UI display
        fake_users = ["ali_traveler", "shiraz_lover", "neg_art", "parsa_guider", "tourist_2024", "iran_gem"]

        # Random date within the last 3 months
        days_ago = random.randint(1, 90)
        date_created = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        return {
            "mediaId": item.get("mediaId"),
            "placeId": item.get("placeId"),
            # Map title and caption to post format
            "title": item.get("title"),
            "description": item.get("caption") or item.get("description", "No description available."),

            # Author info
            "author": {
                "username": item.get("username") or random.choice(fake_users),
                "avatarUrl": "https://i.pravatar.cc/150?u=" + item.get("mediaId", "1"),  # Random avatar
            },

            # Publish date
            "dateCreated": date_created,

            # Ratings
            "overallRate": item.get("overallRate"),
            "stars": int(round(item.get("overallRate", 0))),  # Integer for star display (e.g., 4)
            "ratingsCount": item.get("ratingsCount"),

            # System metadata
            "matchReason": item.get("matchReason"),
            "mlScore": item.get("mlScore"),
        }

    @staticmethod
    def serialize_nearest(items, resolved, client_ip, limit, user_id):
        city = resolved["city"]
        # Loop through and enrich items
        enriched_items = [Team5Serializer._enrich_media_item(item) for item in items]

        return {
            "kind": "nearest",
            "title": "your nearest",
            "source": resolved["source"],
            "userId": user_id,
            "clientIp": client_ip,
            "cityId": city["cityId"],
            "cityName": city["cityName"],
            "limit": limit,
            "count": len(enriched_items),
            "items": enriched_items,
        }

    @staticmethod
    def serialize_personalized(items, user_id, source, limit):
        enriched_items = [Team5Serializer._enrich_media_item(item) for item in items]

        # Separate items based on match reason
        direct = [i for i in enriched_items if i.get("matchReason") == "high_user_rating"]
        similar = [i for i in enriched_items if i.get("matchReason") != "high_user_rating"]

        return {
            "kind": "personalized",
            "source": source,
            "userId": user_id,
            "limit": limit,
            "count": len(enriched_items),
            "items": enriched_items,
            "highRatedItems": direct,
            "similarItems": similar,
        }

    @staticmethod
    def serialize_user(user):
        return {
            "userId": str(user.id),
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "age": getattr(user, 'age', None),
            "dateJoined": user.date_joined.isoformat() if user.date_joined else None,
        }