# See flask-typed(https://github.com/mfnd/flask-typed)
import openapi_schema_pydantic as openapi
from pydantic import BaseModel
from openapi_schema_pydantic.util import PydanticSchema


class HttpError(Exception):
    mime_type = "application/json"

    class ResponseModel(BaseModel):
        message: str | None = None

    def __init_subclass__(cls, **kwargs):
        if not issubclass(cls.ResponseModel, BaseModel):
            raise TypeError(f"ResponseModel should inherit pydantic BaseModel: {cls.__name__}")

    def __init__(self, status_code: int | None = None, **kwargs):
        cls = self.__class__
        self.status_code = cls.status_code if status_code is None else status_code
        self.response = cls.ResponseModel(**kwargs)

    def json(self) -> str:
        return self.response.json()

    def dict(self) -> str:
        return self.response.dict()

    @classmethod
    def schema(cls) -> PydanticSchema:
        return PydanticSchema(schema_class=cls.ResponseModel)


class BadRequestError(HttpError):
    status_code = 400
    message = "Bad request"


class NotFoundError(HttpError):
    status_code = 404
    message = "Not found"


class InternalServerError(HttpError):
    status_code = 500
    message = "Internal server error"
