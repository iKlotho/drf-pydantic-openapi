import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .generator import Document


def open_api_json(request: HttpRequest) -> JsonResponse:
    document = Document()
    schema = document.get_schema(request=request)

    response = JsonResponse(json.loads(schema))
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


def redoc(request: HttpRequest) -> HttpResponse:
    return render(request, "drf_pydantic_openapi/redoc.html")
