#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Fuzzer for openjd-model-for-python to ensure malformed templates
only raise DecodeValidationError or NotImplementedError.

Usage:
    CLI:    python test/openjd/model/test_fuzz.py [--num-tests N] [--seed S] [--verbose]
    pytest: pytest test/openjd/model/test_fuzz.py::test_fuzz
"""

import argparse
import random
import string
import sys
import time
import traceback
from typing import Optional

from openjd.model import (
    DecodeValidationError,
    DocumentType,
    decode_environment_template,
    decode_job_template,
    document_string_to_object,
)

EXPECTED_EXCEPTIONS = (DecodeValidationError, NotImplementedError)


def random_string(min_len=0, max_len=50):
    chars = string.printable + "\x00\x01\x1f"
    return "".join(random.choices(chars, k=random.randint(min_len, max_len)))


def random_value():
    return random.choice(
        [None, "", 0, -1, 123, 1.5, [], {}, True, False, random_string(1, 20), [1, 2, 3]]
    )


def fuzz_spec_version():
    return random.choice(
        [
            None,
            "",
            "invalid",
            "jobtemplate-2023-09",
            "environment-2023-09",
            123,
            "jobtemplate-9999-99",
            random_string(1, 30),
        ]
    )


def fuzz_format_string():
    return random.choice(
        [
            "{{",
            "{{}}",
            "{{Param.}}",
            "{{Param.Name",
            "}}",
            "{{{{nested}}}}",
            "{{" + random_string(1, 10) + "}}",
            "{{Param." + random_string(1, 10) + "}}",
            "normal string",
            "",
        ]
    )


def fuzz_cancelation():
    return random.choice(
        [
            None,
            {},
            {"mode": "NOTIFY_THEN_TERMINATE"},
            {"mode": "TERMINATE"},
            {"mode": "INVALID_MODE"},
            {"mode": random_string(1, 20)},
            {"mode": None},
            {"mode": 123},
            {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": 30},
            {"mode": "NOTIFY_THEN_TERMINATE", "notifyPeriodInSeconds": "invalid"},
            random_string(1, 10),
        ]
    )


def fuzz_task_parameter():
    return random.choice(
        [
            {},
            {"name": "P", "type": "INT", "range": "1-10"},
            {"name": "P", "type": "FLOAT", "range": [1.0, 2.0]},
            {"name": "P", "type": "STRING", "values": ["a", "b"]},
            {"name": "P", "type": "PATH", "values": ["/tmp"]},
            {"name": "P", "type": "INVALID_TYPE", "range": "1-10"},
            {"name": "P", "type": random_string(1, 15), "range": "1-10"},
            {"name": "P", "type": None},
            {"name": "P", "type": 123},
            {"type": "INT", "range": "1-10"},
            random_string(1, 10),
        ]
    )


def fuzz_step():
    base = {"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}
    mutations = [
        {},
        {"name": ""},
        {"name": random_string(1, 10)},
        {"name": "Step1", "script": {}},
        {"name": "Step1", "script": {"actions": {}}},
        {"name": "Step1", "script": {"actions": {"onRun": {}}}},
        {"name": "Step1", "script": {"actions": {"onRun": {"command": ""}}}},
        {
            "name": "Step1",
            "script": {
                "actions": {"onRun": {"command": "echo", "cancelation": fuzz_cancelation()}}
            },
        },
        {**base, "parameterSpace": {}},
        {**base, "parameterSpace": {"taskParameterDefinitions": []}},
        {**base, "parameterSpace": {"taskParameterDefinitions": [fuzz_task_parameter()]}},
        {
            **base,
            "parameterSpace": {
                "taskParameterDefinitions": [{"name": "P", "type": "INT", "range": "1-10"}]
            },
        },
        {**base, "dependencies": [{"dependsOn": random_string()}]},
        {**base, random_string(1, 10): random_value()},
        base,
    ]
    return random.choice(mutations)


def fuzz_job_parameter():
    return random.choice(
        [
            {},
            {"name": "Param1"},
            {"name": "Param1", "type": "STRING"},
            {"name": "Param1", "type": "INT"},
            {"name": "Param1", "type": "FLOAT"},
            {"name": "Param1", "type": "PATH"},
            {"name": "Param1", "type": "INVALID"},
            {"name": "Param1", "type": random_string(1, 15)},
            {"name": "Param1", "type": None},
            {"name": "Param1", "type": 123},
            {"name": "", "type": "STRING"},
            {"name": 123, "type": "STRING"},
            {"type": "STRING"},
            {"name": "P", "type": "INT", "minValue": 10, "maxValue": 5},
            {"name": "P", "type": "INT", "default": "notanint"},
            {"name": "P", "type": "STRING", "allowedValues": []},
            random_string(1, 10),
        ]
    )


def fuzz_job_template():
    base = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "TestJob",
        "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
    }

    mutations = [
        {},
        {"specificationVersion": fuzz_spec_version()},
        {"specificationVersion": "jobtemplate-2023-09"},
        {"specificationVersion": "jobtemplate-2023-09", "name": "Job"},
        {"specificationVersion": "jobtemplate-2023-09", "steps": []},
        {**base, "specificationVersion": None},
        {**base, "specificationVersion": "environment-2023-09"},
        {**base, "name": ""},
        {**base, "name": None},
        {**base, "name": 123},
        {**base, "name": fuzz_format_string()},
        {**base, "steps": []},
        {**base, "steps": None},
        {**base, "steps": "not a list"},
        {**base, "steps": [fuzz_step() for _ in range(random.randint(1, 3))]},
        {**base, "steps": [{}]},
        {**base, "parameterDefinitions": []},
        {**base, "parameterDefinitions": [fuzz_job_parameter()]},
        {**base, "jobEnvironments": [{}]},
        {**base, random_string(1, 15): random_value()},
        base,
    ]
    return random.choice(mutations)


def fuzz_environment_template():
    base = {
        "specificationVersion": "environment-2023-09",
        "environment": {
            "name": "Env1",
            "script": {"actions": {"onEnter": {"command": "echo"}}},
        },
    }

    mutations = [
        {},
        {"specificationVersion": fuzz_spec_version()},
        {"specificationVersion": "environment-2023-09"},
        {"specificationVersion": "environment-2023-09", "environment": {}},
        {**base, "specificationVersion": None},
        {**base, "specificationVersion": "jobtemplate-2023-09"},
        {**base, "environment": {}},
        {**base, "environment": None},
        {**base, "environment": {"name": ""}},
        {**base, "environment": {"name": "Env", "script": {}}},
        {**base, random_string(1, 15): random_value()},
        base,
    ]
    return random.choice(mutations)


def fuzz_yaml_json_string():
    return random.choice(
        [
            "{}",
            "[]",
            "{",
            "[",
            '{"key": "value"}',
            '{"key": }',
            "key: value",
            "- item1\n- item2",
            "---\n...",
            "\x00",
            "",
            "null",
            "true",
            "123",
            '"string"',
            random_string(0, 100),
        ]
    )


def run_fuzzer(num_tests: int, seed: Optional[int], verbose: bool) -> bool:
    if seed is not None:
        random.seed(seed)
    else:
        seed = random.randint(0, 2**32 - 1)
        random.seed(seed)

    print(f"Fuzzing openjd-model with {num_tests} tests (seed={seed})...")
    start_time = time.time()

    crashes = []
    successes = 0

    for i in range(num_tests):
        test_type = random.choice(["job", "env", "doc_json", "doc_yaml"])

        try:
            if test_type == "job":
                template = fuzz_job_template()
                decode_job_template(template=template)
            elif test_type == "env":
                template = fuzz_environment_template()
                decode_environment_template(template=template)
            elif test_type == "doc_json":
                doc = fuzz_yaml_json_string()
                document_string_to_object(document=doc, document_type=DocumentType.JSON)
            else:
                doc = fuzz_yaml_json_string()
                document_string_to_object(document=doc, document_type=DocumentType.YAML)

            successes += 1

        except EXPECTED_EXCEPTIONS:
            successes += 1

        except Exception as e:
            crashes.append(
                {
                    "test_num": i,
                    "test_type": test_type,
                    "input": template if test_type in ("job", "env") else doc,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                }
            )
            if verbose:
                print(f"  CRASH #{i}: {type(e).__name__}: {e}")

        if verbose and (i + 1) % 1000 == 0:
            print(f"  Progress: {i + 1}/{num_tests}")

    elapsed = time.time() - start_time

    print(f"\n{'=' * 60}")
    print("FUZZING RESULTS")
    print(f"{'=' * 60}")
    print(f"Total tests:    {num_tests}")
    print(f"Successes:      {successes}")
    print(f"Crashes:        {len(crashes)}")
    print(f"Time:           {elapsed:.2f}s")
    print(f"Tests/second:   {num_tests / elapsed:.1f}")
    print(f"Seed:           {seed}")

    if crashes:
        print(f"\n{'=' * 60}")
        print("CRASH DETAILS (unexpected exceptions):")
        print(f"{'=' * 60}")
        for crash in crashes[:10]:
            print(f"\nTest #{crash['test_num']} ({crash['test_type']}):")
            print(f"  Error: {crash['error_type']}: {crash['error']}")
            print(f"  Input: {crash['input']!r}")
        if len(crashes) > 10:
            print(f"\n... and {len(crashes) - 10} more crashes")

    return len(crashes) == 0


def test_fuzz():
    """Fuzz test: all malformed inputs should raise DecodeValidationError or NotImplementedError."""
    assert run_fuzzer(num_tests=1000, seed=None, verbose=False)


def main():
    parser = argparse.ArgumentParser(description="Fuzz openjd-model template parsing")
    parser.add_argument(
        "--num-tests", "-n", type=int, default=10000, help="Number of tests (default: 10000)"
    )
    parser.add_argument("--seed", "-s", type=int, default=None, help="Random seed")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    success = run_fuzzer(args.num_tests, args.seed, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
