# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from dataclasses import dataclass
from numbers import Real
from typing import TYPE_CHECKING, Optional, Union

from .._errors import ExpressionError, TokenError
from .._symbol_table import SymbolTable
from ._dyn_constrained_str import DynamicConstrainedStr
from ._expression import InterpolationExpression

if TYPE_CHECKING:
    from pydantic.v1.typing import CallableGenerator


@dataclass
class ExpressionInfo:
    start_pos: int
    end_pos: int
    expression: Optional[InterpolationExpression] = None
    resolved_value: Optional[Union[Real, str]] = None


class FormatStringError(Exception):
    def __init__(self, *, string: str, start: int, end: int, expr: str = "", details: str = ""):
        expression = f"Expression: {expr}. " if expr else ""
        reason = f"Reason: {details}." if details else ""
        msg = (
            f"Failed to parse interpolation expression at [{start}, {end}]. "
            f"{expression}"
            f"{reason}"
        )
        super().__init__(msg)

    def __str__(self) -> str:
        return self.args[0]


class FormatString(DynamicConstrainedStr):
    def __init__(self, value: str):
        """
        Instantiate a FormatString from a given string.

        Verifies that each pair of opening curly braces {{ has a corresponding pair
        of closing curly braces }}, and vice versa.

        Also, verifies that each interpolation expression inside of {{ }} has a valid format.

        Parameters
        ----------
        original_string: str
            A string that contains 0 or more interpolation expressions.
            For example, 'text', '{{expr}}', '{{ expr }}', 'text {{expr}}text{{expr}} text',
            are all valid inputs.

        Raises
        ------
        FormatStringError: if the original string is nonvalid.
        """
        # Note: str is constructed in __new__, so don't call super __init__
        self._processed_list: list[Union[str, ExpressionInfo]] = self._preprocess()

    @property
    def original_value(self) -> str:
        """
        Returns
        -------
        original_string: str
            An original string passed during the construction of this object.
        """
        return self

    @property
    def expressions(self) -> list[ExpressionInfo]:
        """
        Returns
        -------
        expressions: list[ExpressionInfo]
            A list of all interpolation expressions in this interpolated string.
        """
        return [expr for expr in self._processed_list if isinstance(expr, ExpressionInfo)]

    def resolve(self, *, symtab: SymbolTable) -> str:
        """
        Uses a given symbol table to resolve an interpolated string.
        Each interpolation expression in the original string is replaced
        by a value from the symbol table.

        Parameters
        ----------
        symtab: SymbolTable
            A symbol table with values that are used to resolve interpolation
            expressions in the interpolated string.
            For example, to resolve '{{Some.data}}' the table should contain
            the value for 'Some.data'.

        Returns
        -------
        resolved_string:
            A resolved string with all interpolation expressions replaced with corresponding values.

        Raises
        ------
        FormatStringError: if it is impossible to resolve
        all interpolation expressions with a given symbol table.
        """
        resolved_list: list[str] = []
        for element in self._processed_list:
            assert isinstance(element, (ExpressionInfo, str))
            if isinstance(element, str):
                resolved_list.append(element)
                continue

            assert element.expression is not None
            try:
                element.resolved_value = element.expression.evaluate(symtab=symtab)
            except ExpressionError as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=element.start_pos,
                    end=element.end_pos,
                    expr=element.expression.expr,
                    details=str(exc),
                )

            resolved_list.append(str(element.resolved_value))

        return "".join(resolved_list)

    def _preprocess(self) -> list[Union[str, ExpressionInfo]]:
        """
        Scans through the original string to find all interpolation expressions inside of {{ }}.
        Also, validates the content of each interpolation expression inside of {{ }}.

        The output format is designed to be used later by `resolve()` function.
        It allows us to replace each ExpressionInfo with a resolved value
        and then efficiently combine simple strings and resolved values into the final string.

        Raises
        ------
        FormatStringError
            - if the string contains opening pair {{ without a matching closing pair,
              and vice versa.
            - if any expression inside of {{ }} is nonvalid.

        Returns
        -------
        preprocessed_list: list[Union[str, ExpressionInfo]]
            A list, where each element is either
                - a string that doesn't contain interpolation expression {{ }}, or
                - an instance of ExpressionInfo
            For example, for original string 'a {{ B.C }} d {{ E.f }}' the list will be
            ['a ', ExpressionInfo({{ B.C }}), ' d ', ExpressionInfo({{ E.f }})]
        """
        result_list: list[Union[str, ExpressionInfo]] = []

        opening = "{{"
        closing = "}}"

        braces_end = 0
        while braces_end < len(self):
            braces_start = self.find(opening, braces_end)
            expression_end = self.find(closing, braces_end)

            if braces_start == -1 and expression_end == -1:
                result_list.append(self[braces_end:])
                break

            if expression_end < braces_start:
                raise FormatStringError(
                    string=self.original_value,
                    start=braces_end,
                    end=len(self.original_value),
                    details="Braces mismatch",
                )

            if braces_start == -1 and expression_end != -1:
                raise FormatStringError(
                    string=self.original_value,
                    start=braces_end,
                    end=(expression_end + len(closing)),
                    details="Missing opening braces",
                )

            result_list.append(self[braces_end:braces_start])

            expression_start = braces_start + len(opening)
            braces_end = expression_end + len(closing)

            expression_info = ExpressionInfo(braces_start, braces_end)
            try:
                expr = InterpolationExpression(self[expression_start:expression_end])
            except (ExpressionError, TokenError) as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=expression_info.start_pos,
                    end=expression_info.end_pos,
                    details=str(exc),
                )

            expression_info.expression = expr
            result_list.append(expression_info)

        return result_list

    # Pydantic datamodel interfaces
    # ================================
    # Reference: https://pydantic-docs.helpmanual.io/usage/types/#custom-data-types

    @classmethod
    def __get_validators__(cls) -> "CallableGenerator":
        for validator in super().__get_validators__():
            yield validator
        yield cls._validate

    @classmethod
    def _validate(cls, value: str) -> "FormatString":
        # Reference: https://pydantic-docs.helpmanual.io/usage/validators/
        # Class constructor will raise validation errors on the value contents.
        try:
            return cls(value)
        except FormatStringError as e:
            # Pydantic validators must return a ValueError or AssertionError
            # Convert the FormatStringError into a ValueError
            raise ValueError(str(e))
