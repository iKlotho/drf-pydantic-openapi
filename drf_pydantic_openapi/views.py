import json
from typing import Any

from django.views.generic import TemplateView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from .generator import Document
from .settings import config


def get_schema_view(
    api_version=None,
    tag_path_regex=None,
    permission_classes=None,
    authentication_classes=None,
):
    _api_version = api_version
    _tag_path_regex = tag_path_regex
    _permission_classes = permission_classes if permission_classes else {}
    _authentication_classes = authentication_classes if authentication_classes else {}

    class DrfPydanticSchemaView(APIView):
        authentication_classes = _authentication_classes
        permission_classes = _permission_classes

        def get(self, request, *args, **kwargs):
            version = _api_version
            if hasattr(request, "version"):
                version = request.version

            config.initialize_sources()
            document = Document(
                api_version=version,
                tag_path_regex=_tag_path_regex,
            )
            schema = document.get_schema(request=request)
            return Response(json.loads(schema), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    return DrfPydanticSchemaView


class DrfPydanticRedocView(TemplateView):
    api_version = None
    template_name = "drf_pydantic_openapi/redoc.html"
    url_name = "dpo_schema"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        schema_url = f"{self.api_version}:{self.url_name}" if self.api_version else self.url_name
        context["schema_url"] = reverse(schema_url)
        return context


class DrfPydanticRapidocView(TemplateView):
    api_version = None
    template_name = "drf_pydantic_openapi/rapidoc.html"
    url_name = "dpo_schema"
    rapidoc_settings = {}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        schema_url = f"{self.api_version}:{self.url_name}" if self.api_version else self.url_name
        context["schema_url"] = reverse(schema_url)
        return context


class DrfPydanticSwaggerView(TemplateView):
    api_version = None
    template_name = "drf_pydantic_openapi/swagger.html"
    url_name = "dpo_schema"
    rapidoc_settings = {}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        schema_url = f"{self.api_version}:{self.url_name}" if self.api_version else self.url_name
        context["schema_url"] = reverse(schema_url)
        return context
