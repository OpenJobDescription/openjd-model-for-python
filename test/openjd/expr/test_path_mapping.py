# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for PathMappingRule."""

import os
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from openjd.expr import PathMappingRule, PathFormat, ExprProfile, HostContext


class TestPathMappingRuleFromPosix:
    """Tests for mapping rules with POSIX source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/file.txt")
        assert matched is True
        assert result == dest + os.sep + "file.txt"

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/other/path/file.txt")
        assert matched is False
        assert result == "/other/path/file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared2/file.txt")
        assert matched is False
        assert result == "/mnt/shared2/file.txt"


class TestPathMappingRuleFromWindows:
    """Tests for mapping rules with WINDOWS source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\file.txt")
        assert matched is True
        assert result == dest + os.sep + "file.txt"

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_path(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="D:\\other\\file.txt")
        assert matched is False
        assert result == "D:\\other\\file.txt"

    def test_no_match_same_prefix(self, tmp_path) -> None:
        """path mapping operates on the parts, not with string prefixes"""
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects2\\file.txt")
        assert matched is False
        assert result == "C:\\projects2\\file.txt"


class TestPathMappingRuleFromUri:
    """Tests for mapping rules with URI source paths."""

    def test_match_with_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "local" / "assets")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets/teapot.obj")
        assert matched is True
        assert result == dest + os.sep + "teapot.obj"

    def test_match_nested_subpath(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/a/b/c.txt")
        assert matched is True
        assert result == dest + os.sep + os.sep.join(["a", "b", "c.txt"])

    def test_exact_match(self, tmp_path) -> None:
        dest = str(tmp_path / "local" / "assets")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://my-bucket/assets")
        assert matched is True
        assert result == str(dest)

    def test_no_match_different_bucket(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://my-bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://other-bucket/assets/file.obj")
        assert matched is False
        assert result == "s3://other-bucket/assets/file.obj"

    def test_no_match_prefix_overlap(self, tmp_path) -> None:
        """URI matching is on path boundaries, not string prefixes."""
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/dir",
            destination_path=dest,
        )
        matched, result = rule.apply(path="s3://bucket/directory/file.txt")
        assert matched is False
        assert result == "s3://bucket/directory/file.txt"

    def test_no_match_different_scheme(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path=dest,
        )
        matched, result = rule.apply(path="https://bucket/assets/file.txt")
        assert matched is False
        assert result == "https://bucket/assets/file.txt"

    def test_no_match_filesystem_path(self, tmp_path) -> None:
        dest = str(tmp_path / "local")
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/local/file.txt")
        assert matched is False
        assert result == "/mnt/local/file.txt"

    def test_https_scheme(self, tmp_path) -> None:
        dest = tmp_path / "cache"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="https://example.com/models",
            destination_path=dest,
        )
        matched, result = rule.apply(path="https://example.com/models/scene.obj")
        assert matched is True
        assert result == str(dest / "scene.obj")

    def test_custom_scheme(self, tmp_path) -> None:
        dest = tmp_path / "mount"
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="fsx://vol-123/data",
            destination_path=dest,
        )
        matched, result = rule.apply(path="fsx://vol-123/data/file.bin")
        assert matched is True
        assert result == str(dest / "file.bin")


class TestPathMappingRuleValidation:
    """Tests for from_dict validation shared across formats."""


class TestPathMappingRuleSerialization:
    """Tests for from_dict/to_dict serialization."""

    def test_from_dict_posix(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "POSIX",
                "source_path": "/mnt/shared",
                "destination_path": str(tmp_path / "newprefix"),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX
        assert rule.source_path == "/mnt/shared"
        assert rule.destination_path == str(tmp_path / "newprefix")

    def test_from_dict_windows(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "WINDOWS",
                "source_path": "C:\\projects",
                "destination_path": str(tmp_path / "mnt" / "projects"),
            }
        )
        assert rule.source_path_format == PathFormat.WINDOWS
        assert rule.source_path == "C:\\projects"

    def test_from_dict_uri(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "URI",
                "source_path": "s3://bucket/assets",
                "destination_path": str(tmp_path / "local"),
            }
        )
        assert rule.source_path_format == PathFormat.URI
        assert rule.source_path == "s3://bucket/assets"

    def test_from_dict_case_insensitive(self, tmp_path) -> None:
        rule = PathMappingRule.from_dict(
            {
                "source_path_format": "posix",
                "source_path": "/mnt/shared",
                "destination_path": str(tmp_path),
            }
        )
        assert rule.source_path_format == PathFormat.POSIX

    def test_from_dict_empty(self) -> None:
        # Per AGENTS.md "Test Quality Standard": assert exception
        # class + the full message body, not just a substring.
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule.from_dict({})
        assert str(excinfo.value) == "Empty path mapping rule"

    def test_from_dict_missing_field(self) -> None:
        # Pin the full v0-reference-parity error message — the
        # field-names list uses Python's ``list[str]`` repr form
        # (single-quoted names, comma-space separators) so callers
        # porting from v0 see the exact same diagnostic.
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule.from_dict({"source_path_format": "POSIX", "source_path": "/mnt"})
        assert str(excinfo.value) == (
            "Path mapping rule requires the following fields: "
            "['source_path_format', 'source_path', 'destination_path']"
        )

    def test_to_dict_posix(self, tmp_path) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=str(tmp_path / "newprefix"),
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "POSIX"
        assert d["source_path"] == "/mnt/shared"
        assert d["destination_path"] == str(tmp_path / "newprefix")

    def test_to_dict_windows(self) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path="D:\\local",
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "WINDOWS"
        assert d["source_path"] == "C:\\projects"

    def test_to_dict_uri(self) -> None:
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/assets",
            destination_path="/local/cache",
        )
        d = rule.to_dict()
        assert d["source_path_format"] == "URI"
        assert d["source_path"] == "s3://bucket/assets"

    def test_roundtrip(self, tmp_path) -> None:
        original = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=str(tmp_path / "local"),
        )
        restored = PathMappingRule.from_dict(original.to_dict())
        assert restored.source_path_format == original.source_path_format
        assert restored.source_path == original.source_path
        assert restored.destination_path == original.destination_path


class TestTrailingSlash:
    """Tests that trailing separators are preserved after mapping."""

    def test_posix_trailing_slash(self, tmp_path) -> None:
        dest = str(tmp_path / "newprefix")
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        matched, result = rule.apply(path="/mnt/shared/dir/")
        assert matched is True
        assert result.endswith("/") or result.endswith(os.sep)

    def test_windows_trailing_backslash(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir\\")
        assert matched is True
        assert result.endswith("\\") or result.endswith(os.sep)

    def test_windows_trailing_forward_slash(self, tmp_path) -> None:
        dest = str(tmp_path / "mnt" / "projects")
        rule = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path="C:\\projects",
            destination_path=dest,
        )
        matched, result = rule.apply(path="C:\\projects\\subdir/")
        assert matched is True
        assert result.endswith("/") or result.endswith(os.sep) or result.endswith("\\")


class TestFormatMismatch:
    """Tests that constructor rejects wrong path types for the format."""

    def test_posix_rejects_windows_path(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.POSIX,
                source_path=PureWindowsPath("C:\\path"),
                destination_path="/dest",
            )
        # The message contains the pure-Python reference's canonical
        # phrase (so v0 callers' message-substring checks still match)
        # plus the actionable detail (which format was expected, what
        # type was supplied) to help the caller fix their call.
        assert str(excinfo.value) == (
            "Path mapping rule source_path_format does not match source_path type: "
            "source_path must be str or PurePosixPath for POSIX format, got PureWindowsPath"
        )

    def test_windows_rejects_posix_path(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.WINDOWS,
                source_path=PurePosixPath("/posix/path"),
                destination_path="/dest",
            )
        assert str(excinfo.value) == (
            "Path mapping rule source_path_format does not match source_path type: "
            "source_path must be str or PureWindowsPath for WINDOWS format, got PurePosixPath"
        )

    def test_uri_rejects_purepath(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path=PurePosixPath("/mnt/shared"),
                destination_path="/dest",
            )
        assert str(excinfo.value) == (
            "Path mapping rule source_path_format does not match source_path type: "
            "source_path must be str for URI format, got PurePosixPath"
        )


class TestUriValidation:
    """``PathMappingRule(source_path_format=URI, ...)`` validates that
    ``source_path`` parses as a URI (``scheme://...``). Without this
    check, a typo like ``source_path="/not/a/uri"`` would silently
    construct a rule that never matches anything — the failure would
    only surface much later when path mapping is applied at session
    time. Pinned for parity with the v0 reference's ``__init__``
    check."""

    def test_uri_rejects_non_uri_string(self) -> None:
        # Per AGENTS.md "Test Quality Standard": assert exception
        # class + the full message body.
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path="/not/a/uri",
                destination_path="/dest",
            )
        assert str(excinfo.value) == (
            "Path mapping rule with URI source_path_format requires a URI string source_path"
        )

    def test_uri_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path="",
                destination_path="/dest",
            )
        assert str(excinfo.value) == (
            "Path mapping rule with URI source_path_format requires a URI string source_path"
        )

    def test_uri_rejects_relative_string(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule(
                source_path_format=PathFormat.URI,
                source_path="bucket/path",
                destination_path="/dest",
            )
        assert str(excinfo.value) == (
            "Path mapping rule with URI source_path_format requires a URI string source_path"
        )

    @pytest.mark.parametrize(
        "uri",
        [
            "s3://bucket/path",
            "https://example.com/path",
            "file:///mnt/shared",
            "custom-scheme://anything",
        ],
    )
    def test_uri_accepts_valid_schemes(self, uri: str) -> None:
        # No exception. Constructing succeeds and round-trips through
        # the getter unchanged.
        rule = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path=uri,
            destination_path="/dest",
        )
        assert rule.source_path == uri
        assert rule.source_path_format == PathFormat.URI

    def test_uri_validation_via_from_dict(self) -> None:
        """``from_dict`` routes through the same constructor, so the
        URI validation also fires there."""
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule.from_dict(
                {
                    "source_path_format": "URI",
                    "source_path": "/not/a/uri",
                    "destination_path": "/dest",
                }
            )
        assert str(excinfo.value) == (
            "Path mapping rule with URI source_path_format requires a URI string source_path"
        )


class TestFromDictValidation:
    """Tests for from_dict edge cases."""

    def test_from_dict_extra_field_rejected(self) -> None:
        """Extra fields raise ``ValueError`` matching the pure-Python
        reference's ``Unsupported fields ...`` contract."""
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                    "destination_path": "/local",
                    "extra": "field",
                }
            )
        # Python ``set`` repr form: ``{'extra'}`` — single name in
        # braces with single quotes around it.
        assert str(excinfo.value) == (
            "Unsupported fields for constructing path mapping rule: {'extra'}"
        )

    def test_from_dict_multiple_extra_fields_in_message(self) -> None:
        """All offending field names appear in the error message,
        sorted for determinism (Python dict iteration order is
        otherwise insertion-defined)."""
        with pytest.raises(ValueError) as excinfo:
            PathMappingRule.from_dict(
                {
                    "source_path_format": "POSIX",
                    "source_path": "/mnt/shared",
                    "destination_path": "/local",
                    "zeta": 1,
                    "alpha": 2,
                }
            )
        # Sorted alphabetically — zeta after alpha.
        assert str(excinfo.value) == (
            "Unsupported fields for constructing path mapping rule: {'alpha', 'zeta'}"
        )


class TestPathMappingViaProfile:
    """Tests that path-mapping rules registered on an :class:`ExprProfile`
    via :meth:`HostContext.with_rules` flow through every evaluation entry
    point.

    These exercise the canonical wiring for path mapping: a caller builds
    an :class:`ExprProfile` with rules attached and passes it as
    ``profile=`` rather than using a per-call ``path_mapping_rules=``
    kwarg. The profile-based plumbing is shared across
    :func:`evaluate_expression`, :meth:`ParsedExpression.evaluate`,
    :meth:`FormatString.resolve_string`, and :meth:`FormatString.resolve`.

    The destination path of a mapping rule is a *host* path — the
    file is supposed to live there after the mapping. On Windows
    that's a backslash-separated path; on POSIX it's a forward-
    slash path. ``tmp_path`` gives us a real host path the test
    can assert against using ``os.sep``, so these tests pass on
    every platform.
    """

    @staticmethod
    def _profile_with_rule(dest: str) -> ExprProfile:
        rule = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/mnt/shared",
            destination_path=dest,
        )
        return ExprProfile().with_host_context(HostContext.with_rules([rule]))

    def test_parsed_expression_evaluate_applies_rules(self, tmp_path) -> None:
        from openjd.expr import parse_expression

        dest = str(tmp_path / "cache")
        parsed = parse_expression("apply_path_mapping('/mnt/shared/file.exr')")
        result = parsed.evaluate(profile=self._profile_with_rule(dest))
        assert result.item() == dest + os.sep + "file.exr"

    def test_format_string_resolve_string_applies_rules(self, tmp_path) -> None:
        from openjd.expr import FormatString, SymbolTable

        dest = str(tmp_path / "cache")
        fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
        result = fs.resolve_string(SymbolTable({}), profile=self._profile_with_rule(dest))
        assert result == dest + os.sep + "file.exr"

    def test_format_string_resolve_applies_rules(self, tmp_path) -> None:
        from openjd.expr import FormatString, SymbolTable

        dest = str(tmp_path / "cache")
        fs = FormatString("{{apply_path_mapping('/mnt/shared/file.exr')}}")
        result = fs.resolve(SymbolTable({}), profile=self._profile_with_rule(dest))
        assert result.item() == dest + os.sep + "file.exr"


class TestPathMappingRuleRepr:
    """``__repr__`` renders ``source_path_format`` using the Python
    convention (``PathFormat.POSIX``) rather than the underlying Rust
    enum's debug name (``Posix``). Pinned for parity with how Python's
    own enums repr themselves and to make logged repr output drop-in
    pasteable into Python source."""

    def test_repr_uses_python_enum_name_posix(self) -> None:
        r = PathMappingRule(
            source_path_format=PathFormat.POSIX,
            source_path="/a",
            destination_path="/b",
        )
        text = repr(r)
        assert "source_path_format=PathFormat.POSIX" in text
        assert "Posix" not in text  # no leaked Rust debug name

    def test_repr_uses_python_enum_name_windows(self) -> None:
        r = PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=r"C:\src",
            destination_path=r"C:\dst",
        )
        text = repr(r)
        assert "source_path_format=PathFormat.WINDOWS" in text
        assert "Windows" not in text  # no leaked Rust debug name

    def test_repr_uses_python_enum_name_uri(self) -> None:
        r = PathMappingRule(
            source_path_format=PathFormat.URI,
            source_path="s3://bucket/a",
            destination_path="/b",
        )
        text = repr(r)
        assert "source_path_format=PathFormat.URI" in text
        assert "Uri" not in text  # no leaked Rust debug name
