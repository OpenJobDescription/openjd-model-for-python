# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
from dataclasses import is_dataclass
from enum import Enum
from typing import Any, ClassVar, Type, TypeVar, cast, Dict, List

import yaml
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ._errors import DecodeValidationError
from ._types import JobTemplate, OpenJDModel, SchemaVersion
from ._convert_pydantic_error import pydantic_validationerrors_to_str, ErrorDict
from .v2023_09 import JobTemplate as JobTemplate_2023_09

__all__ = ("parse_model", "document_string_to_object", "DocumentType", "decode_template")


class DocumentType(str, Enum):
    JSON = "JSON"
    YAML = "YAML"


# Pydantic injects a __pydantic_model__ attribute into all dataclasses. To be able to parse
# dataclass models we need to be able to invoke Model.__pydantic_model__.parse_obj(), but
# type checkers do not realize that pydantic dataclasses have a __pydantic_model__ attribute.
# So, we type-cast into this class to invoke that method.
class PydanticDataclass:
    # See: https://github.com/pydantic/pydantic/blob/b0215d175ace2a3db76307c5f18819b021f48ab5/pydantic/dataclasses.py#L68
    __pydantic_model__: ClassVar[Type[BaseModel]]


T = TypeVar("T", bound=OpenJDModel)


def _parse_model(*, model: Type[T], obj: Any) -> T:
    if is_dataclass(model):
        return cast(T, cast(PydanticDataclass, model).__pydantic_model__.parse_obj(obj))
    else:
        return cast(T, cast(BaseModel, model).parse_obj(obj))


def parse_model(*, model: Type[T], obj: Any) -> T:
    try:
        return _parse_model(model=model, obj=obj)
    except PydanticValidationError as exc:
        raise DecodeValidationError(
            pydantic_validationerrors_to_str(model, cast(List[ErrorDict], exc.errors()))
        )


def document_string_to_object(*, document: str, document_type: DocumentType) -> Dict[str, Any]:
    """
    Converts the YAML or JSON encoded document into a python dictionary.

    Arguments:
        document (str): A string containing a JSON or YAML encoded document.

    Returns:
        Dict[str, Any]: The decoded document.

    Raises:
        DecodeValidationError
    """
    try:
        if document_type == DocumentType.JSON:
            parsed_document = json.loads(document)
        else:  # YAML
            parsed_document = yaml.safe_load(document)
        if not isinstance(parsed_document, dict):
            raise ValueError()
        return parsed_document
    except (ValueError, json.decoder.JSONDecodeError, yaml.YAMLError):
        raise DecodeValidationError(
            f"The document is not a valid {document_type.value} document consisting of key-value pairs."
        )


def decode_template(*, template: Dict[str, Any]) -> JobTemplate:
    """Given a dictionary containing a Job Template, this will decode the template, run validation checks on it,
    and then return the decoded template.

    Args:
        template (Dict[str, Any]): A Job Template as a dictionary object.

    Returns:
        JobTemplate: The decoded job template.

    Raises:
        DecodeValidationError
        NotImplementedError
    """
    try:
        # Raises: KeyError
        document_version = template["specificationVersion"]
        # Raises: ValueError
        schema_version = SchemaVersion(document_version)
    except KeyError:
        # Unable to get 'specificationVersion' key from the document
        raise DecodeValidationError("Template is missing Open Job Description schema version key")
    except ValueError:
        # Value of the schema version is not one we know.
        raise DecodeValidationError(f"Unknown template version: {document_version}")

    if schema_version == SchemaVersion.v2023_09:
        return parse_model(model=JobTemplate_2023_09, obj=template)
    else:
        raise NotImplementedError(
            f"Template decode for schema {schema_version.value} is not yet implemented."
        )
