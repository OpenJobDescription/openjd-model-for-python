# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Pytest configuration for expr tests."""

from hypothesis import settings

# Register hypothesis profiles for fuzz testing
settings.register_profile("extended", max_examples=10000)
settings.register_profile("quick", max_examples=100)
