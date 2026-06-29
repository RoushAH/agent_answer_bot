# Test-to-Design Mapping

This document maps each test function to its corresponding item in the design document's test plan.

## Design Test Plan → Implementation Mapping

| Design Test # | Test Function Name | Status | Notes |
|--------------|-------------------|---------|-------|
| Test 1 | `test_init_cache_creates_tables` | ✓ | Verifies both tables + schema |
| Test 2 | `test_compute_question_hash_is_deterministic` | ✓ | + normalization test |
| Test 3 | `test_compute_history_hash_is_deterministic` | ✓ | + None/empty list test |
| Test 4 | `test_compute_history_hash_handles_key_ordering` | ✓ | JSON sort_keys verification |
| Test 5 | `test_compute_sql_hash_is_deterministic` | ✓ | Basic hash consistency |
| Test 6 | `test_get_cached_answer_returns_none_on_empty_cache` | ✓ | Cache miss behavior |
| Test 7 | `test_set_and_get_answer_cache_round_trip` | ✓ | Basic store/retrieve |
| Test 8 | `test_answer_cache_respects_ttl` | ✓ | 7-day expiration |
| Test 9 | `test_answer_cache_uses_both_question_and_history_as_key` | ✓ | Composite key verification |
| Test 10 | `test_answer_cache_insert_or_replace_updates_existing` | ✓ | Upsert behavior |
| Test 11 | `test_get_cached_sql_result_returns_none_on_empty_cache` | ✓ | SQL cache miss |
| Test 12 | `test_set_and_get_sql_cache_round_trip` | ✓ | SQL store/retrieve |
| Test 13 | `test_sql_cache_respects_ttl` | ✓ | SQL 7-day expiration |
| Test 14 | `test_clear_expired_cache_removes_old_entries` | ✓ | Selective cleanup |
| Test 15 | `test_clear_all_cache_removes_everything` | ✓ | Complete reset |
| Test 16 | `test_agent_returns_cached_answer_without_calling_llm` | ✓ | Agent cache hit |
| Test 17 | `test_agent_stores_answer_in_cache_after_llm_call` | ✓ | Agent cache write |
| Test 18 | `test_database_returns_cached_sql_result_without_executing_query` | ✓ | DB cache hit |
| Test 19 | `test_database_stores_sql_result_in_cache_after_execution` | ✓ | DB cache write |
| Test 20 | `test_benchmark_clear_all_cache_called_with_no_cache_flag` | ✓ | --no-cache flag |
| Test 21 | `test_benchmark_calls_clear_expired_cache_at_startup` | ✓ | Startup cleanup |

## Additional Edge Case Tests (Beyond Design Plan)

| Test Function Name | Purpose |
|-------------------|---------|
| `test_cache_handles_very_long_answer` | 10KB+ content |
| `test_cache_handles_unicode_content` | Unicode/emoji support |
| `test_cache_handles_json_in_sql_result` | Complex nested JSON |
| `test_multiple_concurrent_cache_operations` | Race condition safety |
| `test_cache_db_path_constant_exists` | Module constant verification |
| `test_cache_ttl_days_constant_exists` | TTL constant verification |
| `test_cache_survives_module_reload` | Persistence verification |
| `test_empty_question_does_not_crash` | Empty string handling |
| `test_none_answer_handled_correctly` | None value handling |
| `test_init_cache_called_multiple_times_is_safe` | Idempotency |
| `test_sql_with_whitespace_differences_cached_separately` | No SQL normalization |
| `test_compute_question_hash_normalizes_whitespace` | Extended Test 2 |
| `test_compute_history_hash_none_equals_empty_list` | Extended Test 3 |

## Test Coverage Summary

- **Design Plan Tests**: 21/21 implemented (100%)
- **Additional Edge Cases**: 13 tests
- **Total Tests**: 34 tests
- **Lines of Code**: ~590 lines

## Test Execution Order

Tests are designed to be independent and can run in any order. Fixtures ensure:
1. Each test gets a clean temporary database
2. No test pollution between runs
3. Automatic cleanup after test completion

## Mock Strategy

### Agent Integration Tests (16-17)
- Mock: `agent.call_llm`, `agent.call_ollama`, `agent.query_db`
- Verify: Cache functions called correctly, LLM skipped on cache hit

### Database Integration Tests (18-19)
- Mock: `database.get_connection`
- Verify: Cache functions called, DB connection skipped on cache hit

### Benchmark Integration Tests (20-21)
- Mock: Benchmark internals as needed
- Verify: Cache management functions called at appropriate times

## Key Design Decisions Reflected in Tests

1. **Hash Function Choice**: SHA-256 (64-char hex)
   - Test: Verify hash length and format
   
2. **Question Normalization**: Lowercase + strip
   - Test: Different whitespace/case produces same hash
   
3. **History Hashing**: JSON with sort_keys=True
   - Test: Key order independence
   
4. **SQL No-Normalization**: Exact string match
   - Test: Whitespace differences create different hashes
   
5. **TTL Implementation**: Unix timestamps (float)
   - Test: Mock time.time() to simulate expiration
   
6. **Upsert Strategy**: INSERT OR REPLACE
   - Test: Second write replaces first
   
7. **Cache Persistence**: SQLite file-based
   - Test: Survives module reload (new connection)

## Notes for Implementation

- All hash functions should use `hashlib.sha256().hexdigest()`
- Question normalization: `question.lower().strip()`
- History JSON: `json.dumps(history or [], sort_keys=True)`
- TTL check: `created_at > time.time() - (CACHE_TTL_DAYS * 86400)`
- Database file: Should be in project root as `agent_cache.db`
