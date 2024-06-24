from collections import defaultdict

import jsonref
import requests
from pydantic import Field
from pydantic.dataclasses import dataclass


@dataclass
class RefSource:
    name: str
    url: str
    schemas_: dict = Field(default={}, repr=False)
    components_: dict = Field(default={}, repr=False)
    initialized: bool = Field(default=False, repr=False)

    def init(self, force: bool = False):
        if not force and self.initialized:
            return
        r = requests.get(self.url, timeout=5)
        data = jsonref.loads(r.text)
        # self.replace_refs_with_empty_dict(data)
        self.schemas_ = data["components"]["schemas"]
        self.components_ = defaultdict(str)
        for k, v in self.schemas_.items():
            self.components_.setdefault(k, v)
        self.initialized = True
