# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Literal, Union
from enum import Enum
from typing_extensions import Annotated
from pydantic.v1 import Field

import pytest

from openjd.model._format_strings import FormatString
from openjd.model._internal import prevalidate_model_template_variable_references
from openjd.model._types import (
    DefinesTemplateVariables,
    OpenJDModel,
    ResolutionScope,
    TemplateVariableDef,
)

# arg2 = Whether a var defined in the arg0 scope is available in the arg1 scope.
#    TEMPLATE scope -> referenced in only TEMPLATE, SESSION, and TASK scope
#    SESSION scope -> referenced in only SESSION and TASK scope
#    TASK scope -> referenced in only TASK scope
SCOPE_AVAILABILITY = [
    pytest.param(
        ResolutionScope.TEMPLATE, ResolutionScope.TEMPLATE, True, id="avail-template-template"
    ),
    pytest.param(
        ResolutionScope.TEMPLATE, ResolutionScope.SESSION, True, id="avail-template-session"
    ),
    pytest.param(ResolutionScope.TEMPLATE, ResolutionScope.TASK, True, id="avail-template-task"),
    pytest.param(
        ResolutionScope.SESSION, ResolutionScope.TEMPLATE, False, id="notavail-session-template"
    ),
    pytest.param(
        ResolutionScope.SESSION, ResolutionScope.SESSION, True, id="avail-session-session"
    ),
    pytest.param(ResolutionScope.SESSION, ResolutionScope.TASK, True, id="avail-session-session"),
    pytest.param(
        ResolutionScope.TASK, ResolutionScope.TEMPLATE, False, id="notavail-task-template"
    ),
    pytest.param(ResolutionScope.TASK, ResolutionScope.SESSION, False, id="notavail-task-session"),
    pytest.param(ResolutionScope.TASK, ResolutionScope.TASK, True, id="avail-task-task"),
]


class TestVariableScope:
    """Tests that a variable defined in a specific scope is referenceable in the correct scopes."""

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_self(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # A variabled defined in a scope must be referenceable in __self__ in the appropriate scopes.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": "{{ Param.Foo }}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_dict_field_self(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # A variabled defined in a scope must be referenceable in __self__ in the appropriate scopes.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: dict[str, FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": {"a": "{{ Param.Foo }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_submodel(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # A variable defined in a scope in a base model is made available in the appropriate scopes in a submodel

        # GIVEN
        class SubModel(OpenJDModel):
            field: FormatString
            _template_variable_scope = ref_scope

        class BaseModel(OpenJDModel):
            name: str
            sub: SubModel

            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        data = {
            "name": "Foo",
            "sub": {"field": "{{ Param.Foo }}"},
        }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_export_to_parent(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # A variable exported by a submodel is made available to the parent in the appropriate scope.

        # GIVEN
        class SubModel(OpenJDModel):
            name: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {"__export__": {"__self__"}}

        class BaseModel(OpenJDModel):
            ref: FormatString
            sub: SubModel

            _template_variable_scope = ref_scope
            _template_variable_sources = {
                "ref": {"sub"},
            }

        data = {
            "ref": "{{ Param.Foo }}",
            "sub": {"name": "Foo"},
        }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    def test_non_export_not_available(self) -> None:
        # Test that if a submodel defines a variable but doesn't export it, then
        # it's not available in the parent.

        # GIVEN
        class Def(OpenJDModel):
            name: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        class BaseModel(OpenJDModel):
            defn: Def
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"defn"}}

        data = {"defn": {"name": "Foo"}, "ref": "{{ Param.Foo }}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 1

    def test_handles_missing_values(self) -> None:
        # Our given data may be missing values for some fields. Ensure we don't explode.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = dict[str, Any]()

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_variable_def_in_wrong_type(self) -> None:
        # The field referenced in DefinesTemplateVariables might not be given a string value. Ensure that we don't explode.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": 12, "ref": "this is okay"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_bad_format_string(self) -> None:
        # A format string may be ill-formed. Ensure we don't explode.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        # Format string in 'ref' is not well formed.
        data = {"name": "Foo", "ref": "{{Param.Foo"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_format_string_with_no_expr(self) -> None:
        # A format string doesn't actually have to have sub-expressions. Ensure we don't explode.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        # Format string in 'ref' is not well formed.
        data = {"name": "Foo", "ref": "No variable reference"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_format_string_with_empty_expr(self) -> None:
        # A format string's expression may be empty. Ensure we don't explode.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        # Format string in 'ref' is not well formed.
        data = {"name": "Foo", "ref": "{{}}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_literal_fields(self) -> None:
        # A test to make sure that the collect variables and field traversal codepaths
        # don't explode when presented with a Literal field

        # GIVEN
        class BaseModel(OpenJDModel):
            lit: Literal["Bob"]
            name: str
            ref: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"lit": "Bob", "name": "Foo", "ref": "{{ Param.Foo }}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_field_not_dict(self) -> None:
        # A test that ensures that we handle the case where the model says that a field should
        # be an object but the value that we're provided isn't actually a model. This shouldn't
        # be flagged as a validation error here, but rather we just need to make sure that we don't
        # blow up; the model's other validators will handle the validation error.

        # GIVEN
        class SubModel(OpenJDModel):
            name: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {"__export__": {"__self__"}}

        class BaseModel(OpenJDModel):
            ref: FormatString
            sub: SubModel

            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {
                "ref": {"sub"},
            }

        data = {"ref": "{{ Param.Foo }}", "sub": "this is not a dict"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 1  # Bad reference to Param.Foo

    def test_handles_field_not_str(self) -> None:
        # A test that ensures that we handle the case where the model says that a field should
        # be a FormatString but the value that we're provided isn't actually a string. This shouldn't
        # be flagged as a validation error here, but rather we just need to make sure that we don't
        # blow up; the model's other validators will handle the validation error.

        # GIVEN
        class SubModel(OpenJDModel):
            name: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {"__export__": {"__self__"}}

        class BaseModel(OpenJDModel):
            ref: FormatString
            sub: SubModel

            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {
                "ref": {"sub"},
            }

        data = {"ref": ["{{Param.Foo}}"], "sub": {"name": "Foo"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_dict_field_not_dict(self) -> None:
        # A variabled defined in a scope must be referenceable in __self__ in the appropriate scopes.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: dict[str, FormatString]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": "Foo", "ref": "{{ Param.Bar }}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_dict_key_not_str(self) -> None:
        # A variabled defined in a scope must be referenceable in __self__ in the appropriate scopes.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: dict[str, FormatString]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": "Foo", "ref": {12: "{{ Param.Bar }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0


class TestSymbolPrefixNesting:
    """Tests that symbol prefixes can be properly nested into submodels."""

    def test_subprefix(self) -> None:
        # Test that the variable defined in a submodel has the prefix defined in the parent

        # GIVEN
        class Submodel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {"ref": {"__self__"}}

        class BaseModel(OpenJDModel):
            sub: Submodel
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_definitions = DefinesTemplateVariables(symbol_prefix="Root.")

        data = {"sub": {"name": "Foo", "ref": "{{ Root.Param.Foo }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_prefix_reset_in_def(self) -> None:
        # Test that resetting a prefix during a variable definition ignores the parent prefix

        # GIVEN
        class Submodel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Sub.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {"ref": {"__self__"}}

        class BaseModel(OpenJDModel):
            sub: Submodel
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_definitions = DefinesTemplateVariables(symbol_prefix="Root.")

        data = {"sub": {"name": "Foo", "ref": "{{ Sub.Foo }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_prefix_reset_in_model(self) -> None:
        # Test that resetting a prefix in the submodel ignores the parent prefix

        # GIVEN
        class Submodel(OpenJDModel):
            name: str
            ref: FormatString
            _template_variable_definitions = DefinesTemplateVariables(
                symbol_prefix="|Sub.",
                defines={TemplateVariableDef(prefix="Inner.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {"ref": {"__self__"}}

        class BaseModel(OpenJDModel):
            sub: Submodel
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_definitions = DefinesTemplateVariables(symbol_prefix="Root.")

        data = {"sub": {"name": "Foo", "ref": "{{ Sub.Inner.Foo }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0


class TestInjectSymbol:
    """Test that injected symbols are referencable at the correct scope."""

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test(self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool) -> None:
        # Test that we can reference an injected symbol in the scopes that it's supposed to be available within.

        # GIVEN
        class Submodel(OpenJDModel):
            ref: FormatString
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}

        class BaseModel(OpenJDModel):
            sub: Submodel
            _template_variable_scope = def_scope
            _template_variable_definitions = DefinesTemplateVariables(
                symbol_prefix="Root.", inject={"Foo", "|New.Bar"}
            )
            _template_variable_sources = {"sub": {"__self__"}}

        data = {"sub": {"ref": "{{ Root.Foo }} {{ New.Bar }}"}}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 2)


class TestListField:
    """Test that if we have a field that's a list that we check its elements correctly."""

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_model(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # Test that if we have a field that's a list of submodels that the variable is available in the
        # appropriate scopes in that submodel.

        # GIVEN
        class SubModel(OpenJDModel):
            field: FormatString
            _template_variable_scope = ref_scope

        class BaseModel(OpenJDModel):
            name: str
            sub: list[SubModel]

            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        data = {
            "name": "Foo",
            "sub": [
                {"field": "{{ Param.Foo }}"},
                {"field": "{{ Param.Foo }}"},
                {"field": "{{ Param.Foo }}"},
            ],
        }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 3)

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_string(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # Test that if we have a field that's a list of FormatStrings that the variable is available in the
        # appropriate scopes in that submodel.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: list[FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": ["{{ Param.Foo }}", "{{ Param.Foo }}", "{{ Param.Foo }}"]}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 3)

    def test_handles_non_list(self) -> None:
        # Test that we don't explode if the model says that we should have a list but the value
        # that we're given for the field isn't actually a list.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: list[FormatString]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": "Foo", "ref": "{{ Param.Foo }}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_list_incorrect_element_type_fstring(self) -> None:
        # Test that we don't explode if the model says that we should have a list of FormatString but the value
        # that we're given for the field has list elements that aren't type str.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: list[FormatString]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": "Foo", "ref": ["{{ Param.Foo }}", 12, {"item": "{{Param.Bar}}"}]}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    def test_handles_list_incorrect_element_type_model(self) -> None:
        # Test that we don't explode if the model says that we should have a list of models but the value
        # that we're given for the field has list elements that aren't dicts.

        # GIVEN
        class SubModel(OpenJDModel):
            field: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE

        class BaseModel(OpenJDModel):
            name: str
            sub: list[SubModel]

            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        data = {
            "name": "Foo",
            "sub": [
                {"field": "{{ Param.Foo }}"},
                "{{ Param.Foo }}",
                {"field": "{{ Param.Foo }}"},
            ],
        }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0


class TestDiscriminatedUnion:
    """Test that if we have a discriminated unions in the model then we handle them correctly.

    Template variables are allowed to be defined and/or referenced within discriminated union fields.
    """

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {"name": "Foo", "sub": {"kind": "ONE", "field1": "{{Param.Foo}}"}}, id="SubModel1"
            ),
            pytest.param(
                {"name": "Foo", "sub": {"kind": "TWO", "field2": "{{Param.Foo}}"}}, id="SubModel2"
            ),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_singleton_reference(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            field1: FormatString
            _template_variable_scope = ref_scope

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            field2: FormatString
            _template_variable_scope = ref_scope

        class BaseModel(OpenJDModel):
            name: str
            sub: Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]

            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {"ref": "{{Param.Foo}}", "sub": {"kind": "ONE", "name1": "Foo"}}, id="SubModel1"
            ),
            pytest.param(
                {"ref": "{{Param.Foo}}", "sub": {"kind": "TWO", "name2": "Foo"}}, id="SubModel2"
            ),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_singleton_definition_export(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly export variable definitions from within the union.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            name1: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name1",
            )
            _template_variable_sources = {
                "__export__": {"__self__"},
            }

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            name2: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name2",
            )
            _template_variable_sources = {
                "__export__": {"__self__"},
            }

        class BaseModel(OpenJDModel):
            ref: FormatString
            sub: Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]
            _template_variable_scope = ref_scope
            _template_variable_sources = {
                "ref": {"sub"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {"name": "Foo", "sub": {"kind": "THREE", "field1": "{{Param.Foo}}"}},
                id="unknown key value",
            ),
            pytest.param(
                {"name": "Foo", "sub": {"kind": 1, "field1": "{{Param.Foo}}"}},
                id="incorrect key type int",
            ),
            pytest.param(
                {"name": "Foo", "sub": {"kind": ["ONE"], "field1": "{{Param.Foo}}"}},
                id="incorrect key type list",
            ),
            pytest.param(
                {"name": "Foo", "sub": {"field1": "{{Param.Foo}}"}}, id="discriminator missing"
            ),
            pytest.param({"name": "Foo", "sub": "Not a dict"}, id="value is not a dict"),
        ],
    )
    def test_singleton_bad_data(self, data: dict[str, Any]) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # don't explode if the value given doesn't have an expected shape/values.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            field1: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            field2: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE

        class BaseModel(OpenJDModel):
            name: str
            sub: Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {
                    "name": "Foo",
                    "sub": [
                        {"kind": "ONE", "field1": "{{Param.Foo}}"},
                        {"kind": "ONE", "field1": "{{Param.Foo}}"},
                    ],
                },
                id="SubModel1",
            ),
            pytest.param(
                {
                    "name": "Foo",
                    "sub": [
                        {"kind": "TWO", "field2": "{{Param.Foo}}"},
                        {"kind": "TWO", "field2": "{{Param.Foo}}"},
                    ],
                },
                id="SubModel2",
            ),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_list_reference(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a list of discriminated union types then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            field1: FormatString
            _template_variable_scope = ref_scope

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            field2: FormatString
            _template_variable_scope = ref_scope

        class BaseModel(OpenJDModel):
            name: str
            sub: list[Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]]
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 2)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {
                    "ref": "{{Param.Foo}} {{Param.Bar}}",
                    "sub": [{"kind": "ONE", "name1": "Foo"}, {"kind": "ONE", "name1": "Bar"}],
                },
                id="SubModel1",
            ),
            pytest.param(
                {
                    "ref": "{{Param.Foo}} {{Param.Bar}}",
                    "sub": [{"kind": "TWO", "name2": "Foo"}, {"kind": "TWO", "name2": "Bar"}],
                },
                id="SubModel2",
            ),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_list_definition_export(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a list of discriminated union types then we
        # properly export variable definitions from within the list of unions.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            name1: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name1",
            )
            _template_variable_sources = {
                "__export__": {"__self__"},
            }

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            name2: str
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name2",
            )
            _template_variable_sources = {
                "__export__": {"__self__"},
            }

        class BaseModel(OpenJDModel):
            ref: FormatString
            sub: list[Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]]
            _template_variable_scope = ref_scope
            _template_variable_sources = {
                "ref": {"sub"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (
            0 if available else 2
        )  # An error for each undefined variable reference

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(
                {"name": "Foo", "sub": {"kind": "ONE", "field1": "{{Param.Foo}}"}}, id="not a list"
            ),
            pytest.param(
                {"name": "Foo", "sub": [{"kind": "THREE", "field1": "{{Param.Foo}}"}]},
                id="unknown key value",
            ),
            pytest.param(
                {"name": "Foo", "sub": [{"kind": 1, "field1": "{{Param.Foo}}"}]},
                id="incorrect key type int",
            ),
            pytest.param(
                {"name": "Foo", "sub": [{"kind": ["ONE"], "field1": "{{Param.Foo}}"}]},
                id="incorrect key type list",
            ),
            pytest.param(
                {"name": "Foo", "sub": [{"field1": "{{Param.Foo}}"}]}, id="discriminator missing"
            ),
            pytest.param({"name": "Foo", "sub": ["Not a dict"]}, id="value is not a dict"),
        ],
    )
    def test_list_bad_data(self, data: dict[str, Any]) -> None:
        # Test that if we have a field that is a list of discriminated union types then we
        # don't explode if the value's list doesn't have an expected shape/values.

        # GIVEN
        class Kind(str, Enum):
            ONE = "ONE"
            TWO = "TWO"

        class SubModel1(OpenJDModel):
            kind: Literal[Kind.ONE]
            field1: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE

        class SubModel2(OpenJDModel):
            kind: Literal[Kind.TWO]
            field2: FormatString
            _template_variable_scope = ResolutionScope.TEMPLATE

        class BaseModel(OpenJDModel):
            name: str
            sub: list[Annotated[Union[SubModel1, SubModel2], Field(..., discriminator="kind")]]
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0


class TestNonDiscriminatedUnion:
    """Test that if we have unions in the model that isn't a discriminated union then we handle them correctly.

    In the current models that we have, there are never variable *definitions* within these sorts of unions;
    there may be variable references.

    Furthermore, unions of model types are not currently present in the model so we do not handle/test that case.
    """

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_singleton_reference(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: Union[int, FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": "{{Param.Foo}}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": "Foo", "ref": ["{{Param.Foo}}"]}, id="list type"),
            pytest.param({"name": "Foo", "ref": True}, id="other scalar"),
        ],
    )
    def test_singleton_bad_data(self, data: dict[str, Any]) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: Union[int, FormatString]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": "Foo", "ref": "{{Param.Foo}}"}, id="singleton"),
            pytest.param({"name": "Foo", "ref": ["{{Param.Foo}}"]}, id="list of formatstring"),
            pytest.param(
                {"name": "Foo", "ref": ["{{Param.Foo}}", "{{Param.Foo}}"]}, id="multi-item list"
            ),
            pytest.param({"name": "Foo", "ref": ["{{Param.Foo}}", 12]}, id="mixed list"),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_singleton_nested_list_reference(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: Union[list[Union[int, FormatString]], FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": "{{Param.Foo}}"}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": "Foo", "ref": ["{{Param.Foo}}"]}, id="list of formatstring"),
            pytest.param(
                {"name": "Foo", "ref": ["{{Param.Foo}}", "{{Param.Foo}}"]}, id="multi-item list"
            ),
            pytest.param({"name": "Foo", "ref": ["{{Param.Foo}}", 12]}, id="mixed list"),
        ],
    )
    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_list_of_union_reference(
        self,
        def_scope: ResolutionScope,
        ref_scope: ResolutionScope,
        available: bool,
        data: dict[str, Any],
    ) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: list[Union[int, FormatString]]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": ["{{Param.Foo}}"]}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == (0 if available else 1)

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param({"name": "Foo", "ref": "{{Param.Foo}}"}, id="not a list"),
            pytest.param({"name": "Foo", "ref": [dict(), dict()]}, id="bad item type: dict"),
            pytest.param({"name": "Foo", "ref": [True, False]}, id="bad item type: scalar"),
        ],
    )
    def test_list_of_union_bad_data(self, data: dict[str, Any]) -> None:
        # Test that if we have a field that is a singleton discriminated union type then we
        # properly resolve and traverse in to the union.

        # GIVEN
        class BaseModel(OpenJDModel):
            name: str
            ref: list[Union[int, FormatString]]
            _template_variable_scope = ResolutionScope.TEMPLATE
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=ResolutionScope.TEMPLATE)},
                field="name",
            )

        data = {"name": "Foo", "ref": ["{{Param.Foo}}"]}

        # WHEN
        errors = prevalidate_model_template_variable_references(BaseModel, data)

        # THEN
        assert len(errors) == 0
