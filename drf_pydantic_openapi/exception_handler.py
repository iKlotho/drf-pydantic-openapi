import pydantic
from rest_framework.views import Response, exception_handler

from .errors import HttpError


def typed_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if isinstance(exc, pydantic.ValidationError):
        response = Response(exc.errors(include_input=False, include_url=False), status=422)

    if isinstance(exc, HttpError):
        response = Response(exc.json(), status=exc.status_code)

    return response
