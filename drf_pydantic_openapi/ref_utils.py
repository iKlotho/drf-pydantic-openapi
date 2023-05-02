import re

from pydantic import BaseModel, Extra, Field, PrivateAttr, create_model
from pydantic.dataclasses import dataclass
from .utils import add_source_name_to_ref
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
    for key in keys:
        if isinstance(obj, dict):
            if key in obj:
                obj = obj[key]

    if isinstance(obj, dict):
        obj.pop(last, None)

    if isinstance(obj, Iterable):
        for ele in obj:
            if isinstance(ele, dict):
                ele.pop(last, None)


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

        model_name = f"{source}_{name}"

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

                    props = schema["properties"]
                    ref_model_name = f"{model._ref_source}_{model._ref_model_name}"
                    if schema_ := config.get_source(model._ref_source):
                        print("EXTENDING model", ref_model_name)
                        print("schema_", schema_)
                        ref_obj = schema_.get(ref_model_name, {}).get("properties", {})
                        for schema_name, schema_value in schema_.items():
                            print(f"new name {model.__name__}_{schema_name}")
                            schema[f"{model.__name__}_{schema_name}"] = schema_value

                        # REMOVE fields set exclude
                        for field in exclude_fields:
                            print("Excluding the val", field)
                            delete_key_from_dict(ref_obj, field)

                        # RENAME field
                        for rename_obj in rename_fields:
                            original_name, new_name = rename_obj
                            if original_value := ref_obj.pop(original_name, None):
                                print("rog", original_value, new_name)
                                original_value["title"] = new_name
                                ref_obj[new_name] = original_value

                        # OVERRIDE
                        # Remove same fields from ref obj to allow override
                        for field in model.__fields__:
                            ref_obj.pop(field, None)

                        props.update(**ref_obj)
                        print("schema", schema_.get(ref_model_name))
                    else:
                        print(f"Couldnt extend the model. Ref name: {ref_model_name}")

        model = create_model(model_name, __base__=Base)

        model
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
