class Team5Serializer:
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

    @staticmethod
    def serialize_nearest_response(resolved, items, client_ip, limit):
        city = resolved["city"]
        return {
            "kind": "nearest",
            "title": "your nearest",
            "source": resolved["source"],
            "clientIp": client_ip,
            "cityId": city["cityId"],
            "cityName": city["cityName"],
            "limit": limit,
            "count": len(items),
            "items": items,
        }

    @staticmethod
    def serialize_personalized_response(items, user_id, source, limit):
        return {
            "kind": "personalized",
            "source": source,
            "userId": user_id,
            "limit": limit,
            "count": len(items),
            "items": items,
            "highRatedItems": [item for item in items if item.get("matchReason") == "high_user_rating"],
            "similarItems": [item for item in items if item.get("matchReason") != "high_user_rating"],
        }