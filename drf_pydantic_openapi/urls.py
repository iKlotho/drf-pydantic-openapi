from django.urls import path

from .views import DrfPydanticRedocView, DrfPydanticSchemaView

urlpatterns = [
    path("docs", DrfPydanticRedocView.as_view(), name="dpo_docs"),
    path("schema.json", DrfPydanticSchemaView.as_view(), name="dpo_schema"),
]
