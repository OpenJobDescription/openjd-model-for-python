# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from dataclasses import dataclass
from typing import Any, Optional, Union

from .._errors import ExpressionError, TokenError
from .._symbol_table import SymbolTable
from ._dyn_constrained_str import DynamicConstrainedStr
from ._expression import InterpolationExpression
from .._types import ModelParsingContextInterface, SpecificationRevision


class _ReconstructionContext(ModelParsingContextInterface):
    """Minimal parsing context used when a FormatString is reconstructed by
    pickle or the copy module (see ``FormatString.__getnewargs_ex__``).

    It carries only the parse-relevant snapshot (specification revision and
    extension set) that the FormatString recorded at construction time, so
    the reconstructed instance is re-parsed under the same grammar (EXPR vs
    legacy) as the original.
    """


@dataclass
class ExpressionInfo:
    start_pos: int
    end_pos: int
    expression: Optional[InterpolationExpression] = None
    # The string form substituted into the surrounding format string, produced
    # by InterpolationExpression.evaluate_to_str during resolve().
    resolved_value: Optional[str] = None


class FormatStringError(ValueError):
    def __init__(self, *, string: str, start: int, end: int, expr: str = "", details: str = ""):
        self.input = string
        expression = f"Expression: {expr}. " if expr else ""
        reason = f"Reason: {details}." if details else ""
        msg = f"Failed to parse interpolation expression at [{start}, {end}]. {expression}{reason}"
        super().__init__(msg)


class FormatString(DynamicConstrainedStr):
    _processed_list: list[Union[str, ExpressionInfo]]
    # Parse-relevant snapshot of the construction context, recorded so that
    # pickle/copy reconstruction re-parses the string under the same grammar
    # (EXPR vs legacy). The context object itself is not retained: it is
    # shared and mutable (its extension set is narrowed while the template's
    # `extensions` field is validated), so we snapshot at construction time.
    _parse_spec_rev: SpecificationRevision
    _parse_extensions: frozenset[str]

    def __new__(cls, value: str, *, context: ModelParsingContextInterface):
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
        self = super().__new__(cls, value, context=context)
        self._parse_spec_rev = context.spec_rev
        self._parse_extensions = frozenset(context.extensions)
        self._processed_list = self._preprocess(context=context)
        return self

    def __getnewargs_ex__(self) -> tuple[tuple[str], dict[str, Any]]:
        """Support for pickling and copying (``pickle``, ``copy.copy``,
        ``copy.deepcopy``, and pydantic's ``model_copy(deep=True)``).

        ``str.__getnewargs__`` supplies only the string value, which cannot
        satisfy the keyword-only ``context`` argument of ``__new__`` — and for
        subclasses that default the argument, it would re-parse an
        EXPR-grammar string with the legacy parser. Reconstruct through
        ``__new__`` with a context carrying the recorded parse snapshot so
        the copy is parsed exactly as the original was.
        """
        context = _ReconstructionContext(
            spec_rev=self._parse_spec_rev,
            supported_extensions=self._parse_extensions,
        )
        return ((str(self),), {"context": context})

    def __getstate__(self) -> None:
        """No instance state is serialized: ``_processed_list`` holds
        engine-backed parse trees that cannot be pickled, and ``__new__``
        fully rebuilds it (and the parse snapshot) from the string value and
        the reconstruction context (see ``__getnewargs_ex__``)."""
        return None

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

    def resolve(self, *, symtab: SymbolTable, path_format: Optional[object] = None) -> str:
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
                # evaluate_to_str applies the engine's spec-defined string
                # coercion for EXPR results (RFC 0005), so booleans/null/lists
                # render per the specification rather than as Python reprs.
                element.resolved_value = element.expression.evaluate_to_str(
                    symtab=symtab, path_format=path_format
                )
            except ExpressionError as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=element.start_pos,
                    end=element.end_pos,
                    expr=element.expression.expr,
                    details=str(exc),
                )

            resolved_list.append(element.resolved_value)

        return "".join(resolved_list)

    def whole_field_expression(self) -> Optional["ExpressionInfo"]:
        """The format string's single whole-field expression, or ``None``.

        A format string is *whole-field* when it consists of exactly one
        ``{{ ... }}`` expression with only whitespace outside the braces
        (Template Schemas: fields with ``string?``/typed null semantics).
        Single-sourced here so every whole-field check (typed value
        resolution, RFC 0006 typed list instantiation) agrees on the rule.
        """
        expressions = self.expressions
        if len(expressions) != 1:
            return None
        info = expressions[0]
        if info.expression is None:
            return None
        prefix = self.original_value[: info.start_pos]
        suffix = self.original_value[info.end_pos :]
        if prefix.strip() or suffix.strip():
            return None
        return info

    def resolve_value(self, *, symtab: SymbolTable, path_format: Optional[object] = None) -> Any:
        """Typed resolution of this format string (RFC 0005/0006).

        When the format string is a single whole-field ``{{ ... }}`` EXPR
        expression (only whitespace outside the braces), returns the engine's
        typed value (an ``ExprValue``), preserving lists, null, and numeric
        types — callers such as the session runner's argument resolution use
        this for RFC 0005 §1.3.2 list flattening and null skipping, mirroring
        openjd-rs's ``FormatString::resolve_with``. In every other case
        (multi-segment strings, legacy non-EXPR expressions) the result is the
        ordinary resolved string, identical to :meth:`resolve`.

        Raises:
            FormatStringError: if the expression cannot be evaluated.
        """
        info = self.whole_field_expression()
        if info is not None:
            expression = info.expression
            assert expression is not None  # guaranteed by whole_field_expression
            try:
                return expression.evaluate_value(symtab=symtab, path_format=path_format)
            except ExpressionError as exc:
                raise FormatStringError(
                    string=self.original_value,
                    start=info.start_pos,
                    end=info.end_pos,
                    expr=expression.expr,
                    details=str(exc),
                )
        return self.resolve(symtab=symtab, path_format=path_format)

    def _preprocess(
        self, *, context: ModelParsingContextInterface
    ) -> list[Union[str, ExpressionInfo]]:
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
                expr = InterpolationExpression(
                    self[expression_start:expression_end], context=context
                )
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
