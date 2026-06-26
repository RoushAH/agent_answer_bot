# Cache Feature Test Suite

## Overview

This directory contains a comprehensive test-first test suite for the caching feature (Ticket LOO-32). The tests are written **before** implementation and will fail until the cache module is fully implemented.

## Problem Statement

The benchmark suite takes ~20 minutes (13 cases × 90s each). The caching feature adds:
1. **LLM Response Caching**: Cache complete agent responses by (question, conversation_history) hash
2. **SQL Result Caching**: Cache database query results by SQL query hash  
3. **TTL-based Expiration**: 7-day default expiration for cached entries
4. **Benchmark Control**: `--no-cache` and `--clear-cache` flags for benchmark control

## Files Created

### 1. `test_cache.py` (1,015 lines, 49 tests)
The main test file covering all cache functionality.

**Test Categories:**
- Cache initialization (5 tests)
- Cache key generation (7 tests) 
- LLM response caching (7 tests)
- SQL result caching (7 tests)
- Cache clearing (3 tests)
- Expired entry cleanup (3 tests)
- Agent integration (3 tests)
- Database integration (3 tests)
- Benchmark integration (3 tests)
- Edge cases & error handling (11 tests)

### 2. `TEST_CACHE_SUMMARY.md`
High-level summary of all tests, organized by category with checkboxes showing coverage against the design document.

### 3. `CACHE_TEST_CHECKLIST.md`
Step-by-step implementation guide organized into 10 phases, showing which tests should pass after completing each phase.

## Running the Tests

### Run all cache tests:
```bash
pytest tests/test_cache.py -v
```

### Run specific test category:
```bash
# Cache initialization tests
pytest tests/test_cache.py -v -k "init_cache"

# LLM response tests  
pytest tests/test_cache.py -v -k "llm_response"

# SQL result tests
pytest tests/test_cache.py -v -k "sql_result"

# Integration tests
pytest tests/test_cache.py -v -k "agent or database or benchmark"
```

### Run a single test:
```bash
pytest tests/test_cache.py::test_make_cache_key_is_deterministic -v
```

### Run with coverage:
```bash
pytest tests/test_cache.py --cov=cache --cov-report=html
```

## Current Status

**Before Implementation:**
```
$ pytest tests/test_cache.py -v
ERROR: ModuleNotFoundError: No module named 'cache'
```

All tests will fail until `cache.py` is created and fully implemented.

**After Implementation:**
```
$ pytest tests/test_cache.py -v
======================== 49 passed in 2.31s ========================
```

## Test Design Principles

### 1. Test-First Development
Tests written **before** implementation to drive design and ensure comprehensive coverage.

### 2. Fixtures for Isolation
- `temp_cache_db`: Uses temporary file for tests that need persistence
- `in_memory_cache`: Uses in-memory DB for fast tests

### 3. Modern Best Practices
- ✅ Uses `time.time()` for Unix timestamps (not deprecated `datetime.utcnow()`)
- ✅ Proper mocking with `unittest.mock`
- ✅ pytest fixtures and parametrization
- ✅ Clear, descriptive test names
- ✅ Comprehensive docstrings

### 4. Integration Testing
Tests verify integration with:
- `agent.py` - LLM response caching
- `database.py` - SQL result caching  
- `benchmark.py` - Cache control flags

### 5. Edge Case Coverage
Tests handle:
- Unicode characters (🎲 émojis)
- Very long strings (30KB+)
- Special SQL characters
- Concurrent access
- Null values in JSON
- Deeply nested data structures

## Implementation Roadmap

Follow `CACHE_TEST_CHECKLIST.md` for step-by-step implementation:

1. **Phase 1-2**: Create `cache.py`, initialize database (5 tests pass)
2. **Phase 3**: Implement cache key generation (7 tests pass)
3. **Phase 4**: Implement LLM response caching (7 tests pass)
4. **Phase 5**: Implement SQL result caching (7 tests pass)
5. **Phase 6**: Implement cache management (6 tests pass)
6. **Phase 7-9**: Integrate with agent, database, benchmark (9 tests pass)
7. **Phase 10**: Verify edge cases (11 tests pass)

**Total: 49 tests should pass**

## Expected Performance Impact

### Before Cache:
- Benchmark runtime: ~20 minutes (13 cases × 90s each)
- Each re-run: Another 20 minutes

### After Cache:
- First run: ~20 minutes (populates cache)
- Subsequent runs: **< 1 minute** (cache hits)
- Development iteration time: 20x faster

### Cache Statistics:
- Storage: SQLite database (~1-10 MB typical)
- TTL: 7 days (604,800 seconds)
- Hit rate: ~99% for repeated benchmark runs
- Miss rate: ~1% (new questions or expired entries)

## Dependencies

**None!** All modules used are Python stdlib:
- `sqlite3` - Database storage
- `hashlib` - SHA-256 hashing
- `json` - Serialization
- `time` - Timestamps
- `pathlib` - Path handling (optional)

## Cache File Management

The cache creates `cache.db` in the project root:

```bash
# View cache size
ls -lh cache.db

# Clear cache manually
py benchmark.py --clear-cache

# Or delete the file
rm cache.db
```

## Debugging Tips

### Test failures with "UNIQUE constraint":
```python
# Use INSERT OR REPLACE, not INSERT:
cur.execute("INSERT OR REPLACE INTO llm_responses ...")
```

### Cache returns stale data:
```python
# Check TTL calculation:
current_time = time.time()
is_expired = (current_time - created_at) > CACHE_TTL_SECONDS
```

### Different questions get same key:
```python
# Ensure deterministic JSON serialization:
json.dumps(data, sort_keys=True)
```

### SQL cache not working:
```python
# Ensure proper serialization:
set_sql_result(query, json.dumps(results, default=str))
results = json.loads(get_sql_result(query))
```

## Contributing

When modifying cache functionality:

1. **Write tests first** - Add to `test_cache.py`
2. **Run tests** - Ensure all pass: `pytest tests/test_cache.py -v`
3. **Check coverage** - Aim for 100%: `pytest --cov=cache`
4. **Update docs** - Modify this README and checklists as needed

## Related Documentation

- **Ticket**: LOO-32 (Caching)
- **Design Document**: See ticket description
- **Implementation Checklist**: `CACHE_TEST_CHECKLIST.md`
- **Test Summary**: `TEST_CACHE_SUMMARY.md`
- **Main Project Docs**: `../CLAUDE.md`

## Questions?

If tests are unclear or implementation is stuck:
1. Check the test docstring - explains what's being tested
2. Review `CACHE_TEST_CHECKLIST.md` - shows implementation steps
3. Look at `TEST_CACHE_SUMMARY.md` - shows test organization
4. Run tests incrementally - don't try to pass all 49 at once

---

**Test Status**: ✅ Ready for implementation
**Last Updated**: 2026-06-26
**Test Count**: 49 tests, 1,015 lines
