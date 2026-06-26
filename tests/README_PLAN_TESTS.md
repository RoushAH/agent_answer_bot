# Plan-First Mode Test Suite

## Overview

This test suite (`test_plan_first_mode.py`) provides comprehensive test coverage for the plan-first mode feature (TICKET: LOO-33). All tests are written **FIRST** following Test-Driven Development (TDD) principles and will initially fail until the implementation is complete.

## Test Categories

### 1. Detection Heuristic Tests (8 tests)
Tests for the `requires_plan()` function that detects multi-step questions:
- Comparison questions ("compare", "vs", "versus", "difference")
- Percentage/ratio questions ("percentage", "percent", "ratio")
- Ranking questions with context ("top X by")
- Compound questions (multiple intents with "and")
- Simple lookups (should NOT trigger planning)
- Single-step calculations (should NOT trigger planning)

### 2. Schema Validation Tests (7 tests)
Tests for the new "plan" action type in `schema.py`:
- Validation that "plan" is added to VALID_ACTIONS
- Proper validation of plan action with "steps" field
- Rejection of plan action without "steps"
- Rejection of plan action with empty steps
- Support for both string and list format for steps
- Ensure existing actions (query, calculate, answer) still work

### 3. Agentic Loop Tests (3 tests)
Tests for plan execution within the agent loop:
- Plan storage and injection into subsequent messages
- Plan actions don't consume turns from the budget
- Prevention of multiple plan actions per question (no plan loops)

### 4. System Prompt Tests (2 tests)
Tests for conditional prompt modifications:
- Planning instructions added when `requires_plan()` returns True
- No planning instructions for simple questions

### 5. API Response Tests (2 tests)
Tests for API modifications in `api.py`:
- API response includes plan field when plan was generated
- API response has null/empty plan for simple questions

### 6. TUI Rendering Tests (2 tests)
Tests for UI changes in `main.py`:
- Plan panel renders without crashing
- Plan text appears in rendered output

### 7. Integration Tests (3 tests)
End-to-end tests simulating real usage:
- Comparison question produces correct answer via plan
- Percentage question uses plan and multiple queries
- Simple question doesn't trigger unnecessary planning

### 8. Edge Cases and Error Handling (5 tests)
Tests for robustness:
- Invalid plan format rejection
- Recovery after plan followed by error
- MAX_TURNS enforcement still works with planning
- Multiline steps validation
- Edge case question handling

## Total Test Count

**32 comprehensive tests** covering all aspects of the plan-first mode feature as specified in the design document.

## Running the Tests

### Run all plan-first tests:
```bash
pytest tests/test_plan_first_mode.py -v
```

### Run specific test category:
```bash
pytest tests/test_plan_first_mode.py -k "requires_plan" -v
pytest tests/test_plan_first_mode.py -k "schema" -v
pytest tests/test_plan_first_mode.py -k "integration" -v
```

### Run with coverage:
```bash
pytest tests/test_plan_first_mode.py --cov=agent --cov=schema --cov=api --cov=main -v
```

## Expected Behavior

### Before Implementation
All tests will fail with import errors or assertion failures because:
- `requires_plan()` function doesn't exist in `agent.py`
- `inject_plan_into_messages()` function doesn't exist in `agent.py`
- "plan" is not in VALID_ACTIONS in `schema.py`
- Plan action validation logic doesn't exist

### After Implementation
All tests should pass, confirming that:
1. Multi-step questions are correctly detected
2. Plan actions validate properly
3. Plans are stored and used throughout execution
4. The agent doesn't waste turns on planning overhead
5. API and TUI properly display plans
6. End-to-end scenarios work correctly

## Implementation Checklist

Use these tests as a guide for implementation order:

- [ ] Step 1: Add "plan" to VALID_ACTIONS in `schema.py` (tests will start passing)
- [ ] Step 2: Implement `requires_plan()` in `agent.py` (8 tests pass)
- [ ] Step 3: Add plan validation to `schema.py` (7 tests pass)
- [ ] Step 4: Implement `inject_plan_into_messages()` in `agent.py`
- [ ] Step 5: Update agentic loop to handle plan actions
- [ ] Step 6: Modify system prompt based on `requires_plan()`
- [ ] Step 7: Update API response model
- [ ] Step 8: Add TUI rendering for plans
- [ ] Step 9: Adjust MAX_TURNS accounting

## Notes

- Tests use `unittest.mock.patch` for isolation
- Tests mock external dependencies (LLM calls, database queries)
- Tests follow existing codebase patterns
- All imports are from actual modules (not test doubles)
- Tests are independent and can run in any order
