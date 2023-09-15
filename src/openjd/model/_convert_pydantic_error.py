# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import TypedDict, Union, Type
from pydantic import BaseModel
from inspect import getmodule

# Calling pydantic's ValidationError.errors() returns a list[ErrorDict], but
# pydantic doesn't export the ErrorDict type publicly. So, we create it here for
# type checking.
# Note that we ignore the 'ctx' key since we don't use it.
# See: https://github.com/pydantic/pydantic/blob/d9c2af3a701ca982945a590de1a1da98b3fb4003/pydantic/error_wrappers.py#L50
Loc = tuple[Union[int, str], ...]


class ErrorDict(TypedDict):
    loc: Loc
    msg: str
    type: str


def pydantic_validationerrors_to_str(root_model: Type[BaseModel], errors: list[ErrorDict]) -> str:
    """This is our own custom stringification of the Pydantic ValidationError to use
    in place of str(<ValidationError>). Pydantic's default stringification too verbose for
    our purpose, and contains information that we don't want.
    """
    results = list[str]()
    for error in errors:
        results.append(_error_dict_to_str(root_model, error))
    return f"{len(errors)} validation errors for {root_model.__name__}\n" + "\n".join(results)


def _error_dict_to_str(root_model: Type[BaseModel], error: ErrorDict) -> str:
    loc = error["loc"]
    msg = error["msg"]

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


def _loc_to_str(root_model: Type[BaseModel], loc: Loc) -> str:
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
