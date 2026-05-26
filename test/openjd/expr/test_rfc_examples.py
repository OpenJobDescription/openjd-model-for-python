# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for RFC 0005/0006/0007 example expressions."""

import sys
from openjd.expr import evaluate_expression, ExprValue, SymbolTable, TypeCode
from openjd.expr import PathFormat

HOST_PATH_FORMAT = PathFormat.WINDOWS if sys.platform == "win32" else PathFormat.POSIX


class TestRFCExamples:
    """Tests for all RFC example expressions."""

    # --- RFC 0005: Arithmetic on frame ranges ---
    def test_frame_range_arithmetic(self) -> None:
        symbols = SymbolTable(
            {
                "Param.FrameStart": 1,
                "Param.FrameEnd": 100,
                "Param.FramesPerTask": 10,
                "Task.Param.Frame": 21,
            }
        )
        result = evaluate_expression(
            "min(Task.Param.Frame + Param.FramesPerTask, Param.FrameEnd) - 1", values=symbols
        )
        assert result.item() == 30

    # --- RFC 0005: Conditional expressions ---
    def test_conditional_draft(self) -> None:
        symbols = SymbolTable({"Param.Quality": "draft"})
        assert (
            evaluate_expression("16 if Param.Quality == 'final' else 4", values=symbols).item() == 4
        )

    def test_conditional_final(self) -> None:
        symbols = SymbolTable({"Param.Quality": "final"})
        assert (
            evaluate_expression("16 if Param.Quality == 'final' else 4", values=symbols).item()
            == 16
        )

    # --- RFC 0005: List flattening / null dropping ---
    def test_verbose_true(self) -> None:
        symbols = SymbolTable({"Param.Verbose": True})
        assert (
            evaluate_expression("'--verbose' if Param.Verbose else null", values=symbols).item()
            == "--verbose"
        )

    def test_verbose_false(self) -> None:
        symbols = SymbolTable({"Param.Verbose": False})
        assert (
            evaluate_expression(
                "'--verbose' if Param.Verbose else null", values=symbols
            ).type.type_code
            == TypeCode.NULLTYPE
        )

    def test_quality_list_with_value(self) -> None:
        # Mirrors the RFC 0005 "args" use-case: a target type that
        # admits ``nulltype``, a single ``string``, or a
        # ``list[string]``. The conditional yields a homogeneous
        # ``list[string]`` (the int is converted to a string
        # explicitly via ``string(...)`` because per RFC 0005
        # "operators evaluate operands unconstrained" — list literal
        # heterogeneity is not papered over by the target type).
        # Exercises the public
        # ``evaluate_expression(target_type=...)`` surface, the
        # equivalent of the reference test's direct ``Evaluator``
        # call.
        from openjd.expr import ExprType

        symbols = SymbolTable({"Param": SymbolTable({"Quality": 5})})
        target_type = ExprType("nulltype | string | list[string]")
        result = evaluate_expression(
            "['--quality', string(Param.Quality)] if Param.Quality > 0 else null",
            values=symbols,
            target_type=target_type,
        )
        assert result.item() == ["--quality", "5"]
        assert result.type == ExprType("list[string]")

    def test_quality_list_branch_null(self) -> None:
        # Companion to ``test_quality_list_with_value``: when the
        # conditional takes the ``else`` branch, the result coerces
        # cleanly to the union's ``nulltype`` member.
        from openjd.expr import ExprType

        symbols = SymbolTable({"Param": SymbolTable({"Quality": 0})})
        target_type = ExprType("nulltype | string | list[string]")
        result = evaluate_expression(
            "['--quality', string(Param.Quality)] if Param.Quality > 0 else null",
            values=symbols,
            target_type=target_type,
        )
        assert result.type.type_code == TypeCode.NULLTYPE

    # --- RFC 0006: String manipulation ---
    def test_string_manipulation(self, tmp_path) -> None:
        input_file = tmp_path / "renders" / "scene_v2.exr"
        symbols = SymbolTable(
            {
                "Param.InputFile": ExprValue(
                    str(input_file), type="path", path_format=HOST_PATH_FORMAT
                )
            }
        )
        result = evaluate_expression(
            "Param.InputFile.stem.upper() + '_final' + Param.InputFile.suffix", values=symbols
        )
        assert result.item() == "SCENE_V2_final.exr"

    # --- RFC 0006: Path operations ---
    def test_path_with_suffix(self, tmp_path) -> None:
        input_file = tmp_path / "renders" / "scene.exr"
        output_dir = tmp_path / "output"
        symbols = SymbolTable(
            {
                "Param.InputFile": ExprValue(
                    str(input_file), type="path", path_format=HOST_PATH_FORMAT
                ),
                "Param.OutputDir": ExprValue(
                    str(output_dir), type="path", path_format=HOST_PATH_FORMAT
                ),
            }
        )
        result = evaluate_expression(
            "(Param.OutputDir / Param.InputFile.name).with_suffix('.png')", values=symbols
        )
        expected = str(output_dir / "scene.png")
        assert str(result) == expected

    # --- RFC 0006: Shell quoting ---
    def test_repr_sh_string(self) -> None:
        symbols = SymbolTable({"Task.Command": "echo 'hello world'"})
        result = evaluate_expression("repr_sh(Task.Command)", values=symbols)
        assert "echo" in result.item() and "hello world" in result.item()

    def test_repr_sh_list(self) -> None:
        symbols = SymbolTable({"args": ["file with spaces.txt", "--flag", "value"]})
        result = evaluate_expression("repr_sh(args)", values=symbols)
        assert "'file with spaces.txt'" in result.item()

    def test_repr_sh_list_path(self) -> None:
        """Test that repr_sh correctly handles list[path] by converting paths to strings."""
        result = evaluate_expression(
            "repr_sh([path('/tmp/a b.txt'), path('/tmp/c.txt')])",
            path_format=PathFormat.POSIX,
        )
        assert result.item() == "'/tmp/a b.txt' /tmp/c.txt"

    # --- RFC 0007: Boolean parameters ---
    def test_gpu_flag_true(self) -> None:
        symbols = SymbolTable({"Param.UseGpu": True})
        assert (
            evaluate_expression("'--gpu' if Param.UseGpu else null", values=symbols).item()
            == "--gpu"
        )

    def test_gpu_flag_false(self) -> None:
        symbols = SymbolTable({"Param.UseGpu": False})
        assert (
            evaluate_expression("'--gpu' if Param.UseGpu else null", values=symbols).type.type_code
            == TypeCode.NULLTYPE
        )
