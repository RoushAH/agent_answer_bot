# Cache Feature - Test-Driven Development

## What Was Created

### Test File
**Location**: `tests/test_cache.py`
- **Lines**: 590
- **Test Functions**: 34
- **Status**: ✓ Created, ✗ All tests currently failing (expected - no implementation yet)

### Documentation Files
1. **TEST_CACHE_SUMMARY.md** - Comprehensive overview of all tests
2. **TEST_CACHE_DESIGN_MAPPING.md** - Maps tests to design document requirements
3. **TEST_CACHE_README.md** - This file

## Test Development Approach

Following **Test-Driven Development (TDD)** principles:

1. ✓ **Write tests FIRST** - Tests are written before implementation
2. ✗ **Tests fail initially** - Confirms tests are actually testing something
3. ⏳ **Implement feature** - Next step: create `cache.py`
4. ⏳ **Tests pass** - Verify implementation correctness
5. ⏳ **Refactor** - Improve code while keeping tests green

## Current Test Status

```
$ pytest tests/test_cache.py -v
ERROR: ModuleNotFoundError: No module named 'cache'
```

This is **expected and correct**! Tests should fail before implementation exists.

## Test Categories

### 1. Core Cache Functions (15 tests)
Tests for basic cache operations: hashing, storing, retrieving, TTL enforcement

### 2. Integration Tests (6 tests)
Tests for integration with:
- `agent.py` - Agent should use and populate cache
- `database.py` - Database should cache SQL results
- `benchmark.py` - Benchmark should support --no-cache flag

### 3. Edge Cases (13 tests)
Tests for:
- Unicode/emoji handling
- Very long content (10KB+)
- Empty strings and None values
- Concurrent operations
- Idempotent initialization

## Key Testing Patterns Used

### Fixtures
```python
@pytest.fixture
def temp_cache_db(tmp_path, monkeypatch):
    """Temporary database for test isolation"""
    
@pytest.fixture
def clean_cache(temp_cache_db):
    """Ensure clean state before/after each test"""
```

### Mocking Strategy
```python
# Mock LLM calls to verify cache hit
with patch('agent.call_llm') as mock_llm:
    result = run_agent(question)
    mock_llm.assert_not_called()  # Should use cache

# Mock time for TTL testing
with patch('time.time', return_value=future_time):
    cached = get_cached_answer(question, history)
    assert cached is None  # Expired
```

### Test Structure
```python
def test_feature_behavior_condition(clean_cache):
    """Clear docstring explaining what is tested."""
    # Arrange - Set up test data
    # Act - Execute the function being tested
    # Assert - Verify expected outcome
```

## Expected Implementation Interface

### Module: `cache.py`

```python
from pathlib import Path
import sqlite3
import hashlib
import json
import time

# Constants
CACHE_DB_PATH: Path = Path(__file__).parent / "agent_cache.db"
CACHE_TTL_DAYS: int = 7

# Hash Functions
def compute_question_hash(question: str) -> str:
    """SHA-256 hash of normalized question (lowercase, stripped)."""
    
def compute_history_hash(conversation_history: list[dict] | None) -> str:
    """SHA-256 hash of JSON-serialized history (sort_keys=True)."""
    
def compute_sql_hash(sql: str) -> str:
    """SHA-256 hash of SQL string (no normalization)."""

# Cache Operations - Answer Cache
def get_cached_answer(question: str, conversation_history: list[dict] | None) -> str | None:
    """Retrieve cached answer if exists and not expired."""
    
def set_cached_answer(question: str, conversation_history: list[dict] | None, answer: str) -> None:
    """Store answer in cache (INSERT OR REPLACE)."""

# Cache Operations - SQL Cache
def get_cached_sql_result(sql: str) -> str | None:
    """Retrieve cached SQL result if exists and not expired."""
    
def set_cached_sql_result(sql: str, result: str) -> None:
    """Store SQL result in cache (INSERT OR REPLACE)."""

# Cache Management
def init_cache() -> None:
    """Create cache database and tables (idempotent)."""
    
def clear_expired_cache() -> int:
    """Delete expired entries, return count deleted."""
    
def clear_all_cache() -> None:
    """Delete all cache entries."""
```

## Running Tests During Implementation

### Run all cache tests
```bash
pytest tests/test_cache.py -v
```

### Run specific test
```bash
pytest tests/test_cache.py::test_init_cache_creates_tables -v
```

### Run with coverage
```bash
pytest tests/test_cache.py --cov=cache --cov-report=html
```

### Run in watch mode (requires pytest-watch)
```bash
ptw tests/test_cache.py -- -v
```

## Implementation Checklist

Based on tests, implementation should include:

- [ ] Create `cache.py` in project root
- [ ] Define `CACHE_DB_PATH` and `CACHE_TTL_DAYS` constants
- [ ] Implement `init_cache()` - Create SQLite tables
  - [ ] `answer_cache` table with UNIQUE(question_hash, history_hash)
  - [ ] `sql_cache` table with UNIQUE(sql_hash)
- [ ] Implement hash functions (SHA-256)
  - [ ] `compute_question_hash()` - lowercase + strip normalization
  - [ ] `compute_history_hash()` - JSON with sort_keys=True
  - [ ] `compute_sql_hash()` - no normalization
- [ ] Implement cache getters (check TTL)
  - [ ] `get_cached_answer()`
  - [ ] `get_cached_sql_result()`
- [ ] Implement cache setters (INSERT OR REPLACE)
  - [ ] `set_cached_answer()`
  - [ ] `set_cached_sql_result()`
- [ ] Implement cache management
  - [ ] `clear_expired_cache()` - return deletion count
  - [ ] `clear_all_cache()`
- [ ] Integrate with `agent.py`
  - [ ] Import cache functions
  - [ ] Check cache before LLM call
  - [ ] Store answer after LLM call
- [ ] Integrate with `database.py`
  - [ ] Import cache functions
  - [ ] Check cache before SQL execution
  - [ ] Store result after SQL execution
- [ ] Integrate with `benchmark.py`
  - [ ] Add `--no-cache` flag
  - [ ] Call `clear_all_cache()` when flag present
  - [ ] Call `clear_expired_cache()` at startup
- [ ] Call `init_cache()` at module import time
- [ ] Run tests and verify all pass

## Success Criteria

✓ All 34 tests pass
✓ Code coverage > 90%
✓ No performance regression in benchmarks
✓ Benchmark runtime reduced from ~20 minutes on repeated runs

## Notes

- Tests use modern Python APIs (e.g., `datetime.now(datetime.UTC)` not deprecated `utcnow()`)
- Tests follow existing codebase patterns (see `test_plan_first_mode.py`, `test_streaming.py`)
- Fixtures ensure test isolation (temporary database per test)
- Comprehensive mocking prevents actual LLM/DB calls during testing
- Edge cases covered (unicode, long content, empty values, concurrent ops)

## Next Steps

1. Create `cache.py` with all required functions
2. Run tests iteratively: `pytest tests/test_cache.py -v`
3. Fix failures one by one until all green
4. Integrate with agent.py, database.py, benchmark.py
5. Run full test suite to ensure no regressions
6. Run benchmark to verify performance improvement

---

**Created**: 2026-06-29
**Test Framework**: pytest
**Python Version**: 3.12+
**Status**: Tests ready, awaiting implementation
