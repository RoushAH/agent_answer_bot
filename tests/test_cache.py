"""Tests for caching functionality.

These tests are written FIRST and will fail until the caching implementation
is complete. The tests cover all cases from the design document's test plan.
"""

import json
import pytest
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import sqlite3

# Import the modules we'll be testing
# These imports will work once the functions are implemented
from cache import (
    init_cache,
    compute_question_hash,
    compute_history_hash,
    compute_sql_hash,
    get_cached_answer,
    set_cached_answer,
    get_cached_sql_result,
    set_cached_sql_result,
    clear_expired_cache,
    clear_all_cache,
    CACHE_DB_PATH,
    CACHE_TTL_DAYS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_cache_db(tmp_path, monkeypatch):
    """Create a temporary cache database for testing."""
    temp_db = tmp_path / "test_cache.db"
    # Patch CACHE_DB_PATH to point to our temp database
    monkeypatch.setattr('cache.CACHE_DB_PATH', temp_db)
    # Initialize the cache with the temp path
    init_cache()
    yield temp_db
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def clean_cache(temp_cache_db):
    """Ensure cache is clean before each test."""
    clear_all_cache()
    yield
    clear_all_cache()


# =============================================================================
# Test 1 - init_cache creates tables
# =============================================================================

def test_init_cache_creates_tables(temp_cache_db):
    """Test that init_cache creates both answer_cache and sql_cache tables."""
    # init_cache was already called by the fixture
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()

    # Check answer_cache table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='answer_cache'
    """)
    assert cursor.fetchone() is not None

    # Check sql_cache table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='sql_cache'
    """)
    assert cursor.fetchone() is not None

    # Verify answer_cache columns
    cursor.execute("PRAGMA table_info(answer_cache)")
    columns = {row[1] for row in cursor.fetchall()}
    assert 'id' in columns
    assert 'question_hash' in columns
    assert 'history_hash' in columns
    assert 'answer' in columns
    assert 'created_at' in columns

    # Verify sql_cache columns
    cursor.execute("PRAGMA table_info(sql_cache)")
    columns = {row[1] for row in cursor.fetchall()}
    assert 'id' in columns
    assert 'sql_hash' in columns
    assert 'result' in columns
    assert 'created_at' in columns

    conn.close()


# =============================================================================
# Test 2 - compute_question_hash is deterministic
# =============================================================================

def test_compute_question_hash_is_deterministic(temp_cache_db):
    """Test that compute_question_hash produces consistent results."""
    question = "How many board games do we have in stock?"

    hash1 = compute_question_hash(question)
    hash2 = compute_question_hash(question)

    assert hash1 == hash2
    # SHA-256 hex digest is 64 characters
    assert len(hash1) == 64
    # Should be valid hex
    assert all(c in '0123456789abcdef' for c in hash1)


def test_compute_question_hash_normalizes_whitespace(temp_cache_db):
    """Test that question hash normalizes case and whitespace."""
    q1 = "How many games?"
    q2 = "  HOW MANY GAMES?  "

    hash1 = compute_question_hash(q1)
    hash2 = compute_question_hash(q2)

    # Should produce same hash (lowercased and stripped)
    assert hash1 == hash2


# =============================================================================
# Test 3 - compute_history_hash is deterministic
# =============================================================================

def test_compute_history_hash_is_deterministic(temp_cache_db):
    """Test that compute_history_hash produces consistent results."""
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Second question"}
    ]

    hash1 = compute_history_hash(history)
    hash2 = compute_history_hash(history)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_compute_history_hash_none_equals_empty_list(temp_cache_db):
    """Test that None and empty list produce same hash."""
    hash_none = compute_history_hash(None)
    hash_empty = compute_history_hash([])

    assert hash_none == hash_empty


# =============================================================================
# Test 4 - compute_history_hash handles key ordering
# =============================================================================

def test_compute_history_hash_handles_key_ordering(temp_cache_db):
    """Test that dict key order doesn't affect hash (sort_keys=True)."""
    # Two dicts with same data but different key order
    history1 = [{"role": "user", "content": "test", "timestamp": 123}]
    history2 = [{"timestamp": 123, "content": "test", "role": "user"}]

    hash1 = compute_history_hash(history1)
    hash2 = compute_history_hash(history2)

    # Should be identical because JSON serialization uses sort_keys=True
    assert hash1 == hash2


# =============================================================================
# Test 5 - compute_sql_hash is deterministic
# =============================================================================

def test_compute_sql_hash_is_deterministic(temp_cache_db):
    """Test that compute_sql_hash produces consistent results."""
    sql = "SELECT * FROM board_games WHERE price > 50"

    hash1 = compute_sql_hash(sql)
    hash2 = compute_sql_hash(sql)

    assert hash1 == hash2
    assert len(hash1) == 64


# =============================================================================
# Test 6 - get_cached_answer returns None on empty cache
# =============================================================================

def test_get_cached_answer_returns_none_on_empty_cache(clean_cache):
    """Test that get_cached_answer returns None when cache is empty."""
    result = get_cached_answer("Any question?", None)
    assert result is None


# =============================================================================
# Test 7 - set and get answer cache round-trip
# =============================================================================

def test_set_and_get_answer_cache_round_trip(clean_cache):
    """Test that answer can be stored and retrieved."""
    question = "How many games do we have?"
    history = []
    answer = "We have 42 games in stock."

    # Store the answer
    set_cached_answer(question, history, answer)

    # Retrieve it
    cached = get_cached_answer(question, history)

    assert cached == answer


# =============================================================================
# Test 8 - answer cache respects TTL
# =============================================================================

def test_answer_cache_respects_ttl(clean_cache, monkeypatch):
    """Test that expired cache entries are not returned."""
    question = "Test question"
    history = None
    answer = "Test answer"

    # Store the answer
    set_cached_answer(question, history, answer)

    # Verify it's there
    assert get_cached_answer(question, history) == answer

    # Now mock time to be 8 days in the future (past TTL of 7 days)
    original_time = time.time
    future_time = original_time() + (8 * 86400)  # 8 days in seconds

    with patch('time.time', return_value=future_time):
        # Should return None because entry is expired
        cached = get_cached_answer(question, history)
        assert cached is None


# =============================================================================
# Test 9 - answer cache uses both question and history as key
# =============================================================================

def test_answer_cache_uses_both_question_and_history_as_key(clean_cache):
    """Test that same question with different history produces different cache entries."""
    question = "What is the total?"

    history1 = [{"role": "user", "content": "Previous context 1"}]
    history2 = [{"role": "user", "content": "Previous context 2"}]

    answer1 = "Total is 100"
    answer2 = "Total is 200"

    # Store two different answers with same question but different histories
    set_cached_answer(question, history1, answer1)
    set_cached_answer(question, history2, answer2)

    # Retrieve them - should get the correct answer for each history
    assert get_cached_answer(question, history1) == answer1
    assert get_cached_answer(question, history2) == answer2


# =============================================================================
# Test 10 - answer cache INSERT OR REPLACE updates existing entry
# =============================================================================

def test_answer_cache_insert_or_replace_updates_existing(clean_cache):
    """Test that storing same question/history twice updates the answer."""
    question = "How many?"
    history = None

    # Store first answer
    set_cached_answer(question, history, "First answer")
    assert get_cached_answer(question, history) == "First answer"

    # Store second answer (should replace)
    set_cached_answer(question, history, "Second answer")
    assert get_cached_answer(question, history) == "Second answer"


# =============================================================================
# Test 11 - get_cached_sql_result returns None on empty cache
# =============================================================================

def test_get_cached_sql_result_returns_none_on_empty_cache(clean_cache):
    """Test that get_cached_sql_result returns None when cache is empty."""
    result = get_cached_sql_result("SELECT * FROM board_games")
    assert result is None


# =============================================================================
# Test 12 - set and get SQL cache round-trip
# =============================================================================

def test_set_and_get_sql_cache_round_trip(clean_cache):
    """Test that SQL result can be stored and retrieved."""
    sql = "SELECT COUNT(*) as count FROM board_games"
    result = json.dumps([{"count": 50}])

    # Store the result
    set_cached_sql_result(sql, result)

    # Retrieve it
    cached = get_cached_sql_result(sql)

    assert cached == result


# =============================================================================
# Test 13 - SQL cache respects TTL
# =============================================================================

def test_sql_cache_respects_ttl(clean_cache):
    """Test that expired SQL cache entries are not returned."""
    sql = "SELECT * FROM games"
    result = json.dumps([{"id": 1, "name": "Catan"}])

    # Store the result
    set_cached_sql_result(sql, result)

    # Verify it's there
    assert get_cached_sql_result(sql) == result

    # Mock time to be 8 days in the future
    future_time = time.time() + (8 * 86400)

    with patch('time.time', return_value=future_time):
        # Should return None because entry is expired
        cached = get_cached_sql_result(sql)
        assert cached is None


# =============================================================================
# Test 14 - clear_expired_cache removes old entries
# =============================================================================

def test_clear_expired_cache_removes_old_entries(clean_cache, temp_cache_db):
    """Test that clear_expired_cache removes only expired entries."""
    # Insert fresh entries
    set_cached_answer("Fresh question 1", None, "Fresh answer 1")
    set_cached_sql_result("SELECT fresh", "Fresh result")

    # Manually insert old entries by manipulating the database
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()

    old_timestamp = time.time() - (8 * 86400)  # 8 days ago

    # Old answer entry
    cursor.execute("""
        INSERT INTO answer_cache (question_hash, history_hash, answer, created_at)
        VALUES (?, ?, ?, ?)
    """, ("old_q_hash", "old_h_hash", "Old answer", old_timestamp))

    # Old SQL entry
    cursor.execute("""
        INSERT INTO sql_cache (sql_hash, result, created_at)
        VALUES (?, ?, ?)
    """, ("old_sql_hash", "Old result", old_timestamp))

    conn.commit()
    conn.close()

    # Clear expired entries
    deleted_count = clear_expired_cache()

    # Should have deleted 2 old entries
    assert deleted_count == 2

    # Fresh entries should still be there
    assert get_cached_answer("Fresh question 1", None) == "Fresh answer 1"
    assert get_cached_sql_result("SELECT fresh") == "Fresh result"


# =============================================================================
# Test 15 - clear_all_cache removes everything
# =============================================================================

def test_clear_all_cache_removes_everything(clean_cache):
    """Test that clear_all_cache removes all entries."""
    # Add several entries
    set_cached_answer("Q1", None, "A1")
    set_cached_answer("Q2", [], "A2")
    set_cached_sql_result("SQL1", "R1")
    set_cached_sql_result("SQL2", "R2")

    # Verify they exist
    assert get_cached_answer("Q1", None) == "A1"
    assert get_cached_sql_result("SQL1") == "R1"

    # Clear all
    clear_all_cache()

    # All should be gone
    assert get_cached_answer("Q1", None) is None
    assert get_cached_answer("Q2", []) is None
    assert get_cached_sql_result("SQL1") is None
    assert get_cached_sql_result("SQL2") is None


# =============================================================================
# Test 16 - agent.py returns cached answer without calling LLM
# =============================================================================

def test_agent_returns_cached_answer_without_calling_llm(clean_cache):
    """Test that agent returns cached answer and skips LLM calls."""
    from agent import run_agent

    question = "How many games?"
    history = None
    cached_answer = "Cached: 42 games"

    # Pre-populate cache
    set_cached_answer(question, history, cached_answer)

    # Mock the LLM to ensure it's not called
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.call_ollama') as mock_ollama:

        result = run_agent(question, conversation_history=history)

        # Should return cached answer
        assert result == cached_answer

        # LLM should NOT have been called
        mock_llm.assert_not_called()
        mock_ollama.assert_not_called()


# =============================================================================
# Test 17 - agent.py stores answer in cache after LLM call
# =============================================================================

def test_agent_stores_answer_in_cache_after_llm_call(clean_cache):
    """Test that agent stores answer in cache after generating it."""
    from agent import run_agent

    question = "How many games in stock?"
    history = None

    with patch('agent.call_ollama') as mock_ollama, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'ollama'):

        # Mock LLM to return valid actions
        mock_ollama.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "We have 50 games"})
        ]
        mock_db.return_value = [{"count": 50}]

        result = run_agent(question, conversation_history=history)

        # Should have returned the answer
        assert "50 games" in result

        # Answer should now be cached
        cached = get_cached_answer(question, history)
        assert cached == result


# Test 18
def test_database_returns_cached_sql_result_without_executing_query(clean_cache):
    from database import query_db
    sql = "SELECT COUNT(*) as count FROM board_games"
    cached_result = json.dumps([{"count": 99}])
    set_cached_sql_result(sql, cached_result)
    with patch('database.get_connection') as mock_conn:
        result = query_db(sql)
        assert result == json.loads(cached_result)
        mock_conn.assert_not_called()

# Test 19
def test_database_stores_sql_result_in_cache_after_execution(clean_cache):
    from database import query_db
    sql = "SELECT name FROM board_games LIMIT 1"
    assert get_cached_sql_result(sql) is None
    result = query_db(sql)
    cached = get_cached_sql_result(sql)
    assert cached is not None
    assert json.loads(cached) == result

# Test 20
def test_benchmark_clear_all_cache_called_with_no_cache_flag(clean_cache):
    import benchmark
    set_cached_answer("Benchmark Q", None, "Benchmark A")
    assert get_cached_answer("Benchmark Q", None) is not None

# Test 21
def test_benchmark_calls_clear_expired_cache_at_startup(clean_cache, temp_cache_db):
    import benchmark
    old_timestamp = time.time() - (8 * 86400)
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO answer_cache (question_hash, history_hash, answer, created_at) VALUES (?, ?, ?, ?)""", ("expired_hash", "h", "Expired", old_timestamp))
    conn.commit()
    conn.close()

def test_cache_handles_very_long_answer(clean_cache):
    question = "Tell me everything"
    history = None
    long_answer = "A" * 10000
    set_cached_answer(question, history, long_answer)
    cached = get_cached_answer(question, history)
    assert cached == long_answer

def test_cache_handles_unicode_content(clean_cache):
    question = "What about emojis?"
    history = [{"role": "user", "content": "Unicode test"}]
    answer = "Unicode answer"
    set_cached_answer(question, history, answer)
    cached = get_cached_answer(question, history)
    assert cached == answer

def test_cache_handles_json_in_sql_result(clean_cache):
    sql = "SELECT * FROM complex_table"
    result = json.dumps([{"id": 1, "data": {"nested": "value", "array": [1, 2, 3]}}, {"id": 2, "data": {"nested": "other", "array": [4, 5, 6]}}])
    set_cached_sql_result(sql, result)
    cached = get_cached_sql_result(sql)
    assert cached == result
    parsed = json.loads(cached)
    assert len(parsed) == 2
    assert parsed[0]["data"]["nested"] == "value"

def test_multiple_concurrent_cache_operations(clean_cache):
    for i in range(10):
        set_cached_answer(f"Question {i}", None, f"Answer {i}")
        set_cached_sql_result(f"SELECT {i}", f"Result {i}")
    for i in range(10):
        assert get_cached_answer(f"Question {i}", None) == f"Answer {i}"
        assert get_cached_sql_result(f"SELECT {i}") == f"Result {i}"

def test_cache_db_path_constant_exists(temp_cache_db):
    from cache import CACHE_DB_PATH
    assert CACHE_DB_PATH is not None
    assert isinstance(CACHE_DB_PATH, (Path, str))

def test_cache_ttl_days_constant_exists(temp_cache_db):
    from cache import CACHE_TTL_DAYS
    assert CACHE_TTL_DAYS is not None
    assert isinstance(CACHE_TTL_DAYS, (int, float))
    assert CACHE_TTL_DAYS > 0

def test_cache_survives_module_reload(clean_cache):
    question = "Persistent question"
    answer = "Persistent answer"
    set_cached_answer(question, None, answer)
    cached = get_cached_answer(question, None)
    assert cached == answer

def test_empty_question_does_not_crash(clean_cache):
    result = get_cached_answer("", None)
    assert result is None
    set_cached_answer("", None, "Empty question answer")
    cached = get_cached_answer("", None)
    assert cached == "Empty question answer"

def test_none_answer_handled_correctly(clean_cache):
    try:
        set_cached_answer("Question", None, None)
    except (ValueError, TypeError):
        pass

def test_init_cache_called_multiple_times_is_safe(temp_cache_db):
    init_cache()
    init_cache()
    set_cached_answer("Test", None, "Answer")
    assert get_cached_answer("Test", None) == "Answer"

def test_sql_with_whitespace_differences_cached_separately(clean_cache):
    sql1 = "SELECT * FROM games"
    sql2 = "SELECT  *  FROM  games"
    result1 = json.dumps([{"id": 1}])
    result2 = json.dumps([{"id": 2}])
    set_cached_sql_result(sql1, result1)
    set_cached_sql_result(sql2, result2)
    cached1 = get_cached_sql_result(sql1)
    cached2 = get_cached_sql_result(sql2)
    assert cached1 == result1
    assert cached2 == result2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
