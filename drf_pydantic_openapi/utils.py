import builtins
import re
from datetime import date, datetime, time
from enum import Enum
from inspect import isclass
from types import NoneType, UnionType
from typing import Annotated, Any, get_args, get_origin
from uuid import UUID

import docstring_parser
import openapi_pydantic as openapi
from openapi_pydantic import Parameter, PathItem
from openapi_pydantic.util import PydanticSchema
from pydantic import BaseModel
from rest_framework import exceptions

from .errors import HttpError

method_mapping = {
    "get": "retrieve",
    "post": "create",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
}

_builtin_openapi_map = {
    builtins.bool: openapi.Schema(type=openapi.DataType.BOOLEAN),
    builtins.str: openapi.Schema(type=openapi.DataType.STRING),
    builtins.int: openapi.Schema(type=openapi.DataType.INTEGER),
    builtins.float: openapi.Schema(type=openapi.DataType.NUMBER),
    datetime: openapi.Schema(type=openapi.DataType.STRING, format="date-time"),
    date: openapi.Schema(type=openapi.DataType.STRING, format="date"),
    time: openapi.Schema(type=openapi.DataType.STRING, format="time"),
    UUID: openapi.Schema(type=openapi.DataType.STRING, format="uuid"),
}


def get_builtin_type(ty: type) -> openapi.Schema | None:
    ty = get_actual_type(ty)
    if schema := _builtin_openapi_map.get(ty):
        return schema.model_copy()
    return None


def get_actual_type(param_type: type) -> Any | type:
    actual_type = None
    origin_type = get_origin(param_type)
    if origin_type is UnionType:
        for alternate_type in get_args(param_type):
            if alternate_type is NoneType:
                continue
            if actual_type is not None:
                raise Exception("Multiple argument types are provided")
            actual_type = alternate_type
    else:
        actual_type = param_type

    return actual_type


class ParameterLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class DocsMetadata:
    def __init__(
        self,
        errors: list[HttpError | type[HttpError]] | None = None,
        body: BaseModel | None = None,
        query: BaseModel | None = None,
        path: BaseModel | None = None,
        response: BaseModel | None = None,
    ):
        self.errors = errors if errors is not None else []
        self.body = body
        self.query = query
        self.path = path
        self.response = response

    def generate_parameters(self, parameter_location: ParameterLocation):
        params = []
        data = None
        if parameter_location == ParameterLocation.QUERY:
            data = self.query
        elif parameter_location == ParameterLocation.PATH:
            data = self.path
        elif parameter_location == ParameterLocation.BODY:
            data = self.body
        else:
            raise Exception(f"Invalid parameter location: {parameter_location}!")

        if data and isclass(data) and issubclass(data, BaseModel):
            for name, field_info in data.model_fields.items():
                field_annotation = field_info.annotation
                if field_annotation is None:
                    raise TypeError(f"No type annotation is provided for parameter: {name}")

                if get_origin(field_annotation) == Annotated:
                    metadata = get_args(field_annotation)
                    field_annotation = metadata[0]

                if isclass(field_annotation) and issubclass(field_annotation, BaseModel):
                    schema = PydanticSchema(schema_class=field_annotation)
                else:
                    schema = get_builtin_type(field_annotation)

                description = field_info.description

                params.append(
                    Parameter(
                        name=name,
                        description=description if description else "",
                        param_in=parameter_location,
                        param_schema=schema,
                        required=field_info.is_required(),
                    ),
                )
        return params


def docs(
    errors: list[HttpError | type[HttpError]] | None = None,
    body: BaseModel | None = None,
    query: BaseModel | None = None,
    path: BaseModel | None = None,
    response: BaseModel | None = None,
):
    def docs_decorator(func):
        func.docs_metadata = DocsMetadata(errors=errors, body=body, query=query, path=path, response=response)
        return func

    return docs_decorator


class Docstring:
    def __init__(self, docstring: str):
        docstring = docstring_parser.parse(docstring)
        self.short_description = docstring.short_description
        self.long_description = docstring.long_description
        self.params = {param.arg_name: param for param in docstring.params}
        self.returns = {returns.type_name: returns for returns in docstring.many_returns}
        self.raises = {exception.type_name: exception for exception in docstring.raises}

    def get_parameter_description(self, name: str) -> str:
        if parameter := self.params.get(name):
            return parameter.description
        return ""


def extract_ref_source(ref: str):
    # Find the ref name
    pattern = r"#/components/schemas/(\w+)"
    match = re.search(pattern, ref)
    if match:
        model_name = match.group(1)
        return model_name


def get_view_version(view) -> str:
    try:
        version, _ = view.determine_version(view.request, **view.kwargs)
        return str(version)
    except exceptions.NotAcceptable:
        return ""


class PathItemEx(PathItem):
    def is_empty(self):
        return not (self.get or self.post or self.delete or self.head or self.put)
