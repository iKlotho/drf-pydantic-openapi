import pydantic
from rest_framework.views import Response, exception_handler

from .errors import HttpError


def typed_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if isinstance(exc, pydantic.ValidationError):
        data = {"detail": exc.errors()}
        response = Response(data, status=422)

    if isinstance(exc, HttpError):
        data = {"detail": exc.dict()}
        response = Response(data, status=exc.status_code)

    return response
