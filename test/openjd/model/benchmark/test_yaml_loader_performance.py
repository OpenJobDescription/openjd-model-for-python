# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Benchmark tests for YAML loader performance comparison between CSafeLoader and SafeLoader.

This module provides comprehensive benchmarking of YAML parsing performance with different
loader implementations, testing both small and large template scenarios.
"""

import time
import statistics
import logging
from typing import Dict, List, Any, cast

import pytest
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("openjd.model.benchmark")


class YAMLLoaderBenchmark:
    """Benchmark suite for YAML loader performance testing."""

    def __init__(self) -> None:
        self.results: Dict[str, List[float]] = {}

    def create_small_template(self) -> str:
        """Create a small OpenJD template for testing."""
        return """
specificationVersion: jobtemplate-2023-09
name: SmallBenchmarkJob
description: A small template for performance testing
parameterDefinitions:
  - name: InputFile
    type: PATH
    objectType: FILE
    dataFlow: IN
  - name: OutputDir
    type: PATH
    objectType: DIRECTORY
    dataFlow: OUT
  - name: FrameRange
    type: STRING
    default: "1-10"
steps:
  - name: RenderStep
    description: Main rendering step
    parameterSpace:
      taskParameterDefinitions:
        - name: Frame
          type: INT
          range: "{{Param.FrameRange}}"
    script:
      actions:
        onRun:
          command: render
          args:
            - "--input"
            - "{{Param.InputFile}}"
            - "--output"
            - "{{Param.OutputDir}}/frame_{{Task.Param.Frame}}.exr"
            - "--frame"
            - "{{Task.Param.Frame}}"
          env:
            - name: RENDER_THREADS
              value: "4"
            - name: RENDER_QUALITY
              value: "high"
"""

    def create_large_template(self, num_steps: int = 50, num_params_per_step: int = 10) -> str:
        """Create a large OpenJD template for stress testing."""
        template_parts = [
            "specificationVersion: jobtemplate-2023-09",
            "name: LargeBenchmarkJob",
            "description: A large template for performance stress testing",
            "parameterDefinitions:",
        ]

        # Add global parameters
        for i in range(20):
            template_parts.extend(
                [
                    f"  - name: GlobalParam{i}",
                    "    type: STRING",
                    f'    default: "value{i}"',
                    f"    description: Global parameter {i} for testing",
                ]
            )

        template_parts.append("steps:")

        # Add multiple steps
        for step_idx in range(num_steps):
            template_parts.extend(
                [
                    f"  - name: Step{step_idx}",
                    f"    description: Processing step {step_idx}",
                    "    parameterSpace:",
                    "      taskParameterDefinitions:",
                ]
            )

            # Add task parameters for each step
            for param_idx in range(num_params_per_step):
                template_parts.extend(
                    [
                        f"        - name: TaskParam{param_idx}",
                        "          type: INT",
                        f'          range: "1-{param_idx + 5}"',
                    ]
                )

            template_parts.extend(
                [
                    '      combination: "('
                    + ", ".join([f"TaskParam{i}" for i in range(min(3, num_params_per_step))])
                    + ')"',
                    "    script:",
                    "      actions:",
                    "        onRun:",
                    f"          command: process_step_{step_idx}",
                    "          args:",
                ]
            )

            # Add multiple arguments
            for arg_idx in range(5):
                template_parts.append(
                    f'            - "--arg{arg_idx}={{{{Task.Param.TaskParam{arg_idx % num_params_per_step}}}}}"'
                )

            template_parts.extend(["          env:"])

            # Add environment variables
            for env_idx in range(3):
                template_parts.extend(
                    [
                        f"            - name: ENV_VAR_{env_idx}",
                        f'              value: "{{{{Param.GlobalParam{env_idx % 20}}}}}"',
                    ]
                )

            # Add dependencies for later steps
            if step_idx > 0:
                template_parts.extend(["    dependencies:"])
                # Add dependencies to previous steps
                for dep_idx in range(min(3, step_idx)):
                    template_parts.append(f"      - dependsOn: Step{dep_idx}")

        return "\n".join(template_parts)

    def benchmark_loader(
        self, template_content: str, loader_type: str, iterations: int = 10
    ) -> List[float]:
        """Benchmark a specific loader type with given template content."""

        times = []

        # Select the appropriate loader directly
        if loader_type == "CSafeLoader":
            try:
                from yaml import CSafeLoader as YamlLoader  # type: ignore[attr-defined]
            except ImportError:
                from yaml import SafeLoader as YamlLoader  # type: ignore[assignment]
        else:
            from yaml import SafeLoader as YamlLoader  # type: ignore[assignment]

        for _ in range(iterations):
            start_time = time.perf_counter()
            # Parse YAML directly instead of using document_string_to_object
            # to avoid the module-level loader selection
            yaml.load(template_content, Loader=YamlLoader)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds

        return times

    def run_benchmark_comparison(
        self, template_content: str, template_name: str, iterations: int = 10
    ) -> Dict[str, Dict[str, Any]]:
        """Run benchmark comparison between CSafeLoader and SafeLoader."""
        logger.info(f"=== BENCHMARKING {template_name.upper()} ===")
        logger.info(f"Template size: {len(template_content):,} characters")
        logger.info(f"Running {iterations} iterations per loader...")

        results = {}

        for loader_type in ["SafeLoader", "CSafeLoader"]:
            logger.info(f"Testing {loader_type}...")
            times = self.benchmark_loader(template_content, loader_type, iterations)

            stats = {
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "min": min(times),
                "max": max(times),
                "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
                "times": times,
            }

            results[loader_type] = stats

            logger.info(f"  Mean: {stats['mean']:.2f}ms")
            logger.info(f"  Median: {stats['median']:.2f}ms")
            logger.info(f"  Min: {stats['min']:.2f}ms")
            logger.info(f"  Max: {stats['max']:.2f}ms")
            logger.info(f"  StdDev: {stats['stdev']:.2f}ms")

        # Calculate performance improvement
        safe_mean = cast(float, results["SafeLoader"]["mean"])
        csafe_mean = cast(float, results["CSafeLoader"]["mean"])
        improvement = safe_mean / csafe_mean if csafe_mean > 0 else 0

        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"SafeLoader mean: {safe_mean:.2f}ms")
        logger.info(f"CSafeLoader mean: {csafe_mean:.2f}ms")
        logger.info(f"Performance improvement: {improvement:.1f}x faster")
        logger.info(f"Time saved per parse: {safe_mean - csafe_mean:.2f}ms")

        return results


class TestYAMLLoaderPerformance:
    """Test class for YAML loader performance benchmarks."""

    @pytest.fixture
    def benchmark_suite(self):
        """Fixture providing a benchmark suite instance."""
        return YAMLLoaderBenchmark()

    def test_small_template_performance(self, benchmark_suite):
        """Test performance with small templates."""
        template_content = benchmark_suite.create_small_template()
        results = benchmark_suite.run_benchmark_comparison(
            template_content, "Small Template", iterations=20
        )

        # Assertions to ensure CSafeLoader is faster
        csafe_mean = results["CSafeLoader"]["mean"]
        safe_mean = results["SafeLoader"]["mean"]

        assert (
            csafe_mean < safe_mean
        ), f"CSafeLoader ({csafe_mean:.2f}ms) should be faster than SafeLoader ({safe_mean:.2f}ms)"

        # Expect at least 2x improvement for small templates
        improvement = safe_mean / csafe_mean
        assert improvement >= 2.0, f"Expected at least 2x improvement, got {improvement:.1f}x"

    def test_large_template_performance(self, benchmark_suite):
        """Test performance with large templates."""
        template_content = benchmark_suite.create_large_template(
            num_steps=30, num_params_per_step=8
        )
        results = benchmark_suite.run_benchmark_comparison(
            template_content, "Large Template", iterations=10
        )

        # Assertions to ensure CSafeLoader is faster
        csafe_mean = results["CSafeLoader"]["mean"]
        safe_mean = results["SafeLoader"]["mean"]

        assert (
            csafe_mean < safe_mean
        ), f"CSafeLoader ({csafe_mean:.2f}ms) should be faster than SafeLoader ({safe_mean:.2f}ms)"

        # Expect at least 4x improvement for large templates
        improvement = safe_mean / csafe_mean
        assert improvement >= 4.0, f"Expected at least 4x improvement, got {improvement:.1f}x"

    def test_extra_large_template_performance(self, benchmark_suite):
        """Test performance with extra large templates for stress testing."""
        template_content = benchmark_suite.create_large_template(
            num_steps=100, num_params_per_step=15
        )
        results = benchmark_suite.run_benchmark_comparison(
            template_content, "Extra Large Template", iterations=5
        )

        # Assertions to ensure CSafeLoader is faster
        csafe_mean = results["CSafeLoader"]["mean"]
        safe_mean = results["SafeLoader"]["mean"]

        assert (
            csafe_mean < safe_mean
        ), f"CSafeLoader ({csafe_mean:.2f}ms) should be faster than SafeLoader ({safe_mean:.2f}ms)"

        # Expect significant improvement for extra large templates
        improvement = safe_mean / csafe_mean
        assert improvement >= 5.0, f"Expected at least 5x improvement, got {improvement:.1f}x"

    def test_template_file_benchmark(self, benchmark_suite, tmp_path):
        """Test performance using temporary files."""
        # Create a medium-sized template
        template_content = benchmark_suite.create_large_template(
            num_steps=20, num_params_per_step=6
        )

        # Write to temporary file
        temp_file = tmp_path / "benchmark_template.yaml"
        temp_file.write_text(template_content)

        # Read and benchmark
        file_content = temp_file.read_text()
        results = benchmark_suite.run_benchmark_comparison(
            file_content, f"File-based Template ({temp_file.name})", iterations=15
        )

        # Verify file was processed correctly
        assert len(file_content) > 1000, "Template file should be substantial"

        # Performance assertions
        csafe_mean = results["CSafeLoader"]["mean"]
        safe_mean = results["SafeLoader"]["mean"]
        improvement = safe_mean / csafe_mean

        assert improvement >= 3.0, f"Expected at least 3x improvement, got {improvement:.1f}x"
