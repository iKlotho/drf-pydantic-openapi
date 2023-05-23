from collections import defaultdict

import requests
from pydantic import Field
from pydantic.dataclasses import dataclass

from .utils import extract_ref_source


@dataclass
class RefSource:
    name: str
    url: str
    schemas_: dict = Field(default={}, repr=False)
    components_: dict = Field(default={}, repr=False)
    initialized: bool = Field(default=False, repr=False)

    def init(self):
        if self.initialized:
            return
        r = requests.get(self.url)
        data = r.json()
        self.schemas_ = data["components"]["schemas"]
        self.components_ = defaultdict(str)
        for k, v in self.schemas_.items():
            self.extend_refs(v)
            self.components_.setdefault(k, v)
        self.initialized = True

    def extend_refs(self, data: dict):
        # Replace $refs with definition
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
