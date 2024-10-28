# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any
import string

import pytest
from pydantic.v1 import BaseModel, ValidationError

from openjd.model.v2023_09 import (
    AmountCapabilityName,
    ArgString,
    AttributeCapabilityName,
    CombinationExpr,
    CommandString,
    Description,
    EnvironmentName,
    EnvironmentVariableNameString,
    EnvironmentVariableValueString,
    Identifier,
    JobName,
    JobTemplateName,
    ParameterStringValue,
    StepName,
    TaskParameterStringValueAsJob,
    UserInterfaceLabelStringValue,
    FileDialogFilterPatternStringValue,
)


class JobTemplateNameModel(BaseModel):
    name: JobTemplateName


class JobNameModel(BaseModel):
    name: JobName


class EnvironmentNameModel(BaseModel):
    name: EnvironmentName


class EnvironmentVariableNameStringModel(BaseModel):
    name: EnvironmentVariableNameString


class EnvironmentVariableValueStringModel(BaseModel):
    value: EnvironmentVariableValueString


class StepNameModel(BaseModel):
    name: StepName


class IdentifierModel(BaseModel):
    id: Identifier


class DescriptionModel(BaseModel):
    desc: Description


class ParameterStringModel(BaseModel):
    str: ParameterStringValue


class ArgStringModel(BaseModel):
    arg: ArgString


class CommandStringModel(BaseModel):
    cmd: CommandString


class CombinationExprModel(BaseModel):
    expr: CombinationExpr


class TaskParameterStringValueAsJobModel(BaseModel):
    str: TaskParameterStringValueAsJob


class AttributeCapabilityNameModel(BaseModel):
    str: AttributeCapabilityName


class AmountCapabilityNameModel(BaseModel):
    str: AmountCapabilityName


class UserInterfaceLabelStringValueModel(BaseModel):
    str: UserInterfaceLabelStringValue


class FileDialogFilterPatternStringValueModel(BaseModel):
    str: FileDialogFilterPatternStringValue


class TestJobTemplateName:
    @pytest.mark.parametrize(
        "value",
        (pytest.param("{{ Job.Parameter.Foo }}", id="is formatstring"),),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"name": value}

        # WHEN
        JobTemplateNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (pytest.param({"name": "{{ Job.Parameter.Foo "}, id="bad format string"),),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            JobTemplateNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestJobName:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest"),
            pytest.param("A" * 128, id="longest"),
            pytest.param("a0 \u0103.:/=+-@{}😀", id="allowable characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"name": value}

        # WHEN
        JobNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": 12}, id="not string"),
            pytest.param({"name": ""}, id="too short"),
            pytest.param({"name": "a" * 129}, id="too long"),
            pytest.param({"name": "\n"}, id="no newline"),
            # Just testing the boundary points of the allowable characters
            pytest.param({"name": "\u0000"}, id="NULL disallowed"),
            pytest.param({"name": "\u001F"}, id="1f disallowed"),
            pytest.param({"name": "\u007F"}, id="DEL disallowed"),
            pytest.param({"name": "\u009F"}, id="9f disallowed"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            JobNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestStepName:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest"),
            pytest.param("A" * 64, id="longest"),
            pytest.param("a0\u0103.:/=+-@😀", id="allowable characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"name": value}

        # WHEN
        StepNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": 12}, id="not string"),
            pytest.param({"name": ""}, id="too short"),
            pytest.param({"name": "a" * 65}, id="too long"),
            pytest.param({"name": "\n"}, id="no newline"),
            # Just testing the boundary points of the allowable characters
            pytest.param({"name": "\u0000"}, id="NULL disallowed"),
            pytest.param({"name": "\u001F"}, id="1f disallowed"),
            pytest.param({"name": "\u007F"}, id="DEL disallowed"),
            pytest.param({"name": "\u009F"}, id="9f disallowed"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            StepNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestEnvironmentName:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest"),
            pytest.param("A" * 64, id="longest"),
            pytest.param("a0\u0103.:/=+-@😀", id="allowable characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"name": value}

        # WHEN
        EnvironmentNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"name": 12}, id="not string"),
            pytest.param({"name": ""}, id="too short"),
            pytest.param({"name": "a" * 65}, id="too long"),
            pytest.param({"name": "\n"}, id="no newline"),
            # Just testing the boundary points of the allowable characters
            pytest.param({"name": "\u0000"}, id="NULL disallowed"),
            pytest.param({"name": "\u001F"}, id="1f disallowed"),
            pytest.param({"name": "\u007F"}, id="DEL disallowed"),
            pytest.param({"name": "\u009F"}, id="9f disallowed"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            EnvironmentNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestEnvironmentVariableNameString:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest(upper-A)"),
            pytest.param("A" * 256, id="longest(upper-A)"),
            pytest.param("Z", id="shortest(upper-Z)"),
            pytest.param("Z" * 256, id="longest(upper-Z)"),
            pytest.param("a", id="shortest(lower-a)"),
            pytest.param("a" * 256, id="longest(lower-a)"),
            pytest.param("z", id="shortest(lower-z)"),
            pytest.param("z" * 256, id="longest(lower-z)"),
            pytest.param("A" + "0" * 255, id="longest(trailing 0)"),
            pytest.param("A" + "9" * 255, id="longest(trailing 9)"),
            pytest.param("A_", id="allows underscore"),
            pytest.param("_a", id="start with underscore"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"name": value}

        # WHEN
        EnvironmentVariableNameStringModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": 12}, id="not string"),
            pytest.param({"name": ""}, id="too short"),
            pytest.param({"name": "a" * 257}, id="too long"),
            pytest.param({"name": " a"}, id="start space"),
            pytest.param({"name": "a "}, id="end space"),
            pytest.param({"name": "0"}, id="no digit start(0)"),
            pytest.param({"name": "9"}, id="no digit start(9)"),
            pytest.param({"name": "!foo"}, id="starts alpha"),
            pytest.param({"name": "F!"}, id="only alphanum"),
        ]
        + [
            pytest.param({"id": f"a{letter}"}, id=f"'{letter}' not allowed")
            for letter in sorted(
                list(
                    set(string.printable)
                    - set(string.ascii_letters)
                    - set(string.digits)
                    - set("_")
                )
            )
        ],
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            EnvironmentVariableNameStringModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestEnvironmentVariableValueString:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("", id="shortest"),
            pytest.param("A" * 2048, id="longest"),
            pytest.param(string.printable, id="many characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"value": value}

        # WHEN
        EnvironmentVariableValueStringModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"value": "a" * 2049}, id="too long"),
        ],
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            EnvironmentVariableValueStringModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestIdentifier:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest(upper-A)"),
            pytest.param("A" * 64, id="longest(upper-A)"),
            pytest.param("Z", id="shortest(upper-Z)"),
            pytest.param("Z" * 64, id="longest(upper-Z)"),
            pytest.param("a", id="shortest(lower-a)"),
            pytest.param("a" * 64, id="longest(lower-a)"),
            pytest.param("z", id="shortest(lower-z)"),
            pytest.param("z" * 64, id="longest(lower-z)"),
            pytest.param("A" + "0" * 63, id="longest(trailing 0)"),
            pytest.param("A" + "9" * 63, id="longest(trailing 9)"),
            pytest.param("_" * 64, id="underscore"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"id": value}

        # WHEN
        IdentifierModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"id": 12}, id="not string"),
            pytest.param({"id": ""}, id="too short"),
            pytest.param({"id": "a" * 65}, id="too long"),
            pytest.param({"id": " a"}, id="start space"),
            pytest.param({"id": "a "}, id="end space"),
            pytest.param({"id": "0"}, id="no digit start(0)"),
            pytest.param({"id": "9"}, id="no digit start(9)"),
            pytest.param({"id": "!foo"}, id="starts alpha"),
            pytest.param({"id": "F!"}, id="only alphanum"),
        ]
        + [
            pytest.param({"id": f"a{letter}"}, id=f"'{letter}' not allowed")
            for letter in sorted(
                list(
                    set(string.printable)
                    - set(string.ascii_letters)
                    - set(string.digits)
                    - set("_")
                )
            )
        ],
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            IdentifierModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestDescription:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="min length"),
            pytest.param("A" * 2048, id="max length"),
            # Control character exlusion cases
            pytest.param("\u0020", id="start of first printable range"),
            pytest.param("\u007E", id="end of first printable range"),
            pytest.param("\u00A0", id="start of second printable range"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"desc": value}

        # WHEN
        DescriptionModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"desc": 12}, id="not string"),
            pytest.param({"desc": ""}, id="too short"),
            pytest.param({"desc": "a" * 2049}, id="too long"),
            pytest.param({"desc": "\u0000"}, id="start of first control character range"),
            pytest.param({"desc": "\u001F"}, id="end of first control character range"),
            pytest.param({"desc": "\u007F"}, id="start of second control character range"),
            pytest.param({"desc": "\u009F"}, id="end of second control character range"),
            pytest.param({"desc": "a\n\u0000"}, id="disallowed after newline"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            DescriptionModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestParameterStringValue:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("", id="min length"),
            pytest.param("A" * 1024, id="max length"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        ParameterStringModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"str": 12}, id="not string"),
            pytest.param({"str": "a" * 1025}, id="too long"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            ParameterStringModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestArgString:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("", id="min length"),
            pytest.param("A" * (32 * 1024), id="long length"),
            # Control character exlusion cases
            pytest.param("\u0020", id="start of first printable range"),
            pytest.param("\u007E", id="end of first printable range"),
            pytest.param("\u00A0", id="start of second printable range"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"arg": value}

        # WHEN
        ArgStringModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"arg": 12}, id="not string"),
            pytest.param({"cmd": "\n"}, id="newline"),
            pytest.param({"cmd": "\r"}, id="carriage return"),
            pytest.param({"cmd": "\t"}, id="horizontal tab"),
            pytest.param({"arg": "\u0000"}, id="start of first control character range"),
            pytest.param({"arg": "\u001F"}, id="end of first control character range"),
            pytest.param({"arg": "\u007F"}, id="start of second control character range"),
            pytest.param({"arg": "\u009F"}, id="end of second control character range"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            ArgStringModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestCommandString:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="min length"),
            pytest.param("A" * (32 * 1024), id="long length"),
            # Control character exlusion cases
            pytest.param("\u0020", id="start of first printable range"),
            pytest.param("\u007E", id="end of first printable range"),
            pytest.param("\u00A0", id="start of second printable range"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"cmd": value}

        # WHEN
        CommandStringModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"cmd": 12}, id="not string"),
            pytest.param({"cmd": ""}, id="too short"),
            pytest.param({"cmd": "\n"}, id="newline"),
            pytest.param({"cmd": "\r"}, id="carriage return"),
            pytest.param({"cmd": "\t"}, id="horizontal tab"),
            pytest.param({"cmd": "\u0000"}, id="start of first control character range"),
            pytest.param({"cmd": "\u001F"}, id="end of first control character range"),
            pytest.param({"cmd": "\u007F"}, id="start of second control character range"),
            pytest.param({"cmd": "\u009F"}, id="end of second control character range"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            CommandStringModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestCombinationExpr:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("A", id="shortest"),
            pytest.param("a" * 1280, id="longest"),
            pytest.param(string.ascii_letters + string.digits, id="allowable identifier chars"),
            pytest.param(" ", id="allowable whitespace"),
            pytest.param("*(),", id="allowable operators"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"expr": value}

        # WHEN
        CombinationExprModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"expr": 12}, id="not string"),
            pytest.param({"expr": ""}, id="too short"),
            pytest.param({"expr": "a" * 1281}, id="too long"),
            # Disallowed characters that appear in the regex and could be allowed
            # if we mess up the regex definition.
            pytest.param({"expr": "^"}, id="carat"),
            pytest.param({"expr": "$"}, id="dollar"),
            pytest.param({"expr": "+"}, id="plus"),
            pytest.param({"expr": "["}, id="square open paren"),
            pytest.param({"expr": "]"}, id="square close paren"),
            pytest.param({"expr": "\\"}, id="backslash character"),
            # No multiline strings
            pytest.param({"expr": "foo\n"}, id="no newline"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            CombinationExprModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestTaskParameterStringValueAsJob:
    @pytest.mark.parametrize(
        "value", (pytest.param("", id="shortest"), pytest.param("A" * 1024, id="longest"))
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        TaskParameterStringValueAsJobModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (pytest.param({"str": "A" * 1025}, id="too long"),),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            TaskParameterStringValueAsJobModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestAmountCapabilityName:
    # Note: The string regex is tested in ../test_capabilities.py

    @pytest.mark.parametrize(
        "value", (pytest.param("a", id="shortest"), pytest.param("A" * 100, id="longest"))
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        AmountCapabilityNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"str": 12}, id="not string"),
            pytest.param({"str": "A" * 101}, id="too long"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            AmountCapabilityNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestAttributeCapabilityName:
    # Note: The string regex is tested in ../test_capabilities.py

    @pytest.mark.parametrize(
        "value", (pytest.param("a", id="shortest"), pytest.param("A" * 100, id="longest"))
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        AttributeCapabilityNameModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"str": 12}, id="not string"),
            pytest.param({"str": "A" * 101}, id="too long"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            AttributeCapabilityNameModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestUserInterfaceLabelStringValue:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("a", id="shortest"),
            pytest.param("A" * 64, id="longest"),
            pytest.param("a0 \u0103.:/=+-@{}😀", id="allowable characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        UserInterfaceLabelStringValueModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"str": 12}, id="not string"),
            pytest.param({"str": ""}, id="too short"),
            pytest.param({"str": "A" * 65}, id="too long"),
            pytest.param({"str": "\n"}, id="no newline"),
            # Just testing the boundary points of the allowable characters
            pytest.param({"str": "\u0000"}, id="NULL disallowed"),
            pytest.param({"str": "\u001F"}, id="1f disallowed"),
            pytest.param({"str": "\u007F"}, id="DEL disallowed"),
            pytest.param({"str": "\u009F"}, id="9f disallowed"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            UserInterfaceLabelStringValueModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0


class TestFileDialogFilterPatternStringValue:
    @pytest.mark.parametrize(
        "value",
        (
            pytest.param("*", id="shortest, special pattern '*'"),
            pytest.param("*.*", id="special pattern '*.*'"),
            pytest.param("*." + "A" * 18, id="longest"),
            pytest.param("*.a0 \u0103.+-😀", id="allowable characters"),
        ),
    )
    def test_parse_success(self, value: str) -> None:
        # GIVEN
        data = {"str": value}

        # WHEN
        FileDialogFilterPatternStringValueModel.parse_obj(data)

        # THEN
        # no exceptions raised

    @pytest.mark.parametrize(
        "data",
        (
            pytest.param({"str": 12}, id="not string"),
            pytest.param({"name": ""}, id="too short"),
            pytest.param({"str": "*." + "A" * 19}, id="too long"),
            pytest.param({"str": "abc"}, id="need prefix '*.'"),
            pytest.param({"str": ".abc"}, id="need prefix '*'"),
            pytest.param({"name": "*.\n"}, id="no newline"),
            # Just testing the boundary points of the allowable characters
            pytest.param({"name": "*.\u0000"}, id="NULL disallowed"),
            pytest.param({"name": "*.\u001F"}, id="1f disallowed"),
            pytest.param({"name": "*.\u007F"}, id="DEL disallowed"),
            pytest.param({"name": "*.\u009F"}, id="9f disallowed"),
            # The list of characters explicitly disallowed
            #    b. Path separators "\" and "/".
            pytest.param({"name": "*.\\"}, id="no '\\'"),
            pytest.param({"name": "*./"}, id="no '/'"),
            #    c. Wildcard characters "*", "?", "[", "]".
            pytest.param({"name": "*.a*"}, id="no '*' outside special case '*.*'"),
            pytest.param({"name": "*.?"}, id="no '?'"),
            pytest.param({"name": "*.["}, id="no '['"),
            pytest.param({"name": "*.]"}, id="no ']'"),
            #    d. Characters commonly disallowed in paths "#", "%", "&", "{", "}", "<", ">",
            #       "$", "!", "'", "\"", ":", "@", "`", "|", "=".
            pytest.param({"name": "*.#"}, id="no '#'"),
            pytest.param({"name": "*.%"}, id="no '%'"),
            pytest.param({"name": "*.&"}, id="no '&'"),
            pytest.param({"name": "*.{"}, id="no '{'"),
            pytest.param({"name": "*.}"}, id="no '}'"),
            pytest.param({"name": "*.<"}, id="no '<'"),
            pytest.param({"name": "*.>"}, id="no '>'"),
            pytest.param({"name": "*.$"}, id="no '$'"),
            pytest.param({"name": "*.!"}, id="no '!'"),
            pytest.param({"name": "*.'"}, id="no '''"),
            pytest.param({"name": '*."'}, id="no '\"'"),
            pytest.param({"name": "*.:"}, id="no ':'"),
            pytest.param({"name": "*.@"}, id="no '@'"),
            pytest.param({"name": "*.`"}, id="no '`'"),
            pytest.param({"name": "*.|"}, id="no '|'"),
            pytest.param({"name": "*.="}, id="no '='"),
        ),
    )
    def test_parse_fails(self, data: dict[str, Any]) -> None:
        # - Constraint tests

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            FileDialogFilterPatternStringValueModel.parse_obj(data)

        # THEN
        assert len(excinfo.value.errors()) > 0
