# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import cast, Any, Callable, Union, Optional
from decimal import Decimal, InvalidOperation

from pydantic_core import PydanticKnownError, ValidationError, InitErrorDetails

from .._format_strings import FormatString


def validate_int_fmtstring_field(
    value: Union[int, float, Decimal, str, FormatString], ge: Optional[int] = None
) -> Union[int, float, Decimal, str, FormatString]:
    """Validates a field that is allowed to be either an integer, a string containing an integer,
    or a string containing expressions that resolve to an integer."""
    value_type_wrong_msg = "Value must be an integer or a string containing an integer."
    # Validate the type
    if isinstance(value, str):
        if not isinstance(value, FormatString):
            value = FormatString(value)
        # If the string value has no expressions, we can validate the value now.
        if len(value.expressions) == 0:
            try:
                int_value = int(value)
            except ValueError:
                raise ValueError(value_type_wrong_msg)
        else:
            # In this case, we cannot validate now. We need to validate this later when the template
            # is instantiated into a job and the expressions have been resolved.
            return value
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        int_value = int(value)
        if int_value != value:
            raise ValueError(value_type_wrong_msg)
    else:
        raise ValueError(value_type_wrong_msg)

    # Validate the value constraints
    if ge is not None and not (int_value >= ge):
        raise PydanticKnownError("greater_than_equal", {"ge": ge})

    return int_value


def validate_float_fmtstring_field(
    value: Union[int, float, Decimal, str, FormatString], ge: Optional[Decimal] = None
) -> Union[int, float, Decimal, str, FormatString]:
    """Validates a field that is allowed to be either an float, a string containing an float,
    or a string containing expressions that resolve to a float."""
    value_type_wrong_msg = "Value must be a float or a string containing a float."
    # Validate the type
    if isinstance(value, str):
        if not isinstance(value, FormatString):
            value = FormatString(value)
        # If the string value has no expressions, we can validate the value now.
        if len(value.expressions) == 0:
            try:
                float_value = Decimal(str(value))
            except InvalidOperation:
                raise ValueError(value_type_wrong_msg)
        else:
            # In this case, we cannot validate now. We need to validate this later when the template
            # is instantiated into a job and the expressions have been resolved.
            return value
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            float_value = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(value_type_wrong_msg)
    else:
        raise ValueError(value_type_wrong_msg)

    # Validate the value constraints
    if ge is not None and not (float_value >= ge):
        raise PydanticKnownError("greater_than_equal", {"ge": ge})

    return float_value


def validate_list_field(value: list, validator: Callable) -> list:
    """Validates a list of values using the provided validator function."""
    errors = list[InitErrorDetails]()
    for i, item in enumerate(value):
        try:
            validator(item)
        except PydanticKnownError as exc:
            # Copy known errors verbatim with added location data
            errors.append(
                InitErrorDetails(
                    type=exc.type,
                    loc=(i,),
                    ctx=exc.context or {},
                    input=item,
                )
            )
        except ValidationError as exc:
            # Convert the ErrorDetails to InitErrorDetails by extending the 'loc' and excluding the 'msg'
            for error_details in exc.errors():
                init_error_details: dict[str, Any] = {}
                for err_key, err_value in error_details.items():
                    if err_key == "loc":
                        init_error_details["loc"] = (i,) + cast(tuple, err_value)
                    elif err_key != "msg":
                        init_error_details[err_key] = err_value
                errors.append(cast(InitErrorDetails, init_error_details))
        except Exception as exc:
            # Copy other errors as value_error
            errors.append(
                InitErrorDetails(
                    type="value_error",
                    loc=(i,),
                    ctx={"error": exc},
                    input=item,
                )
            )
    if errors:
        # Raise the list of all the individual errors as a new ValidationError
        raise ValidationError.from_exception_data("list", line_errors=errors)
    return value
