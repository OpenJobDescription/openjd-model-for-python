# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for path operations."""

import sys
import pytest
from pathlib import PurePath
from openjd.expr import evaluate_expression, ExprValue, ExpressionError, SymbolTable
from openjd.expr import PathFormat

HOST_PATH_FORMAT = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX


def _p(path) -> ExprValue:
    """Helper to create a path-typed ExprValue from a pathlib Path or string."""
    return ExprValue(str(path), type="path", path_format=HOST_PATH_FORMAT)


class TestPaths:
    def test_path_name(self, tmp_path) -> None:
        p = tmp_path / "projects" / "shot01" / "render.exr"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.name", values=symtab).item() == "render.exr"

    def test_path_parent(self, tmp_path) -> None:
        p = tmp_path / "projects" / "shot01" / "render.exr"
        symtab = SymbolTable({"P": _p(p)})
        assert str(evaluate_expression("P.parent", values=symtab)) == str(
            tmp_path / "projects" / "shot01"
        )

    def test_path_stem(self, tmp_path) -> None:
        p = tmp_path / "projects" / "shot01" / "render.exr"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.stem", values=symtab).item() == "render"

    def test_path_stem_multi_extension(self, tmp_path) -> None:
        """stem returns filename without the last suffix (matches Python pathlib)."""
        p = tmp_path / "data" / "archive.tar.gz"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.stem", values=symtab).item() == "archive.tar"

    def test_path_suffix(self, tmp_path) -> None:
        p = tmp_path / "projects" / "shot01" / "render.exr"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.suffix", values=symtab).item() == ".exr"

    def test_path_suffix_multi_extension(self, tmp_path) -> None:
        """suffix returns the last extension only (matches Python pathlib)."""
        p = tmp_path / "data" / "archive.tar.gz"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.suffix", values=symtab).item() == ".gz"

    def test_path_suffixes(self, tmp_path) -> None:
        p = tmp_path / "home" / "user" / "file.tar.gz"
        symtab = SymbolTable({"p": _p(p)})
        result = evaluate_expression("p.suffixes", values=symtab)
        assert result.item() == [".tar", ".gz"]

    def test_path_parts(self, tmp_path) -> None:
        p = tmp_path / "home" / "user" / "file.tar.gz"
        symtab = SymbolTable({"p": _p(p)})
        result = evaluate_expression("p.parts", values=symtab)
        parts = result.item()
        expected = list(p.parts)
        assert parts == expected

    def test_path_join(self, tmp_path) -> None:
        d = tmp_path / "output"
        symtab = SymbolTable({"Dir": _p(d)})
        result = evaluate_expression("Dir / 'subdir' / 'file.txt'", values=symtab)
        assert str(result) == str(d / "subdir" / "file.txt")

    def test_path_concat(self, tmp_path) -> None:
        p = tmp_path / "output" / "file"
        symtab = SymbolTable({"P": _p(p)})
        assert str(evaluate_expression("P + '.txt'", values=symtab)) == str(p) + ".txt"

    def test_with_suffix(self, tmp_path) -> None:
        p = tmp_path / "output" / "render.exr"
        symtab = SymbolTable({"P": _p(p)})
        assert str(evaluate_expression("with_suffix(P, '.png')", values=symtab)).endswith(
            "render.png"
        )

    def test_path_from_string(self) -> None:
        assert (
            str(evaluate_expression("path('/tmp/test')", path_format=PathFormat.POSIX))
            == "/tmp/test"
        )

    def test_path_from_list(self) -> None:
        result = str(evaluate_expression('path(["a", "b", "c"])'))
        assert result == str(PurePath("a", "b", "c"))

    def test_path_from_parts_roundtrip(self, tmp_path) -> None:
        # Reconstruct a path from its parts and verify it matches
        p = tmp_path / "a" / "b" / "c"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("path(P.parts) == P", values=symtab)
        assert result.item() is True

    def test_path_from_sliced_parts(self, tmp_path) -> None:
        p = tmp_path / "a" / "b" / "c" / "d"
        symtab = SymbolTable({"P": _p(p)})
        # Take first N parts that include root + 2 dirs
        result = str(evaluate_expression("path(P.parts[:3])", values=symtab))
        expected = str(PurePath(*p.parts[:3]))
        assert result == expected

    def test_path_from_parts_skip_root(self) -> None:
        # Skip root, get relative path
        result = str(evaluate_expression('path(path("/a/b/c").parts[1:])'))
        assert result == str(PurePath("a", "b", "c"))

    def test_path_from_parts_last_two(self) -> None:
        result = str(evaluate_expression('path(path("/a/b/c/d").parts[-2:])'))
        assert result == str(PurePath("c", "d"))

    def test_path_from_parts_reverse(self) -> None:
        result = str(evaluate_expression('path(path("a/b/c").parts[::-1])'))
        assert result == str(PurePath("c", "b", "a"))


class TestIsAbsolute:
    """Tests for is_absolute on filesystem and URI paths."""

    def test_posix_absolute(self) -> None:
        assert (
            evaluate_expression("path('/a/b').is_absolute()", path_format=PathFormat.POSIX).item()
            is True
        )

    def test_posix_relative(self) -> None:
        assert (
            evaluate_expression("path('a/b').is_absolute()", path_format=PathFormat.POSIX).item()
            is False
        )

    def test_windows_absolute(self) -> None:
        assert (
            evaluate_expression(
                r"path('C:\\a\\b').is_absolute()", path_format=PathFormat.WINDOWS
            ).item()
            is True
        )

    def test_windows_relative(self) -> None:
        assert (
            evaluate_expression("path('a/b').is_absolute()", path_format=PathFormat.WINDOWS).item()
            is False
        )

    def test_uri_always_absolute(self) -> None:
        assert (
            evaluate_expression(
                "path('s3://bucket/key').is_absolute()", path_format=PathFormat.POSIX
            ).item()
            is True
        )

    def test_empty_path(self) -> None:
        assert (
            evaluate_expression("path('').is_absolute()", path_format=PathFormat.POSIX).item()
            is False
        )

    def test_unc_absolute(self) -> None:
        assert (
            evaluate_expression(
                "path('//server/share/dir').is_absolute()", path_format=PathFormat.WINDOWS
            ).item()
            is True
        )

    def test_unc_absolute_posix(self) -> None:
        assert (
            evaluate_expression(
                "path('//server/share/dir').is_absolute()", path_format=PathFormat.POSIX
            ).item()
            is True
        )

    def test_windows_drive_on_posix_not_absolute(self) -> None:
        assert (
            evaluate_expression("path('C:/a/b').is_absolute()", path_format=PathFormat.POSIX).item()
            is False
        )


class TestIsRelativeTo:
    """Tests for is_relative_to on filesystem and URI paths."""

    def test_posix_true(self) -> None:
        assert (
            evaluate_expression(
                "path('/a/b/c').is_relative_to(path('/a/b'))", path_format=PathFormat.POSIX
            ).item()
            is True
        )

    def test_posix_false(self) -> None:
        assert (
            evaluate_expression(
                "path('/a/b/c').is_relative_to(path('/x/y'))", path_format=PathFormat.POSIX
            ).item()
            is False
        )

    def test_posix_same_path(self) -> None:
        assert (
            evaluate_expression(
                "path('/a/b').is_relative_to(path('/a/b'))", path_format=PathFormat.POSIX
            ).item()
            is True
        )

    def test_uri_true(self) -> None:
        assert (
            evaluate_expression(
                "path('s3://bucket/key/file').is_relative_to(path('s3://bucket/key'))",
                path_format=PathFormat.POSIX,
            ).item()
            is True
        )

    def test_uri_false_different_bucket(self) -> None:
        assert (
            evaluate_expression(
                "path('s3://bucket1/key').is_relative_to(path('s3://bucket2/key'))",
                path_format=PathFormat.POSIX,
            ).item()
            is False
        )

    def test_uri_same(self) -> None:
        assert (
            evaluate_expression(
                "path('s3://bucket/key').is_relative_to(path('s3://bucket/key'))",
                path_format=PathFormat.POSIX,
            ).item()
            is True
        )

    def test_uri_vs_filesystem(self) -> None:
        assert (
            evaluate_expression(
                "path('s3://bucket/key').is_relative_to(path('/a/b'))",
                path_format=PathFormat.POSIX,
            ).item()
            is False
        )

    def test_filesystem_vs_uri(self) -> None:
        assert (
            evaluate_expression(
                "path('/a/b').is_relative_to(path('s3://bucket'))",
                path_format=PathFormat.POSIX,
            ).item()
            is False
        )

    def test_unc_true(self) -> None:
        assert (
            evaluate_expression(
                "path('//server/share/dir/file').is_relative_to(path('//server/share'))",
                path_format=PathFormat.WINDOWS,
            ).item()
            is True
        )

    def test_unc_false(self) -> None:
        assert (
            evaluate_expression(
                "path('//server/share/dir').is_relative_to(path('//other/share'))",
                path_format=PathFormat.WINDOWS,
            ).item()
            is False
        )


class TestRelativeTo:
    """Tests for relative_to on filesystem and URI paths."""

    def test_posix_basic(self) -> None:
        result = evaluate_expression(
            "path('/a/b/c').relative_to(path('/a/b'))", path_format=PathFormat.POSIX
        )
        assert str(result) == "c"

    def test_posix_nested(self) -> None:
        result = evaluate_expression(
            "path('/a/b/c/d').relative_to(path('/a'))", path_format=PathFormat.POSIX
        )
        assert str(result) == "b/c/d"

    def test_posix_same_path(self) -> None:
        result = evaluate_expression(
            "path('/a/b').relative_to(path('/a/b'))", path_format=PathFormat.POSIX
        )
        assert str(result) == "."

    def test_posix_not_relative(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(
                "path('/a/b').relative_to(path('/x/y'))", path_format=PathFormat.POSIX
            )
        assert str(exc_info.value) == "".join(
            [
                "relative_to failed: '/a/b' is not relative to '/x/y'\n",
                "  path('/a/b').relative_to(path('/x/y'))\n",
                "  ~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_uri_basic(self) -> None:
        result = evaluate_expression(
            "path('s3://bucket/key/file.txt').relative_to(path('s3://bucket/key'))",
            path_format=PathFormat.POSIX,
        )
        assert str(result) == "file.txt"

    def test_uri_nested(self) -> None:
        result = evaluate_expression(
            "path('s3://bucket/a/b/c').relative_to(path('s3://bucket'))",
            path_format=PathFormat.POSIX,
        )
        assert str(result) == "a/b/c"

    def test_uri_same(self) -> None:
        result = evaluate_expression(
            "path('s3://bucket/key').relative_to(path('s3://bucket/key'))",
            path_format=PathFormat.POSIX,
        )
        assert str(result) == "."

    def test_uri_not_relative(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(
                "path('s3://bucket1/key').relative_to(path('s3://bucket2'))",
                path_format=PathFormat.POSIX,
            )
        assert str(exc_info.value) == "".join(
            [
                "relative_to failed: 's3://bucket1/key' is not relative to 's3://bucket2'\n",
                "  path('s3://bucket1/key').relative_to(path('s3://bucket2'))\n",
                "  ~~~~~~~~~~~~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_uri_vs_filesystem_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(
                "relative_to(path('/a/b'), 's3://bucket')",
                path_format=PathFormat.POSIX,
            )
        assert str(exc_info.value) == "".join(
            [
                "relative_to failed: '/a/b' is not relative to 's3://bucket'\n",
                "  relative_to(path('/a/b'), 's3://bucket')\n",
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_filesystem_vs_uri_error(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(
                'relative_to("s3://bucket/key", path("/a"))',
                path_format=PathFormat.POSIX,
            )
        assert str(exc_info.value) == "".join(
            [
                "No matching signature for relative_to(string, path)\n",
                '  relative_to("s3://bucket/key", path("/a"))\n',
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )

    def test_unc_basic(self) -> None:
        result = evaluate_expression(
            "path('//server/share/dir/file').relative_to(path('//server/share'))",
            path_format=PathFormat.WINDOWS,
        )
        assert str(result) == "dir\\file"

    def test_unc_not_relative(self) -> None:
        with pytest.raises(ExpressionError) as exc_info:
            evaluate_expression(
                "relative_to(path('//server/share/a/b'), path('//other/share'))",
                path_format=PathFormat.WINDOWS,
            )
        assert str(exc_info.value) == "".join(
            [
                "relative_to failed: '\\\\server\\share\\a\\b' is not relative to '\\\\other\\share'\n",
                "  relative_to(path('//server/share/a/b'), path('//other/share'))\n",
                "  ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
            ]
        )


class TestPropertyAccessOnFunctionResults:
    """Tests for property access on function call results."""

    def test_path_name_on_function_result(self) -> None:
        assert evaluate_expression('path("/a/b/c.txt").name').item() == "c.txt"

    def test_path_stem_on_function_result(self) -> None:
        assert evaluate_expression('path("/a/b/c.txt").stem').item() == "c"

    def test_path_parent_on_function_result(self) -> None:
        result = str(evaluate_expression('path("/a/b/c.txt").parent'))
        assert result == str(PurePath("/a/b"))

    def test_chained_property_access(self) -> None:
        assert evaluate_expression('path("/a/b/c.txt").parent.name').item() == "b"

    def test_repeated_parent_access(self, tmp_path) -> None:
        p = tmp_path / "a" / "b" / "c" / "d" / "file.txt"
        symtab = SymbolTable({"P": _p(p)})
        assert str(evaluate_expression("P.parent", values=symtab)) == str(
            tmp_path / "a" / "b" / "c" / "d"
        )
        assert str(evaluate_expression("P.parent.parent", values=symtab)) == str(
            tmp_path / "a" / "b" / "c"
        )
        assert str(evaluate_expression("P.parent.parent.parent", values=symtab)) == str(
            tmp_path / "a" / "b"
        )

    def test_parent_then_name(self, tmp_path) -> None:
        p = tmp_path / "a" / "b" / "c" / "file.txt"
        symtab = SymbolTable({"P": _p(p)})
        assert evaluate_expression("P.parent.name", values=symtab).item() == "c"


class TestWithNumber:
    """Tests for with_number frame number substitution."""

    def test_digit_sequence(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_003.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_072.exr")

    def test_printf_04d(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_%04d.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_0072.exr")

    def test_printf_d(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_%d.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_72.exr")

    def test_hash_4(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_####.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_0072.exr")

    def test_hash_6(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_######.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_000072.exr")

    def test_with_variable(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot_####.exr"
        symtab = SymbolTable({"P": _p(p), "Frame": 42})
        result = evaluate_expression("P.with_number(Frame)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_0042.exr")

    def test_shot_number_preserved_digit_sequence(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot01_003.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot01_072.exr")

    def test_shot_number_preserved_hash(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot01_####.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot01_0072.exr")

    def test_multiple_hash_patterns_uses_last(self, tmp_path) -> None:
        p = tmp_path / "renders" / "##_shot_####.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "##_shot_0072.exr")

    def test_multiple_printf_uses_last(self, tmp_path) -> None:
        p = tmp_path / "renders" / "%02d_shot_%04d.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "%02d_shot_0072.exr")

    def test_no_pattern_appends_number(self, tmp_path) -> None:
        p = tmp_path / "renders" / "shot.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "shot_0072.exr")

    def test_multi_extension_vfx(self, tmp_path) -> None:
        """render.0001.exr — stem is render.0001, replaces digit sequence."""
        p = tmp_path / "renders" / "render.0001.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "render.0072.exr")

    def test_multi_extension_version(self, tmp_path) -> None:
        """file.v2.003.exr — stem is file.v2.003, replaces trailing digits."""
        p = tmp_path / "renders" / "file.v2.003.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "file.v2.072.exr")

    def test_digits_as_extension(self, tmp_path) -> None:
        """file.001 — digits are the extension, not the stem. Appends to stem."""
        p = tmp_path / "renders" / "file.001"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "file_0072.001")

    def test_mixed_printf_and_hash_rightmost_wins(self, tmp_path) -> None:
        """When patterns are mixed, the rightmost one is replaced."""
        p = tmp_path / "renders" / "f_%d_abcdefg_###.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(42)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "f_%d_abcdefg_042.exr")

    def test_mixed_printf_and_digits_rightmost_wins(self, tmp_path) -> None:
        p = tmp_path / "renders" / "file_%04d_003.exr"
        symtab = SymbolTable({"P": _p(p)})
        result = evaluate_expression("P.with_number(72)", values=symtab)
        assert str(result) == str(tmp_path / "renders" / "file_%04d_072.exr")

    def test_printf_padding_too_wide(self) -> None:
        with pytest.raises(ExpressionError, match="exceeds maximum"):
            evaluate_expression("'file_%099d.exr'.with_number(1)")

    def test_hash_padding_too_wide(self) -> None:
        with pytest.raises(ExpressionError, match="exceeds maximum"):
            evaluate_expression("'file_" + "#" * 33 + ".exr'.with_number(1)")


class TestPathFormatHashability:
    """``PathFormat`` is a pyclass enum; verify it is hashable so that
    callers can use it as a dict key or set member alongside the other
    enum-shaped pyclasses (``TypeCode``, ``ExprRevision``,
    ``ExprExtension``)."""

    def test_pathformat_hash_matches_self(self) -> None:
        # Same singleton hashes equal.
        assert hash(PathFormat.POSIX) == hash(PathFormat.POSIX)
        assert hash(PathFormat.WINDOWS) == hash(PathFormat.WINDOWS)
        assert hash(PathFormat.URI) == hash(PathFormat.URI)

    def test_pathformat_distinct_variants_distinct_hash(self) -> None:
        # Three distinct variants → three distinct hashes (no
        # accidental collisions).
        h = {hash(PathFormat.POSIX), hash(PathFormat.WINDOWS), hash(PathFormat.URI)}
        assert len(h) == 3

    def test_pathformat_usable_as_set_member(self) -> None:
        s = {PathFormat.POSIX, PathFormat.WINDOWS}
        assert PathFormat.POSIX in s
        assert PathFormat.URI not in s

    def test_pathformat_usable_as_dict_key(self) -> None:
        d = {PathFormat.POSIX: "p", PathFormat.WINDOWS: "w", PathFormat.URI: "u"}
        assert d[PathFormat.POSIX] == "p"
        assert d[PathFormat.WINDOWS] == "w"
        assert d[PathFormat.URI] == "u"
