from django.conf import settings

from pydantic import BaseModel, Field, validator
from .ref_source import RefSource


class Config(BaseModel):
    ref_sources: dict[str, RefSource] = Field(default={}, alias="REF_SOURCES")

    def get_source(self, name: str) -> RefSource | None:
        """Find source by given source name"""
        if ref_source := self.ref_sources.get(name):
            return ref_source.schemas_


USER_SETTINGS = getattr(settings, "DRF_PYDANTIC_OPENAPI", {"REF_SOURCES": {}})

config = Config(
    **{"REF_SOURCES": {name: RefSource(name, value) for name, value in USER_SETTINGS["REF_SOURCES"].items()}}
)
