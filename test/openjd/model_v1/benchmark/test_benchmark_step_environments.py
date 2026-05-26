# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import time
import cProfile
import pstats
import io
import logging
import pytest
from openjd.model._v1 import create_job, decode_job_template

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("openjd.model.benchmark")


class TestBenchmarkStepEnvironmentsPerformance:
    """Benchmark class to verify performance with large numbers of step environments."""

    def test_job_template_with_many_total_step_environments(self):
        """
        Benchmark that a job template with many total step environments across multiple steps is processed efficiently.

        This test creates steps with many environments each and verifies the processing time.
        """
        # Create a job template with multiple steps, each with step environments
        num_steps = 100  # Create 100 steps
        num_step_envs_per_step = 200  # 200 environments per step

        logger.info(
            f"CREATING JOB TEMPLATE WITH {num_steps} STEPS AND {num_step_envs_per_step} ENVIRONMENTS PER STEP"
        )

        steps = []
        for step_num in range(num_steps):
            steps.append(
                {
                    "name": f"TestStep{step_num}",
                    "script": {
                        "actions": {"onRun": {"command": "echo", "args": [f"Step {step_num}"]}}
                    },
                    "stepEnvironments": [
                        {"name": f"stepEnv{step_num}_{i}", "variables": {"key": f"value{i}"}}
                        for i in range(num_step_envs_per_step)
                    ],
                }
            )

        job_template_with_many_total_envs = {
            "specificationVersion": "jobtemplate-2023-09",
            "name": "Test Job with Many Total Step Environments",
            "steps": steps,
        }

        logger.info("STARTING JOB TEMPLATE PROCESSING")

        # Set up profiler
        profiler = cProfile.Profile()
        profiler.enable()

        start_time = time.time()

        try:
            # Create a proper JobTemplate object from the dictionary using decode_job_template
            job_template = decode_job_template(template=job_template_with_many_total_envs)

            # Call create_job with the JobTemplate object
            _ = create_job(job_template=job_template, job_parameter_values={})

            elapsed_time = time.time() - start_time
            logger.info(f"PERFORMANCE RESULT: create_job completed in {elapsed_time:.2f} seconds")

            # Disable profiler and print results
            profiler.disable()

            # Log the top 20 functions by cumulative time
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)
            logger.info("TOP 20 FUNCTIONS BY CUMULATIVE TIME:")
            for line in s.getvalue().splitlines():
                logger.info(line)

            # Log the top 20 functions by total time
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("time")
            ps.print_stats(20)
            logger.info("TOP 20 FUNCTIONS BY TOTAL TIME:")
            for line in s.getvalue().splitlines():
                logger.info(line)

            # Verify that the operation completed within a reasonable time
            assert (
                elapsed_time < 10
            ), f"Operation took {elapsed_time:.2f} seconds, which exceeds the 10 second threshold"

        except Exception as e:
            # Disable profiler in case of exception
            profiler.disable()

            elapsed_time = time.time() - start_time
            logger.error(
                f"ERROR: create_job failed in {elapsed_time:.2f} seconds with error: {str(e)}"
            )

            # Log profiling information even in case of failure
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)
            logger.info("TOP 20 FUNCTIONS BY CUMULATIVE TIME (BEFORE ERROR):")
            for line in s.getvalue().splitlines():
                logger.info(line)

            pytest.fail(f"create_job failed with error: {str(e)}")
