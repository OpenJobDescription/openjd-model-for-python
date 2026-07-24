# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Regression tests: Jobs carrying deferred (run-time-resolved) FormatStrings
must be picklable and copyable.

FormatString.__new__ requires a keyword-only parsing context, but
str.__getnewargs__ supplies only the string value, so pickle.loads,
copy.copy/deepcopy, and model_copy(deep=True) raised TypeError — and
subclasses that default the context (e.g. ArgString) silently re-parsed
EXPR-grammar strings with the legacy parser (or failed pickling on the
engine-backed parse tree). FormatString now records a parse-context snapshot
and reconstructs through __getnewargs_ex__, re-parsing under the same grammar
(see FormatString.__getstate__/__getnewargs_ex__).
"""

import copy
import pickle

from openjd.model import SymbolTable, create_job, decode_job_template
from openjd.model._format_strings import FormatString
from openjd.model._types import ParameterValue, ParameterValueType
from openjd.model.v2023_09 import ArgString, ModelParsingContext


def _job_with_deferred_fields(extensions: list[str], *, timeout: str):
    """An instantiated Job whose onRun action carries a deferred (unresolved)
    FormatString timeout and a deferred cancelation (mode + notifyPeriod)."""
    template = decode_job_template(
        template={
            "specificationVersion": "jobtemplate-2023-09",
            "extensions": list(extensions),
            "name": "PickleTest",
            "parameterDefinitions": [
                {"name": "TO", "type": "INT", "default": 30},
                {"name": "Mode", "type": "STRING", "default": "TERMINATE"},
            ],
            "steps": [
                {
                    "name": "Step1",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "echo",
                                "timeout": timeout,
                                "cancelation": {
                                    "mode": "{{Param.Mode}}",
                                    "notifyPeriodInSeconds": "{{Param.TO}}",
                                },
                            }
                        }
                    },
                }
            ],
        },
        supported_extensions=extensions,
    )
    return create_job(
        job_template=template,
        job_parameter_values={
            "TO": ParameterValue(type=ParameterValueType.INT, value="30"),
            "Mode": ParameterValue(type=ParameterValueType.STRING, value="TERMINATE"),
        },
    )


def _deferred_symtab() -> SymbolTable:
    symtab = SymbolTable()
    symtab["Param.TO"] = 30
    symtab["Param.Mode"] = "TERMINATE"
    return symtab


def _assert_deferred_fields_equivalent(original, reconstructed) -> None:
    """The reconstructed action's deferred FormatStrings must be FormatStrings
    that evaluate identically to the originals against the same symtab."""
    symtab = _deferred_symtab()
    for attr_path in ("timeout", "cancelation.mode", "cancelation.notifyPeriodInSeconds"):
        orig_value = original
        recon_value = reconstructed
        for part in attr_path.split("."):
            orig_value = getattr(orig_value, part)
            recon_value = getattr(recon_value, part)
        assert isinstance(recon_value, FormatString), attr_path
        assert type(recon_value) is type(orig_value), attr_path
        assert str(recon_value) == str(orig_value), attr_path
        assert recon_value.resolve(symtab=symtab) == orig_value.resolve(symtab=symtab), attr_path


class TestJobPickleRoundTrip:
    def test_expr_job_pickle_round_trip(self) -> None:
        # GIVEN an EXPR + FEATURE_BUNDLE_1 job with deferred timeout and
        # cancelation, where the timeout uses EXPR-only arithmetic (the
        # legacy grammar cannot parse it — a reconstruction under a default
        # context would fail or change semantics).
        job = _job_with_deferred_fields(["EXPR", "FEATURE_BUNDLE_1"], timeout="{{ Param.TO * 2 }}")

        # WHEN
        reconstructed = pickle.loads(pickle.dumps(job))

        # THEN
        original_action = job.steps[0].script.actions.onRun
        recon_action = reconstructed.steps[0].script.actions.onRun
        _assert_deferred_fields_equivalent(original_action, recon_action)
        symtab = _deferred_symtab()
        assert recon_action.timeout.resolve(symtab=symtab) == "60"

    def test_legacy_fb1_job_pickle_round_trip(self) -> None:
        # GIVEN a legacy (non-EXPR) FEATURE_BUNDLE_1 job with a deferred
        # FormatString timeout.
        job = _job_with_deferred_fields(["FEATURE_BUNDLE_1"], timeout="{{Param.TO}}")

        # WHEN
        reconstructed = pickle.loads(pickle.dumps(job))

        # THEN
        original_action = job.steps[0].script.actions.onRun
        recon_action = reconstructed.steps[0].script.actions.onRun
        _assert_deferred_fields_equivalent(original_action, recon_action)
        symtab = _deferred_symtab()
        assert recon_action.timeout.resolve(symtab=symtab) == "30"

    def test_expr_job_deepcopy_and_model_copy(self) -> None:
        # GIVEN
        job = _job_with_deferred_fields(["EXPR", "FEATURE_BUNDLE_1"], timeout="{{ Param.TO * 2 }}")
        original_action = job.steps[0].script.actions.onRun

        # WHEN / THEN: both deep-copy paths reconstruct working FormatStrings.
        for job_copy in (copy.deepcopy(job), job.model_copy(deep=True)):
            copied_action = job_copy.steps[0].script.actions.onRun
            _assert_deferred_fields_equivalent(original_action, copied_action)


class TestFormatStringPickleFaithfulness:
    """The reconstruction context must reproduce the original parse mode:
    re-parsing an EXPR-grammar string under a default (legacy) context would
    reject it outright or silently change its evaluation semantics."""

    def test_expr_arg_string_typed_round_trip(self) -> None:
        # GIVEN an ArgString whose whole-field EXPR list expression only
        # parses under the EXPR grammar.
        context = ModelParsingContext(supported_extensions=["EXPR", "FEATURE_BUNDLE_1"])
        original = ArgString('{{ ["a","b c"] }}', context=context)

        # WHEN
        reconstructed = pickle.loads(pickle.dumps(original))

        # THEN: still an EXPR whole-field expression with identical typed
        # (RFC 0005) evaluation, not a legacy re-parse.
        assert type(reconstructed) is ArgString
        assert reconstructed.whole_field_expression() is not None
        symtab = SymbolTable()
        original_value = original.resolve_value(symtab=symtab)
        reconstructed_value = reconstructed.resolve_value(symtab=symtab)
        assert type(reconstructed_value) is type(original_value)
        assert str(reconstructed_value) == str(original_value)
        assert reconstructed.resolve(symtab=symtab) == original.resolve(symtab=symtab)

    def test_legacy_format_string_copy(self) -> None:
        # A plain legacy-grammar FormatString survives copy.copy and deepcopy.
        context = ModelParsingContext()
        original = FormatString("prefix {{ Task.Param.Frame }} suffix", context=context)
        symtab = SymbolTable()
        symtab["Task.Param.Frame"] = 7
        for reconstructed in (copy.copy(original), copy.deepcopy(original)):
            assert str(reconstructed) == str(original)
            assert reconstructed.resolve(symtab=symtab) == "prefix 7 suffix"
