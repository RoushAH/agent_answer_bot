# Cache Tests Quick Start

## 🎯 Quick Reference

**Test File**: `tests/test_cache.py` (49 tests, 1015 lines)

**Run All Tests**:
```bash
pytest tests/test_cache.py -v
```

**Expected Before Implementation**:
```
ERROR: ModuleNotFoundError: No module named 'cache'
```
✅ This is CORRECT - tests should fail until cache.py exists

**Expected After Implementation**:
```
======================== 49 passed in 2.31s ========================
```

## 📋 Implementation Phases

| Phase | Tasks | Tests Pass | Time |
|-------|-------|------------|------|
| 1-2 | Create cache.py, init DB | 5/49 | 30 min |
| 3 | Cache key generation | 12/49 | 20 min |
| 4 | LLM response cache | 19/49 | 30 min |
| 5 | SQL result cache | 26/49 | 30 min |
| 6 | Cache management | 32/49 | 20 min |
| 7 | Agent integration | 35/49 | 45 min |
| 8 | Database integration | 38/49 | 30 min |
| 9 | Benchmark integration | 41/49 | 20 min |
| 10 | Edge cases | 49/49 | 30 min |
| **TOTAL** | **All features** | **49/49** | **4-6 hrs** |

## 🔍 Run Tests by Category

```bash
# Cache initialization
pytest tests/test_cache.py -v -k "init"

# Cache keys  
pytest tests/test_cache.py -v -k "make_cache_key"

# LLM caching
pytest tests/test_cache.py -v -k "llm_response"

# SQL caching
pytest tests/test_cache.py -v -k "sql_result"

# Integration
pytest tests/test_cache.py -v -k "agent or database or benchmark"

# Edge cases
pytest tests/test_cache.py -v -k "unicode or long or special"
```

## 📦 Module Structure

Create `cache.py` with:

```python
import sqlite3
import hashlib
import json
import time

CACHE_DB_PATH = "cache.db"
CACHE_TTL_SECONDS = 86400 * 7  # 7 days

# Functions to implement:
def init_cache(): ...
def make_cache_key(question, conversation_history): ...
def get_llm_response(cache_key): ...
def set_llm_response(cache_key, question, response): ...
def get_sql_result(sql_query): ...
def set_sql_result(sql_query, result): ...
def clear_cache(): ...
def clear_expired(): ...
```

## 🔗 Integration Points

### agent.py
```python
from cache import make_cache_key, get_llm_response, set_llm_response

def run_agent(question, conversation_history=None):
    cache_key = make_cache_key(question, conversation_history)
    cached = get_llm_response(cache_key)
    if cached:
        return cached
    
    # ... run agent loop ...
    
    set_llm_response(cache_key, question, final_answer)
    return final_answer
```

### database.py
```python
from cache import get_sql_result, set_sql_result
import json

def query_db(sql):
    cached = get_sql_result(sql)
    if cached:
        return json.loads(cached)
    
    # ... execute query ...
    
    set_sql_result(sql, json.dumps(results, default=str))
    return results
```

### benchmark.py
```python
from cache import clear_cache
import sys

if "--no-cache" in sys.argv:
    clear_cache()
    
if "--clear-cache" in sys.argv:
    clear_cache()
    sys.exit(0)
```

## 🐛 Common Issues

| Error | Fix |
|-------|-----|
| UNIQUE constraint failed | Use `INSERT OR REPLACE` |
| Returns stale data | Check TTL: `time.time() - created_at > TTL` |
| Same key for different Q | Use `json.dumps(data, sort_keys=True)` |
| SQL cache broken | JSON serialize: `json.dumps(results, default=str)` |

## 📊 Success Criteria

- [x] All 49 tests pass
- [x] No new dependencies (stdlib only)
- [x] Benchmark runtime: 20 min → <1 min on re-runs
- [x] cache.db created automatically
- [x] --no-cache and --clear-cache work

## 📚 Full Documentation

- **Complete Guide**: `tests/README_CACHE_TESTS.md`
- **Implementation Steps**: `tests/CACHE_TEST_CHECKLIST.md`
- **Test Summary**: `tests/TEST_CACHE_SUMMARY.md`

## ⚡ TL;DR

1. Read `CACHE_TEST_CHECKLIST.md`
2. Create `cache.py` following the checklist
3. Run `pytest tests/test_cache.py -v` after each phase
4. Integrate with agent.py, database.py, benchmark.py
5. All 49 tests should pass ✅

---
*Tests ready! Start implementing at Phase 1 of CACHE_TEST_CHECKLIST.md*
