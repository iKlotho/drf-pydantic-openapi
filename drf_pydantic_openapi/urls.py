from django.urls import path

from .views import open_api_json, redoc

urlpatterns = [
    path("docs", redoc, name="dpo_docs"),
    path("schema.json", open_api_json, name="dpo_schema"),
]
