# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from decimal import localcontext
from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model import DecodeValidationError, decode_job_template, parse_model
from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    FloatTaskParameterDefinition,
    IntTaskParameterDefinition,
    PathTaskParameterDefinition,
    RangeExpressionTaskParameterDefinition,
    RangeListTaskParameterDefinition,
    StepParameterSpaceDefinition,
    StringTaskParameterDefinition,
)


class TestIntTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="min len int list"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1] * 1024}, id="max len int list"
            ),
            pytest.param({"name": "foo", "type": "INT", "range": ["1"]}, id="int as string"),
            pytest.param({"name": "foo", "type": "INT", "range": ["1", 2]}, id="mixed int types"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1, "2", "{{Param.Value}}"]},
                id="mix of item types",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description IntTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our IntTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "INT", "range": [1]}, id="missing name"),
            pytest.param({"name": "foo", "range": [1]}, id="missing type"),
            pytest.param({"name": "foo", "type": "INT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "INT", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": [1], "unknown": "key"}, id="unknown key"
            ),
            pytest.param({"name": "foo", "type": "INT", "range": [1] * 1025}, id="range too long"),
            pytest.param({"name": "foo", "type": "INT", "range": [1.1]}, id="disallow floats"),
            pytest.param({"name": "foo", "type": "INT", "range": [True]}, id="disallow bool"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["1.1"]}, id="disallow float strings"
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": ["notint"]},
                id="literal string not an int",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestFloatTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1]}, id="min len list"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1] * 1024}, id="max len list"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [1.1]}, id="float value"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": ["1"]}, id="int as string"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": ["1.1"]}, id="float as string"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["1", 2, 3.3, "3.4"]},
                id="mixed number types",
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
            pytest.param(
                {
                    "name": "foo",
                    "type": "FLOAT",
                    "range": [1, "2", 3.3, "3.4", "{{Param.Value}}"],
                },
                id="mix of item types",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description TestFloatTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our TestFloatTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=FloatTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "FLOAT", "range": [1]}, id="missing name"),
            pytest.param({"name": "foo", "range": [1]}, id="missing type"),
            pytest.param({"name": "foo", "type": "FLOAT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "FLOAT", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": [1], "unknown": "key"}, id="unknown key"
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": [1] * 1025}, id="range too long"
            ),
            pytest.param({"name": "foo", "type": "FLOAT", "range": [True]}, id="disallow bool"),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
            pytest.param(
                {"name": "foo", "type": "FLOAT", "range": ["notnumber"]},
                id="literal string not a number",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=FloatTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestStringTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "STRING", "range": ["a"]}, id="min len list"),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"] * 1024}, id="max len list"
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["{{Param.Value}}"]},
                id="format string",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StringTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StringTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StringTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "STRING", "range": ["a"]}, id="missing name"),
            pytest.param({"name": "foo", "range": ["a"]}, id="missing type"),
            pytest.param({"name": "foo", "type": "STRING"}, id="missing range"),
            pytest.param({"name": "foo", "type": "STRING", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"], "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["a"] * 1025}, id="list too long"
            ),
            pytest.param(
                {"name": "foo", "type": "STRING", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StringTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestPathTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "PATH", "range": ["a"]}, id="min len list"),
            pytest.param({"name": "foo", "type": "PATH", "range": ["a"] * 1024}, id="max len list"),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["{{Job.Parameter.Value}}"]},
                id="format string",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description PathTaskParameterDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our PathTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=PathTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "INT", "range": [1]}, id="wrong type"),
            pytest.param({"type": "PATH", "range": ["a"]}, id="missing name"),
            pytest.param({"name": "foo", "range": ["a"]}, id="missing type"),
            pytest.param({"name": "foo", "type": "PATH"}, id="missing range"),
            pytest.param({"name": "foo", "type": "PATH", "range": []}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["a"], "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["a"] * 1025}, id="list too long"
            ),
            pytest.param(
                {"name": "foo", "type": "PATH", "range": ["{{ Job.Parameter.Foo"]},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=PathTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestRangeExpressionTaskParameterDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "INT", "range": "1"}, id="one item"),
            pytest.param({"name": "foo", "type": "INT", "range": "1-10"}, id="one range of items"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "10--5:-1"},
                id="one negative range of items",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1-10:2"},
                id="one range of items with steps",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "-5--14:-2"},
                id="negative range with negative steps",
            ),
            pytest.param({"name": "foo", "type": "INT", "range": "-10-0,1-10"}, id="two ranges"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "10-1:-1,11-20:2"},
                id="two ranges with opposite signs",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1-10:2"},
                id="one range of items with steps",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "{{Param.Value}}"},
                id="format string",
            ),
            pytest.param(
                {
                    "name": "foo",
                    "type": "INT",
                    "range": "{{Job.Parameter.Start}}-{{Job.Parameter.End}}:{{Job.Parameter.Step}}",
                },
                id="format string with multiple",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1-5000"},
                id="expansion past the list-form cap",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, str]) -> None:
        # Parsing tests of valid Open Job Description RangeExpression
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our IntTaskParameterDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        # does not raise an exception

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "foo", "type": "STRING", "range": ["1"]}, id="wrong type"),
            pytest.param({"type": "INT", "range": "1"}, id="missing name"),
            pytest.param({"name": "foo", "range": "1"}, id="missing type"),
            pytest.param({"name": "foo", "type": "INT"}, id="missing range"),
            pytest.param({"name": "foo", "type": "INT", "range": ""}, id="range too short"),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "1", "unknown": "key"},
                id="unknown key",
            ),
            pytest.param(
                {"name": "foo", "type": "INT", "range": "{{ Job.Parameter.Foo"},
                id="malformed format string",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description TaskParameterDecl.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=IntTaskParameterDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestTaskParameterRangeLength:
    """§3.4 caps the number of elements in the *list* forms of a task parameter's
    range. §3.4.1.1.1 `<IntRangeExpr>` carries no element cap, so an expression's
    expansion must not be capped — the form exists to express frame ranges, which
    routinely run to thousands of values.
    """

    @pytest.mark.parametrize(
        "range_expr,expected_len",
        (
            pytest.param("1-1024", 1024, id="at the list-form cap"),
            pytest.param("1-1025", 1025, id="one past the list-form cap"),
            pytest.param("1-5000", 5000, id="ordinary frame range"),
            pytest.param("1-100000:2", 50000, id="large range with a step"),
        ),
    )
    def test_range_expression_expansion_is_not_capped(
        self, range_expr: str, expected_len: int
    ) -> None:
        # WHEN the template-layer definition parses a literal range expression
        _parse_model(
            model=IntTaskParameterDefinition,
            obj={"name": "foo", "type": "INT", "range": range_expr},
        )

        # AND the instantiation target parses the same expression
        instantiated = _parse_model(
            model=RangeExpressionTaskParameterDefinition,
            obj={"type": "INT", "range": range_expr},
        )

        # THEN neither rejects it, and the range expands in full
        assert len(instantiated.range) == expected_len

    @pytest.mark.parametrize(
        "model,obj",
        (
            pytest.param(
                IntTaskParameterDefinition,
                {"name": "foo", "type": "INT", "range": [1] * 1025},
                id="template layer",
            ),
            pytest.param(
                RangeListTaskParameterDefinition,
                {"type": "INT", "range": [1] * 1025},
                id="instantiation layer",
            ),
        ),
    )
    def test_list_form_range_is_still_capped(self, model: Any, obj: dict[str, Any]) -> None:
        # WHEN a list-form range one element past the §3.4 cap is parsed
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=model, obj=obj)

        # THEN it is rejected
        assert len(excinfo.value.errors()) > 0


class TestRangeListElementNormalization:
    """§7.5 on a range element: leading zeros go, decimal places stay.

    `['1', '02', '003']` is the task values 1, 2 and 3; keeping the text renders
    `--frame 02`. But `'2.50'` renders `2.50`, because the string form is how a
    template asks for a fixed number of decimal places —
    `EXPR/jobs/expr1.3.4--float-passthrough` pins that for a FLOAT default.
    """

    @pytest.mark.parametrize(
        "param_type",
        (pytest.param("INT", id="INT"), pytest.param("CHUNK[INT]", id="CHUNK[INT]")),
    )
    def test_intstring_elements_carry_their_value(self, param_type: str) -> None:
        # GIVEN an int range mixing the <integer> and <intstring> forms
        obj: dict[str, Any] = {"type": param_type, "range": [1, "02", "003", 4]}
        if param_type == "CHUNK[INT]":
            obj["chunks"] = {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"}

        # WHEN the instantiation target parses it
        model = _parse_model(model=RangeListTaskParameterDefinition, obj=obj)

        # THEN every element is the integer it denotes, and renders without the
        # leading zeros of its source text
        assert model.range == [1, 2, 3, 4]
        assert [str(v) for v in model.range] == ["1", "2", "3", "4"]

    @pytest.mark.parametrize(
        "element,expected",
        (
            pytest.param("1.5", "1.5", id="nothing to strip"),
            # The rule, in both directions at once.
            pytest.param("02.50", "2.50", id="leading zero goes, trailing zero stays"),
            pytest.param("3.500", "3.500", id="trailing zeros stay"),
            pytest.param("-02.50", "-2.50", id="negative"),
            pytest.param("+02.50", "+2.50", id="explicit plus sign is kept"),
            pytest.param("007", "7", id="leading zeros on a whole number"),
            pytest.param("100", "100", id="a zero that is a significant digit"),
            # Neither the zero before the point nor the last of an all-zero
            # integer part is redundant.
            pytest.param("0.50", "0.50", id="the necessary leading zero stays"),
            pytest.param("000", "0", id="all zeros keeps one"),
            pytest.param("0", "0", id="bare zero"),
            pytest.param("0.0", "0.0", id="zero"),
            pytest.param("0.00", "0.00", id="zero keeps its trailing zeros too"),
            # Zero has no sign, which openjd-rs and mainline both render away.
            # Dropping it must not drop the decimal places with it.
            pytest.param("-0.0", "0.0", id="negative zero has no sign"),
            pytest.param("-0.00", "0.00", id="unsigned, but still two places"),
            # An all-zero mantissa spells zero whatever the exponent.
            pytest.param("0E+2", "0E+2", id="exponent form of zero"),
            pytest.param("-0e5", "0e5", id="signed exponent form of zero"),
            # Underflow is not zero being spelled: the digits are the request.
            pytest.param("1e-400", "1e-400", id="underflow keeps its digits"),
            pytest.param("0." + "0" * 400 + "1", "0." + "0" * 400 + "1", id="tiny plain decimal"),
            # float() ignores surrounding whitespace and this text reaches a
            # command line, so it is trimmed rather than forwarded.
            pytest.param("  1.5  ", "1.5", id="surrounding whitespace"),
            pytest.param("1.0", "1.0", id="integral float keeps its point"),
            # Exponent notation is the author's own text and is forwarded. The
            # FLOAT parameter default path does the same for `default: "1E+2"`.
            pytest.param("1E+2", "1E+2", id="exponent notation"),
            pytest.param("01E+2", "1E+2", id="leading zero on an exponent form"),
            pytest.param("0.0000001", "0.0000001", id="below 1e-6"),
            pytest.param(
                "1.2345678901234567890123456789012345678901",
                "1.2345678901234567890123456789012345678901",
                id="more significant digits than a float can hold",
            ),
        ),
    )
    def test_floatstring_elements_keep_their_scale(self, element: str, expected: str) -> None:
        # WHEN the instantiation target parses a float range holding a <floatstring>
        model = _parse_model(
            model=RangeListTaskParameterDefinition, obj={"type": "FLOAT", "range": [element]}
        )

        # THEN it renders as written, less any redundant leading zeros
        assert [str(v) for v in model.range] == [expected]

    @pytest.mark.parametrize(
        "element,expected",
        (
            # An exponent too large for a float still costs only its own
            # characters, which is the whole point: nothing expands it.
            pytest.param("1e999999999", "1e999999999", id="huge positive exponent"),
            pytest.param("1E+1022", "1E+1022", id="positive exponent past the field cap"),
            # Too small for a float either way, and the digits still stand:
            # underflowing to 0.0 is a parse limit, not the author writing zero.
            pytest.param("1e-999999999", "1e-999999999", id="huge negative exponent"),
            pytest.param("1E-1023", "1E-1023", id="negative exponent past the field cap"),
        ),
    )
    def test_a_huge_exponent_costs_only_its_own_characters(
        self, element: str, expected: str
    ) -> None:
        # WHEN 11 characters of template text denote a number needing ~10**9
        # digits in plain notation
        model = _parse_model(
            model=RangeListTaskParameterDefinition, obj={"type": "FLOAT", "range": [element]}
        )

        # THEN nothing expands it, so no bound on the exponent is needed to stop a
        # template allocating ~10**9 characters. Long *literal* text can still
        # exceed TaskParameterStringValueAsJob's cap and fall through to a numeric
        # member of the union, as it does on mainline and in 0.11.6; only the
        # expansion is gone.
        assert [str(v) for v in model.range] == [expected]

    def test_floatstring_rendering_ignores_the_decimal_context(self) -> None:
        # GIVEN an embedding application that has narrowed the process-wide
        # decimal context, and a <floatstring> with more significant digits
        # than that precision allows
        element = "1.2345678901234567890123456789012345678901"

        # WHEN the instantiation target parses it under that context
        with localcontext() as ctx:
            ctx.prec = 5
            model = _parse_model(
                model=RangeListTaskParameterDefinition, obj={"type": "FLOAT", "range": [element]}
            )

        # THEN it is unrounded: the rendering is a property of the template, not
        # of the host application's decimal context
        assert [str(v) for v in model.range] == [element]

    @pytest.mark.parametrize(
        "param_type,range_list",
        (
            # A <float> literal keeps the scale it was written with. openjd-rs
            # renders an integral float as `1.0` too, and the conformance suite
            # pins it (2023-09/base/jobs/3.4--float-parameter).
            pytest.param("FLOAT", [0.5, 1.0, 1.5], id="FLOAT numeric literals"),
            pytest.param("INT", [1, 2, 3], id="INT numeric literals"),
            # STRING and PATH ranges are text by definition — §3.4.1.3/§3.4.1.4
            # give no numeric form, so nothing about them is normalizable.
            pytest.param("STRING", ["02", "003", "1.50"], id="STRING"),
            pytest.param("PATH", ["/frames/02", "/frames/003"], id="PATH"),
        ),
    )
    def test_elements_that_must_not_change(self, param_type: str, range_list: list) -> None:
        # WHEN the instantiation target parses a range that normalization must not touch
        model = _parse_model(
            model=RangeListTaskParameterDefinition,
            obj={"type": param_type, "range": range_list},
        )

        # THEN every element renders exactly as it was written
        assert [str(v) for v in model.range] == [str(v) for v in range_list]

    def test_unparseable_element_is_left_alone(self) -> None:
        # GIVEN a range element that does not denote a number — reachable when a
        # format string resolves to non-numeric text, since the template-layer
        # element check only sees literals.
        # WHEN the instantiation target parses it
        model = _parse_model(
            model=RangeListTaskParameterDefinition, obj={"type": "INT", "range": ["notanumber"]}
        )

        # THEN it is carried through unchanged rather than rejected here
        assert model.range == ["notanumber"]


class TestStepParameterSpaceDefinition:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "INT", "range": [1]}]},
                id="int parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "FLOAT", "range": [1]}]},
                id="float parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "STRING", "range": ["1"]}]},
                id="string parameter",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "foo", "type": "PATH", "range": ["/tmp"]}]},
                id="path parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": f"foo{i}", "type": "INT", "range": [1]} for i in range(0, 16)
                    ]
                },
                id="most number of parameters",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar",
                },
                id="with combination expr",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description StepParameterSpaceDefinition
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our StepParameterSpaceDefinition model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=StepParameterSpaceDefinition, obj=data)

        # THEN
        # no exception is raised

    @pytest.mark.parametrize(
        "data,expected_num_errors",
        (
            pytest.param({}, 1, id="empty object"),
            pytest.param({"taskParameterDefinitions": []}, 1, id="empty parameter list"),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": f"foo{i}", "type": "INT", "range": [1]} for i in range(0, 17)
                    ]
                },
                1,
                id="too many parameters",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "foo", "type": "INT", "range": [1]},
                    ],
                },
                1,
                id="duplicate parameter name",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "range": [1]},
                    ]
                },
                # If the discriminator ("type" field) is missing then we should only see a single
                # error if the typed union discriminator is set up correctly. If it's not
                # set up correctly, then we'll get one error for every type in the union.
                1,
                id="discriminator missing",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT"},
                    ]
                },
                # If we're missing a required field ("range") and the Union discriminator
                # is set up correctly, then we should only see a single error for the field being
                # missing in the specific Unioned type. If it's not set up correctly, then we'll
                # see at least an error from each type in the Union.
                1,
                id="discriminator works",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo  bar",
                },
                1,
                id="malformed combination expr",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo",
                },
                1,
                id="combination expr doesn't reference all parameters #1",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar * baz",
                },
                1,
                id="combination expr refs undefined parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * bar * foo",
                },
                1,
                id="combination expr double refs a parameter",
            ),
            pytest.param(
                {
                    "taskParameterDefinitions": [
                        {"name": "foo", "type": "INT", "range": [1]},
                        {"name": "bar", "type": "INT", "range": [1]},
                    ],
                    "combination": "foo * foo",
                },
                2,
                id="combination expr double refs & missing ref",
            ),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any], expected_num_errors: int) -> None:
        # Failure case testing for Open Job Description StepParameterSpaceDefinition.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=StepParameterSpaceDefinition, obj=data)

        # THEN
        assert len(excinfo.value.errors()) == expected_num_errors, str(excinfo.value)


class TestTaskParameterTypeNameCase:
    """Template Schemas §2: task parameter type names are case-sensitive in base
    2023-09 and case-insensitive when the EXPR extension is enabled.

    The conformance fixture is
    ``EXPR/job_templates/proposed/3.4.1--task-param-type-case-insensitive.yaml``
    (openjd-specifications#166).

    These go through ``decode_job_template`` rather than the module's usual
    ``_parse_model`` because the rule is gated on the extension set. The public
    ``parse_model`` also supplies one for a bare model, which
    ``test_bare_model_via_public_parse_model_honours_expr`` covers.
    """

    # Every task parameter type, with a deliberately mis-cased spelling for each.
    # The mis-cased spellings vary in shape on purpose: all-lower, leading-cap,
    # alternating, and a bracketed name.
    TYPES: tuple = (
        pytest.param("INT", "int", "1-3", None, id="int"),
        pytest.param("FLOAT", "Float", ["1.0", "2.0"], None, id="float"),
        pytest.param("STRING", "sTrInG", ["fg", "bg"], None, id="string"),
        pytest.param("PATH", "pAtH", ["/tmp/a", "/tmp/b"], None, id="path"),
        pytest.param(
            "CHUNK[INT]",
            "chunk[int]",
            "1-3",
            {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            id="chunk-int",
        ),
    )

    @staticmethod
    def _tmpl(type_name: str, range_value: Any, chunks: Any, extensions: tuple[str, ...]) -> dict:
        param: dict[str, Any] = {"name": "F", "type": type_name, "range": range_value}
        if chunks is not None:
            param["chunks"] = chunks
        template: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": {"taskParameterDefinitions": [param]},
                    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                }
            ],
        }
        if extensions:
            template["extensions"] = list(extensions)
        return template

    @staticmethod
    def _decode(template: dict) -> None:
        # The caller allowlists both extensions in every case. What varies is whether
        # the template declares them, because the effective set is the intersection.
        decode_job_template(template=template, supported_extensions=["EXPR", "TASK_CHUNKING"])

    @staticmethod
    def _extensions_for(canonical: str, expr: bool) -> tuple[str, ...]:
        exts = ("TASK_CHUNKING",) if canonical == "CHUNK[INT]" else ()
        return (*exts, "EXPR") if expr else exts

    # ── The four cases: EXPR on/off x spelling canonical/mis-cased ──

    @pytest.mark.parametrize("canonical, miscased, range_value, chunks", TYPES)
    def test_no_expr_canonical_case_accepted(
        self, canonical: str, miscased: str, range_value: Any, chunks: Any
    ) -> None:
        # Case 1 of 4. Without EXPR, the spec spelling is the only accepted one,
        # and it is accepted. Negative control: proves a rejection in case 2 is
        # about the casing and not about the type being unavailable.
        self._decode(
            self._tmpl(canonical, range_value, chunks, self._extensions_for(canonical, expr=False))
        )

    @pytest.mark.parametrize("canonical, miscased, range_value, chunks", TYPES)
    def test_no_expr_miscased_rejected(
        self, canonical: str, miscased: str, range_value: Any, chunks: Any
    ) -> None:
        # Case 2 of 4. Without EXPR, type names are case-sensitive, so a mis-cased
        # spelling must be rejected. This is the case that fails if the normalizer
        # is registered without its EXPR gate.
        with pytest.raises(DecodeValidationError) as excinfo:
            self._decode(
                self._tmpl(
                    miscased, range_value, chunks, self._extensions_for(canonical, expr=False)
                )
            )
        message = str(excinfo.value)
        assert "steps[0] -> parameterSpace -> taskParameterDefinitions[0]" in message, message
        # The author's spelling appears in the diagnostic, not the canonical one.
        assert f"'{miscased}'" in message, message
        # Rejected for the casing, not for a missing extension. CHUNK[INT] is the
        # case that could otherwise fail for the wrong reason.
        assert "requires the TASK_CHUNKING extension" not in message, message

    @pytest.mark.parametrize("canonical, miscased, range_value, chunks", TYPES)
    def test_with_expr_canonical_case_accepted(
        self, canonical: str, miscased: str, range_value: Any, chunks: Any
    ) -> None:
        # Case 3 of 4. Enabling EXPR must not break the spec spelling. Negative
        # control against a fold that rewrites the name into something unmatchable.
        self._decode(
            self._tmpl(canonical, range_value, chunks, self._extensions_for(canonical, expr=True))
        )

    @pytest.mark.parametrize("canonical, miscased, range_value, chunks", TYPES)
    def test_with_expr_miscased_accepted(
        self, canonical: str, miscased: str, range_value: Any, chunks: Any
    ) -> None:
        # Case 4 of 4. With EXPR, a mis-cased spelling is equivalent to the
        # canonical one. This is the conformance fixture's assertion, and the case
        # that fails if the normalizer is not registered at all.
        self._decode(
            self._tmpl(miscased, range_value, chunks, self._extensions_for(canonical, expr=True))
        )

    # ── The gate is on EXPR, not on the extension that supplies the type ──

    def test_chunk_int_miscased_needs_expr_not_only_task_chunking(self) -> None:
        # TASK_CHUNKING makes CHUNK[INT] available; EXPR is what makes its name
        # case-insensitive. Declaring only TASK_CHUNKING must still reject
        # 'chunk[int]', which pins that the fold reads EXPR specifically.
        with pytest.raises(DecodeValidationError):
            self._decode(
                self._tmpl(
                    "chunk[int]",
                    "1-3",
                    {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
                    ("TASK_CHUNKING",),
                )
            )

    def test_expr_declared_but_not_allowlisted_is_an_extension_error(self) -> None:
        # Pins the intersection semantics, not the fold: the rejection comes from
        # the extension allowlist before the type name is reached.
        with pytest.raises(DecodeValidationError) as excinfo:
            decode_job_template(
                template=self._tmpl("int", "1-3", None, ("EXPR",)),
                supported_extensions=[],
            )
        assert "Unsupported extension names: EXPR" in str(excinfo.value), str(excinfo.value)

    def test_bare_model_via_public_parse_model_honours_expr(self) -> None:
        # public parse_model builds a context from supported_extensions, so the fold
        # reaches a bare StepParameterSpaceDefinition with no enclosing template.
        parse_model(
            model=StepParameterSpaceDefinition,
            obj={"taskParameterDefinitions": [{"name": "F", "type": "int", "range": "1-3"}]},
            supported_extensions=["EXPR"],
        )
        with pytest.raises(DecodeValidationError):
            parse_model(
                model=StepParameterSpaceDefinition,
                obj={"taskParameterDefinitions": [{"name": "F", "type": "int", "range": "1-3"}]},
                supported_extensions=[],
            )

    # ── The fold is ASCII, so a non-ASCII character is not a spelling variant ──

    # str.upper() folds each of these wholly into the type-name alphabet: U+0131
    # LATIN SMALL LETTER DOTLESS I to 'I', U+017F LONG S to 'S', U+FB02 ligature fl
    # to 'FL', U+FB06 ligature st to 'ST'. A Unicode-aware fold reads them as INT,
    # STRING, FLOAT and STRING.
    NON_ASCII_LOOKALIKES: tuple = (
        pytest.param("\u0131NT", id="dotless-i-int"),
        pytest.param("\u017fTRING", id="long-s-string"),
        pytest.param("\ufb02OAT", id="fl-ligature-float"),
        pytest.param("\ufb06RING", id="st-ligature-string"),
    )

    @pytest.mark.parametrize("type_name", NON_ASCII_LOOKALIKES)
    def test_non_ascii_lookalike_rejected_with_expr(self, type_name: str) -> None:
        with pytest.raises(DecodeValidationError) as excinfo:
            self._decode(self._tmpl(type_name, "1-3", None, ("EXPR",)))
        assert f"'{type_name}'" in str(excinfo.value), str(excinfo.value)

    @pytest.mark.parametrize("type_name", NON_ASCII_LOOKALIKES)
    def test_non_ascii_lookalike_rejected_without_expr(self, type_name: str) -> None:
        # Inert against this change by design: without EXPR no fold runs, so this
        # cannot fail. Present so the pair covers both extension states.
        with pytest.raises(DecodeValidationError):
            self._decode(self._tmpl(type_name, "1-3", None, ()))

    # ── Malformed input reaches the fold now that it runs on this field ──

    @pytest.mark.parametrize(
        "parameter_space",
        (
            pytest.param({"taskParameterDefinitions": None}, id="null-list"),
            pytest.param({"taskParameterDefinitions": {}}, id="mapping-not-list"),
            pytest.param({"taskParameterDefinitions": "int"}, id="string-not-list"),
            pytest.param({"taskParameterDefinitions": ["int"]}, id="list-of-non-dicts"),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "F", "type": 3, "range": "1-3"}]},
                id="type-is-int",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "F", "type": True, "range": "1-3"}]},
                id="type-is-bool",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "F", "type": ["int"], "range": "1-3"}]},
                id="type-is-list",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "F", "type": None, "range": "1-3"}]},
                id="type-is-null",
            ),
            pytest.param(
                {"taskParameterDefinitions": [{"name": "F", "range": "1-3"}]}, id="type-missing"
            ),
        ),
    )
    def test_malformed_input_is_a_validation_error_not_a_crash(self, parameter_space: Any) -> None:
        # Registering the fold on this field routed these through it for the first
        # time, so its isinstance guards became load-bearing here. Without them
        # these raise TypeError, AttributeError or KeyError out of
        # decode_job_template instead of DecodeValidationError. pytest.raises
        # fails on any other exception type, which is the pin.
        template: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": ["EXPR"],
            "name": "T",
            "steps": [
                {
                    "name": "S",
                    "parameterSpace": parameter_space,
                    "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                }
            ],
        }
        with pytest.raises(DecodeValidationError):
            self._decode(template)

    # ── A mis-cased name now reaches the validators that run after the fold ──

    def test_miscased_duplicate_names_report_the_duplicate_not_the_type(self) -> None:
        # Before the fold ran on this field, 'int' failed at discriminator
        # resolution and never reached the unique-name rule. Now it does.
        with pytest.raises(DecodeValidationError, match="Duplicate values for name"):
            self._decode(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR"],
                    "name": "T",
                    "steps": [
                        {
                            "name": "S",
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {"name": "F", "type": "int", "range": "1-3"},
                                    {"name": "F", "type": "INT", "range": "1-3"},
                                ]
                            },
                            "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                        }
                    ],
                }
            )

    def test_two_miscased_chunk_int_report_the_one_chunk_rule(self) -> None:
        # Same reason: the one-CHUNK[INT]-per-step rule is only reachable once the
        # mis-cased spellings resolve to the CHUNK[INT] variant.
        chunks = {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"}
        with pytest.raises(DecodeValidationError, match="Only one CHUNK\\[INT\\]"):
            self._decode(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "extensions": ["EXPR", "TASK_CHUNKING"],
                    "name": "T",
                    "steps": [
                        {
                            "name": "S",
                            "parameterSpace": {
                                "taskParameterDefinitions": [
                                    {
                                        "name": "A",
                                        "type": "chunk[int]",
                                        "range": "1-3",
                                        "chunks": chunks,
                                    },
                                    {
                                        "name": "B",
                                        "type": "Chunk[Int]",
                                        "range": "1-3",
                                        "chunks": chunks,
                                    },
                                ]
                            },
                            "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}},
                        }
                    ],
                }
            )
