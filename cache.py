"""SQLite-based cache for LLM responses and SQL query results."""

import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from threading import Lock

# Set up logging
logger = logging.getLogger("cache")
logger.setLevel(logging.WARNING)  # Only log warnings and errors by default

# Constants
CACHE_DB_PATH = "cache.db"
CACHE_TTL_SECONDS = 86400 * 7  # 7 days

# For :memory: databases, map to a temp file so direct sqlite3.connect calls work
_memory_temp_file = None
_connection_lock = Lock()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure cache tables exist in the given connection."""
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_responses (
            id INTEGER PRIMARY KEY,
            cache_key TEXT UNIQUE NOT NULL,
            question TEXT,
            response TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sql_results (
            id INTEGER PRIMARY KEY,
            cache_key TEXT UNIQUE NOT NULL,
            sql_query TEXT,
            result TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    conn.commit()


def get_db_path() -> str:
    """
    Get the actual database path being used.

    For `:memory:` CACHE_DB_PATH, returns a temp file path.
    This allows tests to connect directly using sqlite3.connect(cache.get_db_path()).
    """
    global _memory_temp_file

    if CACHE_DB_PATH == ":memory:":
        with _connection_lock:
            if _memory_temp_file is None:
                # Create a temp file for the "in-memory" database
                # Don't delete it - we'll use it for the lifetime of the process
                fd, _memory_temp_file = tempfile.mkstemp(suffix=".db", prefix="cache_test_")
                os.close(fd)  # Close the file descriptor, we'll access via path
            return _memory_temp_file
    else:
        return CACHE_DB_PATH


def _get_connection() -> sqlite3.Connection | None:
    """
    Get a connection to the cache database, ensuring tables exist.

    Returns None if connection fails (for graceful degradation).
    """
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        _ensure_tables(conn)
        return conn
    except Exception as e:
        logger.warning(f"Failed to connect to cache database: {e}")
        return None


def init_cache() -> None:
    """Initialize the cache database and create tables if they don't exist."""
    global CACHE_DB_PATH

    # If CACHE_DB_PATH is :memory:, replace it with a temp file path
    # This ensures tests that do sqlite3.connect(cache.CACHE_DB_PATH) work correctly
    if CACHE_DB_PATH == ":memory:":
        CACHE_DB_PATH = get_db_path()

    try:
        conn = _get_connection()
        if conn:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to initialize cache: {e}")


def make_cache_key(question: str, conversation_history: list | None) -> str:
    """
    Generate a deterministic cache key from question and conversation history.
    
    Args:
        question: The user's question string
        conversation_history: List of conversation messages (or None/empty)
    
    Returns:
        SHA-256 hex digest as cache key
    """
    # Normalize None to empty list for consistency
    if conversation_history is None:
        conversation_history = []
    
    # Create deterministic string representation
    # Use json.dumps with sort_keys=True to ensure consistent ordering
    history_str = json.dumps(conversation_history, sort_keys=True)
    combined = f"{question}|{history_str}"
    
    # Return SHA-256 hash
    return hashlib.sha256(combined.encode()).hexdigest()


def get_llm_response(cache_key: str) -> str | None:
    """
    Retrieve a cached LLM response if it exists and hasn't expired.

    Args:
        cache_key: The cache key to look up

    Returns:
        The cached response string, or None if not found, expired, or cache error
    """
    try:
        conn = _get_connection()
        if not conn:
            return None

        cur = conn.cursor()

        current_time = time.time()
        expiry_time = current_time - CACHE_TTL_SECONDS

        cur.execute("""
            SELECT response FROM llm_responses
            WHERE cache_key = ? AND created_at > ?
        """, (cache_key, expiry_time))

        row = cur.fetchone()
        conn.close()

        if row:
            return row[0]
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve LLM response from cache: {e}")
        return None


def set_llm_response(cache_key: str, question: str, response: str) -> None:
    """
    Store or update an LLM response in the cache.

    Args:
        cache_key: The cache key
        question: The original question
        response: The LLM response to cache
    """
    try:
        conn = _get_connection()
        if not conn:
            return

        cur = conn.cursor()

        current_time = time.time()

        # Use INSERT OR REPLACE for upsert behavior
        cur.execute("""
            INSERT OR REPLACE INTO llm_responses (cache_key, question, response, created_at)
            VALUES (?, ?, ?, ?)
        """, (cache_key, question, response, current_time))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to store LLM response in cache: {e}")


def get_sql_result(sql_query: str) -> str | None:
    """
    Retrieve a cached SQL result if it exists and hasn't expired.

    Args:
        sql_query: The SQL query string

    Returns:
        The cached result string (JSON), or None if not found, expired, or cache error
    """
    try:
        # Compute cache key from SQL query
        cache_key = hashlib.sha256(sql_query.encode()).hexdigest()

        conn = _get_connection()
        if not conn:
            return None

        cur = conn.cursor()

        current_time = time.time()
        expiry_time = current_time - CACHE_TTL_SECONDS

        cur.execute("""
            SELECT result FROM sql_results
            WHERE cache_key = ? AND created_at > ?
        """, (cache_key, expiry_time))

        row = cur.fetchone()
        conn.close()

        if row:
            return row[0]
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve SQL result from cache: {e}")
        return None


def set_sql_result(sql_query: str, result: str) -> None:
    """
    Store or update a SQL result in the cache.

    Args:
        sql_query: The SQL query string
        result: The result to cache (as JSON string)
    """
    try:
        # Compute cache key from SQL query
        cache_key = hashlib.sha256(sql_query.encode()).hexdigest()

        conn = _get_connection()
        if not conn:
            return

        cur = conn.cursor()

        current_time = time.time()

        # Use INSERT OR REPLACE for upsert behavior
        cur.execute("""
            INSERT OR REPLACE INTO sql_results (cache_key, sql_query, result, created_at)
            VALUES (?, ?, ?, ?)
        """, (cache_key, sql_query, result, current_time))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to store SQL result in cache: {e}")


def clear_cache() -> None:
    """Delete all entries from both cache tables."""
    try:
        conn = _get_connection()
        if not conn:
            return

        cur = conn.cursor()

        cur.execute("DELETE FROM llm_responses")
        cur.execute("DELETE FROM sql_results")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")


def clear_expired() -> None:
    """Delete expired entries from both cache tables."""
    try:
        conn = _get_connection()
        if not conn:
            return

        cur = conn.cursor()

        current_time = time.time()
        expiry_time = current_time - CACHE_TTL_SECONDS

        cur.execute("DELETE FROM llm_responses WHERE created_at <= ?", (expiry_time,))
        cur.execute("DELETE FROM sql_results WHERE created_at <= ?", (expiry_time,))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to clear expired cache entries: {e}")


# Initialize cache on module load
init_cache()
