# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the typed ``*UserInterface`` pyclasses returned by the
``user_interface`` getter on each ``Job*ParameterDefinition``
pyclass.

Mirror the 11 Rust ``openjd_model::template::*UserInterface`` struct
types plus ``FileFilter``:

* ``StringUserInterface`` — common only
* ``IntUserInterface`` — + ``single_step_delta``
* ``FloatUserInterface`` — + ``decimals``, ``single_step_delta``
* ``PathUserInterface`` — + ``file_filters``, ``file_filter_default``
* ``BoolUserInterface`` — common only (EXPR)
* ``RangeExprUserInterface`` — common only (EXPR)
* ``ListSimpleUserInterface`` — common only — used by
  ``LIST[STRING]`` and ``LIST[BOOL]``
* ``ListPathUserInterface`` — + ``file_filters``,
  ``file_filter_default`` (EXPR)
* ``ListIntUserInterface`` — + ``single_step_delta`` (EXPR)
* ``ListFloatUserInterface`` — + ``decimals``, ``single_step_delta``
  (EXPR)
* ``HiddenOnlyUserInterface`` — common only — used by
  ``LIST[LIST[INT]]`` (EXPR)

All UI types share three common fields: ``control: Optional[str]``,
``label: Optional[str]``, ``group_label: Optional[str]`` (with
``groupLabel`` camelCase alias). See report finding #11
(``user_interface`` exposure).
"""

from openjd.model._v1 import decode_job_template
from openjd.model._v1.template import (
    BoolUserInterface,
    FileFilter,
    FloatUserInterface,
    HiddenOnlyUserInterface,
    IntUserInterface,
    JobBoolParameterDefinition,
    JobFloatParameterDefinition,
    JobIntParameterDefinition,
    JobListBoolParameterDefinition,
    JobListFloatParameterDefinition,
    JobListIntParameterDefinition,
    JobListListIntParameterDefinition,
    JobListPathParameterDefinition,
    JobListStringParameterDefinition,
    JobPathParameterDefinition,
    JobRangeExprParameterDefinition,
    ListFloatUserInterface,
    ListIntUserInterface,
    ListPathUserInterface,
    ListSimpleUserInterface,
    PathUserInterface,
    RangeExprUserInterface,
    StringUserInterface,
)


def _decode_with_param(param: dict, *, extensions=None):
    """Build a one-step template with a single ``parameterDefinitions``
    entry and run it through ``decode_job_template``. Returns the
    typed pyclass for the parameter (the first/only entry)."""
    template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "T",
        "parameterDefinitions": [param],
        "steps": [{"name": "S", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }
    if extensions:
        template["extensions"] = list(extensions)
    t = decode_job_template(
        template=template,
        supported_extensions=list(extensions) if extensions else None,
    )
    assert t.parameter_definitions is not None
    return t.parameter_definitions[0]


# ── Empty / missing user_interface ──


class TestUserInterfaceAccessor:
    def test_no_user_interface_field(self) -> None:
        """A parameter without a ``userInterface`` field has
        ``param.user_interface is None`` (and the camelCase alias)."""
        d = _decode_with_param({"name": "F", "type": "STRING"})
        assert d.user_interface is None
        assert d.userInterface is None

    def test_camelcase_alias(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "STRING",
                "userInterface": {"control": "LINE_EDIT"},
            }
        )
        # ``user_interface`` and ``userInterface`` getters both return
        # a typed pyclass; the underlying class object is the same.
        assert type(d.user_interface) is type(d.userInterface)
        assert d.user_interface.control == d.userInterface.control


# ── Common fields (control / label / group_label) on every variant ──


class TestCommonFields:
    """Every ``*UserInterface`` shares the three common fields. Spot-
    check each variant exposes them correctly."""

    def test_string_common_fields(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "STRING",
                "userInterface": {
                    "control": "LINE_EDIT",
                    "label": "A label",
                    "groupLabel": "Group A",
                },
            }
        )
        ui = d.user_interface
        assert isinstance(ui, StringUserInterface)
        assert ui.control == "LINE_EDIT"
        assert ui.label == "A label"
        assert ui.group_label == "Group A"
        assert ui.groupLabel == "Group A"

    def test_optional_fields_default_to_none(self) -> None:
        """Each common field is optional; a userInterface block can
        carry just a control."""
        d = _decode_with_param(
            {
                "name": "F",
                "type": "STRING",
                "userInterface": {"control": "LINE_EDIT"},
            }
        )
        ui = d.user_interface
        assert ui.control == "LINE_EDIT"
        assert ui.label is None
        assert ui.group_label is None


# ── IntUserInterface (single_step_delta) ──


class TestIntUserInterface:
    def test_full(self) -> None:
        d = _decode_with_param(
            {
                "name": "Frame",
                "type": "INT",
                "userInterface": {
                    "control": "SPIN_BOX",
                    "label": "Frame",
                    "groupLabel": "Animation",
                    "singleStepDelta": 5,
                },
            }
        )
        assert isinstance(d, JobIntParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, IntUserInterface)
        assert ui.control == "SPIN_BOX"
        assert ui.label == "Frame"
        assert ui.group_label == "Animation"
        assert ui.single_step_delta == 5
        # camelCase aliases
        assert ui.singleStepDelta == 5
        assert ui.groupLabel == "Animation"

    def test_no_single_step_delta(self) -> None:
        d = _decode_with_param(
            {
                "name": "Frame",
                "type": "INT",
                "userInterface": {"control": "SPIN_BOX"},
            }
        )
        ui = d.user_interface
        assert ui.single_step_delta is None
        assert ui.singleStepDelta is None


# ── FloatUserInterface (decimals + single_step_delta) ──


class TestFloatUserInterface:
    def test_full(self) -> None:
        d = _decode_with_param(
            {
                "name": "X",
                "type": "FLOAT",
                "userInterface": {
                    "control": "SPIN_BOX",
                    "decimals": 3,
                    "singleStepDelta": 0.25,
                },
            }
        )
        assert isinstance(d, JobFloatParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, FloatUserInterface)
        assert ui.decimals == 3
        assert ui.single_step_delta == 0.25
        assert ui.singleStepDelta == 0.25

    def test_only_decimals(self) -> None:
        d = _decode_with_param(
            {
                "name": "X",
                "type": "FLOAT",
                "userInterface": {"decimals": 4},
            }
        )
        ui = d.user_interface
        assert ui.decimals == 4
        assert ui.single_step_delta is None


# ── PathUserInterface (file_filters + file_filter_default) ──


class TestPathUserInterface:
    def test_with_file_filters(self) -> None:
        d = _decode_with_param(
            {
                "name": "Input",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {
                    "control": "CHOOSE_INPUT_FILE",
                    "label": "Input file",
                    "fileFilters": [
                        {"label": "Images", "patterns": ["*.png", "*.jpg"]},
                        {"label": "All", "patterns": ["*"]},
                    ],
                    "fileFilterDefault": {
                        "label": "Images",
                        "patterns": ["*.png", "*.jpg"],
                    },
                },
            }
        )
        assert isinstance(d, JobPathParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, PathUserInterface)
        assert ui.control == "CHOOSE_INPUT_FILE"

        filters = ui.file_filters
        assert filters is not None
        assert len(filters) == 2
        assert all(isinstance(f, FileFilter) for f in filters)
        assert filters[0].label == "Images"
        assert filters[0].patterns == ["*.png", "*.jpg"]
        assert filters[1].label == "All"

        default = ui.file_filter_default
        assert isinstance(default, FileFilter)
        assert default.label == "Images"
        # camelCase aliases
        assert ui.fileFilters is not None
        assert ui.fileFilterDefault is not None

    def test_no_file_filters(self) -> None:
        d = _decode_with_param(
            {
                "name": "Out",
                "type": "PATH",
                "objectType": "DIRECTORY",
                "dataFlow": "OUT",
                "userInterface": {"control": "CHOOSE_DIRECTORY"},
            }
        )
        ui = d.user_interface
        assert ui.file_filters is None
        assert ui.file_filter_default is None


class TestFileFilter:
    def test_label_and_patterns(self) -> None:
        d = _decode_with_param(
            {
                "name": "Input",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {
                    "fileFilters": [
                        {"label": "Source", "patterns": ["*.py", "*.rs", "*.c"]},
                    ],
                },
            }
        )
        ff = d.user_interface.file_filters[0]
        assert ff.label == "Source"
        assert ff.patterns == ["*.py", "*.rs", "*.c"]


# ── EXPR-extension UI variants ──


class TestBoolUserInterface:
    def test_common_only(self) -> None:
        d = _decode_with_param(
            {
                "name": "B",
                "type": "BOOL",
                "default": True,
                "userInterface": {"control": "CHECK_BOX", "label": "Enable"},
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobBoolParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, BoolUserInterface)
        assert ui.control == "CHECK_BOX"
        assert ui.label == "Enable"


class TestRangeExprUserInterface:
    def test_common_only(self) -> None:
        d = _decode_with_param(
            {
                "name": "Frames",
                "type": "RANGE_EXPR",
                "userInterface": {"control": "LINE_EDIT", "label": "Frame range"},
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobRangeExprParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, RangeExprUserInterface)
        assert ui.control == "LINE_EDIT"


class TestListSimpleUserInterface:
    def test_list_string(self) -> None:
        d = _decode_with_param(
            {
                "name": "Tags",
                "type": "LIST[STRING]",
                "userInterface": {"control": "LINE_EDIT_LIST", "label": "Tags"},
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListStringParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, ListSimpleUserInterface)
        assert ui.control == "LINE_EDIT_LIST"

    def test_list_bool(self) -> None:
        """LIST[BOOL] also uses ListSimpleUserInterface."""
        d = _decode_with_param(
            {
                "name": "Flags",
                "type": "LIST[BOOL]",
                "userInterface": {"control": "CHECK_BOX_LIST"},
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListBoolParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, ListSimpleUserInterface)
        assert ui.control == "CHECK_BOX_LIST"


class TestListPathUserInterface:
    def test_with_file_filters(self) -> None:
        d = _decode_with_param(
            {
                "name": "Inputs",
                "type": "LIST[PATH]",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {
                    "control": "CHOOSE_INPUT_FILE_LIST",
                    "fileFilters": [
                        {"label": "Source", "patterns": ["*.py"]},
                    ],
                },
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListPathParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, ListPathUserInterface)
        assert ui.control == "CHOOSE_INPUT_FILE_LIST"
        assert ui.file_filters is not None
        assert ui.file_filters[0].label == "Source"


class TestListIntUserInterface:
    def test_single_step_delta(self) -> None:
        d = _decode_with_param(
            {
                "name": "Counts",
                "type": "LIST[INT]",
                "userInterface": {
                    "control": "SPIN_BOX_LIST",
                    "singleStepDelta": 10,
                },
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListIntParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, ListIntUserInterface)
        assert ui.single_step_delta == 10


class TestListFloatUserInterface:
    def test_decimals_and_single_step_delta(self) -> None:
        d = _decode_with_param(
            {
                "name": "Weights",
                "type": "LIST[FLOAT]",
                "userInterface": {
                    "control": "SPIN_BOX_LIST",
                    "decimals": 4,
                    "singleStepDelta": 0.001,
                },
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListFloatParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, ListFloatUserInterface)
        assert ui.decimals == 4
        assert ui.single_step_delta == 0.001


class TestHiddenOnlyUserInterface:
    def test_common_only(self) -> None:
        """LIST[LIST[INT]] uses HiddenOnlyUserInterface — hidden-only
        per spec, but the UI block can still carry control/label
        metadata."""
        d = _decode_with_param(
            {
                "name": "Matrix",
                "type": "LIST[LIST[INT]]",
                "userInterface": {"control": "HIDDEN", "label": "Matrix"},
            },
            extensions=["EXPR"],
        )
        assert isinstance(d, JobListListIntParameterDefinition)
        ui = d.user_interface
        assert isinstance(ui, HiddenOnlyUserInterface)
        assert ui.control == "HIDDEN"
        assert ui.label == "Matrix"


# ── Variant-to-UI dispatch sanity check ──


class TestVariantDispatch:
    """Verify that each ``Job*ParameterDefinition`` variant returns
    the correct ``*UserInterface`` pyclass type."""

    def test_string_returns_string_ui(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "STRING",
                "userInterface": {"control": "LINE_EDIT"},
            }
        )
        assert isinstance(d.user_interface, StringUserInterface)

    def test_int_returns_int_ui(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "INT",
                "userInterface": {"control": "SPIN_BOX"},
            }
        )
        assert isinstance(d.user_interface, IntUserInterface)

    def test_float_returns_float_ui(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "FLOAT",
                "userInterface": {"control": "SPIN_BOX"},
            }
        )
        assert isinstance(d.user_interface, FloatUserInterface)

    def test_path_returns_path_ui(self) -> None:
        d = _decode_with_param(
            {
                "name": "F",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {"control": "CHOOSE_INPUT_FILE"},
            }
        )
        assert isinstance(d.user_interface, PathUserInterface)
