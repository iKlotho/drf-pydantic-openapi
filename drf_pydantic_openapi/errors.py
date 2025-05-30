# See flask-typed(https://github.com/mfnd/flask-typed)
from typing import ClassVar

from pydantic import BaseModel


class HttpError(Exception):
    mime_type = "application/json"
    ResponseModel: ClassVar[type[BaseModel]]
    status_code: int

    def __init_subclass__(cls, **kwargs):
        if not issubclass(cls.ResponseModel, BaseModel):
            raise TypeError(f"ResponseModel should inherit pydantic BaseModel: {cls.__name__}")

    def __init__(self, status_code: int | None = None, **kwargs):
        cls = self.__class__
        self.status_code = cls.status_code if status_code is None else status_code
        self.response = cls.ResponseModel(**kwargs)

    def json(self) -> str:
        return self.response.model_dump_json()

    def dict(self) -> str:
        return self.response.model_dump()

    @classmethod
    def schema(cls):
        # schema =  PydanticSchema(schema_class=cls.ResponseModel)
        model_name = f"{cls.status_code}_ResponseModel"
        return cls.ResponseModel.model_json_schema(ref_template=f"#/components/schemas/{model_name}")


class SimpleHttpError(HttpError):
    class ResponseModel(BaseModel):
        message: str | None = None


class BadRequestError(SimpleHttpError):
    status_code = 400
    message = "Bad request"


class NotFoundError(SimpleHttpError):
    status_code = 404
    message = "Not found"


class InternalServerError(SimpleHttpError):
    status_code = 500
    message = "Internal server error"
