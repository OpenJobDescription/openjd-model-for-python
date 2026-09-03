# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the EXPR-extension LIST[*] and RANGE_EXPR job parameter types
(RFC 0007): structural parsing, list/item constraints, EXPR gating, and
case-insensitive type names."""

import pytest

from openjd.model import DecodeValidationError, decode_job_template

_STEP = {"name": "S", "script": {"actions": {"onRun": {"command": "echo", "args": ["hi"]}}}}


def _tmpl(param_def, *, extensions=("EXPR",)):
    t = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": [param_def],
        "steps": [_STEP],
    }
    if extensions:
        t["extensions"] = list(extensions)
    return t


def _decode(t):
    return decode_job_template(template=t, supported_extensions=["EXPR"])


class TestListValid:
    @pytest.mark.parametrize(
        "param",
        [
            {"name": "S", "type": "LIST[STRING]", "default": ["a", "b"]},
            {
                "name": "P",
                "type": "LIST[PATH]",
                "default": ["/a", "/b"],
                "objectType": "FILE",
                "dataFlow": "IN",
            },
            {"name": "I", "type": "LIST[INT]", "default": [1, 2, 3]},
            {"name": "F", "type": "LIST[FLOAT]", "default": [1.0, 2.5]},
            {"name": "B", "type": "LIST[BOOL]", "default": [True, False]},
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1, 2], [3]]},
            {"name": "R", "type": "RANGE_EXPR", "default": "1-100:10"},
        ],
    )
    def test_accepts(self, param):
        _decode(_tmpl(param))

    def test_item_constraints_ok(self):
        _decode(
            _tmpl(
                {
                    "name": "S",
                    "type": "LIST[STRING]",
                    "default": ["alpha"],
                    "minLength": 1,
                    "maxLength": 5,
                    "item": {"allowedValues": ["alpha", "beta"], "minLength": 3},
                }
            )
        )

    def test_case_insensitive_type(self):
        _decode(_tmpl({"name": "I", "type": "list[int]", "default": [1]}))


class TestListInvalid:
    def test_requires_expr(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_tmpl({"name": "I", "type": "LIST[INT]", "default": [1]}, extensions=()))

    @pytest.mark.parametrize(
        "param",
        [
            {"name": "S", "type": "LIST[STRING]", "default": "notalist"},  # scalar not list
            {"name": "I", "type": "LIST[INT]", "default": ["not", "ints"]},  # wrong item type
            {
                "name": "I",
                "type": "LIST[INT]",
                "default": [-5],
                "item": {"minValue": 0},
            },  # below min
            {
                "name": "S",
                "type": "LIST[STRING]",
                "default": [""],
                "item": {"minLength": 1},
            },  # too short
            {
                "name": "S",
                "type": "LIST[STRING]",
                "default": ["a", "b", "c"],
                "maxLength": 2,
            },  # too long
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1, "a"]]},  # string in inner
            {"name": "LL", "type": "LIST[LIST[INT]]", "default": [[1], 3]},  # scalar in outer
            {
                "name": "LL",
                "type": "LIST[LIST[INT]]",
                "default": [[999]],
                "item": {"item": {"maxValue": 100}},
            },
            {"name": "R", "type": "RANGE_EXPR", "default": "not-a-range"},  # bad range expr
        ],
    )
    def test_rejects(self, param):
        with pytest.raises(DecodeValidationError):
            _decode(_tmpl(param))


class TestJobParameterTypeNameCase:
    """Template Schemas §2: job parameter type names are case-sensitive in base
    2023-09 and case-insensitive when the EXPR extension is enabled.

    ``TestListValid.test_case_insensitive_type`` covers one of the four
    extension-by-spelling combinations. This covers all four, on both an
    EXPR-only type and a base type, and pins that the shared fold is ASCII.

    The task parameter counterpart is
    ``test_parameter_space.py::TestTaskParameterTypeNameCase``.
    """

    # (canonical spelling, a mis-cased spelling, a valid default)
    TYPES: tuple = (
        ("STRING", "string", "a"),  # base type, available without EXPR
        ("INT", "iNt", 1),  # base type
        ("LIST[INT]", "list[int]", [1, 2]),  # EXPR-only type
        ("LIST[LIST[INT]]", "List[List[Int]]", [[1], [2]]),  # EXPR-only, nested brackets
    )

    @staticmethod
    def _param(type_name, default):
        return {"name": "P", "type": type_name, "default": default}

    @pytest.mark.parametrize("canonical, miscased, default", TYPES)
    def test_no_expr_canonical_case(self, canonical, miscased, default):
        # Case 1 of 4. Without EXPR the spec spelling is the only one accepted.
        # A base type is accepted; an EXPR-only type is rejected for needing EXPR,
        # which is a different rejection from the casing one in case 2.
        template = _tmpl(self._param(canonical, default), extensions=())
        if canonical.startswith("LIST["):
            with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
                _decode(template)
        else:
            _decode(template)

    @pytest.mark.parametrize("canonical, miscased, default", TYPES)
    def test_no_expr_miscased_rejected(self, canonical, miscased, default):
        # Case 2 of 4. Without EXPR, type names are case-sensitive.
        with pytest.raises(DecodeValidationError) as excinfo:
            _decode(_tmpl(self._param(miscased, default), extensions=()))
        message = str(excinfo.value)
        assert "parameterDefinitions[0]" in message, message
        assert f"'{miscased}'" in message, message
        # Rejected for the casing, not for the extension. An EXPR-only type spelled
        # correctly would say "requires the EXPR extension" instead.
        assert "requires the EXPR extension" not in message, message

    @pytest.mark.parametrize("canonical, miscased, default", TYPES)
    def test_with_expr_canonical_case_accepted(self, canonical, miscased, default):
        # Case 3 of 4. Enabling EXPR must not break the spec spelling.
        _decode(_tmpl(self._param(canonical, default)))

    @pytest.mark.parametrize("canonical, miscased, default", TYPES)
    def test_with_expr_miscased_accepted(self, canonical, miscased, default):
        # Case 4 of 4.
        _decode(_tmpl(self._param(miscased, default)))

    # ── The fold is ASCII ──

    # str.upper() folds each of these wholly into the type-name alphabet: U+0131
    # dotless i to 'I', U+017F long s to 'S', U+FB02 ligature fl to 'FL', U+FB06
    # ligature st to 'ST'. A Unicode-aware fold reads them as real type names.
    LOOKALIKES = ("\u0131NT", "\u017fTRING", "\ufb02OAT", "\ufb06RING")

    @pytest.mark.parametrize("type_name", LOOKALIKES)
    def test_non_ascii_lookalike_rejected_with_expr(self, type_name):
        with pytest.raises(DecodeValidationError) as excinfo:
            _decode(_tmpl(self._param(type_name, None)))
        assert f"'{type_name}'" in str(excinfo.value), str(excinfo.value)

    @pytest.mark.parametrize("type_name", LOOKALIKES)
    def test_non_ascii_lookalike_rejected_without_expr(self, type_name):
        # Inert against this change by design: without EXPR no fold runs. Present
        # so the pair covers both extension states.
        with pytest.raises(DecodeValidationError):
            _decode(_tmpl(self._param(type_name, None), extensions=()))
