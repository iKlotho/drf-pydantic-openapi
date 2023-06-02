import re
from dataclasses import dataclass

from rest_framework.schemas.utils import is_list_view

from .utils import method_mapping


@dataclass
class Path:
    """
    Container for application api paths
    """

    path: str
    # used to extract tags
    path_prefix: str
    method: str
    view: callable

    def __post_init__(self):
        if not self.path_prefix.startswith("^"):
            self.path_prefix = "^" + self.path_prefix

    def get_tags(self) -> list[str]:
        return self._tokenize_path()[:1]

    def _tokenize_path(self) -> list:
        # remove path prefix
        path = re.sub(pattern=self.path_prefix, repl="", string=self.path, flags=re.IGNORECASE)
        # remove path variables
        path = re.sub(pattern=r"\{[\w\-]+\}", repl="", string=path)
        # cleanup and tokenize remaining parts.
        path = path.rstrip("/").lstrip("/").split("/")
        return [t for t in path if t]

    def get_operation_id(self) -> str:
        tokenized_path = self._tokenize_path()
        # replace dashes as they can be problematic later in code generation
        tokenized_path = [t.replace("-", "_") for t in tokenized_path]

        if self.method == "GET" and is_list_view(self.path, self.method, self.view):
            action = "list"
        else:
            action = method_mapping[self.method.lower()]

        if not tokenized_path:
            tokenized_path.append("root")

        return "_".join(tokenized_path + [action])
