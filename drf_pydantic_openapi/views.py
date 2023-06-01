import json
from typing import Any, Dict

from django.views.generic import TemplateView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from .generator import Document


class DrfPydanticSchemaView(APIView):
    # TODO: get these from settings
    authentication_classes = {}
    permission_classes = {}
    api_version = None

    def get(self, request, *args, **kwargs):
        version = self.api_version
        if hasattr(request, "version"):
            version = request.version

        document = Document(api_version=version)
        schema = document.get_schema(request=request)
        return Response(json.loads(schema), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


class DrfPydanticRedocView(TemplateView):
    api_version = None
    template_name = "drf_pydantic_openapi/redoc.html"
    url_name = "dpo_schema"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        schema_url = f"{self.api_version}:{self.url_name}" if self.api_version else self.url_name
        context["schema_url"] = reverse(schema_url)
        return context
