"""SQLite-based cache for LLM responses and SQL query results."""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cache")

# =============================================================================
# CONFIGURATION
# =============================================================================

CACHE_DB_PATH = "cache.db"
CACHE_TTL_SECONDS = 86400 * 7  # 7 days

# =============================================================================
# INITIALIZATION
# =============================================================================

def init_cache() -> None:
    """Create (or open) the SQLite database and ensure tables exist."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        # Create llm_responses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_responses (
                id INTEGER PRIMARY KEY,
                cache_key TEXT UNIQUE NOT NULL,
                question TEXT,
                response TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

        # Create sql_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sql_results (
                id INTEGER PRIMARY KEY,
                cache_key TEXT UNIQUE NOT NULL,
                sql_query TEXT,
                result TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to initialize cache: {e}")


# Initialize cache on module load
init_cache()

# =============================================================================
# CACHE KEY GENERATION
# =============================================================================

def make_cache_key(question: str, conversation_history: Optional[list]) -> str:
    """
    Generate a deterministic cache key from question and conversation history.
    
    Args:
        question: The user's question string
        conversation_history: List of conversation messages (or None/empty)
    
    Returns:
        SHA-256 hex digest string (64 characters)
    """
    # Normalize None and empty list to be equivalent
    if conversation_history is None or conversation_history == []:
        conversation_history = []
    
    # Serialize both to a deterministic string
    # Use sort_keys=True to ensure consistent JSON ordering
    history_str = json.dumps(conversation_history, sort_keys=True)
    combined = f"{question}|{history_str}"
    
    # Return SHA-256 hash
    return hashlib.sha256(combined.encode()).hexdigest()

# =============================================================================
# LLM RESPONSE CACHE
# =============================================================================

def get_llm_response(cache_key: str) -> Optional[str]:
    """
    Retrieve a cached LLM response by cache key.

    Args:
        cache_key: The cache key to look up

    Returns:
        The cached response string if found and not expired, None otherwise
    """
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        current_time = time.time()
        cutoff_time = current_time - CACHE_TTL_SECONDS

        cursor.execute("""
            SELECT response FROM llm_responses
            WHERE cache_key = ? AND created_at >= ?
        """, (cache_key, cutoff_time))

        row = cursor.fetchone()
        conn.close()

        if row:
            return row[0]
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached LLM response: {e}")
        return None


def set_llm_response(cache_key: str, question: str, response: str) -> None:
    """
    Store (or update) an LLM response in the cache.

    Args:
        cache_key: The cache key
        question: The original question
        response: The LLM response text
    """
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        current_time = time.time()

        # Use INSERT OR REPLACE to handle upsert
        cursor.execute("""
            INSERT OR REPLACE INTO llm_responses (cache_key, question, response, created_at)
            VALUES (?, ?, ?, ?)
        """, (cache_key, question, response, current_time))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to cache LLM response: {e}")

# =============================================================================
# SQL RESULT CACHE
# =============================================================================

def get_sql_result(sql_query: str) -> Optional[str]:
    """
    Retrieve a cached SQL query result.

    Args:
        sql_query: The SQL query string

    Returns:
        The cached result string (JSON serialized) if found and not expired, None otherwise
    """
    try:
        # Generate cache key from SQL query
        cache_key = hashlib.sha256(sql_query.encode()).hexdigest()

        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        current_time = time.time()
        cutoff_time = current_time - CACHE_TTL_SECONDS

        cursor.execute("""
            SELECT result FROM sql_results
            WHERE cache_key = ? AND created_at >= ?
        """, (cache_key, cutoff_time))

        row = cursor.fetchone()
        conn.close()

        if row:
            return row[0]
        return None
    except Exception as e:
        logger.warning(f"Failed to get cached SQL result: {e}")
        return None


def set_sql_result(sql_query: str, result: str) -> None:
    """
    Store (or update) a SQL query result in the cache.

    Args:
        sql_query: The SQL query string
        result: The query result (JSON serialized string)
    """
    try:
        # Generate cache key from SQL query
        cache_key = hashlib.sha256(sql_query.encode()).hexdigest()

        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        current_time = time.time()

        # Use INSERT OR REPLACE to handle upsert
        cursor.execute("""
            INSERT OR REPLACE INTO sql_results (cache_key, sql_query, result, created_at)
            VALUES (?, ?, ?, ?)
        """, (cache_key, sql_query, result, current_time))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to cache SQL result: {e}")

# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

def clear_cache() -> None:
    """Delete all rows from both cache tables."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM llm_responses")
        cursor.execute("DELETE FROM sql_results")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")


def clear_expired() -> None:
    """Delete rows older than CACHE_TTL_SECONDS from both tables."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        current_time = time.time()
        cutoff_time = current_time - CACHE_TTL_SECONDS

        cursor.execute("DELETE FROM llm_responses WHERE created_at < ?", (cutoff_time,))
        cursor.execute("DELETE FROM sql_results WHERE created_at < ?", (cutoff_time,))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to clear expired cache entries: {e}")
