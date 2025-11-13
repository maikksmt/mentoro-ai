from django.urls import path
from .views import editorial as views

app_name = "editorial"

urlpatterns = [
    path("me/drafts/", views.my_drafts, name="my_drafts"),
    path("me/submit/", views.submit_to_review, name="submit_to_review"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/update/", views.review_update, name="review_update"),
    path("register-author/", views.register_author, name="register_author"),
]
