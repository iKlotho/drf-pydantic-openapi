from pydantic import Field
import json
import re
import requests
from .utils import add_source_name_to_ref
from pydantic.dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class RefSource:
    name: str
    url: str
    schemas_: dict = Field(default={}, repr=False)

    def __post_init__(self):
        r = requests.get(self.url)
        raw_data = r.text
        # Add source name prefix to schema models
        # CpeDataModel -> soothsayer_CpeDataModel
        pattern = r'"\$ref":\s*"#/components/schemas/(\w+)"'
        raw_data = re.sub(
            pattern,
            lambda match: match.group(0).replace(match.group(1), f"{self.name}_{match.group(1)}"),
            raw_data,
        )
        data = json.loads(raw_data)
        self.schemas_ = {add_source_name_to_ref(self.name, k): v for k, v in data["components"]["schemas"].items()}
