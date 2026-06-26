# Cache Implementation Test Checklist

Use this checklist while implementing the cache feature to ensure all tests pass.

## Phase 1: Basic Cache Module Setup ✅

- [ ] Create `cache.py` in project root
- [ ] Import `sqlite3`, `hashlib`, `json`, `time` from stdlib
- [ ] Define constants:
  - [ ] `CACHE_DB_PATH = "cache.db"`
  - [ ] `CACHE_TTL_SECONDS = 86400 * 7` (7 days)

## Phase 2: Database Initialization ✅

- [ ] Implement `init_cache()` function
  - [ ] Creates/opens SQLite database at `CACHE_DB_PATH`
  - [ ] Creates `llm_responses` table with columns:
    - `id INTEGER PRIMARY KEY`
    - `cache_key TEXT UNIQUE NOT NULL`
    - `question TEXT`
    - `response TEXT NOT NULL`
    - `created_at REAL NOT NULL`
  - [ ] Creates `sql_results` table with columns:
    - `id INTEGER PRIMARY KEY`
    - `cache_key TEXT UNIQUE NOT NULL`
    - `sql_query TEXT`
    - `result TEXT NOT NULL`
    - `created_at REAL NOT NULL`
- [ ] Call `init_cache()` at module load time

**Tests to pass**: 5 initialization tests

## Phase 3: Cache Key Generation ✅

- [ ] Implement `make_cache_key(question, conversation_history)` function
  - [ ] Handle `None` conversation_history (treat as empty list)
  - [ ] Serialize question and history to deterministic JSON (use `sort_keys=True`)
  - [ ] Concatenate serialized strings
  - [ ] Return SHA-256 hex digest using `hashlib.sha256().hexdigest()`

**Tests to pass**: 7 cache key tests

## Phase 4: LLM Response Caching ✅

- [ ] Implement `get_llm_response(cache_key)` function
  - [ ] Query `llm_responses` table for matching `cache_key`
  - [ ] Check if `created_at` is within TTL (use `time.time()`)
  - [ ] Return `response` if found and valid, else `None`

- [ ] Implement `set_llm_response(cache_key, question, response)` function
  - [ ] Insert or replace row in `llm_responses`
  - [ ] Store current timestamp using `time.time()`
  - [ ] Use UPSERT behavior (INSERT OR REPLACE in SQLite)

**Tests to pass**: 7 LLM response caching tests

## Phase 5: SQL Result Caching ✅

- [ ] Implement `get_sql_result(sql_query)` function
  - [ ] Compute SHA-256 hash of `sql_query` as cache key
  - [ ] Query `sql_results` table for matching key
  - [ ] Check TTL expiration
  - [ ] Return `result` if valid, else `None`

- [ ] Implement `set_sql_result(sql_query, result)` function
  - [ ] Compute SHA-256 hash of `sql_query`
  - [ ] Insert or replace row in `sql_results`
  - [ ] Store current timestamp
  - [ ] Result should be JSON string (caller serializes)

**Tests to pass**: 7 SQL result caching tests

## Phase 6: Cache Management ✅

- [ ] Implement `clear_cache()` function
  - [ ] Delete all rows from `llm_responses` table
  - [ ] Delete all rows from `sql_results` table

- [ ] Implement `clear_expired()` function
  - [ ] Delete rows from `llm_responses` where `created_at < (now - TTL)`
  - [ ] Delete rows from `sql_results` where `created_at < (now - TTL)`

**Tests to pass**: 6 cache clearing/expiration tests

## Phase 7: Agent Integration ✅

Modify `agent.py`:

- [ ] Import cache functions at top:
  ```python
  from cache import make_cache_key, get_llm_response, set_llm_response
  ```

- [ ] In main agent function (before LLM loop):
  - [ ] Compute cache key: `cache_key = make_cache_key(question, conversation_history)`
  - [ ] Check cache: `cached = get_llm_response(cache_key)`
  - [ ] If cached, return immediately: `return cached`

- [ ] After agent produces final answer:
  - [ ] Store in cache: `set_llm_response(cache_key, question, final_answer)`
  - [ ] Return answer

**Tests to pass**: 3 agent integration tests

## Phase 8: Database Integration ✅

Modify `database.py`:

- [ ] Import cache functions at top:
  ```python
  from cache import get_sql_result, set_sql_result
  ```

- [ ] In query execution function (e.g., `query_db`):
  - [ ] Before executing: `cached = get_sql_result(sql_query)`
  - [ ] If cached: deserialize and return: `return json.loads(cached)`
  - [ ] After executing: serialize results: `result_json = json.dumps(results, default=str)`
  - [ ] Store in cache: `set_sql_result(sql_query, result_json)`
  - [ ] Return results

**Tests to pass**: 3 database integration tests

## Phase 9: Benchmark Integration ✅

Modify `benchmark.py`:

- [ ] Import cache function at top:
  ```python
  from cache import clear_cache
  ```

- [ ] Add command-line argument parsing (if not exists):
  - [ ] Add `--no-cache` argument
  - [ ] When present, call `clear_cache()` before running benchmarks
  
- [ ] Add `--clear-cache` argument:
  - [ ] When present, call `clear_cache()` and exit

**Tests to pass**: 3 benchmark integration tests

## Phase 10: Edge Cases ✅

- [ ] Test with Unicode characters
- [ ] Test with very long strings
- [ ] Test with special SQL characters
- [ ] Test concurrent access (should work with SQLite)
- [ ] Test persistence across module reloads
- [ ] Test JSON with null values
- [ ] Test deeply nested data structures

**Tests to pass**: 11 edge case tests

## Running Tests

After each phase, run:
```bash
pytest tests/test_cache.py -v -k "phase_keyword"
```

Run all tests:
```bash
pytest tests/test_cache.py -v
```

## Success Criteria

✅ All 49 tests pass
✅ Benchmark runtime reduced from ~20 minutes to <1 minute on repeated runs
✅ No new dependencies added (all stdlib)
✅ `cache.db` file created automatically
✅ Documentation updated in `CLAUDE.md`

## Common Issues

**Issue**: Tests fail with "UNIQUE constraint failed"
**Fix**: Use `INSERT OR REPLACE` instead of `INSERT` for upsert behavior

**Issue**: Cache hits but returns stale data
**Fix**: Verify TTL check uses `time.time() - CACHE_TTL_SECONDS`

**Issue**: Different questions get same cache key
**Fix**: Ensure JSON serialization uses `sort_keys=True` and includes both question and history

**Issue**: SQL cache not working
**Fix**: Ensure results are serialized to JSON before storing and deserialized when retrieving

## Final Verification

Before submitting PR, verify:
- [ ] All tests pass: `pytest tests/test_cache.py -v`
- [ ] Benchmark works with cache: `py benchmark.py` (runs fast)
- [ ] Benchmark works without cache: `py benchmark.py --no-cache` (runs slow)
- [ ] Cache can be cleared: `py benchmark.py --clear-cache`
- [ ] No new dependencies in `requirements.txt`
- [ ] Documentation updated with cache info
