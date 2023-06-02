import inspect
import os
import re
from collections import defaultdict
from inspect import isclass

from django.urls import get_resolver
from openapi_schema_pydantic import (
    Info,
    MediaType,
    OpenAPI,
    Operation,
    PathItem,
    RequestBody,
    Response,
)
from openapi_schema_pydantic.util import (
    PydanticSchema,
    construct_open_api_with_schema_class,
)
from pydantic import BaseModel
from rest_framework.schemas.generators import BaseSchemaGenerator

from .path import Path
from .settings import config
from .utils import Docstring, ParameterLocation, get_view_version, method_mapping


class Document(BaseSchemaGenerator):
    def __init__(self, api_version: str, tag_path_regex: str | None, *args, **kwargs) -> None:
        self.api_version = api_version
        self.tag_path_regex = tag_path_regex
        self.openapi = OpenAPI(info=Info(title="test", version="3.0.0"), paths={})
        self.responses = {}
        super().__init__(*args, **kwargs)

    @property
    def _tag_path_regex(self):
        # Get path prefix regex
        return self.tag_path_regex if self.tag_path_regex else config.tag_path_regex

    def find_path_prefix(self, view_endpoints):
        if self._tag_path_regex is None:
            non_trivial_prefix = len(set([view.__class__ for _, _, view in view_endpoints])) > 1
            if non_trivial_prefix:
                path_prefix = os.path.commonpath([path for path, _, _ in view_endpoints])
                path_prefix = re.escape(path_prefix)  # guard for RE special chars in path
            else:
                path_prefix = "/"
        else:
            path_prefix = self._tag_path_regex

        return path_prefix

    def generate_responses(self, docstring, view_func):
        response = {}
        handler_signature = inspect.signature(view_func)
        return_type = handler_signature.return_annotation
        docs = getattr(view_func, "docs_metadata", None)
        if docs:
            if response_model := docs.response:
                return_type = response_model

            for error in docs.errors:
                description = ""
                if docstring and (raises := docstring.raises.get(error.__name__)):
                    description = raises.description
                response[error.status_code] = Response(
                    description=description,
                    content={"application/json": MediaType(schema=error.schema())},
                )

        if return_type is not inspect._empty:
            if isclass(return_type) and issubclass(return_type, BaseModel):
                schema = PydanticSchema(schema_class=return_type)
                description = ""
                if docstring and (returns := docstring.returns.get(error.__name__)):
                    description = returns.description
                response["200"] = Response(
                    description=description,
                    content={"application/json": MediaType(schema=schema)},
                )
        return response

    def generate_operation(self, path: Path) -> Operation | None:
        method = path.method.lower()
        view_func = getattr(path.view, method, getattr(path.view, method_mapping[method], None))

        if not view_func:
            return

        request_body = None

        docs = getattr(view_func, "docs_metadata", None)
        docstring = getattr(view_func, "__doc__", None)
        docstring = Docstring(docstring) if docstring else None

        if method.lower() in ("put", "patch", "post"):
            if docs and isclass(docs.body) and issubclass(docs.body, BaseModel):
                schema = PydanticSchema(schema_class=docs.body)
                request_body = RequestBody(content={"application/json": MediaType(schema=schema)})

        parameters = []
        if docs and (path_param := docs.generate_parameter(ParameterLocation.PATH)):
            parameters.append(path_param)
        if docs and (query_param := docs.generate_parameter(ParameterLocation.QUERY)):
            parameters.append(query_param)

        return Operation(
            operation_id=path.get_operation_id(),
            requestBody=request_body,
            tags=path.get_tags(),
            responses=self.generate_responses(docstring, view_func),
            summary=docstring.short_description if docstring else "",
            description=docstring.long_description if docstring else "",
            parameters=parameters,
        )

    def generate_docs(self, paths: list[Path]):
        docs = PathItem()
        for path in paths:
            if operation := self.generate_operation(path):
                setattr(docs, path.method.lower(), operation)
        return docs

    def get_schema(self, request=None, public=False):
        self._initialise_endpoints()
        _, view_endpoints = self._get_paths_and_endpoints(request)
        paths = defaultdict(list)
        path_prefix = self.find_path_prefix(view_endpoints)

        for path, method, view in view_endpoints:
            if self.api_version:
                # resolver required by NamespaceVersioning
                view.request.resolver_match = get_resolver().resolve(path)
                if get_view_version(view) != self.api_version:
                    continue
            paths[path].append(
                Path(
                    path=path,
                    path_prefix=path_prefix,
                    method=method,
                    view=view,
                )
            )

        for path in paths.keys():
            docs = self.generate_docs(paths[path])
            self.openapi.paths[path] = docs

        self.openapi = construct_open_api_with_schema_class(self.openapi)
        return self.openapi.json(by_alias=True, exclude_none=True)
