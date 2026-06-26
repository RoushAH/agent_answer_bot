# Cache Tests README

## Quick Start

Run all cache tests:
```bash
py -m pytest tests/test_cache.py -v
```

Run a specific test:
```bash
py -m pytest tests/test_cache.py::test_make_cache_key_returns_consistent_hash -v
```

## Current Status

**All tests currently FAIL** - This is EXPECTED and CORRECT!

The tests are written using Test-Driven Development (TDD). They define what cache.py should do BEFORE it is implemented.

Expected error:
```
ModuleNotFoundError: No module named 'cache'
```

## After Implementation

Once cache.py is implemented with all the required functions, run:
```bash
py -m pytest tests/test_cache.py -v
```

You should see:
```
========================= 25 PASSED =========================
```

## Test Structure

The test file contains:
- 2 pytest fixtures (temp_cache_db, clean_cache)
- 25 test functions covering:
  - Database initialization
  - Cache key generation
  - LLM response caching
  - SQL result caching
  - Cache management
  - Integration with agent and database
  - Edge cases and error handling
  - Performance tests

## Key Test Fixtures

### temp_cache_db
Creates a temporary SQLite database for testing. Each test gets a clean, isolated database that is automatically deleted after the test completes.

### clean_cache
Ensures each test starts with an empty cache by calling clear_cache() before and after each test.

## Test Categories

1. **Unit Tests** - Test individual cache functions in isolation
2. **Integration Tests** - Test cache integration with agent.py and database.py
3. **Edge Case Tests** - Test unusual inputs and error conditions
4. **Performance Tests** - Ensure cache operations are fast

## What The Tests Expect

### cache.py should export:
- `CACHE_DB_PATH` - Path to cache database file
- `CACHE_TTL_SECONDS` - Time-to-live for cache entries (7 days)
- `init_cache()` - Initialize database and tables
- `make_cache_key(question, conversation_history)` - Generate cache key
- `get_llm_response(cache_key)` - Retrieve cached LLM response
- `set_llm_response(cache_key, question, response)` - Store LLM response
- `get_sql_result(sql_query)` - Retrieve cached SQL result
- `set_sql_result(sql_query, result)` - Store SQL result
- `clear_cache()` - Delete all cache entries
- `clear_expired()` - Delete only expired entries

### Database Schema

**llm_responses table:**
- id (INTEGER PRIMARY KEY)
- cache_key (TEXT UNIQUE NOT NULL)
- question (TEXT)
- response (TEXT NOT NULL)
- created_at (REAL NOT NULL)

**sql_results table:**
- id (INTEGER PRIMARY KEY)
- cache_key (TEXT UNIQUE NOT NULL)
- sql_query (TEXT)
- result (TEXT NOT NULL)
- created_at (REAL NOT NULL)

## Implementation Checklist

- [ ] Create cache.py
- [ ] Add constants (CACHE_DB_PATH, CACHE_TTL_SECONDS)
- [ ] Implement init_cache()
- [ ] Implement make_cache_key()
- [ ] Implement get_llm_response() and set_llm_response()
- [ ] Implement get_sql_result() and set_sql_result()
- [ ] Implement clear_cache() and clear_expired()
- [ ] Integrate with agent.py
- [ ] Integrate with database.py
- [ ] Add --no-cache flag to benchmark.py
- [ ] Run tests: All 25 should pass

## Documentation

See also:
- tests/TEST_CACHE_SUMMARY.md - Comprehensive test documentation
- TEST_CACHE_CREATED.md - Implementation checklist
- Design document - Complete specification

---
Created: 2026-06-26
