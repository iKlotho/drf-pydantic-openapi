from collections import OrderedDict
import re

from pydantic import BaseModel, Extra, Field, PrivateAttr, create_model
from pydantic.dataclasses import dataclass

from drf_pydantic_openapi.ref_source import Component
from .utils import add_source_name_to_ref, extract_ref_source
from typing import ClassVar, Type
from jsonpath_ng import jsonpath, parse
from typing import Iterable
from copy import deepcopy


def delete_key_from_dict(obj: dict, key: str):
    """
    Delete given key from dictionary
    Accepts `a.b`, `a.b.c` notion
    TODO: support list of dict
    """
    keys = key.split(".")
    last = keys.pop()
    if "properties" in obj.keys():
        obj = obj["properties"]

    for key in keys:
        if isinstance(obj, dict):
            if key in obj:
                obj = obj[key]
        if "properties" in obj.keys():
            obj = obj["properties"]

    if isinstance(obj, Iterable):
        for ele in obj:
            if isinstance(ele, dict):
                ele.pop(last, None)

    if isinstance(obj, dict):
        obj.pop(last, None)


def resolve_schema(schema_: dict, model: str):
    # Extract model and its rrefs
    if model in schema_:
        pass


class RefTypeFactory:
    def __call__(self, source: str, name: str) -> Type:
        """
        Create new pydantic object with a name that has source prefix
        Since source ref models will be in a following format source_MODEL
        We can call $ref to this model within our newly created type
        """

        model_name = f"{name}"

        class Base(BaseModel):
            _ref_source: ClassVar[str] = source
            _ref_model_name: ClassVar[str] = name

            class Config:
                @staticmethod
                def schema_extra(schema: dict, model) -> None:
                    from .settings import config

                    exclude_fields = set()
                    rename_fields = set()

                    model_config = model.__config__

                    if hasattr(model_config, "ref_exclude"):
                        for val in model_config.ref_exclude:
                            exclude_fields.add(val)

                    if hasattr(model_config, "ref_rename"):
                        for val in model_config.ref_rename:
                            rename_fields.add(val)

                    properties = schema["properties"]
                    # Find the reference source schema
                    if ref_source := config.get_source(model._ref_source):
                        # Copy ref component to modify as we need
                        ref_component = ref_source.components_[model._ref_model_name]
                        if not isinstance(ref_component, dict):
                            print("Cant extend str model")
                            return

                        ref_component = ref_component.copy()
                        ref_properties = ref_component.get("properties", {})

                        for field in exclude_fields:
                            print(f"Deleting the field", field, "ref", ref_properties)
                            delete_key_from_dict(ref_properties, field)

                        for rename_obj in rename_fields:
                            original_name, new_name = rename_obj
                            if original_value := ref_properties.pop(original_name, None):
                                original_value["title"] = " ".join(p.capitalize() for p in new_name.split("_"))
                                ref_properties[new_name] = original_value

                        # OVERRIDE
                        # Remove same fields from ref obj to allow override
                        for field in model.__fields__:
                            ref_properties.pop(field, None)

                        properties.update(**ref_properties)
                        # Sort properties by key
                        schema["properties"] = OrderedDict(sorted(properties.items(), key=lambda t: t[0]))

                    else:
                        print(
                            f"Couldnt extend the model. Ref name: {model._ref_model_name}, source: {model._ref_source}"
                        )

        model = create_model(model_name, __base__=Base)

        return type(
            model_name,
            (model,),
            {},
        )

    @classmethod
    def from_ref(cls, ref: str):
        pattern = r"#/components/schemas/(\w+)"
        match = re.search(pattern, ref)
        model_name = match.group(1)
        source, name = model_name.split("_")
        return RefType(source, name)


RefType = RefTypeFactory()
