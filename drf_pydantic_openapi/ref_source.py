from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

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

    def _load_resource(self) -> str:
        parsed = urlparse(self.url)
        if parsed.scheme == "file":
            return Path(parsed.path).read_text()
        elif parsed.scheme in ["http", "https"]:
            r = requests.get(self.url, timeout=5)
            return r.text
        else:
            raise Exception("invalid resource scheme")

    def init(self, force: bool = False) -> None:
        if not force and self.initialized:
            return
        data = jsonref.loads(self._load_resource())
        # self.replace_refs_with_empty_dict(data)
        self.schemas_ = data["components"]["schemas"]
        self.components_ = defaultdict(str)
        for k, v in self.schemas_.items():
            self.components_.setdefault(k, v)
        self.initialized = True
