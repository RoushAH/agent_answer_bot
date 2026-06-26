# Error Handling Implementation Examples

This document shows the key error handling patterns added to fix the CRITICAL review issue.

## Pattern 1: Connection Function

**Before (would crash):**
```python
def _get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    _ensure_tables(conn)
    return conn
```

**After (graceful degradation):**
```python
def _get_connection() -> sqlite3.Connection | None:
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        _ensure_tables(conn)
        return conn
    except Exception as e:
        logger.warning(f"Failed to connect to cache database: {e}")
        return None
```

## Pattern 2: Cache Read Operations

**Before (would crash):**
```python
def get_llm_response(cache_key: str) -> str | None:
    conn = _get_connection()
    cur = conn.cursor()
    # ... query logic ...
    return row[0] if row else None
```

**After (graceful degradation):**
```python
def get_llm_response(cache_key: str) -> str | None:
    try:
        conn = _get_connection()
        if not conn:
            return None
        cur = conn.cursor()
        # ... query logic ...
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"Failed to retrieve LLM response from cache: {e}")
        return None
```

## Pattern 3: Cache Write Operations

**Before (would crash):**
```python
def set_llm_response(cache_key: str, question: str, response: str) -> None:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE ...")
    conn.commit()
    conn.close()
```

**After (graceful degradation):**
```python
def set_llm_response(cache_key: str, question: str, response: str) -> None:
    try:
        conn = _get_connection()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE ...")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to store LLM response in cache: {e}")
```

## Pattern 4: Integration Points (Agent)

**Before (would crash):**
```python
# Check cache first
cache_key = make_cache_key(user_query, conversation_history)
cached_answer = get_llm_response(cache_key)
if cached_answer is not None:
    emit("cache_hit", "", "Using cached response")
    return cached_answer
```

**After (graceful degradation):**
```python
# Check cache first (with error handling)
try:
    cache_key = make_cache_key(user_query, conversation_history)
    cached_answer = get_llm_response(cache_key)
    if cached_answer is not None:
        emit("cache_hit", "", "Using cached response")
        return cached_answer
except Exception:
    # If cache check fails, continue to run agent normally
    pass
```

## Pattern 5: Integration Points (Database)

**Before (would crash):**
```python
def query_db(sql: str) -> list[dict]:
    # Check cache first
    cached_result = get_sql_result(sql)
    if cached_result is not None:
        return json.loads(cached_result)
    
    # Execute query
    # ...
    
    # Cache the result
    set_sql_result(sql, json.dumps(results))
    return results
```

**After (graceful degradation):**
```python
def query_db(sql: str) -> list[dict]:
    # Check cache first (with error handling)
    try:
        cached_result = get_sql_result(sql)
        if cached_result is not None:
            return json.loads(cached_result)
    except Exception:
        pass  # Continue to execute query normally
    
    # Execute query
    # ...
    
    # Cache the result (with error handling)
    try:
        set_sql_result(sql, json.dumps(results))
    except Exception:
        pass  # Still return the results
    
    return results
```

## Key Principles

1. **Never crash the application** - All cache operations are wrapped in try-except
2. **Always degrade gracefully** - Return None or continue without cache
3. **Log warnings for debugging** - Use logger.warning() to track issues
4. **Maintain core functionality** - Cache failures don't prevent queries or answers
5. **Check for None returns** - Integration points check if conn is None

## Coverage Summary

- ✅ 8 functions in cache.py have error handling
- ✅ 4 integration points (agent.py and database.py) have error handling
- ✅ All SQLite operations are protected
- ✅ All cache operations can fail without crashing the app
- ✅ Logging provides visibility into cache issues

## Testing Scenarios

These scenarios should all result in logged warnings but continued operation:

1. **Disk full** - set_* operations fail, but queries/answers still work
2. **Database locked** - SQLite lock errors logged, operations continue
3. **Corrupted cache.db** - Connection fails, app works without cache
4. **Permission denied** - File access errors logged, app continues
5. **Invalid SQL** - Caught and logged, doesn't crash

