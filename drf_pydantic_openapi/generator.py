import inspect
from collections import defaultdict
from dataclasses import dataclass
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

from .utils import (
    Docstring,
    ParameterLocation,
    get_view_version,
)


@dataclass
class Path:
    """
    Container for application api paths
    """

    name: str
    method: str
    view: callable


class Document(BaseSchemaGenerator):
    def __init__(self, api_version: str, *args, **kwargs) -> None:
        self.api_version = api_version
        self.openapi = OpenAPI(info=Info(title="test", version="3.0.0"), paths={})
        self.responses = {}
        self.method_mapping = {
            "get": "retrieve",
            "post": "create",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }
        super().__init__(*args, **kwargs)

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
            else:
                print("No type found")
        return response

    def generate_operation(self, path: str, method: str, view) -> Operation | None:
        method = method.lower()
        view_func = getattr(view, method, getattr(view, self.method_mapping[method], None))

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

        path_name = path.replace("/", "_")

        return Operation(
            operation_id=f"{method}_{path_name}_operation",
            requestBody=request_body,
            responses=self.generate_responses(docstring, view_func),
            summary=docstring.short_description if docstring else "",
            description=docstring.long_description if docstring else "",
            parameters=parameters,
        )

    def generate_docs(self, paths: list[Path]):
        docs = PathItem()
        for path in paths:
            if operation := self.generate_operation(path.name, path.method, path.view):
                setattr(docs, path.method.lower(), operation)
        return docs

    def get_schema(self, request=None, public=False):
        self._initialise_endpoints()
        _, view_endpoints = self._get_paths_and_endpoints(request)
        paths = defaultdict(list)
        for path, method, view in view_endpoints:
            if self.api_version:
                # resolver required by NamespaceVersioning
                view.request.resolver_match = get_resolver().resolve(path)
                if get_view_version(view) != self.api_version:
                    continue
            paths[path].append(Path(name=path, method=method, view=view))

        for path in paths.keys():
            docs = self.generate_docs(paths[path])
            self.openapi.paths[path] = docs

        self.openapi = construct_open_api_with_schema_class(self.openapi)
        return self.openapi.json(by_alias=True, exclude_none=True)
