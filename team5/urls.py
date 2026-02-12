from django.urls import path
from . import views

urlpatterns = [
    path("", views.base),
    path("ping/", views.ping),
    path("api/cities/", views.get_cities),
    path("api/places/city/<str:city_id>/", views.get_city_places),
    path("api/media/", views.get_media),
    path("api/media/<str:media_id>/comments/", views.get_media_comments),
    path("api/users/", views.get_registered_users),
    path("api/users/<str:user_id>/ratings/", views.get_user_ratings),
    path("api/recommendations/popular/", views.get_popular_recommendations),
    path("api/recommendations/random/", views.get_random_recommendations),
    path("api/recommendations/nearest/", views.get_nearest_recommendations),
    path("api/recommendations/personalized/", views.get_personalized_recommendations),
    path("api/recommendations/weather/", views.get_weather_recommendations),
    path("api/recommendations/occasions/", views.get_occasion_recommendations),
    path("api/recommendations/feedback/", views.submit_recommendation_feedback),
    path("api/recommendations/ab/summary/", views.get_ab_test_summary),
    path("api/users/<str:user_id>/interests/", views.get_user_interests),
    path("api/train", views.train),
    path("api/ml/status", views.ml_status),
    path("api/recommendations/", views.get_recommendations_api, name="team5_main_api"),
]