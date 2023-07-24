from django.urls import path

from .views import DrfPydanticRedocView, get_schema_view

urlpatterns = [
    path("docs", DrfPydanticRedocView.as_view(), name="dpo_docs"),
    path("schema.json", get_schema_view().as_view(), name="dpo_schema"),
]
