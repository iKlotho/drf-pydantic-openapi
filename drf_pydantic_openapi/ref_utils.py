import re
from collections import OrderedDict
from typing import ClassVar, Iterable, Type

from loguru import logger
from pydantic import BaseModel, create_model

from .settings import config


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


class RefTypeFactory:
    def __call__(self, source: str, name: str) -> Type:
        """
        Create a pydantic model to reference other source of openapi definitionts.
        `schema_extra` method will be called when the pydantic converts the object to json schema.
        With this method new keys can be added to result
        """

        class Base(BaseModel):
            _ref_source: ClassVar[str] = source
            _ref_model_name: ClassVar[str] = name

            class Config:
                @staticmethod
                def schema_extra(schema: dict, model) -> None:
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
                        ref_component = ref_source.components_[model._ref_model_name]
                        if not isinstance(ref_component, dict):
                            logger.warning(f"Cant extend type: {type(ref_component)}")
                            return

                        ref_component = ref_component.copy()
                        ref_properties = ref_component.get("properties", {})

                        for field in exclude_fields:
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
                        # Sort properties by key, can be removed
                        schema["properties"] = OrderedDict(sorted(properties.items(), key=lambda t: t[0]))

                    else:
                        print(
                            f"Couldnt extend the model. Ref name: {model._ref_model_name}, source: {model._ref_source}"
                        )

        model = create_model(name, __base__=Base)

        return type(
            name,
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
