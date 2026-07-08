# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any

import pytest
from pydantic import ValidationError

from openjd.model._parse import _parse_model
from openjd.model.v2023_09 import (
    ChunkIntTaskParameterDefinition,
    ModelParsingContext,
    StepParameterSpaceDefinition,
)

PARAMETRIZE_CASES: tuple = (
    "data",
    (
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1],
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="min len int list",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1] * 1024,
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="max len int list",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["1"],
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="int as string",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["1", 2],
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="mixed int types",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["{{Param.Value}}"],
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="format string",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [-1, 0, 1, "2", "{{Param.Value}}"],
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            id="mix of item types and values",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {"defaultTaskCount": 10, "rangeConstraint": "NONCONTIGUOUS"},
            },
            id="non-contiguous chunks",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 0,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="target runtime seconds of 0",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="target runtime seconds of 1000",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": "10",
                    "targetRuntimeSeconds": 100,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="defaultTaskCount is str",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": "{{Param.ChunkSize}}",
                    "targetRuntimeSeconds": 100,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="defaultTaskCount is str with expression",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": "100",
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="targetRuntimeSeconds is str",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": "{{Param.TargetChunkRuntime}}",
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            id="targetRuntimeSeconds is str expression",
        ),
    ),
)


@pytest.mark.parametrize(*PARAMETRIZE_CASES)
def test_chunk_int_task_parameter_parse_success(data: dict[str, Any]) -> None:
    # It parses successfully when the TASK_CHUNKING extension is requested
    _parse_model(
        model=ChunkIntTaskParameterDefinition,
        obj=data,
        context=ModelParsingContext(supported_extensions=["TASK_CHUNKING"]),
    )

    # It fails to parse without the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(model=ChunkIntTaskParameterDefinition, obj=data)
    assert "The CHUNK[INT] task parameter requires the TASK_CHUNKING extension." in str(
        excinfo.value
    )
    assert excinfo.value.error_count() == 1


PARAMETRIZE_CASES = (
    "data,error_message,error_count",
    (
        pytest.param({}, "Field required", 4, id="empty object"),
        pytest.param(
            {
                "name": "foo",
                "type": "FLOAT",
                "range": [1],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "type\n  Input should be",
            1,
            id="wrong type",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1],
            },
            "chunks\n  Field required",
            1,
            id="missing chunks",
        ),
        pytest.param(
            {
                "type": "CHUNK[INT]",
                "range": [1],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "name\n  Field required",
            1,
            id="missing name",
        ),
        pytest.param(
            {
                "name": "foo",
                "range": [1],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "type\n  Field required",
            1,
            id="missing type",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "range\n  Field required",
            1,
            id="missing range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "List should have at least 1 item after validation, not 0",
            2,
            id="range too short",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1],
                "unknown": "key",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Extra inputs are not permitted",
            1,
            id="unknown key",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1] * 1025,
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "List should have at most 1024 items after validation, not 1025",
            2,
            id="range too long",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1.1],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow floats in range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1, 2],
                "chunks": {
                    "defaultTaskCount": 10.1,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow floats in defaultTaskCount",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1, 2],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000.01,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow floats in targetRuntimeSeconds",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [True],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow bool in range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1],
                "chunks": {
                    "defaultTaskCount": True,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow bool in defaultTaskCount",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": [1],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": True,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow bool in targetRuntimeSeconds",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["1.1"],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow float strings in range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["1"],
                "chunks": {
                    "defaultTaskCount": "1.1",
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow float strings in defaultTaskCount",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["1"],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": "1000.1",
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="disallow float strings in targetRuntimeSeconds",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["{{ Job.Parameter.Foo"],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Failed to parse interpolation expression at [0, 20]. Reason: Braces mismatch.",
            1,
            id="malformed format string in range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": ["notint"],
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="literal string not an int in range",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "chunks.defaultTaskCount\n  Field required",
            1,
            id="missing defaultTaskCount",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 10,
                    "targetRuntimeSeconds": 1000,
                },
            },
            "chunks.rangeConstraint\n  Field required",
            1,
            id="missing rangeConstraint",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 0,
                    "targetRuntimeSeconds": 1000,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Input should be greater than or equal to 1",
            1,
            id="defaultTaskCount 0 (too small)",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 1,
                    "targetRuntimeSeconds": -1,
                    "rangeConstraint": "NONCONTIGUOUS",
                },
            },
            "Input should be greater than or equal to 0",
            1,
            id="targetRuntimeSeconds -1 (too small)",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 1,
                    "targetRuntimeSeconds": 0,
                    "rangeConstraint": "UNCONTIGUOUS",
                },
            },
            "chunks.rangeConstraint\n  Input should be 'CONTIGUOUS' or 'NONCONTIGUOUS'",
            1,
            id="rangeConstraint incorrect value UNCONTIGUOUS",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": "0",
                    "targetRuntimeSeconds": 0,
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Input should be greater than or equal to 1",
            1,
            id="defaultTaskCount is str with non-positive integer value",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": "1.5",
                    "targetRuntimeSeconds": 0,
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="defaultTaskCount is str with non-integer value",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": "{{Param.ChunkSize}",
                    "targetRuntimeSeconds": 0,
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Failed to parse interpolation expression at [0, 18]. Reason: Braces mismatch.",
            1,
            id="defaultTaskCount is str with incorrect expression",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 2,
                    "targetRuntimeSeconds": "0.1",
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Value must be an integer or a string containing an integer.",
            1,
            id="targetRuntimeSeconds is str with non-integer value",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 2,
                    "targetRuntimeSeconds": "-1",
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Input should be greater than or equal to 0",
            1,
            id="targetRuntimeSeconds is str with negative integer value",
        ),
        pytest.param(
            {
                "name": "foo",
                "type": "CHUNK[INT]",
                "range": "1-100",
                "chunks": {
                    "defaultTaskCount": 2,
                    "targetRuntimeSeconds": "{{Param.TargetChunkRuntime}",
                    "rangeConstraint": "CONTIGUOUS",
                },
            },
            "Failed to parse interpolation expression at [0, 27]. Reason: Braces mismatch.",
            1,
            id="targetRuntimeSeconds is str with incorrect expression",
        ),
    ),
)


@pytest.mark.parametrize(*PARAMETRIZE_CASES)
def test_chunk_int_task_parameter_parse_fails(
    data: dict[str, Any], error_message: str, error_count: int
) -> None:
    # It fails to parse with a test-specific message with the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(
            model=ChunkIntTaskParameterDefinition,
            obj=data,
            context=ModelParsingContext(supported_extensions=["TASK_CHUNKING"]),
        )
    print(excinfo.value)
    assert error_message in str(excinfo.value)
    assert excinfo.value.error_count() == error_count

    # It fails to parse without the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(model=ChunkIntTaskParameterDefinition, obj=data)
    assert "The CHUNK[INT] task parameter requires the TASK_CHUNKING extension." in str(
        excinfo.value
    )
    assert excinfo.value.error_count() == 1


@pytest.mark.parametrize(
    "data",
    (
        pytest.param(
            {
                "taskParameterDefinitions": [
                    {"name": "foo", "type": "INT", "range": "1-5"},
                    {"name": "bar", "type": "INT", "range": "6-10"},
                    {
                        "name": "baz",
                        "type": "CHUNK[INT]",
                        "range": "1-10",
                        "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
                    },
                ],
                "combination": "(foo, bar) * baz",
            },
            id="combination expr with CHUNK[INT]",
        ),
    ),
)
def test_param_space_with_chunk_int_parse_success(data: dict[str, Any]) -> None:
    # It parses successfully when the TASK_CHUNKING extension is requested
    _parse_model(
        model=StepParameterSpaceDefinition,
        obj=data,
        context=ModelParsingContext(supported_extensions=["TASK_CHUNKING"]),
    )

    # It fails to parse without the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(model=StepParameterSpaceDefinition, obj=data)
    assert "The CHUNK[INT] task parameter requires the TASK_CHUNKING extension." in str(
        excinfo.value
    )
    assert excinfo.value.error_count() == 1


@pytest.mark.parametrize(
    "data,error_message,error_count",
    (
        pytest.param(
            {
                "taskParameterDefinitions": [
                    {"name": "foo", "type": "INT", "range": "1-5"},
                    {"name": "bar", "type": "INT", "range": "11-20"},
                    {
                        "name": "baz",
                        "type": "CHUNK[INT]",
                        "range": "1-10",
                        "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
                    },
                ],
                "combination": "foo * (bar, baz)",
            },
            "CHUNK[INT] parameter baz must not be part of an associative expression.",
            1,
            id="CHUNK[INT] directly in associative expression",
        ),
        pytest.param(
            {
                "taskParameterDefinitions": [
                    {"name": "foo", "type": "INT", "range": "11-20"},
                    {"name": "bar", "type": "INT", "range": "12"},
                    {
                        "name": "baz",
                        "type": "CHUNK[INT]",
                        "range": "1-10",
                        "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
                    },
                ],
                "combination": "(foo, bar * baz)",
            },
            "CHUNK[INT] parameter baz must not be part of an associative expression.",
            1,
            id="CHUNK[INT] nested in product before associative expression",
        ),
    ),
)
def test_param_space_with_chunk_int_parse_fails(
    data: dict[str, Any], error_message: str, error_count: int
) -> None:
    # It fails to parse with a test-specific message with the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(
            model=StepParameterSpaceDefinition,
            obj=data,
            context=ModelParsingContext(supported_extensions=["TASK_CHUNKING"]),
        )
    print(excinfo.value)
    assert error_message in str(excinfo.value)
    assert excinfo.value.error_count() == error_count

    # It fails to parse without the TASK_CHUNKING extension
    with pytest.raises(ValidationError) as excinfo:
        _parse_model(model=StepParameterSpaceDefinition, obj=data)
    assert "The CHUNK[INT] task parameter requires the TASK_CHUNKING extension." in str(
        excinfo.value
    )
    assert excinfo.value.error_count() == 1


def test_only_one_chunk_parameter():
    data = {
        "taskParameterDefinitions": [
            {
                "name": "oof",
                "type": "CHUNK[INT]",
                "range": "1-10",
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
            {"name": "foo", "type": "INT", "range": [1]},
            {"name": "bar", "type": "INT", "range": [1]},
            {
                "name": "baz",
                "type": "CHUNK[INT]",
                "range": "1-10",
                "chunks": {"defaultTaskCount": 1, "rangeConstraint": "CONTIGUOUS"},
            },
        ],
    }

    with pytest.raises(ValidationError) as excinfo:
        _parse_model(
            model=StepParameterSpaceDefinition,
            obj=data,
            context=ModelParsingContext(supported_extensions=["TASK_CHUNKING"]),
        )

    # THEN
    assert "Only one CHUNK[INT] task parameter is permitted" in str(excinfo.value)
    assert len(excinfo.value.errors()) == 1, str(excinfo.value)
