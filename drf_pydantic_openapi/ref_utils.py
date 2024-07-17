import copy
from collections import OrderedDict
from collections.abc import Iterable
from typing import ClassVar

from loguru import logger
from pydantic import BaseModel, ConfigDict, create_model

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


def json_schema_extra(schema: dict, model: BaseModel) -> None:
    exclude_fields = set()
    rename_fields = set()

    model_config = model.model_config

    if ref_exclude := model_config.get("ref_exclude"):
        for val in ref_exclude:
            exclude_fields.add(val)

    if ref_rename := model_config.get("ref_rename"):
        for val in ref_rename:
            rename_fields.add(val)

    properties = schema["properties"]
    # Find the reference source schema
    if ref_source := config.get_source(model._ref_source):
        ref_component = ref_source.components_[model._ref_model_name]
        if not isinstance(ref_component, dict):
            logger.warning(f"Can't extend type: {type(ref_component)} with model {model._ref_model_name}")
            return

        ref_component = copy.deepcopy(ref_component)
        ref_properties = ref_component.get("properties", {})
        ref_additional_properties = ref_component.get("additionalProperties", {})
        ref_required = ref_component.get("required", [])

        for field in exclude_fields:
            delete_key_from_dict(ref_properties, field)
            if field in ref_required:
                ref_required.remove(field)

        for rename_obj in rename_fields:
            original_name, new_name = rename_obj
            if original_name in ref_required:
                ref_required.remove(original_name)
                ref_required.append(new_name)

            if original_value := ref_properties.pop(original_name, None):
                original_value["title"] = " ".join(p.capitalize() for p in new_name.split("_"))
                ref_properties[new_name] = original_value

        # OVERRIDE
        # Remove same fields from ref obj to allow override
        for field in model.model_fields.keys():
            ref_properties.pop(field, None)

        properties.update(**ref_properties)
        # Sort properties by key, can be removed
        schema["properties"] = OrderedDict(sorted(properties.items(), key=lambda t: t[0]))
        schema["required"] = list(set(schema.get("required", []) + ref_required))
        if ref_additional_properties:
            schema["additionalProperties"] = ref_additional_properties

    else:
        logger.warning(f"Couldn't extend the model. Ref name: {model._ref_model_name}, source: {model._ref_source}")


class RefTypeFactory:
    def __call__(self, source: str, name: str) -> type:
        """
        Create a pydantic model to reference other source of openapi definitionts.
        `json_schema_extra` method will be called when the pydantic converts the object to json schema.
        With this method new keys can be added to result
        """

        class Base(BaseModel):
            _ref_source: ClassVar[str] = source
            _ref_model_name: ClassVar[str] = name
            model_config = ConfigDict(
                json_schema_extra=json_schema_extra,
            )

        model = create_model(name, __base__=Base)

        return type(
            name,
            (model,),
            {},
        )


RefType = RefTypeFactory()
