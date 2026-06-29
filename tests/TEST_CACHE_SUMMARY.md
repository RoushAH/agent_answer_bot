# Cache Feature Test Suite Summary

## Overview
This test suite covers the caching functionality for the agent answer bot. Tests are written FIRST following TDD principles and will fail until implementation exists.

## Test File Created
- `tests/test_cache.py` - 590 lines, 38 test functions

## Test Coverage

### Core Functionality Tests (Tests 1-15)

1. **test_init_cache_creates_tables** - Verifies SQLite tables `answer_cache` and `sql_cache` are created with correct schema
2. **test_compute_question_hash_is_deterministic** - Ensures question hashing is consistent (SHA-256, 64 chars)
3. **test_compute_question_hash_normalizes_whitespace** - Verifies case/whitespace normalization
4. **test_compute_history_hash_is_deterministic** - Ensures conversation history hashing is consistent
5. **test_compute_history_hash_none_equals_empty_list** - Verifies None and [] produce same hash
6. **test_compute_history_hash_handles_key_ordering** - Verifies dict key order doesn't affect hash (sort_keys=True)
7. **test_compute_sql_hash_is_deterministic** - Ensures SQL hashing is consistent
8. **test_get_cached_answer_returns_none_on_empty_cache** - Verifies cache miss behavior
9. **test_set_and_get_answer_cache_round_trip** - Verifies basic store/retrieve cycle
10. **test_answer_cache_respects_ttl** - Verifies 7-day TTL enforcement
11. **test_answer_cache_uses_both_question_and_history_as_key** - Verifies composite key behavior
12. **test_answer_cache_insert_or_replace_updates_existing** - Verifies upsert behavior
13. **test_get_cached_sql_result_returns_none_on_empty_cache** - Verifies SQL cache miss
14. **test_set_and_get_sql_cache_round_trip** - Verifies SQL cache store/retrieve
15. **test_sql_cache_respects_ttl** - Verifies SQL cache TTL enforcement

### Cache Management Tests (Tests 14-15)
16. **test_clear_expired_cache_removes_old_entries** - Verifies selective expiration cleanup
17. **test_clear_all_cache_removes_everything** - Verifies complete cache reset

### Integration Tests (Tests 16-21)
18. **test_agent_returns_cached_answer_without_calling_llm** - Verifies agent uses cache and skips LLM
19. **test_agent_stores_answer_in_cache_after_llm_call** - Verifies agent caches new answers
20. **test_database_returns_cached_sql_result_without_executing_query** - Verifies database uses cache
21. **test_database_stores_sql_result_in_cache_after_execution** - Verifies database caches results
22. **test_benchmark_clear_all_cache_called_with_no_cache_flag** - Verifies --no-cache flag integration
23. **test_benchmark_calls_clear_expired_cache_at_startup** - Verifies automatic cleanup on startup

### Edge Case Tests (Additional)
24. **test_cache_handles_very_long_answer** - Verifies 10KB+ answers work
25. **test_cache_handles_unicode_content** - Verifies unicode/emoji support
26. **test_cache_handles_json_in_sql_result** - Verifies complex nested JSON storage
27. **test_multiple_concurrent_cache_operations** - Verifies concurrent operations don't interfere
28. **test_cache_db_path_constant_exists** - Verifies CACHE_DB_PATH is defined
29. **test_cache_ttl_days_constant_exists** - Verifies CACHE_TTL_DAYS is defined (> 0)
30. **test_cache_survives_module_reload** - Verifies persistence across connections
31. **test_empty_question_does_not_crash** - Verifies empty string handling
32. **test_none_answer_handled_correctly** - Verifies None value handling
33. **test_init_cache_called_multiple_times_is_safe** - Verifies idempotent initialization
34. **test_sql_with_whitespace_differences_cached_separately** - Verifies no SQL normalization

## Test Fixtures

### `temp_cache_db`
- Creates temporary cache database for each test
- Patches CACHE_DB_PATH to use temp location
- Auto-cleanup via pytest's tmp_path fixture

### `clean_cache`
- Ensures cache is empty before and after each test
- Calls clear_all_cache() for isolation
- Depends on temp_cache_db

## Expected Module Interface

### Constants
```python
CACHE_DB_PATH: Path | str  # Path to agent_cache.db
CACHE_TTL_DAYS: int | float  # Default: 7
```

### Functions
```python
def init_cache() -> None: ...
def compute_question_hash(question: str) -> str: ...
def compute_history_hash(conversation_history: list[dict] | None) -> str: ...
def compute_sql_hash(sql: str) -> str: ...
def get_cached_answer(question: str, conversation_history: list[dict] | None) -> str | None: ...
def set_cached_answer(question: str, conversation_history: list[dict] | None, answer: str) -> None: ...
def get_cached_sql_result(sql: str) -> str | None: ...
def set_cached_sql_result(sql: str, result: str) -> None: ...
def clear_expired_cache() -> int: ...
def clear_all_cache() -> None: ...
```

## Database Schema

### answer_cache table
- id: INTEGER PRIMARY KEY AUTOINCREMENT
- question_hash: TEXT NOT NULL
- history_hash: TEXT NOT NULL
- answer: TEXT NOT NULL
- created_at: REAL NOT NULL (Unix timestamp)
- UNIQUE(question_hash, history_hash)

### sql_cache table
- id: INTEGER PRIMARY KEY AUTOINCREMENT
- sql_hash: TEXT NOT NULL UNIQUE
- result: TEXT NOT NULL
- created_at: REAL NOT NULL (Unix timestamp)

## Running the Tests

```bash
# All cache tests
pytest tests/test_cache.py -v

# Specific test
pytest tests/test_cache.py::test_init_cache_creates_tables -v

# With coverage
pytest tests/test_cache.py --cov=cache --cov-report=html
```

## Current Status
✗ All tests FAIL (expected) - ModuleNotFoundError: No module named 'cache'

Once `cache.py` is implemented, these tests will verify correctness.

## Design Notes
- Uses SHA-256 for all hashing (64-char hex digests)
- Question hashing includes lowercase + strip normalization
- History hashing uses JSON with sort_keys=True for key-order independence
- SQL hashing has NO normalization (whitespace differences create separate cache entries)
- TTL uses Unix timestamps (float) for sub-second precision
- INSERT OR REPLACE strategy for upserts
- Cache initialization is idempotent (safe to call multiple times)

## Code Quality Standards Applied
- Modern Python datetime: Uses `time.time()` for Unix timestamps
- Proper pytest fixtures with cleanup
- Mocking for isolation (database, LLM calls)
- Clear test names following pattern: test_<component>_<behavior>_<condition>
- Comprehensive docstrings
- Edge case coverage (unicode, empty strings, None values, long content)
