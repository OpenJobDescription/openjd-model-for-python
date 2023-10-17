# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import cast, Dict, List

import pytest

from openjd.model._format_strings import FormatString
from openjd.model import parse_model
from openjd.model._internal import validate_model_template_variable_references
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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

        # THEN
        assert len(errors) == (0 if available else 1)


def test_non_export_not_available() -> None:
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
    model = parse_model(model=BaseModel, obj=data)

    # WHEN
    errors = validate_model_template_variable_references(
        cast(OpenJDModel, type(model)), dict(model._iter())
    )

    # THEN
    assert len(errors) == 1


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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
            sub: List[SubModel]

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
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
            ref: List[FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {"name": "Foo", "ref": ["{{ Param.Foo }}", "{{ Param.Foo }}", "{{ Param.Foo }}"]}
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

        # THEN
        assert len(errors) == (0 if available else 3)


class TestDictField:
    """Test that if we have a field that's a dict that we check its elements correctly."""

    @pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
    def test_available_in_model(
        self, def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
    ) -> None:
        # Test that if we have a field that's a dict of submodels that the variable is available in the
        # appropriate scopes in that submodel.

        # GIVEN
        class SubModel(OpenJDModel):
            field: FormatString
            _template_variable_scope = ref_scope

        class BaseModel(OpenJDModel):
            name: str
            sub: Dict[str, SubModel]

            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )
            _template_variable_sources = {
                "sub": {"__self__"},
            }

        data = {
            "name": "Foo",
            "sub": {
                "a": {"field": "{{ Param.Foo }}"},
                "b": {"field": "{{ Param.Foo }}"},
                "c": {"field": "{{ Param.Foo }}"},
            },
        }
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

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
            ref: Dict[str, FormatString]
            _template_variable_scope = ref_scope
            _template_variable_sources = {"ref": {"__self__"}}
            _template_variable_definitions = DefinesTemplateVariables(
                defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
                field="name",
            )

        data = {
            "name": "Foo",
            "ref": {"a": "{{ Param.Foo }}", "b": "{{ Param.Foo }}", "c": "{{ Param.Foo }}"},
        }
        model = parse_model(model=BaseModel, obj=data)

        # WHEN
        errors = validate_model_template_variable_references(
            cast(OpenJDModel, type(model)), dict(model._iter())
        )

        # THEN
        assert len(errors) == (0 if available else 3)


@pytest.mark.parametrize("def_scope, ref_scope, available", SCOPE_AVAILABILITY)
def test_dict_key_as_name(
    def_scope: ResolutionScope, ref_scope: ResolutionScope, available: bool
) -> None:
    # Test that a dictionary key can be correctly used as a symbol name available in the appropriate scopes.

    # GIVEN
    class SubModel(OpenJDModel):
        value: str
        _template_variable_definitions = DefinesTemplateVariables(
            defines={TemplateVariableDef(prefix="|Param.", resolves=def_scope)},
            field="__key__",
        )
        _template_variable_sources = {"__export__": {"__self__"}}

    class BaseModel(OpenJDModel):
        ref: FormatString
        sub: Dict[str, SubModel]

        _template_variable_scope = ref_scope
        _template_variable_sources = {
            "ref": {"sub"},
        }

    data = {
        "ref": "{{ Param.Foo }} {{ Param.Bar }}",
        "sub": {
            "Foo": {"value": "v1"},
            "Bar": {"value": "v2"},
        },
    }
    model = parse_model(model=BaseModel, obj=data)

    # WHEN
    errors = validate_model_template_variable_references(
        cast(OpenJDModel, type(model)), dict(model._iter())
    )

    # THEN
    assert len(errors) == (0 if available else 2)
