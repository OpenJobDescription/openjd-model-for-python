# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from contextlib import contextmanager
from typing import Annotated, Any, Union, Dict

from pydantic import ValidationError
from pydantic import TypeAdapter
from pydantic_core import InitErrorDetails

from .._symbol_table import SymbolTable
from .._format_strings import FormatString
from .._types import OpenJDModel

__all__ = ("instantiate_model", "resolve_whole_field_typed_list")


def _expr_value_is_list(result: Any) -> bool:
    """Whether an EXPR engine ``ExprValue`` result carries a list.

    The binding does not (yet) expose an ``is_list`` predicate, so the check
    inspects the value's EXPR type string. Kept in exactly one place so the
    interface-sniffing has a single seam to replace with a typed binding
    predicate later.
    """
    result_type = getattr(result, "type", None)
    return result_type is not None and str(result_type).startswith("list[")


def resolve_whole_field_typed_list(value: FormatString, symtab: SymbolTable) -> Any:
    """RFC 0006 typed whole-field resolution to a native list, or ``None``.

    When ``value`` is a single whole-field ``{{ ... }}`` expression (only
    whitespace outside the expression) that evaluates to a list, return the
    native Python list. Any other shape or result — multi-segment format
    strings, scalar results, or evaluation errors — returns ``None`` so the
    caller falls back to ordinary string resolution, mirroring the
    typed-then-string fallback in openjd-rs's range instantiation. An
    evaluation error is deliberately not raised here: the string-resolution
    fallback re-evaluates and surfaces it with full format-string context.
    """
    info = value.whole_field_expression()
    if info is None:
        return None
    expression = info.expression
    if expression is None:  # pragma: no cover - excluded by whole_field_expression
        return None
    try:
        result = expression.evaluate_value(symtab=symtab)
    except ValueError:
        # ExpressionError/FormatStringError (both ValueError subclasses):
        # fall back to string resolution, which re-raises with context.
        return None
    # EXPR-backed evaluation returns the engine's ExprValue. List results are
    # returned RAW (not unwrapped) so the element type variants survive to the
    # coercion hook (JobCreationMetadata.typed_resolve_coerce) — unwrapping
    # via .item() erases them (a bool becomes int 1/0), which is how typed
    # ranges diverged from openjd-rs's per-variant checks (ranges.rs).
    if _expr_value_is_list(result):
        return result
    if isinstance(result, list):
        return result
    return None


def unwrap_typed_resolution(raw: Any) -> Any:
    """Unwrap a typed whole-field resolution result to native Python: the
    engine's list ``ExprValue`` becomes a plain list; native results pass
    through. Used when a model defines no ``typed_resolve_coerce`` hook."""
    if _expr_value_is_list(raw):
        return raw.item()
    return raw


def _compute_typed_resolutions(model: "OpenJDModel", symtab: SymbolTable) -> dict[str, Any]:
    """RFC 0006 typed whole-field resolutions for the model's
    ``typed_resolve_fields``, computed exactly once per field.

    The result feeds both the ``create_as`` target-model decision and the
    field instantiation in :func:`instantiate_model`, so the (Rust-boundary)
    expression evaluation is not repeated and the two consumers cannot
    disagree. Fields whose typed resolution does not apply are absent from
    the mapping (the caller falls back to normal string resolution).
    """
    typed_resolved: dict[str, Any] = {}
    for field_name in model._job_creation_metadata.typed_resolve_fields:
        field_value = getattr(model, field_name, None)
        if isinstance(field_value, FormatString):
            typed_value = resolve_whole_field_typed_list(field_value, symtab)
            if typed_value is not None:
                typed_resolved[field_name] = typed_value
    return typed_resolved


# Cache for TypeAdapter instances
_type_adapter_cache: Dict[int, TypeAdapter] = {}


def get_type_adapter(field_type: Any) -> TypeAdapter:
    """Get a TypeAdapter for the given field type, using a cache for efficiency.
    Assumes field_type refers to shared type definitions from the model so two field_types
    referring to the same underlying model type will have the same id and share an adapter.

    Args:
        field_type: The type to adapt.

    Returns:
        A TypeAdapter for the given type.
    """
    # Use id as cache key
    type_key = id(field_type)
    if type_key not in _type_adapter_cache:
        _type_adapter_cache[type_key] = TypeAdapter(field_type)
    return _type_adapter_cache[type_key]


@contextmanager
def capture_validation_errors(
    *, output_errors: list[InitErrorDetails], loc: tuple[Union[str, int], ...], input: Any
):
    """Context manager to collect validation errors from pydantic into a list.

    Args:
        output_error_list (list[InitErrorDetails]): The list to collect errors into.
        loc (tuple): The location of the input value being validated.
        input (Any): The input value being validated.
    """
    try:
        yield
    except ValidationError as exc:
        # Convert the ErrorDetails to InitErrorDetails by extending the 'loc' and excluding the 'msg'
        for error_details in exc.errors():
            init_error_details: dict[str, Any] = {}
            for err_key, err_value in error_details.items():
                if err_key == "loc":
                    init_error_details["loc"] = (*loc, *err_value)  # type: ignore
                elif err_key != "msg":
                    init_error_details[err_key] = err_value
            output_errors.append(init_error_details)  # type: ignore
    except ValueError as exc:
        output_errors.append(
            InitErrorDetails(
                type="value_error",
                loc=loc,
                ctx={"error": exc},
                input=input,
            )
        )


def instantiate_model(  # noqa: C901
    model: OpenJDModel,
    symtab: SymbolTable,
) -> OpenJDModel:
    """This function is for instantiating a Template model into a Job model.

    It does a depth-first traversal through the model, mutating each stage according
    to the instructions given in the model's create-job metadata.

    Args:
        model (OpenJDModel): The model instance to transform.
        symtab (SymbolTable): The symbol table containing fully qualified Job parameter values
            used during the instantiation.

    Raises:
        ValidationError - If there are any validation errors from the target models.

    Returns:
        OpenJDModel: The transformed model.
    """
    errors = list[InitErrorDetails]()
    instantiated_fields = dict[str, Any]()

    # Extend the symbol table for this model's subtree if defined (e.g. a
    # step's Step.Name and step-level EXPR `let` bindings). This runs before
    # the transform, so the hook always sees the model as authored, and that
    # ordering is load-bearing for two reasons.
    #
    # A transform may rebuild the model rather than adjust it -- StepTemplate's
    # syntax-sugar transform returns a `model_construct`ed copy -- so the fields
    # the hook reads (a step's `name` and its `let`) are only guaranteed to be
    # the authored ones on this side of it. The current transform carries `let`
    # through deliberately; running the hook first is what keeps that the
    # transform's choice rather than a requirement on every future one.
    #
    # And create_job_with_symbol_tables invokes the same hook on the same
    # untransformed StepTemplate to build the step symbol table it publishes for
    # the runtime to seed a session with. That table is only the scope the
    # step's own fields (script, parameter space, host requirements) were
    # instantiated against if both callers hand the hook the same model.
    if model._job_creation_metadata.extends_symtab is not None:
        symtab = model._job_creation_metadata.extends_symtab(model, symtab)

    # Apply pre-transform if defined
    if model._job_creation_metadata.transform is not None:
        model = model._job_creation_metadata.transform(model)

    typed_resolved = _compute_typed_resolutions(model, symtab)

    # Determine the target model to create as
    target_model = model.__class__
    if model._job_creation_metadata.create_as is not None:
        create_as_metadata = model._job_creation_metadata.create_as
        if create_as_metadata.model is not None:
            target_model = create_as_metadata.model
        elif create_as_metadata.callable is not None:
            target_model = create_as_metadata.callable(model, typed_resolved)

    for field_name in model.__class__.model_fields.keys():
        if field_name in model._job_creation_metadata.exclude_fields:
            # The field is marked for being excluded
            continue
        target_field_name = model._job_creation_metadata.rename_fields.get(field_name, field_name)
        target_field_type: Any = target_model.model_fields[target_field_name].annotation
        for metadata in target_model.model_fields[target_field_name].metadata:
            target_field_type = Annotated[target_field_type, metadata]

        if not hasattr(model, field_name):
            # Field has no value. Set to None and move on.
            instantiated_fields[target_field_name] = None
            continue

        field_value = getattr(model, field_name)
        instantiated: Any = None
        with capture_validation_errors(output_errors=errors, loc=(field_name,), input=field_value):
            # Instantiate and resolve format string expressions
            needs_resolve = field_name in model._job_creation_metadata.resolve_fields
            if field_name in typed_resolved:
                # RFC 0006 typed whole-field resolution (computed above). The
                # model's coercion hook (when set) enforces element/target
                # type agreement on the engine's typed elements — errors
                # raised here aggregate into the model's validation errors.
                raw_typed = typed_resolved[field_name]
                coerce = model._job_creation_metadata.typed_resolve_coerce
                if coerce is not None:
                    instantiated = coerce(model, field_name, raw_typed)
                else:
                    instantiated = unwrap_typed_resolution(raw_typed)
            elif isinstance(field_value, list):
                if field_name in model._job_creation_metadata.reshape_field_to_dict:
                    key_field = model._job_creation_metadata.reshape_field_to_dict[field_name]
                    instantiated = _instantiate_list_field_as_dict(
                        field_value, symtab, needs_resolve, key_field
                    )
                else:
                    instantiated = _instantiate_list_field_as_list(
                        field_value, symtab, needs_resolve
                    )
            elif isinstance(field_value, dict):
                instantiated = _instantiate_dict_field(field_value, symtab, needs_resolve)
            else:
                instantiated = _instantiate_noncollection_value(field_value, symtab, needs_resolve)

            # Validate as the target field type using cached TypeAdapter
            type_adapter = get_type_adapter(target_field_type)
            instantiated = type_adapter.validate_python(instantiated)
            instantiated_fields[target_field_name] = instantiated

    if not errors:
        if model._job_creation_metadata.adds_fields is not None:
            new_fields = model._job_creation_metadata.adds_fields(model, symtab)
            instantiated_fields.update(**new_fields)

        with capture_validation_errors(output_errors=errors, loc=(), input=field_value):
            result = target_model(**instantiated_fields)

    if errors:
        raise ValidationError.from_exception_data(
            title=model.__class__.__name__, line_errors=errors
        )

    return result


def _instantiate_noncollection_value(
    value: Any,
    symtab: SymbolTable,
    needs_resolve: bool,
) -> Any:
    """Instantiate a single value that must not be a collection type (list, dict, etc).

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.

    Note: fields named in ``typed_resolve_fields`` whose RFC 0006 typed
    whole-field resolution succeeded never reach this function —
    ``instantiate_model`` resolves them once up front.
    """
    if isinstance(value, OpenJDModel):
        return instantiate_model(value, symtab)
    elif isinstance(value, FormatString) and needs_resolve:
        value = value.resolve(symtab=symtab)

    return value


def _instantiate_list_field_as_list(  # noqa: C901
    value: list[Any],
    symtab: SymbolTable,
    needs_resolve: bool,
) -> list[Any]:
    """As _instantiate_noncollection_value, but where the value is a list.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
    """
    errors: list[InitErrorDetails] = []
    result: list[Any] = []
    for idx, item in enumerate(value):
        with capture_validation_errors(output_errors=errors, loc=(idx,), input=value):
            # Raises: ValidationError, FormatStringError
            result.append(
                _instantiate_noncollection_value(
                    item,
                    symtab,
                    needs_resolve,
                )
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_list_field_as_list", line_errors=errors
        )

    return result


def _instantiate_list_field_as_dict(  # noqa: C901
    value: list[Any], symtab: SymbolTable, needs_resolve: bool, key_field: str
) -> dict[str, Any]:
    """As _instantiate_noncollection_value, but where the value is a list.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
        key_field (str): The name of the key in each object that defines the output dictionary key.
    """
    errors: list[InitErrorDetails] = []
    result: dict[str, Any] = {}
    for idx, item in enumerate(value):
        key = getattr(item, key_field)
        with capture_validation_errors(output_errors=errors, loc=(idx,), input=value):
            result[key] = _instantiate_noncollection_value(
                item,
                symtab,
                needs_resolve,
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_list_field_as_dict", line_errors=errors
        )

    return result


def _instantiate_dict_field(
    value: dict[str, Any],
    symtab: SymbolTable,
    needs_resolve: bool,
) -> dict[str, Any]:
    """As _instantiate_noncollection_value, but where the value is a dict.

    Arguments:
        within_model (OpenJDModel): The model within which the value is located.
        value (Any): Value to process.
        symtab (SymbolTable): Symbol table for format string value lookups.
        needs_resolve (bool): Whether to resolve the value as a format string.
    """
    errors: list[InitErrorDetails] = []
    result: dict[str, Any] = {}
    for key, item in value.items():
        with capture_validation_errors(output_errors=errors, loc=(key,), input=value):
            result[key] = _instantiate_noncollection_value(
                item,
                symtab,
                needs_resolve,
            )

    if errors:
        raise ValidationError.from_exception_data(
            title="_instantiate_dict_field", line_errors=errors
        )

    return result
