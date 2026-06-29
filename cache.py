"""SQLite-based caching for LLM answers and SQL query results."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path

# =============================================================================
# CONSTANTS
# =============================================================================

CACHE_DB_PATH = Path(__file__).parent / "agent_cache.db"
CACHE_TTL_DAYS = 7

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_cache() -> None:
    """Create the SQLite database and cache tables if they don't exist."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    # Create answer_cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS answer_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_hash TEXT NOT NULL,
            history_hash TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(question_hash, history_hash)
        )
    """)
    
    # Create sql_cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sql_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sql_hash TEXT NOT NULL UNIQUE,
            result TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize cache on module import
init_cache()

# =============================================================================
# HASH FUNCTIONS
# =============================================================================

def compute_question_hash(question: str) -> str:
    """
    Compute SHA-256 hash of a question string.
    
    The question is lowercased and stripped before hashing for normalization.
    
    Args:
        question: The question string
        
    Returns:
        Hex digest of the SHA-256 hash
    """
    normalized = question.lower().strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def compute_history_hash(conversation_history: list[dict] | None) -> str:
    """
    Compute SHA-256 hash of conversation history.
    
    The history is JSON-serialized with sorted keys for deterministic hashing.
    None or empty list both produce the same hash.
    
    Args:
        conversation_history: List of message dicts or None
        
    Returns:
        Hex digest of the SHA-256 hash
    """
    if conversation_history is None or len(conversation_history) == 0:
        history_json = "[]"
    else:
        history_json = json.dumps(conversation_history, sort_keys=True)
    
    return hashlib.sha256(history_json.encode('utf-8')).hexdigest()


def compute_sql_hash(sql: str) -> str:
    """
    Compute SHA-256 hash of a SQL string.
    
    The SQL is stripped before hashing.
    
    Args:
        sql: The SQL query string
        
    Returns:
        Hex digest of the SHA-256 hash
    """
    normalized = sql.strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

# =============================================================================
# ANSWER CACHE FUNCTIONS
# =============================================================================

def get_cached_answer(question: str, conversation_history: list[dict] | None) -> str | None:
    """
    Retrieve cached answer for a question with conversation history.
    
    Returns None if no valid (non-expired) cache entry exists.
    
    Args:
        question: The question string
        conversation_history: List of message dicts or None
        
    Returns:
        Cached answer string or None
    """
    question_hash = compute_question_hash(question)
    history_hash = compute_history_hash(conversation_history)
    
    # Calculate expiry threshold
    expiry_time = time.time() - (CACHE_TTL_DAYS * 86400)
    
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT answer FROM answer_cache
        WHERE question_hash = ? AND history_hash = ? AND created_at > ?
    """, (question_hash, history_hash, expiry_time))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return None


def set_cached_answer(question: str, conversation_history: list[dict] | None, answer: str) -> None:
    """
    Store an answer in the cache.

    Uses INSERT OR REPLACE to update existing entries.

    Args:
        question: The question string
        conversation_history: List of message dicts or None
        answer: The answer string to cache

    Raises:
        TypeError: If answer is None
    """
    if answer is None:
        raise TypeError("Answer cannot be None")

    question_hash = compute_question_hash(question)
    history_hash = compute_history_hash(conversation_history)
    current_time = time.time()

    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO answer_cache (question_hash, history_hash, answer, created_at)
        VALUES (?, ?, ?, ?)
    """, (question_hash, history_hash, answer, current_time))

    conn.commit()
    conn.close()

# =============================================================================
# SQL CACHE FUNCTIONS
# =============================================================================

def get_cached_sql_result(sql: str) -> str | None:
    """
    Retrieve cached result for a SQL query.
    
    Returns None if no valid (non-expired) cache entry exists.
    
    Args:
        sql: The SQL query string
        
    Returns:
        Cached result string (JSON-serialized) or None
    """
    sql_hash = compute_sql_hash(sql)
    
    # Calculate expiry threshold
    expiry_time = time.time() - (CACHE_TTL_DAYS * 86400)
    
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT result FROM sql_cache
        WHERE sql_hash = ? AND created_at > ?
    """, (sql_hash, expiry_time))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row[0]
    return None


def set_cached_sql_result(sql: str, result: str) -> None:
    """
    Store a SQL query result in the cache.
    
    Args:
        sql: The SQL query string
        result: The result string (should be JSON-serialized if structured data)
    """
    sql_hash = compute_sql_hash(sql)
    current_time = time.time()
    
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO sql_cache (sql_hash, result, created_at)
        VALUES (?, ?, ?)
    """, (sql_hash, result, current_time))
    
    conn.commit()
    conn.close()

# =============================================================================
# CACHE MANAGEMENT FUNCTIONS
# =============================================================================

def clear_expired_cache() -> int:
    """
    Remove all expired cache entries.
    
    Returns:
        Total number of rows deleted
    """
    expiry_time = time.time() - (CACHE_TTL_DAYS * 86400)
    
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    # Delete expired answer cache entries
    cursor.execute("DELETE FROM answer_cache WHERE created_at <= ?", (expiry_time,))
    answer_deleted = cursor.rowcount
    
    # Delete expired SQL cache entries
    cursor.execute("DELETE FROM sql_cache WHERE created_at <= ?", (expiry_time,))
    sql_deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return answer_deleted + sql_deleted


def clear_all_cache() -> None:
    """Remove all cache entries (both answer and SQL caches)."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM answer_cache")
    cursor.execute("DELETE FROM sql_cache")
    
    conn.commit()
    conn.close()
