# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""URI-aware path operations through the expression evaluator.

Mirrors the public-API portion of the reference branch's
``test/openjd/expr/test_uri_paths.py``. The reference also tests
private helpers (``_uri_path.is_uri`` etc.) that the binding does not
expose; those tests live in the underlying Rust crate's integration
suite (``openjd-rs/crates/openjd-expr/tests/integration/``) and are
not duplicated here. The binding-side coverage exercises the same
end-to-end behaviour through ``evaluate_expression``.

The reference uses ``ExprValue.to_string()`` for the rendered URI;
the Rust-backed binding spells that as ``str(value)``. Identical
output, identical contract.
"""

from openjd.expr import ExprValue, PathFormat, SymbolTable, evaluate_expression


class TestUriPathExpressions:
    """URI-mode `path()` properties resolve through the evaluator."""

    def test_uri_name(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").name').item() == "file.obj"

    def test_uri_stem(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").stem').item() == "file"

    def test_uri_suffix(self) -> None:
        assert evaluate_expression('path("s3://bucket/dir/file.obj").suffix').item() == ".obj"

    def test_uri_suffixes(self) -> None:
        result = evaluate_expression('path("https://host/archive.tar.gz").suffixes')
        assert result.item() == [".tar", ".gz"]

    def test_uri_parent(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj").parent')
        assert str(result) == "s3://bucket/dir"

    def test_uri_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj").parts')
        assert result.item() == ["s3://bucket", "dir", "file.obj"]

    def test_uri_parent_chain(self) -> None:
        assert str(evaluate_expression('path("s3://bucket/a/b").parent')) == "s3://bucket/a"
        assert str(evaluate_expression('path("s3://bucket/a/b").parent.parent')) == "s3://bucket"
        # The authority component is the floor: parent of the bare
        # authority is itself.
        assert (
            str(evaluate_expression('path("s3://bucket/a/b").parent.parent.parent'))
            == "s3://bucket"
        )

    def test_uri_bare_authority(self) -> None:
        assert evaluate_expression('path("s3://bucket").name').item() == ""
        assert evaluate_expression('path("s3://bucket").parts').item() == ["s3://bucket"]
        assert str(evaluate_expression('path("s3://bucket").parent')) == "s3://bucket"


class TestUriPathNoNormalization:
    """URI path portions are preserved verbatim — no segment
    collapsing or dot-segment resolution."""

    def test_double_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a//b/file.txt")')
        assert str(result) == "s3://bucket/a//b/file.txt"

    def test_double_slash_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/a//b/file.txt").parts')
        assert result.item() == ["s3://bucket", "a", "", "b", "file.txt"]

    def test_triple_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a///b")')
        assert str(result) == "s3://bucket/a///b"

    def test_dot_segments_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/./b/../c")')
        assert str(result) == "s3://bucket/a/./b/../c"

    def test_dot_segments_parts(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/./b/../c").parts')
        assert result.item() == ["s3://bucket", "a", ".", "b", "..", "c"]

    def test_trailing_slash_preserved(self) -> None:
        result = evaluate_expression('path("s3://bucket/prefix/")')
        assert str(result) == "s3://bucket/prefix/"

    def test_roundtrip_via_parts(self) -> None:
        result = evaluate_expression(
            'path(path("s3://bucket/a//b/file.txt").parts) == path("s3://bucket/a//b/file.txt")'
        )
        assert result.item() is True


class TestUriPathOperators:
    """Operators on URI paths."""

    def test_join_string(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir") / "sub/file.obj"')
        assert str(result) == "s3://bucket/dir/sub/file.obj"

    def test_join_multi(self) -> None:
        result = evaluate_expression('path("s3://bucket") / "a" / "b" / "c.txt"')
        assert str(result) == "s3://bucket/a/b/c.txt"

    def test_join_absolute_replaces(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir") / path("/local/path")')
        assert str(result).endswith("/local/path")

    def test_join_trailing_slash_no_double(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/") / "file.obj"')
        assert str(result) == "s3://bucket/dir/file.obj"

    def test_concat(self) -> None:
        result = evaluate_expression('path("s3://bucket/file") + ".txt"')
        assert str(result) == "s3://bucket/file.txt"

    def test_with_suffix(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_suffix(".png")')
        assert str(result) == "s3://bucket/renders/scene.png"

    def test_with_name(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_name("other.obj")')
        assert str(result) == "s3://bucket/renders/other.obj"

    def test_with_stem(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/scene.exr").with_stem("final")')
        assert str(result) == "s3://bucket/renders/final.exr"

    def test_as_posix_identity(self) -> None:
        result = evaluate_expression('path("s3://bucket/a/b").as_posix()')
        assert result.item() == "s3://bucket/a/b"

    def test_with_number(self) -> None:
        result = evaluate_expression('path("s3://bucket/renders/shot_####.exr").with_number(42)')
        assert str(result) == "s3://bucket/renders/shot_0042.exr"


class TestUriPathConstruction:
    """URI paths can be built from a string or a parts list."""

    def test_from_string(self) -> None:
        result = evaluate_expression('path("s3://bucket/dir/file.obj")')
        assert str(result) == "s3://bucket/dir/file.obj"

    def test_from_parts(self) -> None:
        result = evaluate_expression('path(["s3://bucket", "dir", "file.obj"])')
        assert str(result) == "s3://bucket/dir/file.obj"

    def test_from_parts_with_empty_preserves_double_slash(self) -> None:
        result = evaluate_expression('path(["s3://bucket", "a", "", "b"])')
        assert str(result) == "s3://bucket/a//b"

    def test_from_parts_bare(self) -> None:
        result = evaluate_expression('path(["s3://bucket"])')
        assert str(result) == "s3://bucket"


class TestUriPathSchemeVariety:
    """A handful of common URI schemes round-trip through the evaluator."""

    def test_https(self) -> None:
        result = evaluate_expression('path("https://example.com/models/scene.obj")')
        assert str(result) == "https://example.com/models/scene.obj"
        assert (
            evaluate_expression('path("https://example.com/models/scene.obj").name').item()
            == "scene.obj"
        )

    def test_fsx(self) -> None:
        result = evaluate_expression('path("fsx://vol-123/data/file.bin").parts')
        assert result.item() == ["fsx://vol-123", "data", "file.bin"]

    def test_custom_scheme(self) -> None:
        result = evaluate_expression('path("my-scheme+2://server/path/file.txt").parent')
        assert str(result) == "my-scheme+2://server/path"


class TestUriPathInSymbolTable:
    """URI paths can be passed in as symbol-table entries."""

    def test_uri_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"P": ExprValue("s3://bucket/dir/file.obj", type="path", path_format=PathFormat.POSIX)}
        )
        assert (
            evaluate_expression("P.name", values=symtab, path_format=PathFormat.POSIX).item()
            == "file.obj"
        )
        assert (
            str(evaluate_expression("P.parent", values=symtab, path_format=PathFormat.POSIX))
            == "s3://bucket/dir"
        )

    def test_uri_join_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"Dir": ExprValue("s3://bucket/assets", type="path", path_format=PathFormat.POSIX)}
        )
        result = evaluate_expression(
            "Dir / 'sub' / 'file.obj'", values=symtab, path_format=PathFormat.POSIX
        )
        assert str(result) == "s3://bucket/assets/sub/file.obj"

    def test_uri_with_suffix_in_symtab(self) -> None:
        symtab = SymbolTable(
            {"P": ExprValue("s3://bucket/scene.exr", type="path", path_format=PathFormat.POSIX)}
        )
        result = evaluate_expression(
            "P.with_suffix('.png')", values=symtab, path_format=PathFormat.POSIX
        )
        assert str(result) == "s3://bucket/scene.png"
