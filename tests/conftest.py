"""Pytest configuration for test suite."""

import pytest
from cache import clear_all_cache


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clear cache before each test to ensure test isolation."""
    clear_all_cache()
    yield
    clear_all_cache()
