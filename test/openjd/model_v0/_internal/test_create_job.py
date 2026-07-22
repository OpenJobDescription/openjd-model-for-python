# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Union, cast

import pytest
from pydantic import PositiveInt, ValidationError

from openjd.model import SymbolTable
from openjd.model._format_strings import FormatString
from openjd.model import SpecificationRevision
from openjd.model._internal._create_job import (
    instantiate_model,
    get_type_adapter,
    _type_adapter_cache,
)
from openjd.model._types import (
    JobCreateAsMetadata,
    JobCreationMetadata,
    OpenJDModel,
)
from openjd.model.v2023_09 import ModelParsingContext as ModelParsingContext_v2023_09


class TestGetTypeAdapter:
    """Tests for the get_type_adapter function."""

    def setup_method(self):
        """Clear the type adapter cache before each test."""
        _type_adapter_cache.clear()

    def test_get_type_adapter_caching(self):
        """Test that get_type_adapter caches TypeAdapters for repeated calls with the same type."""
        # First call should create a new TypeAdapter
        str_type = str
        str_type_id = id(str_type)
        adapter1 = get_type_adapter(str_type)

        # Second call should return the cached TypeAdapter
        adapter2 = get_type_adapter(str_type)

        # The adapters should be the same object (not just equal)
        assert adapter1 is adapter2

        # The cache should contain the entry
        assert str_type_id in _type_adapter_cache

        # Different types should get different adapters
        int_type = int
        adapter_int = get_type_adapter(int_type)
        assert adapter_int is not adapter1
        assert id(int_type) in _type_adapter_cache


class BaseModelForTesting(OpenJDModel):
    # Specific version doesn't matter for these tests
    revision = SpecificationRevision.UNDEFINED


class TestInternalCreateJobNoMetadata:
    """Tests of the internal create-job instantiation with models
    that do not have any create-job metadata.
    This tests our basic construction and case handling for most of
    the model entities that the traversal will see.
    """

    def test_model_of_scalars(self) -> None:
        # Test of a single model of scalars. There is no recursion involved in the
        # traversal of this.

        # GIVEN
        class Model(BaseModelForTesting):
            a: int
            b: str
            c: Decimal

        model = Model(a=1, b="two", c="3.5")
        symtab = SymbolTable()

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == model
        assert result is not model

    def test_model_with_optional(self) -> None:
        # Test of a model that contains optional fields where we don't have a value
        # for one of them

        # GIVEN
        class Model(BaseModelForTesting):
            a: Optional[int] = None
            b: Optional[str] = None
            c: Decimal

        model = Model(a=1, c="3.5")
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert model.b is None
        assert result == model
        assert result is not model

    def test_recursion(self) -> None:
        # Test of basic recursion with no collection field types.

        # GIVEN
        class InnerModel(BaseModelForTesting):
            a: int
            b: str

        class Model(BaseModelForTesting):
            inner: InnerModel
            c: str

        inner_model = InnerModel(a=1, b="two")
        model = Model(c="see", inner=inner_model)
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert result == model
        assert result.inner is not inner_model

    def test_model_has_list_non_models(self) -> None:
        # Test that we properly instantiate a model that contains lists of non-models.

        # GIVEN
        @dataclass(frozen=True)
        class NonModelType:
            f: str

        class Model(BaseModelForTesting):
            i: list[int]
            i2: list[NonModelType]

        model = Model(i=[1, 2, 3], i2=[NonModelType("one"), NonModelType("two")])
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert result == model
        assert result.i is not model.i
        assert result.i2 is not model.i2
        assert all(model.i[i] is result.i[i] for i in range(0, len(model.i)))
        assert all(model.i2[i] is result.i2[i] for i in range(0, len(model.i2)))

    def test_model_has_list_of_models(self) -> None:
        # Test that we properly instantiate a model that contains a list of other models.

        # GIVEN
        class Inner(BaseModelForTesting):
            f: str

        class Model(BaseModelForTesting):
            ii: list[Inner]

        model = Model(ii=[{"f": "one"}, {"f": "two"}])
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert result == model
        assert all(result.ii[i] is not model.ii[i] for i in range(0, len(model.ii)))

    def test_model_has_dict_of_nonmodels(self) -> None:
        # Test that we properly instantiate a model that contains a dict whose values are not models.

        # GIVEN
        @dataclass(frozen=True)
        class NonModelType:
            f: str

        class Model(BaseModelForTesting):
            d1: dict[str, int]
            d2: dict[str, NonModelType]

        model = Model(
            d1={"k1": 1, "k2": 2},
            d2={
                "kk1": NonModelType("one"),
                "kk2": NonModelType("two"),
            },
        )
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert result == model
        assert all(result.d1[k] is model.d1[k] for k in model.d1)
        assert all(result.d2[k] is model.d2[k] for k in model.d2)

    def test_model_has_dict_of_models(self) -> None:
        # Test that we properly instantiate a model that contains a dict whose values are models.

        # GIVEN
        class Inner(BaseModelForTesting):
            f: str

        class Model(BaseModelForTesting):
            d1: dict[str, Inner]

        model = Model(
            d1={"k1": {"f": "one"}, "k2": {"f": "two"}},
        )
        symtab = SymbolTable()

        # WHEN
        result = cast(Model, instantiate_model(model, symtab))

        # THEN
        assert result == model
        assert all(result.d1[k] is not model.d1[k] for k in model.d1)


class TestInternalCreateJobResolvesFormatStrings:
    """Tests that JobCreationMetadata.resolve_fields is respected.
    We support resolving fields that are:
     1. FormatStrings
     2. lists of FormatStrings
     3. lists of a mix of FormatStrings and non-FormatStrings (e.g. ints,floats,regular-strings,etc)
    """

    def test_as_field(self) -> None:
        # Test that we resolve the desired format strings when they are the value of a field.

        # GIVEN
        f1 = FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09())
        f2 = FormatString("{{ Param.V2 }}", context=ModelParsingContext_v2023_09())

        class ResolvedModel(BaseModelForTesting):
            f1: str
            f2: str

        class Model(BaseModelForTesting):
            f1: FormatString
            f2: FormatString

            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=ResolvedModel), resolve_fields={"f1"}
            )

        model = Model(f1=f1, f2=f2)
        symtab = SymbolTable(source={"Param.V": "ValueOfV"})
        expected = ResolvedModel(f1="ValueOfV", f2=f2)

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected

    def test_within_list(self) -> None:
        # Test that we resolve the desired format strings when they are located within a list field.

        # GIVEN
        f1 = FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09())
        f2 = FormatString("{{ Param.V2 }}", context=ModelParsingContext_v2023_09())

        class TargetModel(BaseModelForTesting):
            f1: list[str]
            f2: FormatString

        class Model(BaseModelForTesting):
            f1: list[FormatString]
            f2: FormatString

            _job_creation_metadata = JobCreationMetadata(
                resolve_fields={"f1"}, create_as=JobCreateAsMetadata(model=TargetModel)
            )

        model = Model(f1=[f1, f1, f1], f2=f2)
        symtab = SymbolTable(source={"Param.V": "ValueOfV"})
        expected = TargetModel(f1=["ValueOfV", "ValueOfV", "ValueOfV"], f2=f2)

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected

    def test_within_mixed_list(self) -> None:
        # Test that we resolve the desired format strings when they are located within a list field,
        # amongst other values that are not format strings.

        # GIVEN
        f1 = FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09())
        f2 = FormatString("{{ Param.V2 }}", context=ModelParsingContext_v2023_09())

        class TargetModel(BaseModelForTesting):
            f1: list[Union[int, str]]
            f2: FormatString

        class Model(BaseModelForTesting):
            f1: list[Union[int, FormatString]]
            f2: FormatString

            _job_creation_metadata = JobCreationMetadata(
                resolve_fields={"f1"}, create_as=JobCreateAsMetadata(model=TargetModel)
            )

        model = Model(f1=[f1, 12], f2=f2)
        symtab = SymbolTable(source={"Param.V": "ValueOfV"})
        expected = TargetModel(f1=["ValueOfV", 12], f2=f2)

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobCreateAs:
    """Tests that a model will instantiate as a given model class rather than the model's class."""

    def test_given_model(self) -> None:
        # Test that we use a given specific model class when provided.

        # GIVEN
        class TargetModel(BaseModelForTesting):
            f: str

        class Model(BaseModelForTesting):
            f: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel)
            )

        model = Model(f="some string")
        symtab = SymbolTable()
        expected = TargetModel(f="some string")

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected

    def test_given_callable(self) -> None:
        # Test that we derive the model class to use from a callable when it's given.

        # GIVEN
        class TargetModel(BaseModelForTesting):
            f: str

        class Model(BaseModelForTesting):
            f: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(callable=lambda m, symtab: TargetModel)
            )

        model = Model(f="some string")
        symtab = SymbolTable()
        expected = TargetModel(f="some string")

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobExcludeField:
    """Test that the given excluded fields are respected when instantiating a model."""

    def test(self) -> None:
        # GIVEN
        class TargetModel(BaseModelForTesting):
            f: str

        class Model(BaseModelForTesting):
            f: str
            e: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel), exclude_fields={"e"}
            )

        model = Model(f="one", e="ignore")
        symtab = SymbolTable()
        expected = TargetModel(f="one")

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobAddsFields:
    """Test that we use a provided callable to materialize new fields & their values."""

    def test(self) -> None:
        # GIVEN
        class TargetModel(BaseModelForTesting):
            name: str
            type: str
            n1: str

        class Model(BaseModelForTesting):
            name: str
            type: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel),
                adds_fields=lambda model, symtab: {
                    "n1": symtab[f"Param.{cast(Model, model).name}"],
                },
            )

        model = Model(name="Foo", type="INT")
        symtab = SymbolTable(source={"Param.Foo": "FooValue"})
        expected = TargetModel(name="Foo", type="INT", n1="FooValue")

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobReshapes:
    """Test that we reshape list fields into a dict when requested."""

    def test(self) -> None:
        # GIVEN
        class InnerModelTarget(BaseModelForTesting):
            f: str

        class TargetModel(BaseModelForTesting):
            inner: dict[str, InnerModelTarget]

        class InnerModel(BaseModelForTesting):
            name: str
            f: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=InnerModelTarget), exclude_fields={"name"}
            )

        class Model(BaseModelForTesting):
            inner: list[InnerModel]
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel),
                reshape_field_to_dict={"inner": "name"},
            )

        inner1 = InnerModel(name="foo", f="foo-value")
        inner2 = InnerModel(name="bar", f="bar-value")
        model = Model(inner=[inner1, inner2])
        symtab = SymbolTable()
        expected_inner1 = InnerModelTarget(f="foo-value")
        expected_inner2 = InnerModelTarget(f="bar-value")
        expected = TargetModel(inner={"foo": expected_inner1, "bar": expected_inner2})

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobRenames:
    """Test that we rename fields when requested."""

    def test(self) -> None:
        # GIVEN
        class TargetModel(BaseModelForTesting):
            renamed: str

        class Model(BaseModelForTesting):
            named: str
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel), rename_fields={"named": "renamed"}
            )

        model = Model(named="foo")
        symtab = SymbolTable()
        expected = TargetModel(renamed="foo")

        # WHEN
        result = instantiate_model(model, symtab)

        # THEN
        assert result == expected


class TestInternalCreateJobExceptions:
    """Testing that exceptions are raised & captured properly when instantiating a model.
    The strategy with these tests is that we'll create a model that translates into a different
    model class when instantiated. The model data will be such that it doesn't pass validation
    in the target model, and this will raise an exception when the target model is constructed.
    """

    def test_simple(self) -> None:
        # Simple test. No recursion. No collections.

        # GIVEN
        class TargetModel(BaseModelForTesting):
            vv: PositiveInt
            ff: FormatString

        class Model(BaseModelForTesting):
            vv: int
            ff: FormatString
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel), resolve_fields={"ff"}
            )

        model = Model(
            vv=-10, ff=FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09())
        )
        symtab = SymbolTable(
            source={"Param.V": "{{ Foo.Bar"}  # a bad format string to fire an exception
        )

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            instantiate_model(model, symtab)
        exc = excinfo.value
        errors = exc.errors()

        # THEN
        assert len(errors) == 2
        locs = [err["loc"] for err in errors]
        assert ("vv",) in locs
        assert ("ff",) in locs

    def test_nested(self) -> None:
        # Testing exceptions from models nested within a model

        # GIVEN
        class TargetInner(BaseModelForTesting):
            vv: PositiveInt
            ff: FormatString

        class TargetModel(BaseModelForTesting):
            ii: TargetInner

        class InnerModel(BaseModelForTesting):
            vv: int
            ff: FormatString
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetInner), resolve_fields={"ff"}
            )

        class Model(BaseModelForTesting):
            ii: InnerModel
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel)
            )

        model = Model(
            ii={
                "vv": -10,
                "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
            }
        )
        symtab = SymbolTable(
            source={"Param.V": "{{ Foo.Bar"}  # a bad format string to fire an exception
        )

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            instantiate_model(model, symtab)
        exc = excinfo.value
        errors = exc.errors()

        # THEN
        assert len(errors) == 2
        locs = [err["loc"] for err in errors]
        assert ("ii", "vv") in locs
        assert ("ii", "ff") in locs

    def test_within_list(self) -> None:
        # Test that the errors within list elements are correctly captured

        # GIVEN
        class TargetInner(BaseModelForTesting):
            vv: PositiveInt
            ff: FormatString

        class InnerModel(BaseModelForTesting):
            vv: int
            ff: FormatString
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetInner), resolve_fields={"ff"}
            )

        class Model(BaseModelForTesting):
            ii: list[InnerModel]

        model = Model(
            ii=[
                {
                    "vv": -10,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
                {
                    "vv": -5,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
            ]
        )
        symtab = SymbolTable(
            source={"Param.V": "{{ Foo.Bar"}  # a bad format string to fire an exception
        )

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            instantiate_model(model, symtab)
        exc = excinfo.value
        errors = exc.errors()

        # THEN
        assert len(errors) == 4
        locs = [err["loc"] for err in errors]
        assert ("ii", 0, "vv") in locs
        assert ("ii", 0, "ff") in locs
        assert ("ii", 1, "vv") in locs
        assert ("ii", 1, "ff") in locs

    def test_within_reshape_list(self) -> None:
        # Test that the errors within list elements are correctly captured when that list is being
        # reshaped into a dict.

        # GIVEN
        class TargetInner(BaseModelForTesting):
            vv: PositiveInt
            ff: int

        class TargetModel(BaseModelForTesting):
            ii: dict[str, TargetInner]

        class InnerModel(BaseModelForTesting):
            name: str
            vv: int
            ff: FormatString
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetInner),
                exclude_fields={"name"},
                resolve_fields={"ff"},
            )

        class Model(BaseModelForTesting):
            ii: list[InnerModel]
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetModel),
                reshape_field_to_dict={"inner": "name"},
            )

        model = Model(
            ii=[
                {
                    "name": "foo",
                    "vv": -10,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
                {
                    "name": "bar",
                    "vv": -5,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
            ]
        )
        symtab = SymbolTable(
            source={"Param.V": "not an integer"}  # a bad format string to fire an exception
        )

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            instantiate_model(model, symtab)
        exc = excinfo.value
        errors = exc.errors()

        # THEN
        assert len(errors) == 4
        locs = [err["loc"] for err in errors]
        assert ("ii", 0, "vv") in locs
        assert ("ii", 0, "ff") in locs
        assert ("ii", 1, "vv") in locs
        assert ("ii", 1, "ff") in locs

    def test_within_dict(self) -> None:
        # Test that the errors within dictionary elements are correctly captured

        # GIVEN
        class TargetInner(BaseModelForTesting):
            vv: PositiveInt
            ff: int

        class InnerModel(BaseModelForTesting):
            vv: int
            ff: FormatString
            _job_creation_metadata = JobCreationMetadata(
                create_as=JobCreateAsMetadata(model=TargetInner),
                resolve_fields={"ff"},
            )

        class Model(BaseModelForTesting):
            dd: dict[str, InnerModel]

        model = Model(
            dd={
                "foo": {
                    "vv": -10,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
                "bar": {
                    "vv": -5,
                    "ff": FormatString("{{ Param.V }}", context=ModelParsingContext_v2023_09()),
                },
            }
        )
        symtab = SymbolTable(
            source={"Param.V": "not an integer"}  # a non-integer to fire an exception
        )

        # WHEN
        with pytest.raises(ValidationError) as excinfo:
            instantiate_model(model, symtab)
        exc = excinfo.value
        errors = exc.errors()

        # THEN
        assert len(errors) == 4, str(exc)
        locs = [err["loc"] for err in errors]
        assert ("dd", "foo", "vv") in locs
        assert ("dd", "foo", "ff") in locs
        assert ("dd", "bar", "vv") in locs
        assert ("dd", "bar", "ff") in locs
