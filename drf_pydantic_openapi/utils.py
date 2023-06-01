import builtins
import re
from enum import Enum
from inspect import isclass
from typing import Type

import docstring_parser
from openapi_schema_pydantic import Parameter, Schema
from openapi_schema_pydantic.util import PydanticSchema
from pydantic import BaseModel
from rest_framework import exceptions

from .errors import HttpError

_builtin_openapi_map = {
    builtins.bool: "boolean",
    builtins.str: "string",
    builtins.int: "integer",
    builtins.float: "number",
}


def get_builtin_type(ty: Type):
    return _builtin_openapi_map.get(ty)


class ParameterLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class DocsMetadata:
    def __init__(
        self,
        errors: list[HttpError | Type[HttpError]] | None = None,
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

    def generate_parameter(self, parameter_location: ParameterLocation):
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
            for _, field in data.__fields__.items():
                type_ = field.type_
                if issubclass(type_, BaseModel):
                    schema = PydanticSchema(schema_class=type_)
                else:
                    schema = Schema(type=get_builtin_type(type_))

                description = field.field_info.description

                return Parameter(
                    name=field.name,
                    description=description if description else "",
                    param_in=parameter_location,
                    param_schema=schema,
                    required=field.required,
                )


def docs(
    errors: list[HttpError | Type[HttpError]] | None = None,
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
