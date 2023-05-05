import builtins
from enum import Enum
import re
from typing import Type

import docstring_parser
from pydantic import BaseModel
from openapi_schema_pydantic.util import PydanticSchema
from openapi_schema_pydantic import Schema, Parameter
from inspect import isclass

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
        body=None,
        query=None,
        path=None,
    ):
        self.errors = errors if errors is not None else []
        self.body = body
        self.query = query
        self.path = path

    def generate_parameter(self, parameter_location: ParameterLocation):
        data = None
        if parameter_location == ParameterLocation.QUERY:
            data = self.query
        elif parameter_location == ParameterLocation.PATH:
            data = self.path
        else:
            raise Exception("Invalid parameter location!")

        if data and isclass(data) and issubclass(data, BaseModel):
            for name, field in data.__fields__.items():
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
    body=None,
    query=None,
    path=None,
):
    def docs_decorator(func):
        func.docs_metadata = DocsMetadata(errors=errors, body=body, query=query, path=path)
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


def find_schema(source: str, name: str):
    from .settings import config

    for ref_source in config.ref_sources:
        if ref_source.name == source:
            for k, v in ref_source.schemas.items():
                if k == f"{source}_{name}":
                    return v


def extract_ref_source(ref):
    pattern = r"#/components/schemas/(\w+)"
    match = re.search(pattern, ref)
    if match:
        model_name = match.group(1)
        return model_name


def replace_ref_source(ref, source):
    pattern = r'"\$ref":\s*"#/components/schemas/(\w+)"'
    match = re.search(pattern, ref)
    if match:
        model_name = match.group(1)
        new_model_name = f"{source}_{model_name}"
        if source not in ref:
            return ref.replace(model_name, new_model_name)

    return ref


def add_source_name_to_ref(source: str, name: str):
    if source in name:
        return name
    return f"{source}_{name}"


def extend_openapi(open_api):
    from .settings import config

    new_open_api = open_api.copy(deep=True)
    if new_open_api.components:
        for ref_source in config.ref_sources.values():
            new_open_api.components.schemas.update(**ref_source.fetch_custom_components())

    return new_open_api
