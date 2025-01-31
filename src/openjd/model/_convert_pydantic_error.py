# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Type, Union
from pydantic import BaseModel
from pydantic_core import ErrorDetails
from inspect import getmodule


def pydantic_validationerrors_to_str(
    root_model: Type[BaseModel], errors: list[ErrorDetails]
) -> str:
    """This is our own custom stringification of the Pydantic ValidationError to use
    in place of str(<ValidationError>). Pydantic's default stringification too verbose for
    our purpose, and contains information that we don't want.
    """
    results = list[str]()
    for error_details in errors:
        results.append(_error_dict_to_str(root_model, error_details))
    return f"{len(errors)} validation errors for {root_model.__name__}\n" + "\n".join(results)


def _error_dict_to_str(root_model: Type[BaseModel], error_details: ErrorDetails) -> str:
    error_type = error_details["type"]
    loc = error_details["loc"]
    # Skip the "Value error," prefix by getting the exception message directly.
    # This preserves the message formatting created when Pydantic V1 was in use.
    if error_type == "value_error":
        msg = str(error_details["ctx"]["error"])
    else:
        msg = error_details["msg"]

    # When a model's root_validator raises an error other than a ValidationError
    # (i.e. raises something like a ValueError or a TypeError) then pydantic
    # reports the field name of the error as "__root__". We handle this specially
    # when printing errors out since there are no "__root__" fields in our models,
    # and we don't want to mislead or confuse customers.
    # "__root__" will *always* be the last element of the 'loc' if it is present, by
    # definition of how root validators work.
    #
    # We want errors from the base model's root validator to not be indented.
    # This conveys that the error isn't from a nested object.
    # eg.
    # ```
    # field -> inner:
    #    field missing
    # JobTemplate: must provide one of 'min' or 'max'
    # ```
    if loc == ("__root__",):
        return f"{root_model.__name__}: {msg}"
    return f"{_loc_to_str(root_model, loc)}:\n\t{msg}"


def _loc_to_str(root_model: Type[BaseModel], loc: tuple[Union[int, str], ...]) -> str:
    model_module = getmodule(root_model)

    # If a nested error is from a root validator, then just report the error as being
    # for the field that points to the object.
    if loc[-1] == "__root__":
        loc = loc[:-1]

    loc_elements = list[str]()
    for item in loc:
        if isinstance(item, int):
            loc_elements[-1] = f"{loc_elements[-1]}[{item}]"
        elif item in model_module.__dict__:
            # If the name appears in the same module as the model then it is itself
            # a model. This means that it's inserted because we're somewhere within
            # a discriminated union; pydantic includes the name of the union class
            # in the loc when traversing through a discriminated union (but, oddly,
            # *only* when traversing through a discriminated union).
            pass
        else:
            loc_elements.append(item)
    return " -> ".join(loc_elements)
