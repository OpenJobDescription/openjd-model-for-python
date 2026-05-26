# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest

from openjd.expr import (
    evaluate_expression,
    ExprProfile,
    HostContext,
    ExpressionError,
    PathMappingRule,
    PathFormat,
)


class TestHostContextOnProfile:
    """Verify the ``ExprProfile.with_host_context`` chain is what
    governs which functions are available during evaluation, after
    the removal of the public ``FunctionLibrary`` surface."""

    def test_default_profile_no_host_context(self) -> None:
        """``ExprProfile()`` defaults to ``HostContext.none()``."""
        profile = ExprProfile()
        assert profile.host_context == HostContext.none()
        assert profile.host_context.is_enabled() is False

    def test_with_rules_enables_host_context(self) -> None:
        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        assert profile.host_context.is_enabled() is True

    def test_with_unresolved_enables_host_context(self) -> None:
        profile = ExprProfile().with_host_context(HostContext.unresolved())
        assert profile.host_context.is_enabled() is True
        assert profile.host_context.is_unresolved() is True


class TestApplyPathMappingContext:
    """``apply_path_mapping`` is a host-context function (RFC 0006)
    that is available only when ``HostContext`` is set on the
    profile."""

    def test_not_available_with_default_profile(self) -> None:
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')", profile=ExprProfile())

    def test_not_available_with_no_profile(self) -> None:
        # Same as default profile — the implicit profile is
        # ``ExprProfile.current()`` which has no host context.
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')")

    def test_available_with_host_context(self) -> None:
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("apply_path_mapping('/some/path')", profile=profile)
        # No rules configured, path returned normalized to OS-native format
        assert str(result) == str(PurePath("/some/path"))

    def test_method_syntax_without_host_context(self) -> None:
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("'/path'.apply_path_mapping()", profile=ExprProfile())

    def test_method_syntax_with_host_context(self) -> None:
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("'/some/path'.apply_path_mapping()", profile=profile)
        assert str(result) == str(PurePath("/some/path"))

    def test_with_path_mapping_rules(self, tmp_path) -> None:
        """apply_path_mapping should apply rules when configured on the profile."""
        from pathlib import PurePosixPath

        dest = tmp_path / "new" / "path"
        rules = [
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PurePosixPath("/old/path"),
                destination_path=dest,
            )
        ]
        profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

        result = evaluate_expression("apply_path_mapping('/old/path/file.txt')", profile=profile)
        assert str(result) == str(dest / "file.txt")

    def test_unmatched_path_unchanged(self, tmp_path) -> None:
        """Paths not matching any rule should be returned normalized to OS-native format."""
        from pathlib import PurePosixPath, PurePath

        dest = tmp_path / "mapped" / "path"
        rules = [
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PurePosixPath("/specific/path"),
                destination_path=dest,
            )
        ]
        profile = ExprProfile().with_host_context(HostContext.with_rules(rules))

        result = evaluate_expression("apply_path_mapping('/other/path/file.txt')", profile=profile)
        assert str(result) == str(PurePath("/other/path/file.txt"))

    def test_no_rules_returns_path_unchanged(self) -> None:
        """With no rules configured, path should be returned normalized to OS-native format."""
        from pathlib import PurePath

        profile = ExprProfile().with_host_context(HostContext.with_rules([]))
        result = evaluate_expression("apply_path_mapping('/any/path')", profile=profile)
        assert str(result) == str(PurePath("/any/path"))


class TestSubmissionContextFunctions:
    """Submission-time (non-host-context) functions work without
    needing a host context on the profile."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            pytest.param("1 + 2", 3, id="arithmetic"),
            pytest.param("min(5, 3)", 3, id="min"),
            pytest.param("upper('hello')", "HELLO", id="upper"),
            pytest.param("len('test')", 4, id="len"),
        ],
    )
    def test_submission_functions_available(self, expr: str, expected) -> None:
        """Core functions should work with the default profile (no
        host context)."""
        result = evaluate_expression(expr, profile=ExprProfile())
        assert result.item() == expected

    def test_path_functions_available_without_host_context(self, tmp_path) -> None:
        """Path manipulation functions don't require host context."""
        import sys
        from openjd.expr import SymbolTable, ExprValue
        from openjd.expr import PathFormat

        host_pf = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX
        render_file = tmp_path / "projects" / "render.exr"
        symtab = SymbolTable({"P": ExprValue(str(render_file), type="path", path_format=host_pf)})

        # These should all work without host context.
        result = evaluate_expression("P.stem", values=symtab, profile=ExprProfile())
        assert result.item() == "render"

        result = evaluate_expression("P.suffix", values=symtab, profile=ExprProfile())
        assert result.item() == ".exr"

        result = evaluate_expression("with_suffix(P, '.png')", values=symtab, profile=ExprProfile())
        assert str(result).endswith("render.png")


class TestUnresolvedHostContext:
    """``HostContext.unresolved()`` is the job-template-validation
    mode: host-context functions are registered with stub
    implementations that return ``Unresolved(T)`` so the type
    checker can run before real path-mapping rules are bound."""

    def test_apply_path_mapping_returns_unresolved_path(self) -> None:
        from openjd.expr import TypeCode

        profile = ExprProfile().with_host_context(HostContext.unresolved())
        result = evaluate_expression("apply_path_mapping('/some/path')", profile=profile)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_apply_path_mapping_method_returns_unresolved_path(self) -> None:
        from openjd.expr import TypeCode

        profile = ExprProfile().with_host_context(HostContext.unresolved())
        result = evaluate_expression("'/some/path'.apply_path_mapping()", profile=profile)
        assert result.type.type_code == TypeCode.UNRESOLVED

    def test_not_available_without_any_context(self) -> None:
        """``apply_path_mapping`` still errors without any host
        context, even when one was previously bound on a different
        profile instance — profiles are immutable, ``with_host_context``
        returns a new one."""
        with pytest.raises(ExpressionError, match="apply_path_mapping"):
            evaluate_expression("apply_path_mapping('/path')", profile=ExprProfile())
