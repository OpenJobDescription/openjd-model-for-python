# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for EXPR `let` bindings (RFC 0007 §3.6), Step.Name in step
environments, host-context function scoping, and type-aware expression
validation."""

import json

import pytest

from openjd.model import (
    DecodeValidationError,
    SymbolTable,
    create_job,
    decode_job_template,
    model_to_object,
)

_EXTS = ["EXPR", "FEATURE_BUNDLE_1"]


def _decode(template):
    return decode_job_template(template=template, supported_extensions=_EXTS)


def _job(steps, *, params=None, extensions=("EXPR",)):
    t = {"specificationVersion": "jobtemplate-2023-09", "name": "T", "steps": steps}
    if params is not None:
        t["parameterDefinitions"] = params
    if extensions:
        t["extensions"] = list(extensions)
    return t


def _onrun(arg):
    return {"actions": {"onRun": {"command": "echo", "args": [arg]}}}


class TestLetValid:
    def test_step_let_visible_in_script(self):
        _decode(
            _job(
                [{"name": "S", "let": ["x = 1", "y = x + 1"], "script": _onrun("{{y}}")}],
            )
        )

    def test_script_let(self):
        _decode(
            _job([{"name": "S", "script": {"let": ["a = 2"], **_onrun("{{a}}")}}]),
        )

    # §3.6.1 boundary: 512 characters is the maximum and must be accepted, with
    # EXPR alone, since the cap does not depend on FEATURE_BUNDLE_1.
    def test_name_512_chars(self):
        name = "a" * 512
        # Referenced, not just declared: a cap further down the path would
        # otherwise be invisible here.
        _decode(_job([{"name": "S", "let": [f"{name} = 1"], "script": _onrun(f"{{{{{name}}}}}")}]))

    def test_name_512_chars_with_fb1(self):
        name = "a" * 512
        _decode(
            _job(
                [{"name": "S", "let": [f"{name} = 1"], "script": _onrun(f"{{{{{name}}}}}")}],
                extensions=("EXPR", "FEATURE_BUNDLE_1"),
            )
        )

    def test_name_512_chars_script(self):
        name = "a" * 512
        _decode(
            _job([{"name": "S", "script": {"let": [f"{name} = 1"], **_onrun(f"{{{{{name}}}}}")}}])
        )

    def test_chained_and_functions(self):
        _decode(
            _job(
                [
                    {
                        "name": "S",
                        "let": ["total = sum(Param.Items)", "n = len(Param.Items)"],
                        "script": _onrun("{{total}}-{{n}}"),
                    }
                ],
                params=[{"name": "Items", "type": "LIST[INT]", "default": [1, 2, 3]}],
            )
        )


class TestLetInvalid:
    def test_requires_expr(self):
        with pytest.raises(DecodeValidationError, match="requires the EXPR extension"):
            _decode(_job([{"name": "S", "let": ["x = 1"], "script": _onrun("hi")}], extensions=()))

    def test_empty(self):
        with pytest.raises(DecodeValidationError, match="at least one"):
            _decode(_job([{"name": "S", "let": [], "script": _onrun("hi")}]))

    def test_duplicate_name(self):
        with pytest.raises(DecodeValidationError, match="unique"):
            _decode(_job([{"name": "S", "let": ["x = 1", "x = 2"], "script": _onrun("hi")}]))

    def test_too_many(self):
        many = [f"v{i} = {i}" for i in range(51)]
        with pytest.raises(DecodeValidationError, match="at most"):
            _decode(_job([{"name": "S", "let": many, "script": _onrun("hi")}]))

    def test_uppercase_name(self):
        with pytest.raises(DecodeValidationError, match="identifier"):
            _decode(_job([{"name": "S", "let": ["Foo = 1"], "script": _onrun("hi")}]))

    def test_shadow_enclosing(self):
        with pytest.raises(DecodeValidationError, match="shadows"):
            _decode(
                _job(
                    [
                        {
                            "name": "S",
                            "let": ["x = 1"],
                            "script": {"let": ["x = 2"], **_onrun("hi")},
                        }
                    ]
                )
            )

    def test_self_reference(self):
        # A binding cannot reference its own name on its RHS (not yet bound at
        # its definition point). Mirrors openjd-rs "references itself".
        with pytest.raises(DecodeValidationError, match="cannot reference itself"):
            _decode(_job([{"name": "S", "let": ["x = x + 1"], "script": _onrun("hi")}]))

    # §3.6.1 caps a `<UserIdentifier>` at 512 characters. `_job` declares EXPR
    # alone, so these pin the cap independently of FEATURE_BUNDLE_1.
    def test_name_513_chars(self):
        name = "a" * 513
        with pytest.raises(
            DecodeValidationError,
            match=r"at most 512 characters long: 'a{32}'\.\.\. \(513 characters\)",
        ):
            _decode(_job([{"name": "S", "let": [f"{name} = 1"], "script": _onrun("hi")}]))

    def test_name_513_chars_names_the_offending_binding(self):
        # The validator is a field_validator on the whole list, so the error path
        # is `let` with no index; the message has to identify the binding itself.
        name = "b" * 513
        with pytest.raises(DecodeValidationError, match=r"'b{32}'\.\.\. \(513 characters\)"):
            _decode(_job([{"name": "S", "let": ["ok = 1", f"{name} = 2"], "script": _onrun("hi")}]))

    def test_name_513_chars_with_fb1(self):
        name = "a" * 513
        with pytest.raises(DecodeValidationError, match="at most 512 characters"):
            _decode(
                _job(
                    [{"name": "S", "let": [f"{name} = 1"], "script": _onrun("hi")}],
                    extensions=("EXPR", "FEATURE_BUNDLE_1"),
                )
            )

    def test_name_513_chars_script(self):
        name = "a" * 513
        with pytest.raises(DecodeValidationError, match="at most 512 characters"):
            _decode(
                _job([{"name": "S", "script": {"let": [f"{name} = 1"], **_onrun("hi")}}]),
            )

    def test_comprehension_shadows_let(self):
        with pytest.raises(DecodeValidationError, match="shadows"):
            _decode(
                _job(
                    [
                        {
                            "name": "S",
                            "let": ["x = 10"],
                            "script": _onrun("{{ [x for x in Param.Items] }}"),
                        }
                    ],
                    params=[{"name": "Items", "type": "LIST[INT]", "default": [1, 2]}],
                )
            )


class TestStepName:
    def test_step_name_in_step_environment_with_expr(self):
        _decode(
            _job(
                [
                    {
                        "name": "Render",
                        "stepEnvironments": [
                            {"name": "Setup", "variables": {"CUR": "{{ Step.Name }}"}}
                        ],
                        "script": _onrun("hi"),
                    }
                ]
            )
        )

    def test_step_name_requires_expr(self):
        with pytest.raises(DecodeValidationError):
            _decode(
                _job(
                    [
                        {
                            "name": "Render",
                            "stepEnvironments": [
                                {"name": "Setup", "variables": {"CUR": "{{ Step.Name }}"}}
                            ],
                            "script": _onrun("hi"),
                        }
                    ],
                    extensions=(),
                )
            )


class TestHostContextScope:
    def test_apply_path_mapping_in_job_name_rejected(self):
        with pytest.raises(DecodeValidationError, match="only available at runtime"):
            _decode(
                _job([{"name": "S", "script": _onrun("hi")}])
                | {"name": "{{ apply_path_mapping('/x') }}"}
            )

    def test_apply_path_mapping_in_task_arg_ok(self):
        _decode(_job([{"name": "S", "script": _onrun("{{ apply_path_mapping('/x') }}")}]))


class TestSymbolTyping:
    def test_path_method_access(self):
        _decode(
            _job(
                [{"name": "S", "script": _onrun("{{ Param.File.name }}")}],
                params=[{"name": "File", "type": "PATH", "default": "/a/b.exr"}],
            )
        )

    def test_string_type_mismatch_rejected(self):
        with pytest.raises(DecodeValidationError):
            _decode(
                _job(
                    [{"name": "S", "script": _onrun("{{ Param.Name + 1 }}")}],
                    params=[{"name": "Name", "type": "STRING", "default": "hi"}],
                )
            )


class TestStepScopeIsTemplateScope:
    """Step-level `let` bindings resolve in *template* scope at job creation, so
    PATH-typed values render POSIX regardless of the host that creates the job —
    matching openjd-rs, whose instantiation hardcodes PathFormat::Posix and uses
    the host's format only inside sessions."""

    def test_step_symtab_renders_paths_posix(self):
        # GIVEN
        template = _decode(
            _job(
                [
                    {
                        "name": "S",
                        "let": ['p = string(path("/mnt/out"))'],
                        "script": _onrun("{{p}}"),
                    }
                ]
            )
        )

        # WHEN
        symtab = template.steps[0]._extend_step_symtab(SymbolTable())

        # THEN
        assert str(symtab["p"]) == "/mnt/out"

    def test_step_symtab_path_predicate_is_host_independent(self):
        # The conformance failure this guards: on Windows a host-format
        # rendering makes a POSIX-prefix test false at create time.
        # GIVEN
        template = _decode(
            _job(
                [
                    {
                        "name": "S",
                        "let": ['under = startswith(path("/foo/bar"), "/foo")'],
                        "script": _onrun("{{under}}"),
                    }
                ]
            )
        )

        # WHEN
        symtab = template.steps[0]._extend_step_symtab(SymbolTable())

        # THEN
        assert str(symtab["under"]) == "true"


class TestTemplateScopeLetCount:
    """The instantiated Step's script carries a merged `let` — the step-level
    bindings first, then the script's own. `_template_scope_let_count` records
    how many leading entries are the step-level ones, so a session handed the
    step's resolved symbol table can skip re-evaluating them in host scope."""

    @staticmethod
    def _script(step, *, extensions=("EXPR",)):
        template = _decode(_job([step], extensions=extensions))
        return create_job(job_template=template, job_parameter_values={}).steps[0].script

    def test_no_step_lets_is_zero(self):
        script = self._script({"name": "S", "script": _onrun("hi")})

        assert script._template_scope_let_count == 0
        assert script.let is None

    def test_script_lets_only_is_zero(self):
        script = self._script({"name": "S", "script": {"let": ["a = 1"], **_onrun("{{a}}")}})

        assert script._template_scope_let_count == 0
        assert script.let == ["a = 1"]

    def test_step_lets_only(self):
        script = self._script(
            {"name": "S", "let": ["a = 1", "b = 2"], "script": _onrun("{{a}}{{b}}")}
        )

        assert script._template_scope_let_count == 2
        assert script.let == ["a = 1", "b = 2"]

    def test_both_scopes_counts_only_the_step_level_ones(self):
        script = self._script(
            {
                "name": "S",
                "let": ["a = 1", "b = 2"],
                "script": {"let": ["c = 3"], **_onrun("{{a}}{{c}}")},
            }
        )

        # THEN: the count is the step-level count, and the merged order puts the
        # step-level bindings first — the two together are what makes a prefix
        # skip correct.
        assert script._template_scope_let_count == 2
        assert script.let == ["a = 1", "b = 2", "c = 3"]

    def test_syntax_sugar_script_records_the_count(self):
        # The de-sugaring path builds its own merged `let`, so it needs the same
        # boundary recorded.
        script = self._script(
            {
                "name": "S",
                "let": ["a = 1"],
                "python": {"script": "print(1)", "let": ["b = 2"]},
            },
            extensions=("EXPR", "FEATURE_BUNDLE_1"),
        )

        assert script._template_scope_let_count == 1
        assert script.let == ["a = 1", "b = 2"]

    def test_count_is_private_and_not_serialized(self):
        # Hard requirement: recording the boundary must not change the model's
        # serialized shape.
        step = {
            "name": "S",
            "let": ["a = 1"],
            "script": {"let": ["c = 3"], **_onrun("{{a}}{{c}}")},
        }
        job = create_job(job_template=_decode(_job([step])), job_parameter_values={})

        # WHEN
        obj = model_to_object(model=job)

        # THEN
        assert job.steps[0].script._template_scope_let_count == 1
        assert "_template_scope_let_count" not in json.dumps(obj)
        assert obj["steps"][0]["script"]["let"] == ["a = 1", "c = 3"]
