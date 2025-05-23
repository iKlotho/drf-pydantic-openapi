import inspect
import os
import re
from collections import defaultdict
from inspect import isclass
from types import UnionType
from typing import get_args, get_origin

from django.urls import get_resolver
from loguru import logger

# TODO: check desired openapi version and import accordingly
from openapi_pydantic import (
    Info,
    MediaType,
    OpenAPI,
    Operation,
    RequestBody,
    Response,
    Schema,
    Server,
)
from openapi_pydantic.util import PydanticSchema, construct_open_api_with_schema_class
from pydantic import BaseModel
from rest_framework.schemas.generators import BaseSchemaGenerator

from .path import Path
from .settings import config
from .utils import (
    Docstring,
    ParameterLocation,
    PathItemEx,
    get_view_version,
    method_mapping,
)


class Document(BaseSchemaGenerator):
    def __init__(self, api_version: str, tag_path_regex: str | None, *args, **kwargs) -> None:
        self.api_version = api_version
        self.tag_path_regex = tag_path_regex
        # TODO: change info
        servers = [Server(url=server) for server in config.servers]
        self.openapi = OpenAPI(
            openapi=config.openapi_version,
            info=Info(title=config.title, version=config.api_version, description=config.description),
            paths={},
            servers=servers,
        )
        self.responses = {}
        super().__init__(*args, **kwargs)

    @property
    def _tag_path_regex(self):
        # Get path prefix regex
        return self.tag_path_regex if self.tag_path_regex else config.tag_path_regex

    def find_path_prefix(self, view_endpoints):
        if self._tag_path_regex is None:
            non_trivial_prefix = len({view.__class__ for _, _, view in view_endpoints}) > 1
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

                response[str(error.status_code)] = Response(
                    description=description,
                    content={"application/json": MediaType(schema=error.schema())},
                )

        if return_type is not inspect.Signature.empty:
            origin_type = get_origin(return_type)
            if origin_type is UnionType:
                # group by status_code and mime_type
                types = defaultdict(list)
                for single_return_type in get_args(return_type):
                    if isclass(single_return_type) and issubclass(single_return_type, BaseModel):
                        mime_type = str(single_return_type.model_config.get("mime_type", "application/json"))
                        status_code = str(single_return_type.model_config.get("status_code", 200))
                        types[(status_code, mime_type)].append(PydanticSchema(schema_class=single_return_type))

                for (status_code, mime_type), response_type in types.items():
                    # if multiple responses defined use oneOf otherwise return the single type
                    media_type_schema = Schema(oneOf=response_type) if len(response_type) > 1 else response_type[0]
                    response[status_code] = Response(
                        description="", content={mime_type: MediaType(schema=media_type_schema)},
                    )
            elif isclass(return_type) and issubclass(return_type, BaseModel):
                mime_type = str(return_type.model_config.get("mime_type", "application/json"))
                status_code = str(return_type.model_config.get("status_code", 200))
                schema = PydanticSchema(schema_class=return_type)
                description = ""
                if docstring and (returns := docstring.returns.get(return_type.__name__)):
                    description = returns.description
                response[status_code] = Response(
                    description=description,
                    content={mime_type: MediaType(schema=schema)},
                )
            else:
                logger.warning(f"Unsupported return type {return_type}")

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
        if docs and (path_params := docs.generate_parameters(ParameterLocation.PATH)):
            parameters.extend(path_params)
        if docs and (query_params := docs.generate_parameters(ParameterLocation.QUERY)):
            parameters.extend(query_params)

        return Operation(
            operationId=path.get_operation_id(),
            requestBody=request_body,
            tags=path.get_tags(),
            responses=self.generate_responses(docstring, view_func),
            summary=docstring.short_description if docstring else "",
            description=docstring.long_description if docstring else "",
            parameters=parameters,
        )

    def generate_docs(self, paths: list[Path]):
        docs = PathItemEx()
        for path in paths:
            if operation := self.generate_operation(path):
                if not config.include_empty_endpoints:
                    if operation.responses:
                        setattr(docs, path.method.lower(), operation)
                else:
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
                ),
            )

        for path in paths.keys():
            if docs := self.generate_docs(paths[path]):
                if not docs.is_empty():
                    self.openapi.paths[path] = docs

        self.openapi = construct_open_api_with_schema_class(self.openapi)

        if config.security_definitions:
            self.openapi.components.securitySchemes = config.security_definitions
            self.openapi.security = [{security_method: []} for security_method in config.security_definitions.keys()]
        return self.openapi.model_dump_json(by_alias=True, exclude_none=True)
