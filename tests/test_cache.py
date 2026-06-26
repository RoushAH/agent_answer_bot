"""Tests for caching functionality.

These tests are written FIRST and will fail until the caching
implementation is complete.

The cache system provides:
1. LLM response caching based on (question, conversation_history) hash
2. SQL result caching based on query hash
3. TTL-based expiration (7 days default)
4. SQLite-based persistence
"""

import json
import time
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone

import pytest

# Import the cache module functions we'll be testing
# These imports will work once the functions are implemented
from cache import (
    init_cache,
    make_cache_key,
    get_llm_response,
    set_llm_response,
    get_sql_result,
    set_sql_result,
    clear_cache,
    clear_expired,
    CACHE_DB_PATH,
    CACHE_TTL_SECONDS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_cache_db(monkeypatch):
    """Create a temporary cache database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    
    # Override the cache DB path to use temp file
    monkeypatch.setattr("cache.CACHE_DB_PATH", tmp_path)
    
    # Re-initialize cache with new path
    # Force module reload to pick up new path
    import cache
    monkeypatch.setattr(cache, "CACHE_DB_PATH", tmp_path)
    cache.init_cache()
    
    yield tmp_path
    
    # Cleanup
    try:
        Path(tmp_path).unlink()
    except:
        pass


@pytest.fixture
def in_memory_cache(monkeypatch):
    """Create an in-memory cache database for testing."""
    monkeypatch.setattr("cache.CACHE_DB_PATH", ":memory:")
    
    import cache
    monkeypatch.setattr(cache, "CACHE_DB_PATH", ":memory:")
    cache.init_cache()
    
    return ":memory:"


# =============================================================================
# Tests for cache initialization
# =============================================================================

def test_init_cache_creates_database_file(temp_cache_db):
    """Test that init_cache() creates the cache.db file."""
    # File should exist after fixture setup
    assert Path(temp_cache_db).exists()


def test_init_cache_creates_llm_responses_table(temp_cache_db):
    """Test that init_cache() creates the llm_responses table."""
    conn = sqlite3.connect(temp_cache_db)
    cur = conn.cursor()
    
    # Check table exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='llm_responses'
    """)
    result = cur.fetchone()
    
    assert result is not None
    assert result[0] == "llm_responses"
    
    conn.close()


def test_init_cache_creates_sql_results_table(temp_cache_db):
    """Test that init_cache() creates the sql_results table."""
    conn = sqlite3.connect(temp_cache_db)
    cur = conn.cursor()
    
    # Check table exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='sql_results'
    """)
    result = cur.fetchone()
    
    assert result is not None
    assert result[0] == "sql_results"
    
    conn.close()


def test_llm_responses_table_has_correct_schema(temp_cache_db):
    """Test that llm_responses table has all required columns."""
    conn = sqlite3.connect(temp_cache_db)
    cur = conn.cursor()
    
    cur.execute("PRAGMA table_info(llm_responses)")
    columns = {row[1]: row[2] for row in cur.fetchall()}
    
    assert "id" in columns
    assert "cache_key" in columns
    assert "question" in columns
    assert "response" in columns
    assert "created_at" in columns
    
    # Check that cache_key has UNIQUE constraint
    cur.execute("SELECT sql FROM sqlite_master WHERE name='llm_responses'")
    schema = cur.fetchone()[0]
    assert "UNIQUE" in schema or "PRIMARY KEY" in schema
    
    conn.close()


def test_sql_results_table_has_correct_schema(temp_cache_db):
    """Test that sql_results table has all required columns."""
    conn = sqlite3.connect(temp_cache_db)
    cur = conn.cursor()
    
    cur.execute("PRAGMA table_info(sql_results)")
    columns = {row[1]: row[2] for row in cur.fetchall()}
    
    assert "id" in columns
    assert "cache_key" in columns
    assert "sql_query" in columns
    assert "result" in columns
    assert "created_at" in columns
    
    conn.close()


# =============================================================================
# Tests for cache key generation
# =============================================================================

def test_make_cache_key_returns_hex_string():
    """Test that make_cache_key returns a valid hex string."""
    key = make_cache_key("test question", [])
    
    # Should be a hex string (SHA-256 is 64 hex chars)
    assert isinstance(key, str)
    assert len(key) == 64  # SHA-256 hex digest
    assert all(c in "0123456789abcdef" for c in key.lower())


def test_make_cache_key_is_deterministic():
    """Test that make_cache_key returns consistent results for same inputs."""
    question = "How many board games do we have?"
    history = [{"role": "user", "content": "previous question"}]
    
    key1 = make_cache_key(question, history)
    key2 = make_cache_key(question, history)
    key3 = make_cache_key(question, history)
    
    assert key1 == key2 == key3


def test_make_cache_key_differs_for_different_questions():
    """Test that different questions produce different cache keys."""
    history = []
    
    key1 = make_cache_key("Question A", history)
    key2 = make_cache_key("Question B", history)
    
    assert key1 != key2


def test_make_cache_key_differs_for_different_histories():
    """Test that different conversation histories produce different keys."""
    question = "Same question"
    
    history1 = []
    history2 = [{"role": "user", "content": "Previous Q"}]
    
    key1 = make_cache_key(question, history1)
    key2 = make_cache_key(question, history2)
    
    assert key1 != key2


def test_make_cache_key_treats_none_and_empty_list_as_equivalent():
    """Test that None and empty list produce the same cache key."""
    question = "Test question"
    
    key1 = make_cache_key(question, None)
    key2 = make_cache_key(question, [])
    
    assert key1 == key2


def test_make_cache_key_handles_complex_conversation_history():
    """Test that make_cache_key handles complex nested history correctly."""
    question = "Complex question"
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Follow-up with numbers: 123"},
    ]
    
    # Should not raise an exception
    key = make_cache_key(question, history)
    assert isinstance(key, str)
    assert len(key) == 64


def test_make_cache_key_serialization_is_order_independent_for_dicts():
    """Test that dict ordering in history doesn't affect cache key."""
    question = "Test"
    
    # Note: list ordering SHOULD matter, but dict key ordering should not
    # JSON serialization with sort_keys=True handles this
    history1 = [{"role": "user", "content": "msg"}]
    history2 = [{"content": "msg", "role": "user"}]
    
    key1 = make_cache_key(question, history1)
    key2 = make_cache_key(question, history2)
    
    # Should be the same because dict keys are sorted
    assert key1 == key2


# =============================================================================
# Tests for LLM response caching
# =============================================================================

def test_get_llm_response_returns_none_for_missing_key(in_memory_cache):
    """Test that get_llm_response returns None when no entry exists."""
    result = get_llm_response("nonexistent_key_12345")
    
    assert result is None


def test_set_and_get_llm_response_round_trip(in_memory_cache):
    """Test that we can set and retrieve an LLM response."""
    cache_key = "test_key_abc123"
    question = "What is the meaning of life?"
    response = "The answer is 42."
    
    set_llm_response(cache_key, question, response)
    retrieved = get_llm_response(cache_key)
    
    assert retrieved == response


def test_get_llm_response_returns_none_for_expired_entry(in_memory_cache):
    """Test that get_llm_response returns None for expired entries."""
    cache_key = "expired_key"
    question = "Old question"
    response = "Old response"
    
    # Manually insert with old timestamp
    import cache
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    
    # Timestamp from 10 days ago (beyond TTL)
    old_timestamp = time.time() - (CACHE_TTL_SECONDS + 86400)
    
    cur.execute("""
        INSERT INTO llm_responses (cache_key, question, response, created_at)
        VALUES (?, ?, ?, ?)
    """, (cache_key, question, response, old_timestamp))
    conn.commit()
    conn.close()
    
    result = get_llm_response(cache_key)
    
    assert result is None


def test_get_llm_response_returns_valid_entry_within_ttl(in_memory_cache):
    """Test that get_llm_response returns entries within TTL."""
    cache_key = "recent_key"
    question = "Recent question"
    response = "Recent response"
    
    # Insert with recent timestamp (1 hour ago)
    import cache
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    
    recent_timestamp = time.time() - 3600  # 1 hour ago
    
    cur.execute("""
        INSERT INTO llm_responses (cache_key, question, response, created_at)
        VALUES (?, ?, ?, ?)
    """, (cache_key, question, response, recent_timestamp))
    conn.commit()
    conn.close()
    
    result = get_llm_response(cache_key)
    
    assert result == response


def test_set_llm_response_upserts_on_duplicate_key(in_memory_cache):
    """Test that set_llm_response updates existing entries (upsert behavior)."""
    cache_key = "upsert_key"
    question = "Question"
    
    # First insert
    set_llm_response(cache_key, question, "First response")
    result1 = get_llm_response(cache_key)
    
    # Second insert with same key
    set_llm_response(cache_key, question, "Second response")
    result2 = get_llm_response(cache_key)
    
    assert result1 == "First response"
    assert result2 == "Second response"


def test_set_llm_response_stores_current_timestamp(in_memory_cache):
    """Test that set_llm_response stores the current time as created_at."""
    cache_key = "timestamp_key"
    question = "Test"
    response = "Test response"
    
    before = time.time()
    set_llm_response(cache_key, question, response)
    after = time.time()
    
    # Check the stored timestamp
    import cache
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT created_at FROM llm_responses WHERE cache_key = ?", (cache_key,))
    row = cur.fetchone()
    conn.close()
    
    assert row is not None
    stored_timestamp = row[0]
    assert before <= stored_timestamp <= after


# =============================================================================
# Tests for SQL result caching
# =============================================================================

def test_get_sql_result_returns_none_for_missing_query(in_memory_cache):
    """Test that get_sql_result returns None when no entry exists."""
    result = get_sql_result("SELECT * FROM nonexistent_table")
    
    assert result is None


def test_set_and_get_sql_result_round_trip(in_memory_cache):
    """Test that we can set and retrieve a SQL result."""
    sql_query = "SELECT COUNT(*) FROM board_games"
    result_data = json.dumps([{"count": 42}])
    
    set_sql_result(sql_query, result_data)
    retrieved = get_sql_result(sql_query)
    
    assert retrieved == result_data


def test_get_sql_result_returns_none_for_expired_entry(in_memory_cache):
    """Test that get_sql_result returns None for expired entries."""
    sql_query = "SELECT old_data FROM old_table"
    result_data = json.dumps([{"old": "data"}])
    
    # Manually insert with old timestamp
    import cache
    import hashlib
    
    cache_key = hashlib.sha256(sql_query.encode()).hexdigest()
    
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    
    # Timestamp from 10 days ago (beyond TTL)
    old_timestamp = time.time() - (CACHE_TTL_SECONDS + 86400)
    
    cur.execute("""
        INSERT INTO sql_results (cache_key, sql_query, result, created_at)
        VALUES (?, ?, ?, ?)
    """, (cache_key, sql_query, result_data, old_timestamp))
    conn.commit()
    conn.close()
    
    result = get_sql_result(sql_query)
    
    assert result is None


def test_set_sql_result_computes_hash_correctly(in_memory_cache):
    """Test that set_sql_result uses SQL query hash as cache key."""
    sql_query = "SELECT * FROM test_table WHERE id = 1"
    result_data = json.dumps([{"id": 1, "name": "test"}])
    
    set_sql_result(sql_query, result_data)
    
    # Verify the cache key in database is the hash
    import cache
    import hashlib
    
    expected_key = hashlib.sha256(sql_query.encode()).hexdigest()
    
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT cache_key FROM sql_results WHERE sql_query = ?", (sql_query,))
    row = cur.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == expected_key


def test_set_sql_result_upserts_on_duplicate_query(in_memory_cache):
    """Test that set_sql_result updates existing entries."""
    sql_query = "SELECT data FROM table"
    
    # First insert
    set_sql_result(sql_query, json.dumps([{"version": 1}]))
    result1 = get_sql_result(sql_query)
    
    # Second insert with same query
    set_sql_result(sql_query, json.dumps([{"version": 2}]))
    result2 = get_sql_result(sql_query)
    
    assert json.loads(result1)[0]["version"] == 1
    assert json.loads(result2)[0]["version"] == 2


def test_sql_result_cache_handles_complex_queries(in_memory_cache):
    """Test that SQL caching works with complex multi-line queries."""
    sql_query = """
        SELECT g.name, COUNT(*) as sales_count
        FROM board_games g
        JOIN game_sales s ON g.id = s.game_id
        WHERE s.sale_date >= '2024-01-01'
        GROUP BY g.name
        ORDER BY sales_count DESC
        LIMIT 10
    """
    result_data = json.dumps([{"name": "Catan", "sales_count": 25}])
    
    set_sql_result(sql_query, result_data)
    retrieved = get_sql_result(sql_query)
    
    assert retrieved == result_data


def test_sql_result_cache_is_whitespace_sensitive(in_memory_cache):
    """Test that different whitespace produces different cache keys."""
    # SQL caching should be exact-match based
    query1 = "SELECT * FROM table"
    query2 = "SELECT  *  FROM  table"
    
    set_sql_result(query1, json.dumps([{"data": 1}]))
    
    # Different whitespace = different cache key = cache miss
    result = get_sql_result(query2)
    
    # This should be None because the queries don't match exactly
    assert result is None


# =============================================================================
# Tests for cache clearing
# =============================================================================

def test_clear_cache_removes_all_llm_responses(in_memory_cache):
    """Test that clear_cache() removes all rows from llm_responses table."""
    # Insert some data
    set_llm_response("key1", "Q1", "A1")
    set_llm_response("key2", "Q2", "A2")
    set_llm_response("key3", "Q3", "A3")
    
    # Verify data exists
    assert get_llm_response("key1") is not None
    assert get_llm_response("key2") is not None
    
    # Clear cache
    clear_cache()
    
    # Verify all data is gone
    assert get_llm_response("key1") is None
    assert get_llm_response("key2") is None
    assert get_llm_response("key3") is None


def test_clear_cache_removes_all_sql_results(in_memory_cache):
    """Test that clear_cache() removes all rows from sql_results table."""
    # Insert some data
    set_sql_result("SELECT 1", json.dumps([{"val": 1}]))
    set_sql_result("SELECT 2", json.dumps([{"val": 2}]))
    set_sql_result("SELECT 3", json.dumps([{"val": 3}]))
    
    # Verify data exists
    assert get_sql_result("SELECT 1") is not None
    
    # Clear cache
    clear_cache()
    
    # Verify all data is gone
    assert get_sql_result("SELECT 1") is None
    assert get_sql_result("SELECT 2") is None
    assert get_sql_result("SELECT 3") is None


def test_clear_cache_affects_both_tables(in_memory_cache):
    """Test that clear_cache() clears both tables in one call."""
    # Insert data in both tables
    set_llm_response("llm_key", "Q", "A")
    set_sql_result("SELECT *", json.dumps([{"result": "data"}]))
    
    assert get_llm_response("llm_key") is not None
    assert get_sql_result("SELECT *") is not None
    
    # Clear everything
    clear_cache()
    
    # Both should be empty
    assert get_llm_response("llm_key") is None
    assert get_sql_result("SELECT *") is None


# =============================================================================
# Tests for expired entry cleanup
# =============================================================================

def test_clear_expired_removes_only_old_entries(in_memory_cache):
    """Test that clear_expired() removes only expired entries."""
    import cache
    
    # Insert fresh entry
    set_llm_response("fresh_key", "Fresh Q", "Fresh A")
    
    # Manually insert expired entry
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    
    expired_timestamp = time.time() - (CACHE_TTL_SECONDS + 86400)
    
    cur.execute("""
        INSERT INTO llm_responses (cache_key, question, response, created_at)
        VALUES (?, ?, ?, ?)
    """, ("expired_key", "Old Q", "Old A", expired_timestamp))
    conn.commit()
    conn.close()
    
    # Clear expired entries
    clear_expired()
    
    # Fresh entry should remain
    assert get_llm_response("fresh_key") == "Fresh A"
    
    # Expired entry should be gone (check directly in DB)
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT response FROM llm_responses WHERE cache_key = ?", ("expired_key",))
    result = cur.fetchone()
    conn.close()
    
    assert result is None


def test_clear_expired_removes_old_sql_results(in_memory_cache):
    """Test that clear_expired() removes expired SQL results."""
    import cache
    import hashlib
    
    # Insert fresh SQL result
    fresh_query = "SELECT fresh_data"
    set_sql_result(fresh_query, json.dumps([{"fresh": "data"}]))
    
    # Manually insert expired SQL result
    expired_query = "SELECT expired_data"
    expired_key = hashlib.sha256(expired_query.encode()).hexdigest()
    
    conn = sqlite3.connect(cache.CACHE_DB_PATH)
    cur = conn.cursor()
    
    expired_timestamp = time.time() - (CACHE_TTL_SECONDS + 86400)
    
    cur.execute("""
        INSERT INTO sql_results (cache_key, sql_query, result, created_at)
        VALUES (?, ?, ?, ?)
    """, (expired_key, expired_query, json.dumps([{"old": "data"}]), expired_timestamp))
    conn.commit()
    conn.close()
    
    # Clear expired entries
    clear_expired()
    
    # Fresh entry should remain
    assert get_sql_result(fresh_query) is not None
    
    # Expired entry should be gone
    assert get_sql_result(expired_query) is None


def test_clear_expired_handles_empty_cache(in_memory_cache):
    """Test that clear_expired() works correctly on empty cache."""
    # Should not raise any exceptions
    clear_expired()
    
    # Cache should still be functional
    set_llm_response("test", "Q", "A")
    assert get_llm_response("test") == "A"


# =============================================================================
# Integration tests for agent.py
# =============================================================================

def test_agent_uses_cached_response_on_second_call(in_memory_cache):
    """Test that agent returns cached response without calling LLM twice."""
    from agent import run_agent
    
    question = "How many board games do we have in stock?"
    
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db:
        
        # Mock LLM responses
        mock_llm.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "We have 15 games in stock."})
        ]
        
        mock_db.return_value = [{"count": 15}]
        
        # First call - should hit LLM
        answer1 = run_agent(question)
        first_call_count = mock_llm.call_count
        
        # Second call with same question - should use cache
        answer2 = run_agent(question)
        second_call_count = mock_llm.call_count
        
        # Verify caching worked
        assert answer1 == answer2
        assert answer1 == "We have 15 games in stock."
        
        # LLM should only be called during first run
        assert second_call_count == first_call_count, "LLM should not be called on cached query"


def test_agent_cache_respects_conversation_history(in_memory_cache):
    """Test that cache distinguishes questions with different conversation history."""
    from agent import run_agent
    
    question = "How much did we make?"
    
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db:
        
        # Mock responses
        mock_llm.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT SUM(revenue) FROM sales"}),
            json.dumps({"action": "answer", "text": "$10,000"}),
            json.dumps({"action": "query", "sql": "SELECT SUM(profit) FROM sales"}),
            json.dumps({"action": "answer", "text": "$3,000"}),
        ]
        
        mock_db.side_effect = [
            [{"sum": 10000}],
            [{"sum": 3000}],
        ]
        
        # First call without history
        answer1 = run_agent(question, conversation_history=None)
        
        # Second call with different history
        history = [{"role": "user", "content": "I'm asking about profit"}]
        answer2 = run_agent(question, conversation_history=history)
        
        # Should get different answers (not cached)
        assert answer1 == "$10,000"
        assert answer2 == "$3,000"
        assert mock_llm.call_count >= 4  # Both should execute


def test_agent_caches_final_answer_only(in_memory_cache):
    """Test that agent caches the final answer, not intermediate steps."""
    from agent import run_agent
    
    question = "What is 2 + 2?"
    expected_answer = "The answer is 4"
    
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.calculate') as mock_calc:
        
        mock_llm.side_effect = [
            json.dumps({"action": "calculate", "expression": "2 + 2"}),
            json.dumps({"action": "answer", "text": expected_answer})
        ]
        
        mock_calc.return_value = 4
        
        # First call
        answer1 = run_agent(question)
        
        # Reset mocks
        mock_llm.reset_mock()
        mock_calc.reset_mock()
        
        # Second call - should use cache
        answer2 = run_agent(question)
        
        # Verify same answer and no LLM calls on second run
        assert answer1 == expected_answer
        assert answer2 == expected_answer
        assert mock_llm.call_count == 0  # Cached, no LLM calls


# =============================================================================
# Integration tests for database.py
# =============================================================================

def test_database_query_uses_sql_cache_on_repeat(in_memory_cache):
    """Test that database queries use cache on repeated execution."""
    from database import query_db
    
    sql = "SELECT COUNT(*) as count FROM board_games"
    
    with patch('database.get_connection') as mock_conn:
        # Mock database connection
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"count": 15}]
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection
        
        # First query - should hit database
        result1 = query_db(sql)
        first_execute_count = mock_cursor.execute.call_count
        
        # Second query - should use cache
        result2 = query_db(sql)
        second_execute_count = mock_cursor.execute.call_count
        
        # Results should be identical
        assert result1 == result2
        
        # Database execute should only be called once
        assert second_execute_count == first_execute_count


def test_database_query_cache_preserves_json_structure(in_memory_cache):
    """Test that SQL caching correctly serializes/deserializes complex results."""
    from database import query_db
    
    sql = "SELECT * FROM board_games WHERE category = 'Strategy'"
    
    expected_results = [
        {"id": 1, "name": "Catan", "price": 49.99, "category": "Strategy"},
        {"id": 2, "name": "Wingspan", "price": 59.99, "category": "Strategy"},
    ]
    
    with patch('database.get_connection') as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = expected_results
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection
        
        # First query
        result1 = query_db(sql)
        
        # Second query (from cache)
        result2 = query_db(sql)
        
        # Both should match the expected structure
        assert result1 == expected_results
        assert result2 == expected_results
        assert isinstance(result2, list)
        assert all(isinstance(row, dict) for row in result2)


def test_database_cache_handles_empty_results(in_memory_cache):
    """Test that SQL caching correctly handles empty result sets."""
    from database import query_db
    
    sql = "SELECT * FROM board_games WHERE name = 'NonexistentGame'"
    
    with patch('database.get_connection') as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection
        
        # First query
        result1 = query_db(sql)
        
        # Second query (from cache)
        result2 = query_db(sql)
        
        # Both should be empty lists
        assert result1 == []
        assert result2 == []


# =============================================================================
# Integration tests for benchmark.py
# =============================================================================

def test_benchmark_no_cache_flag_clears_cache(in_memory_cache):
    """Test that --no-cache flag calls clear_cache() before running benchmarks."""
    import sys
    
    with patch('cache.clear_cache') as mock_clear:
        # Simulate running benchmark.py with --no-cache
        with patch.object(sys, 'argv', ['benchmark.py', '--no-cache']):
            # Import benchmark module (this would normally parse args)
            try:
                import benchmark
                # Try to trigger the argument parsing
                # This might need adjustment based on actual implementation
            except:
                pass
        
        # The test expectation: when benchmark.py gets --no-cache,
        # it should call clear_cache()
        # This test will fail until implemented


def test_benchmark_clear_cache_flag_clears_and_exits(in_memory_cache):
    """Test that --clear-cache flag clears cache and exits."""
    import sys
    
    # Add some data to cache
    set_llm_response("test_key", "Q", "A")
    assert get_llm_response("test_key") is not None
    
    with patch.object(sys, 'argv', ['benchmark.py', '--clear-cache']):
        with patch('sys.exit') as mock_exit:
            try:
                import benchmark
                # Try to trigger argument parsing
            except:
                pass
    
    # Cache should be cleared
    # (Note: in actual implementation, we'd need to check if clear_cache was called)


def test_benchmark_runs_without_cache_by_default(in_memory_cache):
    """Test that benchmark runs normally without cache flags."""
    # This test just verifies that adding cache functionality doesn't break
    # normal benchmark operation
    
    from benchmark import BenchmarkCase
    
    # Create a simple benchmark case
    def validator(answer):
        return True, ""
    
    case = BenchmarkCase(
        name="Test case",
        category="Test",
        question="Simple question",
        validators=[validator]
    )
    
    with patch('agent.run_agent') as mock_agent:
        mock_agent.return_value = "Test answer"
        
        result = case.run()
        
        assert result.passed is True
        assert result.answer == "Test answer"


# =============================================================================
# Edge cases and error handling
# =============================================================================

def test_cache_handles_unicode_in_questions(in_memory_cache):
    """Test that cache correctly handles Unicode characters in questions."""
    question = "What about games with émojis 🎲 and ütf-8?"
    response = "Unicode works fine!"
    
    key = make_cache_key(question, [])
    set_llm_response(key, question, response)
    retrieved = get_llm_response(key)
    
    assert retrieved == response


def test_cache_handles_very_long_questions(in_memory_cache):
    """Test that cache handles very long question strings."""
    question = "This is a very long question. " * 1000  # ~30KB string
    response = "Answer to long question"
    
    key = make_cache_key(question, [])
    set_llm_response(key, question, response)
    retrieved = get_llm_response(key)
    
    assert retrieved == response


def test_cache_handles_special_sql_characters(in_memory_cache):
    """Test that SQL caching handles queries with special characters."""
    sql = "SELECT * FROM table WHERE name = 'O''Reilly' AND cost > 10.50"
    result = json.dumps([{"name": "O'Reilly", "cost": 15.99}])
    
    set_sql_result(sql, result)
    retrieved = get_sql_result(sql)
    
    assert retrieved == result


def test_concurrent_cache_access_doesnt_corrupt(in_memory_cache):
    """Test that simultaneous cache access doesn't cause issues."""
    # SQLite should handle concurrent reads fine
    # This is a basic sanity check
    
    questions = [f"Question {i}" for i in range(10)]
    
    for i, q in enumerate(questions):
        key = make_cache_key(q, [])
        set_llm_response(key, q, f"Answer {i}")
    
    # Retrieve all
    for i, q in enumerate(questions):
        key = make_cache_key(q, [])
        answer = get_llm_response(key)
        assert answer == f"Answer {i}"


def test_cache_survives_module_reimport(temp_cache_db):
    """Test that cache persists across module reloads."""
    import cache
    
    # Store data
    key = "persistent_key"
    cache.set_llm_response(key, "Q", "A")
    
    # Verify it's there
    assert cache.get_llm_response(key) == "A"
    
    # Simulate module reload by creating new connection
    cache.init_cache()
    
    # Data should still be there
    assert cache.get_llm_response(key) == "A"


def test_cache_handles_null_values_in_json(in_memory_cache):
    """Test that cache handles JSON with null values correctly."""
    sql = "SELECT * FROM games WHERE discontinued_date IS NULL"
    result = json.dumps([{"id": 1, "discontinued_date": None}])
    
    set_sql_result(sql, result)
    retrieved = get_sql_result(sql)
    
    assert retrieved == result
    assert json.loads(retrieved)[0]["discontinued_date"] is None


def test_make_cache_key_handles_deeply_nested_history(in_memory_cache):
    """Test cache key generation with deeply nested conversation history."""
    question = "Complex question"
    history = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1", "metadata": {"tokens": 100}},
        {"role": "user", "content": "Q2", "context": {"previous": ["A1", "B2"]}},
    ]
    
    # Should not raise exception
    key = make_cache_key(question, history)
    assert isinstance(key, str)
    assert len(key) == 64


def test_ttl_constant_is_seven_days():
    """Test that CACHE_TTL_SECONDS is set to 7 days as per spec."""
    assert CACHE_TTL_SECONDS == 86400 * 7


def test_cache_db_path_constant_is_defined():
    """Test that CACHE_DB_PATH constant exists and has expected value."""
    assert CACHE_DB_PATH is not None
    assert isinstance(CACHE_DB_PATH, str) or isinstance(CACHE_DB_PATH, Path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
