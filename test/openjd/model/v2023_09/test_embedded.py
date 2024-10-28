# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic.v1 import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import EmbeddedFileText


class TestEmbeddedFileText:
    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": "Foo", "type": "TEXT", "data": "some text"}, id="all required"),
            pytest.param({"name": "Foo", "type": "TEXT", "data": "1"}, id="data min length"),
            pytest.param(
                {"name": "Foo", "type": "TEXT", "data": "1" * (32 * 1024)}, id="data long length"
            ),
            pytest.param(
                {"name": "Foo", "type": "TEXT", "data": "some text", "filename": "1"},
                id="filename min length",
            ),
            pytest.param(
                {"name": "Foo", "type": "TEXT", "data": "some text", "filename": "1" * 64},
                id="filename max length",
            ),
            pytest.param(
                {"name": "Foo", "type": "TEXT", "data": "some text", "runnable": True},
                id="runnable",
            ),
        ),
    )
    def test_parse_success(self, data: dict[str, Any]) -> None:
        # Parsing tests of valid Open Job Description EmbeddedFileText
        # It is sufficient to check that parsing the input does not
        # raise an exception. We trust the Pydantic package's testing
        # so, if the input parses then our EmbeddedFileText model is correctly
        # constructed for valid input.

        # WHEN
        _parse_model(model=EmbeddedFileText, obj=data)

        # THEN
        # no exception was raised.

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({}, id="empty object"),
            pytest.param({"name": "foo", "type": "text", "data": "some text"}, id="unknown type"),
            pytest.param({"name": "foo", "type": "TEXT", "data": ""}, id="data too short"),
            pytest.param(
                {"name": "foo", "type": "TEXT", "data": "some text", "filename": ""},
                id="filename too short",
            ),
            pytest.param(
                {"name": "foo", "type": "TEXT", "data": "some text", "filename": "f" * 65},
                id="filename too long",
            ),
            pytest.param(
                {"name": "foo", "type": "TEXT", "data": "some text", "runnable": "True"},
                id="runnable must be bool",
            ),
            # TODO - tests for filename allowed characters
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # Failure case testing for Open Job Description EmbeddedFileText.
        # - Constraint tests
        # - extra field test

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            _parse_model(model=EmbeddedFileText, obj=data)

        # THEN
        assert len(excinfo.value.errors()) > 0
