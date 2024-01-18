# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from bisect import bisect
from collections.abc import Iterator, Sized
from functools import total_ordering
from itertools import chain
from typing import Tuple

from ._errors import ExpressionError, TokenError
from ._tokenstream import Token, TokenStream, TokenType


class IntRangeExpr(Sized):
    """An Int Range Expression is a set of integer values represented as a sorted list of IntRange objects."""

    _start: int
    _end: int
    _ranges: list[IntRange]
    _length: int
    _range_length_indicies: list[int]

    def __init__(self, ranges: list[IntRange]):
        # Sort the ranges, then combine them where possible
        sorted_ranges = sorted(ranges)
        self._ranges = [sorted_ranges[0]]
        for range in sorted_ranges[1:]:
            if (
                self._ranges[-1].step == range.step
                and self._ranges[-1].end + range.step == range.start
            ):
                self._ranges[-1] = IntRange(self._ranges[-1].start, range.end, range.step)
            else:
                self._ranges.append(range)
        self._start = self.ranges[0].start
        self._end = self.ranges[-1].end

        # used to binary search ranges for __getitem__
        # ie. [32, 100, 132]
        self._range_length_indicies = []
        length = 0
        for r in self.ranges:
            length += len(r)
            self._range_length_indicies.append(length)

        self._length = length

        self._validate()

    @staticmethod
    def from_str(range_str: str) -> IntRangeExpr:
        """Creates a range expression object from a range stored as a string."""
        return Parser().parse(range_str)

    @staticmethod
    def from_list(values: list[int | str]) -> IntRangeExpr:
        """Creates a range expression object from a list of integers/strings containing integers."""
        if len(values) == 0:
            return IntRangeExpr([])
        elif len(values) == 1:
            value = int(values[0])
            return IntRangeExpr([IntRange(value, value)])
        else:
            # Convert to integers, remove duplicates, and sort
            values_as_int: list[int] = sorted({int(i) for i in values})
            # Find all the ranges, and concatenate them
            ranges = []
            start = values_as_int[0]
            step = None

            for value in values_as_int[1:]:
                if step is None:
                    end = value
                    step = end - start
                else:
                    if value - end == step:
                        end = value
                    else:
                        ranges.append(IntRange(start, end, step))
                        start = value
                        step = None
            ranges.append(IntRange(start, end, step or 1))
            return IntRangeExpr(ranges)

    def __len__(self) -> int:
        return self._length

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IntRangeExpr):
            raise NotImplementedError
        return self.ranges == other.ranges

    def __str__(self) -> str:
        return ",".join(str(range) for range in self.ranges)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.ranges})"

    def __iter__(self) -> Iterator[int]:
        return chain(*self.ranges)

    def __getitem__(self, index: int) -> int:
        """
        Note: since we have to binary search the underlying ranges in the expression, this function is O(log(n))
        """
        # support negative indicies
        if index < 0:
            index = len(self) + index

        if not (0 <= index < self._length):
            raise IndexError(f"index {index} is out of range")

        # gets the index for insertion position
        # (ie. we receive the index to the range that contains the item we're looking for)
        range_index = bisect(self._range_length_indicies, index)
        if range_index == 0:
            return self.ranges[0][index]
        else:
            actual_index = index - self._range_length_indicies[range_index - 1]
            return self.ranges[range_index][actual_index]

    @property
    def start(self) -> int:
        """The smallest value in the range expression."""
        return self._start

    @property
    def end(self) -> int:
        """The largest value in the range expression"""
        return self._end

    @property
    def ranges(self) -> list[IntRange]:
        """read-only property"""
        return self._ranges.copy()

    def _validate(self) -> None:
        """raises: ValueError - if not valid"""

        if len(self) <= 0:
            raise ValueError("range expression cannot be empty")

        # Validate that the ranges are not overlapping
        prev_range: IntRange | None = None
        for range_ in self.ranges:
            # With the ranges already sorted, we can just ensure that
            # earlier entries are completely less than later entries, regardless
            # of ascending vs. descending
            if prev_range and max(prev_range.start, prev_range.end) >= min(
                range_.start, range_.end
            ):
                raise ValueError(
                    f"Range expression is not valid due to overlapping ranges:\n"
                    f"\t{prev_range} overlaps with {range_}"
                )
            prev_range = range_


@total_ordering
class IntRange(Sized):
    """Inclusive on the start and end value"""

    _start: int
    _end: int
    _step: int
    _range: range

    def __init__(self, start: int, end: int, step: int = 1):
        self._start = start
        self._end = end
        self._step = step

        # makes the range inclusive on end value
        offset = 0
        if self._step > 0:
            offset = 1
        elif self._step < 0:
            offset = -1

        self._range = range(self._start, self._end + offset, self._step)

        self._validate()

    def __str__(self) -> str:
        if len(self) == 1:
            return str(self._start)
        elif self.step == 1:
            return f"{self._start}-{self._end}"
        else:
            return f"{self._start}-{self._end}:{self._step}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(start={self._start}, end={self._end}, step={self._step})"

    def __len__(self):
        return len(self._range)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IntRange):
            raise NotImplementedError
        return (self.start, self.end, self.step) == (other.start, other.end, other.step)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, IntRange):
            raise NotImplementedError
        return (self.start, self.end, self.step) < (other.start, other.end, other.step)

    def __iter__(self) -> Iterator[int]:
        return iter(self._range)

    def __getitem__(self, index: int) -> int:
        if index >= len(self):
            raise IndexError(f"index {index} is out of range")
        return self._range[index]

    @property
    def start(self) -> int:
        """read-only property"""
        return self._start

    @property
    def end(self) -> int:
        """read-only property"""
        return self._end

    @property
    def step(self) -> int:
        """read-only property"""
        return self._step

    def _validate(self) -> None:
        """raises: ValueError - if not valid"""

        if self._step == 0:
            raise ValueError("Range: step must not be zero")

        if self._start < self._end and self._step < 0:
            raise ValueError("Range: an ascending range must have a positive step")

        if self._start > self._end and self._step > 0:
            raise ValueError("Range: a descending range must have a negative step")

        if len(self) <= 0:
            raise ValueError("Range: cannot be empty")


class PosIntToken(Token):
    """A positive integer"""


class HyphenToken(Token):
    """The '-' character."""


class ColonToken(Token):
    """The ':' character."""


class CommaToken(Token):
    """The ',' character."""


# Map of TokenTypes to their corresponding Token class.
# Required by the TokenStream used by the parser to map
# lexical tokens to the correct token class.
_tokenmap = {
    TokenType.POSINT: PosIntToken,
    TokenType.HYPHEN: HyphenToken,
    TokenType.COLON: ColonToken,
    TokenType.COMMA: CommaToken,
}


class Parser:
    """Range expression parser.

    Full Grammar:
        <RangeExpr> ::= <Element> | <Element>,<RangeExpr>
        <Element> ::= <WS>*<Number><WS>* | <WS>*<Range><WS>* | <WS>*<StepRange><WS>*
        <Range> ::= <Number><WS>*-<WS>*<Number>
        <StepRange> ::= <Range>:<Step>
        <Number> ::= Any numeric base-10 value (int)
        <Step> ::= base-10 non-zero number
        <WS> ::= whitespace character: tabs or spaces
    """

    def parse(self, expr: str) -> IntRangeExpr:
        """Generate an IntRangeExpr for the given string range expression.

        Raises:
            TokenError: If an unexpected token is encountered.
            ExpressionError: If the expresssion is malformed.
        """

        # Raises: TokenError
        self._tokens = TokenStream(expr, supported_tokens=_tokenmap)

        if self._tokens.at_end():
            raise ExpressionError("Empty expression")

        result = self._expression()
        if not self._tokens.at_end():
            token = self._tokens.next()
            raise TokenError(self._tokens.expr, token.value, token.start)

        return result

    def _integer(self) -> Tuple[str, PosIntToken]:
        """Matches one number (integer) within a range expression

        Grammar:
            <Number> ::= Any numeric base-10 value (int)
        """
        num_sign = "+"  # positive/negative 0 is still 0

        try:
            # Check if there's a hyphen preceding the number, indicating a negative number
            if isinstance(self._tokens.lookahead(0), HyphenToken):
                num_sign = "-"
                self._tokens.next()

            token = self._tokens.next()
            if not isinstance(token, PosIntToken):
                raise ExpressionError(f"Expected {PosIntToken}, received {token}")
        except IndexError as e:
            raise ExpressionError(
                "Unexpectedly reached end of expression when parsing an integer"
            ) from e

        return num_sign, token

    def _range(self) -> IntRange:
        """Matches one element within a range expression.

        Grammar:
            <Element> ::= <WS>*<Number><WS>* | <WS>*<Range><WS>* | <WS>*<StepRange><WS>*
            <StepRange> ::= <Range>:<Step>
            <Range> ::= <Number><WS>*-<WS>*<Number>
            <Number> ::= Any numeric base-10 value (int)
            <Step> ::= base-10 non-zero number
            <WS> ::= whitespace character: tabs or spaces

        Raises
            ExpressionError: If the expresssion is malformed.

        Returns:

        """
        # get the start integer
        start_sign, start = self._integer()

        # Just a start number? Technically a Range
        if self._tokens.at_end() or isinstance(self._tokens.lookahead(0), CommaToken):
            return IntRange(
                start=int(start_sign + start.value), end=int(start_sign + start.value), step=1
            )

        token = self._tokens.next()
        if not isinstance(token, HyphenToken):
            raise ExpressionError(f"Expected {HyphenToken}, received {token}")

        # get the end integer
        end_sign, end = self._integer()

        # Check if we're done with this range, or if there's a step to handle
        if self._tokens.at_end() or isinstance(self._tokens.lookahead(0), CommaToken):
            return IntRange(
                start=int(start_sign + start.value), end=int(end_sign + end.value), step=1
            )

        # Not done, now expecting a colon to indicate the step
        if self._tokens.at_end():
            raise ExpressionError(f"Expected {ColonToken}, reached end of expression")
        token = self._tokens.next()
        if not isinstance(token, ColonToken):
            raise ExpressionError(f"Expected {ColonToken}, received {token}")

        # get the step integer
        step_sign, step = self._integer()

        try:
            return IntRange(
                start=int(start_sign + start.value),
                end=int(end_sign + end.value),
                step=int(step_sign + step.value),
            )
        except ValueError:
            raise ExpressionError("Failed to create Range") from ValueError

    def _expression(self) -> IntRangeExpr:
        """Matches a range expression.

        Grammar:
            <RangeExpr> ::= <Element> | <Element>,<RangeExpr>
            <Element> ::= <WS>*<Number><WS>* | <WS>*<Range><WS>* | <WS>*<StepRange><WS>*
            <Range> ::= <Number><WS>*-<WS>*<Number>
            <StepRange> ::= <Range>:<Step>
            <Number> ::= Any numeric base-10 value (int)
            <Step> ::= base-10 non-zero number
            <WS> ::= whitespace character: tabs or spaces

        Raises:
            TokenError: If an unexpected token is encountered
            ExpressionError: If the expresssion is malformed.

        Returns:
            IntRangeExpr: The full range expression parsed
        """
        range_ = self._range()
        ranges: list[IntRange] = [range_]
        try:
            while isinstance(self._tokens.lookahead(0), CommaToken):
                self._tokens.next()
                range_ = self._range()
                ranges.append(range_)
            else:
                if not self._tokens.at_end():
                    token = self._tokens.next()
                    raise ExpressionError(f"Expected {CommaToken}, received {token}")
        except IndexError:
            pass

        try:
            return IntRangeExpr(ranges)
        except ValueError as error:
            raise ExpressionError("Failed to create IntRangeExpr") from error
