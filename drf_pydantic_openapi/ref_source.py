from collections import defaultdict
from pydantic import Field
import json
import re
import requests
from .utils import add_source_name_to_ref, extract_ref_source
from pydantic.dataclasses import dataclass


@dataclass
class Component:
    name: str
    schema_: dict


@dataclass
class RefSource:
    name: str
    url: str
    schemas_: dict = Field(default={}, repr=False)
    components_: dict = Field(default={}, repr=False)
    custom_components: list[Component] = Field(default=[], repr=False)

    def __post_init__(self):
        r = requests.get(self.url)
        data = r.json()
        self.schemas_ = data["components"]["schemas"]
        self.components_ = defaultdict(str)
        for k, v in self.schemas_.items():
            self.extend_refs(v)
            self.components_.setdefault(k, v)

    def extend_refs(self, data: dict):
        if "properties" in data.keys():
            for k, v in data["properties"].items():
                comp = v
                if "items" in v.keys():
                    comp = v["items"]

                if "additionalProperties" in v.keys():
                    comp = v["additionalProperties"]

                if "$ref" in comp.keys():
                    ref_name = extract_ref_source(comp["$ref"])
                    if ref_obj := self.schemas_[ref_name]:
                        if "items" in v.keys():
                            data["properties"][k]["items"] = ref_obj
                        else:
                            data["properties"][k] = ref_obj

    def register_new_component(self, component: Component):
        self.custom_components.append(component)

    def fetch_custom_components(self) -> dict:
        return {component.name: component.schema_ for component in self.custom_components}
