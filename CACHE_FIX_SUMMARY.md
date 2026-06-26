# Cache Implementation Test Fixes

## Problem
Tests were failing due to cache pollution between test runs. The SQLite cache was persisting across tests, causing:
1. Cached responses to be returned instead of mocked values
2. Tests to receive unexpected results from previous test runs
3. Mock assertions to fail because cached values bypassed the mocked functions

## Root Cause
The cache implementation in `cache.py` initializes a SQLite database on module import and persists data across test runs. Tests that mock LLM responses or database queries were still getting cached values from previous test executions.

## Solution
Added pytest fixtures to both test files to automatically clear the cache before and after each test:

### Files Modified:
1. **tests/test_plan_first_mode.py**
   - Added `clear_test_cache` fixture with `autouse=True`
   - Imports `clear_cache` from cache module
   - Clears cache before each test and after completion

2. **tests/test_streaming.py**
   - Added `clear_test_cache` fixture with `autouse=True`
   - Imports `clear_cache` from cache module
   - Clears cache before each test and after completion

### Implementation:
```python
from cache import clear_cache

@pytest.fixture(autouse=True)
def clear_test_cache():
    """Clear cache before each test to prevent test pollution."""
    clear_cache()
    yield
    clear_cache()
```

## Test Results
All 72 tests now pass consistently:
- 25 cache tests ✓
- 26 plan-first mode tests ✓
- 21 streaming tests ✓

## Key Insights
- The cache implementation itself was correct and working as designed
- The issue was entirely test isolation - tests needed to clean up shared state
- Using pytest's `autouse=True` fixture ensures cache clearing happens automatically for every test
- The fixture pattern (clear before, yield, clear after) ensures cleanup even if tests fail

## Future Recommendations
- Consider using a separate test cache database path for tests
- Could mock cache functions at the module level for unit tests
- Document the importance of cache clearing in test documentation
