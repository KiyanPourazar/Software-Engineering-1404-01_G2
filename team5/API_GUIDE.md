# 🚀 Team 5 Recommendation System - API Documentation

This guide provides technical details for integrating with Team 5's recommendation engine. Our API supports multiple strategies and is pre-configured for future A/B testing.

---

## 📡 Base URL
`http://<host>:<port>/team5/api/recommendations/`

---

## 1. Fetch Recommendations
Retrieves a list of recommended media based on user profile and selected strategy.

**Endpoint:** `GET /api/recommendations/`

### 📥 Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `userId` | `string` | **Yes** | - | Unique identifier of the user (UUID or ID). |
| `strategy` | `string` | No | `personalized` | Choices: `personalized`, `popular`, `weather`, `nearest`. |
| `version` | `string` | No | `A` | Used for A/B Testing. Use `A` for control or `B` for variants. |
| `limit` | `int` | No | `10` | Maximum number of items to return (Max: 100). |

### 📤 Sample Response
```json
{
    "status": "success",
    "metadata": {
        "team": "team5",
        "api_version": "v2.0",
        "ab_test_group": "A",
        "applied_strategy": "personalized",
        "limit": 10
    },
    "data": {
        "userId": "123e4567-e89b-12d3-a456-426614174000",
        "count": 2,
        "items": [
            { "id": "m1", "title": "Inception", "category": "movie" },
            { "id": "m2", "title": "Interstellar", "category": "movie" }
        ]
    }
}
```
## 2. Submit Interaction Feedback
Logs user interactions (likes/dislikes) to improve future recommendations and track A/B test results.

**Endpoint:** `POST /api/recommendations/feedback/`

### 📥 Request Body (JSON)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `userId` | `string` | **Yes** | The ID of the interacting user. |
| `action` | `string` | **Yes** | Category of the recommendation (e.g., `personalized`). |
| `liked` | `boolean` | **Yes** | `true` for like, `false` for dislike. |
| `version` | `string` | No | The version group (`A` or `B`) the user was assigned to. |
| `shownMediaIds` | `array` | No | List of media IDs that were displayed in that session. |

### 📤 Sample Response
```json
{
    "ok": true,
    "detail": "Feedback successfully saved for version A"
}
```
🛠 Integration Notes
A/B Testing: If you are conducting a test, ensure you pass the version parameter in both GET and POST requests to maintain data consistency.

Error Handling: If userId is missing, the API returns a 400 Bad Request with a descriptive error message.