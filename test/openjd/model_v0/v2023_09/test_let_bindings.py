# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for EXPR `let` bindings (RFC 0007 §3.6), Step.Name in step
environments, host-context function scoping, and type-aware expression
validation."""

import pytest

from openjd.expr import PathFormat
from openjd.model import (
    DecodeValidationError,
    SymbolTable,
    create_job_with_symbol_tables,
    decode_job_template,
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


class TestStepLetIsNotMergedIntoScript:
    """A step-level `let` is resolved once, in template scope, at job creation,
    and its values travel in the step's symbol table. It is therefore *not*
    merged into the script's own `let`: doing so would have the session
    re-evaluate the same bindings in the host's scope, re-rendering PATH values
    and overwriting the correctly formatted seeded value."""

    @staticmethod
    def _resolved_script(step):
        template = _decode(_job([step], extensions=("EXPR", "FEATURE_BUNDLE_1")))
        return template.steps[0].resolve_syntax_sugar().script

    def test_script_branch_keeps_only_the_scripts_own_let(self):
        # GIVEN / WHEN
        script = self._resolved_script(
            {
                "name": "S",
                "let": ["a = 1", "b = 2"],
                "script": {"let": ["c = 3"], **_onrun("{{a}}{{c}}")},
            }
        )

        # THEN
        assert script.let == ["c = 3"]

    @pytest.mark.parametrize("interpreter", ("python", "bash", "cmd", "powershell", "node"))
    def test_simple_action_branch_keeps_only_the_actions_own_let(self, interpreter):
        # The de-sugaring path builds a fresh script, so it has to make the same
        # choice independently of the `script:` branch.
        # GIVEN / WHEN
        script = self._resolved_script(
            {
                "name": "S",
                "let": ["a = 1", "b = 2"],
                interpreter: {"script": "print(1)", "let": ["c = 3"]},
            }
        )

        # THEN
        assert script.let == ["c = 3"]


class TestStepLetTravelsInTheStepSymbolTable:
    """The transport that replaces the merge: `create_job_with_symbol_tables`
    resolves the step-level `let` at creation and hands the values over in the
    step's symbol table, PATH values stored so each host renders them itself."""

    @staticmethod
    def _tables(step):
        template = _decode(_job([step]))
        return create_job_with_symbol_tables(job_template=template, job_parameter_values={})

    _STEP = {
        "name": "S",
        "let": ["a = 1", 'root = path("/foo/bar")', 'txt = string(path("/mnt/out"))'],
        "script": {"let": ["scriptonly = 7"], **_onrun("{{a}}{{scriptonly}}")},
    }

    def test_step_let_values_are_carried_and_paths_render_per_host(self):
        # GIVEN
        result = self._tables(self._STEP)
        table = result.step_symbol_tables["S"]

        # WHEN
        posix = table.to_symtab(path_format=PathFormat.POSIX)
        windows = table.to_symtab(path_format=PathFormat.WINDOWS)

        # THEN: the values the deleted merge used to have the session recompute
        # are already here, and the PATH one is stored so it renders in each
        # host's own format rather than the creating host's.
        assert str(posix["a"]) == "1"
        assert str(posix["root"]) == "/foo/bar"
        assert str(windows["root"]) == "\\foo\\bar"
        # Rendered to a string at create time, in template scope, so it stays
        # POSIX on every host -- this is what re-evaluating in host scope broke.
        assert str(posix["txt"]) == "/mnt/out"
        assert str(windows["txt"]) == "/mnt/out"
        # AND: the script still carries only its own bindings, for the session
        # to evaluate in host scope.
        assert result.job.steps[0].script.let == ["scriptonly = 7"]

    def test_script_let_is_not_in_the_step_symbol_table(self):
        # A script-level binding resolves at session time in host scope, so it
        # must not be evaluated into -- or leak into -- the create-time table.
        # GIVEN
        result = self._tables(self._STEP)

        # WHEN
        symtab = result.step_symbol_tables["S"].to_symtab(path_format=PathFormat.POSIX)

        # THEN
        assert "scriptonly" not in symtab
        assert "a" in symtab
