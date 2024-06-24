from django.conf import settings
from loguru import logger
from pydantic import BaseModel, Field

from .ref_source import RefSource


class Config(BaseModel):
    ref_sources: dict[str, RefSource] = Field(default={}, alias="REF_SOURCES")
    tag_path_regex: str = Field(default=None, alias="TAG_PATH_REGEX")
    openapi_version: str = Field(default="3.1.0", alias="OPENAPI_VERSION")
    api_version: str = Field(default="1.0.0", alias="API_VERSION")
    include_empty_endpoints: bool = Field(default=True, alias="INCLUDE_EMPTY_ENDPOINTS")
    servers: list[str] = Field(default=list, alias="SERVERS")
    title: str = Field(default="DPO Api", alias="TITLE")
    description: str = Field(default="", alias="DESCRIPTION")
    security_definitions: dict = Field(default={}, alias="SECURITY_DEFINITIONS")

    def get_source(self, name: str) -> RefSource | None:
        """Find source by given source name"""
        if ref_source := self.ref_sources.get(name):
            try:
                ref_source.init()
                return ref_source
            except Exception as e:
                logger.warning(f"Error while initializing the {name} source: {str(e)}")

    def initialize_sources(self):
        for _, ref_source in self.ref_sources.items():
            ref_source.init(force=True)


USER_SETTINGS = getattr(settings, "DRF_PYDANTIC_OPENAPI", {"REF_SOURCES": {}})

# Override ref_sources to use the class
USER_SETTINGS["REF_SOURCES"] = {name: RefSource(name, value) for name, value in USER_SETTINGS["REF_SOURCES"].items()}

config = Config(**USER_SETTINGS)
