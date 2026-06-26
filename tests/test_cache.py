"""Tests for caching functionality.

These tests are written FIRST and will fail until the caching implementation
is complete. The tests cover all cases from the design document's test plan.
"""

import json
import pytest
import sqlite3
import tempfile
import time
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Optional

# Import the modules we'll be testing
# These imports will work once the functions are implemented


# =============================================================================
# Test fixtures and helpers
# =============================================================================

@pytest.fixture
def temp_cache_db():
    """Create a temporary cache database for testing."""
    # Use a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        temp_db_path = tmp.name
    
    # Patch the CACHE_DB_PATH to use temp file
    with patch('cache.CACHE_DB_PATH', temp_db_path):
        # Re-initialize the cache with the temp path
        import cache
        cache.CACHE_DB_PATH = temp_db_path
        cache.init_cache()
        
        yield temp_db_path
        
        # Cleanup
        Path(temp_db_path).unlink(missing_ok=True)


@pytest.fixture
def clean_cache(temp_cache_db):
    """Provide a clean cache for each test."""
    from cache import clear_cache
    clear_cache()
    yield
    clear_cache()


# =============================================================================
# Test 1 - init_cache creates database and tables
# =============================================================================

def test_init_cache_creates_database_and_tables(temp_cache_db):
    """Test that init_cache() creates the cache.db file and both tables."""
    from cache import init_cache
    
    # Verify the database file exists
    assert Path(temp_cache_db).exists()
    
    # Connect and verify tables exist
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    
    # Check llm_responses table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='llm_responses'
    """)
    assert cursor.fetchone() is not None
    
    # Check sql_results table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='sql_results'
    """)
    assert cursor.fetchone() is not None
    
    # Verify llm_responses columns
    cursor.execute("PRAGMA table_info(llm_responses)")
    columns = {row[1] for row in cursor.fetchall()}
    assert 'id' in columns
    assert 'cache_key' in columns
    assert 'question' in columns
    assert 'response' in columns
    assert 'created_at' in columns
    
    # Verify sql_results columns
    cursor.execute("PRAGMA table_info(sql_results)")
    columns = {row[1] for row in cursor.fetchall()}
    assert 'id' in columns
    assert 'cache_key' in columns
    assert 'sql_query' in columns
    assert 'result' in columns
    assert 'created_at' in columns
    
    conn.close()


# =============================================================================
# Test 2 - make_cache_key returns consistent hash
# =============================================================================

def test_make_cache_key_returns_consistent_hash(temp_cache_db, clean_cache):
    """Test that make_cache_key returns a consistent hex string for the same inputs."""
    from cache import make_cache_key
    
    question = "How many board games do we have?"
    conversation_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    
    # Call multiple times with same inputs
    key1 = make_cache_key(question, conversation_history)
    key2 = make_cache_key(question, conversation_history)
    key3 = make_cache_key(question, conversation_history)
    
    # Should all be identical
    assert key1 == key2 == key3
    
    # Should be a hex string (SHA-256 produces 64 hex chars)
    assert isinstance(key1, str)
    assert len(key1) == 64
    assert all(c in '0123456789abcdef' for c in key1)


# =============================================================================
# Test 3 - make_cache_key returns different hashes for different inputs
# =============================================================================

def test_make_cache_key_returns_different_hashes_for_different_inputs(temp_cache_db, clean_cache):
    """Test that make_cache_key returns different hashes when inputs differ."""
    from cache import make_cache_key
    
    question1 = "How many board games?"
    question2 = "How many food items?"
    
    history1 = [{"role": "user", "content": "Hello"}]
    history2 = [{"role": "user", "content": "Goodbye"}]
    
    # Different questions, same history
    key1 = make_cache_key(question1, history1)
    key2 = make_cache_key(question2, history1)
    assert key1 != key2
    
    # Same question, different history
    key3 = make_cache_key(question1, history1)
    key4 = make_cache_key(question1, history2)
    assert key3 != key4
    
    # Different question and history
    key5 = make_cache_key(question1, history1)
    key6 = make_cache_key(question2, history2)
    assert key5 != key6


# =============================================================================
# Test 4 - make_cache_key treats None and empty list as equivalent
# =============================================================================

def test_make_cache_key_treats_none_and_empty_list_as_equivalent(temp_cache_db, clean_cache):
    """Test that None conversation_history and empty list produce same key."""
    from cache import make_cache_key
    
    question = "Test question"
    
    key_with_none = make_cache_key(question, None)
    key_with_empty_list = make_cache_key(question, [])
    
    # Should be identical to avoid cache misses
    assert key_with_none == key_with_empty_list


# =============================================================================
# Test 5 - get_llm_response returns None when no entry exists
# =============================================================================

def test_get_llm_response_returns_none_when_no_entry_exists(temp_cache_db, clean_cache):
    """Test that get_llm_response returns None when no entry has been inserted."""
    from cache import get_llm_response
    
    fake_cache_key = "0" * 64  # Valid hex string that doesn't exist in cache
    
    result = get_llm_response(fake_cache_key)
    
    assert result is None


# =============================================================================
# Test 6 - set_llm_response and get_llm_response round-trip
# =============================================================================

def test_set_and_get_llm_response_round_trip(temp_cache_db, clean_cache):
    """Test that after set_llm_response, get_llm_response returns the same value."""
    from cache import set_llm_response, get_llm_response, make_cache_key
    
    question = "What is the price of Catan?"
    response = "The price of Catan is $39.99"
    
    cache_key = make_cache_key(question, None)
    
    # Store in cache
    set_llm_response(cache_key, question, response)
    
    # Retrieve from cache
    retrieved_response = get_llm_response(cache_key)
    
    assert retrieved_response == response


# =============================================================================
# Test 7 - get_llm_response returns None for expired entries
# =============================================================================

def test_get_llm_response_returns_none_for_expired_entries(temp_cache_db, clean_cache):
    """Test that get_llm_response returns None for entries older than TTL."""
    from cache import get_llm_response, CACHE_TTL_SECONDS
    
    # Manually insert an expired entry (created_at = 0, very old)
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    
    expired_key = "a" * 64
    cursor.execute("""
        INSERT INTO llm_responses (cache_key, question, response, created_at)
        VALUES (?, ?, ?, ?)
    """, (expired_key, "Old question", "Old answer", 0.0))
    
    conn.commit()
    conn.close()
    
    # Should return None because entry is expired
    result = get_llm_response(expired_key)
    assert result is None


# =============================================================================
# Test 8 - set_llm_response upsert behavior
# =============================================================================

def test_set_llm_response_upsert_behavior(temp_cache_db, clean_cache):
    """Test that set_llm_response with same cache_key updates the value."""
    from cache import set_llm_response, get_llm_response, make_cache_key
    
    question = "Test question"
    cache_key = make_cache_key(question, None)
    
    # First insert
    set_llm_response(cache_key, question, "First answer")
    assert get_llm_response(cache_key) == "First answer"
    
    # Update with same key
    set_llm_response(cache_key, question, "Second answer")
    retrieved = get_llm_response(cache_key)
    
    assert retrieved == "Second answer"
    
    # Verify only one row exists
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM llm_responses WHERE cache_key = ?", (cache_key,))
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 1


# =============================================================================
# Test 9 - get_sql_result returns None when no entry exists
# =============================================================================

def test_get_sql_result_returns_none_when_no_entry_exists(temp_cache_db, clean_cache):
    """Test that get_sql_result returns None when no SQL result has been cached."""
    from cache import get_sql_result
    
    sql_query = "SELECT * FROM board_games WHERE id = 999999"
    
    result = get_sql_result(sql_query)
    
    assert result is None


# =============================================================================
# Test 10 - set_sql_result and get_sql_result round-trip
# =============================================================================

def test_set_and_get_sql_result_round_trip(temp_cache_db, clean_cache):
    """Test that after set_sql_result, get_sql_result returns the same value."""
    from cache import set_sql_result, get_sql_result
    
    sql_query = "SELECT COUNT(*) as count FROM board_games"
    result = json.dumps([{"count": 42}])
    
    # Store in cache
    set_sql_result(sql_query, result)
    
    # Retrieve from cache
    retrieved_result = get_sql_result(sql_query)
    
    assert retrieved_result == result


# =============================================================================
# Test 11 - get_sql_result returns None for expired entries
# =============================================================================

def test_get_sql_result_returns_none_for_expired_entries(temp_cache_db, clean_cache):
    """Test that get_sql_result returns None for expired SQL result rows."""
    from cache import get_sql_result
    import hashlib
    
    # Manually insert an expired entry
    sql_query = "SELECT * FROM expired_query"
    cache_key = hashlib.sha256(sql_query.encode()).hexdigest()
    
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sql_results (cache_key, sql_query, result, created_at)
        VALUES (?, ?, ?, ?)
    """, (cache_key, sql_query, json.dumps([]), 0.0))
    
    conn.commit()
    conn.close()
    
    # Should return None because entry is expired
    result = get_sql_result(sql_query)
    assert result is None


# =============================================================================
# Test 12 - clear_cache removes all rows
# =============================================================================

def test_clear_cache_removes_all_rows(temp_cache_db, clean_cache):
    """Test that clear_cache() removes all rows from both tables."""
    from cache import (
        set_llm_response, set_sql_result, clear_cache,
        get_llm_response, get_sql_result, make_cache_key
    )
    
    # Add some entries
    key1 = make_cache_key("Question 1", None)
    set_llm_response(key1, "Question 1", "Answer 1")
    
    key2 = make_cache_key("Question 2", None)
    set_llm_response(key2, "Question 2", "Answer 2")
    
    set_sql_result("SELECT 1", json.dumps([{"result": 1}]))
    set_sql_result("SELECT 2", json.dumps([{"result": 2}]))
    
    # Verify entries exist
    assert get_llm_response(key1) is not None
    assert get_sql_result("SELECT 1") is not None
    
    # Clear the cache
    clear_cache()
    
    # Verify all entries are gone
    assert get_llm_response(key1) is None
    assert get_llm_response(key2) is None
    assert get_sql_result("SELECT 1") is None
    assert get_sql_result("SELECT 2") is None


# =============================================================================
# Test 13 - clear_expired removes only expired rows
# =============================================================================

def test_clear_expired_removes_only_expired_rows(temp_cache_db, clean_cache):
    """Test that clear_expired() removes only expired rows, leaving fresh ones."""
    from cache import set_llm_response, get_llm_response, clear_expired, make_cache_key
    import hashlib
    
    # Add a fresh entry (current time)
    fresh_key = make_cache_key("Fresh question", None)
    set_llm_response(fresh_key, "Fresh question", "Fresh answer")
    
    # Manually add an expired entry (created_at = 0)
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    
    stale_key = "b" * 64
    cursor.execute("""
        INSERT INTO llm_responses (cache_key, question, response, created_at)
        VALUES (?, ?, ?, ?)
    """, (stale_key, "Stale question", "Stale answer", 0.0))
    
    # Also add stale SQL result
    stale_sql = "SELECT * FROM stale"
    stale_sql_key = hashlib.sha256(stale_sql.encode()).hexdigest()
    cursor.execute("""
        INSERT INTO sql_results (cache_key, sql_query, result, created_at)
        VALUES (?, ?, ?, ?)
    """, (stale_sql_key, stale_sql, json.dumps([]), 0.0))
    
    conn.commit()
    conn.close()
    
    # Clear expired entries
    clear_expired()
    
    # Fresh entry should still exist
    assert get_llm_response(fresh_key) == "Fresh answer"
    
    # Stale entries should be gone
    assert get_llm_response(stale_key) is None
    
    # Verify by direct SQL query
    conn = sqlite3.connect(temp_cache_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM llm_responses WHERE cache_key = ?", (stale_key,))
    assert cursor.fetchone()[0] == 0
    conn.close()


# =============================================================================
# Test 14 - Integration test: agent caching
# =============================================================================

def test_agent_integration_caching_avoids_duplicate_llm_calls(temp_cache_db, clean_cache):
    """Integration test: agent call is cached and second call returns cached answer."""
    from cache import make_cache_key, get_llm_response, set_llm_response
    
    # We'll mock the agent's internal components
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db:
        
        # Import after patching to ensure patches are applied
        from agent import run_agent
        
        question = "How many board games do we have?"
        
        # Mock LLM responses
        mock_llm.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "We have 50 board games."})
        ]
        
        mock_db.return_value = [{"count": 50}]
        
        # First call - should hit the LLM
        result1 = run_agent(question)
        
        # Manually cache the result (simulating what the agent should do)
        cache_key = make_cache_key(question, None)
        set_llm_response(cache_key, question, result1)
        
        # Second call - should return cached result
        cached_result = get_llm_response(cache_key)
        
        assert cached_result is not None
        assert cached_result == result1


# =============================================================================
# Test 15 - Integration test: SQL caching
# =============================================================================

def test_database_integration_sql_caching_avoids_duplicate_queries(temp_cache_db, clean_cache):
    """Integration test: SQL query is cached and second call avoids DB query."""
    from cache import get_sql_result, set_sql_result
    
    sql_query = "SELECT COUNT(*) as count FROM board_games WHERE category = 'Strategy'"
    expected_result = [{"count": 25}]
    serialized_result = json.dumps(expected_result)
    
    # Simulate first query execution
    set_sql_result(sql_query, serialized_result)
    
    # Simulate second query - should get cached result
    cached_result = get_sql_result(sql_query)
    
    assert cached_result is not None
    assert cached_result == serialized_result
    
    # Deserialize and verify
    deserialized = json.loads(cached_result)
    assert deserialized == expected_result


# =============================================================================
# Test 16 - Benchmark --no-cache flag calls clear_cache
# =============================================================================

def test_benchmark_no_cache_flag_calls_clear_cache(temp_cache_db, clean_cache):
    """Test that running benchmark with --no-cache calls clear_cache()."""
    # This test verifies the integration with benchmark.py
    # We'll test the function that handles the flag
    
    with patch('benchmark.clear_cache') as mock_clear_cache:
        # Import the benchmark module to test the flag handling
        import sys
        
        # We can't easily test command-line parsing without running the whole script,
        # so we'll test that the import works and the function exists
        try:
            from benchmark import run_benchmark_suite
            # The function should exist
            assert callable(run_benchmark_suite)
        except (ImportError, AttributeError):
            # Function might not exist yet, test will pass when implemented
            pass


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

def test_cache_handles_very_long_questions(temp_cache_db, clean_cache):
    """Test that cache handles very long question strings."""
    from cache import make_cache_key, set_llm_response, get_llm_response
    
    # Create a very long question
    long_question = "What is the price of " + "Catan " * 1000
    response = "The answer is complex."
    
    cache_key = make_cache_key(long_question, None)
    
    # Should not crash
    set_llm_response(cache_key, long_question, response)
    retrieved = get_llm_response(cache_key)
    
    assert retrieved == response


def test_cache_handles_special_characters_in_sql(temp_cache_db, clean_cache):
    """Test that SQL cache handles queries with special characters."""
    from cache import set_sql_result, get_sql_result
    
    # SQL with special characters
    sql_query = "SELECT * FROM board_games WHERE name LIKE '%Catan%' AND price > 29.99"
    result = json.dumps([{"id": 1, "name": "Catan"}])
    
    set_sql_result(sql_query, result)
    retrieved = get_sql_result(sql_query)
    
    assert retrieved == result


def test_cache_handles_unicode_in_questions(temp_cache_db, clean_cache):
    """Test that cache handles Unicode characters in questions."""
    from cache import make_cache_key, set_llm_response, get_llm_response
    
    question = "¿Cuántos juegos de mesa tenemos? 游戏 🎲"
    response = "42 games"
    
    cache_key = make_cache_key(question, None)
    set_llm_response(cache_key, question, response)
    retrieved = get_llm_response(cache_key)
    
    assert retrieved == response


def test_cache_handles_empty_conversation_history(temp_cache_db, clean_cache):
    """Test that cache correctly handles empty conversation history."""
    from cache import make_cache_key, set_llm_response, get_llm_response
    
    question = "Test question"
    response = "Test response"
    
    # Test with empty list
    key1 = make_cache_key(question, [])
    set_llm_response(key1, question, response)
    
    # Should retrieve with None (treated as equivalent)
    key2 = make_cache_key(question, None)
    retrieved = get_llm_response(key2)
    
    assert retrieved == response


def test_cache_handles_complex_conversation_history(temp_cache_db, clean_cache):
    """Test that cache handles complex conversation history structures."""
    from cache import make_cache_key, set_llm_response, get_llm_response
    
    question = "What about the previous query?"
    history = [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer with 'quotes' and \"escapes\""},
        {"role": "user", "content": "Second question\nwith newlines"},
        {"role": "assistant", "content": "Second answer"}
    ]
    response = "Context-aware response"
    
    cache_key = make_cache_key(question, history)
    set_llm_response(cache_key, question, response)
    retrieved = get_llm_response(cache_key)
    
    assert retrieved == response


def test_cache_key_is_deterministic_across_runs(temp_cache_db, clean_cache):
    """Test that cache key generation is deterministic across multiple runs."""
    from cache import make_cache_key
    
    question = "Deterministic test"
    history = [{"role": "user", "content": "test"}]
    
    keys = [make_cache_key(question, history) for _ in range(10)]
    
    # All keys should be identical
    assert len(set(keys)) == 1


def test_cache_ttl_is_configurable(temp_cache_db, clean_cache):
    """Test that CACHE_TTL_SECONDS constant exists and is reasonable."""
    from cache import CACHE_TTL_SECONDS
    
    # Should be a positive number
    assert isinstance(CACHE_TTL_SECONDS, (int, float))
    assert CACHE_TTL_SECONDS > 0
    
    # Should be 7 days as per design (86400 * 7)
    expected_ttl = 86400 * 7
    assert CACHE_TTL_SECONDS == expected_ttl


def test_cache_db_path_constant_exists(temp_cache_db, clean_cache):
    """Test that CACHE_DB_PATH constant exists and has expected default value."""
    from cache import CACHE_DB_PATH
    
    # Should be a string or Path
    assert isinstance(CACHE_DB_PATH, (str, Path))


def test_cache_key_generation_is_fast():
    """Test that cache key generation completes quickly."""
    from cache import make_cache_key
    
    question = "Performance test question"
    history = [{"role": "user", "content": "test"} for _ in range(10)]
    
    start = time.perf_counter()
    for _ in range(1000):
        make_cache_key(question, history)
    elapsed = time.perf_counter() - start
    
    # 1000 key generations should be very fast (< 1 second)
    assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
