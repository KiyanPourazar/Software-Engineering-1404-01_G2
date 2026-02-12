class Team5Serializer:
    """Handles data transformation for Team5 responses."""

    @staticmethod
    def _enrich_media_item(item):
        """Normalize media payload to match current frontend card schema."""
        author_display_name = (item.get("authorDisplayName") or "").strip()
        return {
            "mediaId": item.get("mediaId"),
            "placeId": item.get("placeId"),
            "title": item.get("title"),
            "caption": item.get("caption") or item.get("description", ""),
            "authorDisplayName": author_display_name,
            "mediaImageUrl": item.get("mediaImageUrl", ""),
            "createdAt": item.get("createdAt", ""),
            "overallRate": item.get("overallRate"),
            "ratingsCount": item.get("ratingsCount"),
            "userRate": item.get("userRate"),
            "liked": item.get("liked"),
            "matchReason": item.get("matchReason"),
            "mlScore": item.get("mlScore"),
            "abVariant": item.get("abVariant"),
            "abBucket": item.get("abBucket"),
            "triggerComment": item.get("triggerComment"),
            "triggerMediaId": item.get("triggerMediaId"),
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
