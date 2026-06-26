# Plan-First Mode Testing

## Overview

This document describes the comprehensive test suite created for the plan-first mode feature (TICKET: LOO-33).

## Test-Driven Development Approach

Following TDD principles, **all tests were written FIRST** before any implementation. This ensures:
- Clear requirements and specifications
- Implementation guided by tests
- High confidence that features work as designed
- Regression prevention for future changes

## Test Files Created

### 1. tests/test_plan_first_mode.py
**Main test suite** - 591 lines, 30 test functions

Comprehensive coverage of:
- Multi-step question detection
- Schema validation for plan actions
- Agentic loop execution
- System prompt modifications
- API response changes
- TUI rendering
- End-to-end integration scenarios
- Edge cases and error handling

### 2. tests/__init__.py
Makes tests directory a proper Python package

### 3. tests/README_PLAN_TESTS.md
Detailed documentation including:
- Test categories breakdown
- Design document alignment verification
- Running instructions
- Implementation checklist

### 4. tests/TEST_SUMMARY.md
Quick reference with:
- Test count by category (table format)
- Files created summary
- Coverage alignment with design
- Next steps

### 5. tests/EXPECTED_OUTPUT.txt
Example test output showing:
- What to expect before implementation (failures)
- What to expect after implementation (all pass)
- Common failure messages
- Run commands

## Test Statistics

- **Total Tests**: 30
- **Lines of Test Code**: 591
- **Test Categories**: 8
- **Files Modified**: 1 (requirements.txt - added pytest)
- **Documentation Files**: 4

### Breakdown by Category

| Category | Tests | Coverage |
|----------|-------|----------|
| Detection Heuristic | 8 | `requires_plan()` function |
| Schema Validation | 7 | "plan" action type |
| Agentic Loop | 3 | Plan execution & storage |
| System Prompt | 2 | Conditional prompts |
| API Response | 2 | Response model changes |
| TUI Rendering | 2 | UI plan display |
| Integration | 3 | End-to-end scenarios |
| Edge Cases | 5 | Error handling |

## Running Tests

### Basic Commands

```bash
# Run all plan-first tests
pytest tests/test_plan_first_mode.py -v

# Run specific test
pytest tests/test_plan_first_mode.py::test_requires_plan_returns_true_for_comparison_questions -v

# Run tests matching pattern
pytest tests/test_plan_first_mode.py -k "requires_plan" -v

# Stop on first failure
pytest tests/test_plan_first_mode.py -x

# Show print statements
pytest tests/test_plan_first_mode.py -s
```

### With Coverage

```bash
# Generate coverage report
pytest tests/test_plan_first_mode.py --cov=agent --cov=schema --cov=api --cov=main -v

# HTML coverage report
pytest tests/test_plan_first_mode.py --cov=agent --cov=schema --cov-report=html
```

## Expected Test Behavior

### Before Implementation
- **~24 tests will FAIL** with ImportError or AssertionError
- **~6 tests may PASS** (testing existing functionality)
- This is **expected and correct** for TDD!

### After Implementation
- **All 30 tests should PASS**
- Indicates feature is fully implemented per design
- Ready for integration and deployment

## Implementation Guidance

Tests serve as a roadmap for implementation. Follow this order:

1. ✅ **Step 1**: Add "plan" to VALID_ACTIONS
   - Tests: `test_plan_action_is_in_valid_actions`

2. ✅ **Step 2**: Implement `requires_plan()` function
   - Tests: 8 detection heuristic tests

3. ✅ **Step 3**: Add plan validation to schema
   - Tests: 7 schema validation tests

4. ✅ **Step 4**: Implement `inject_plan_into_messages()`
   - Tests: `test_plan_is_stored_and_injected_into_subsequent_messages`

5. ✅ **Step 5**: Update agentic loop
   - Tests: 3 agentic loop tests

6. ✅ **Step 6**: Modify system prompt
   - Tests: 2 system prompt tests

7. ✅ **Step 7**: Update API response
   - Tests: 2 API response tests

8. ✅ **Step 8**: Add TUI rendering
   - Tests: 2 TUI rendering tests

9. ✅ **Step 9**: Verify end-to-end
   - Tests: 3 integration tests + 5 edge case tests

## Key Features of Test Suite

### Quality Attributes

✅ **Comprehensive**: Covers all design document requirements plus extras
✅ **Isolated**: Heavy use of mocks and patches
✅ **Independent**: Tests can run in any order
✅ **Well-Documented**: Clear docstrings and comments
✅ **Modern**: Uses current best practices (no deprecated APIs)
✅ **Maintainable**: Follows existing codebase patterns

### Testing Techniques Used

- **Mocking**: unittest.mock.patch for external dependencies
- **Parameterization**: Multiple assertions per test where logical
- **Integration Testing**: End-to-end scenario verification
- **Edge Case Testing**: Error conditions and boundary values
- **Regression Testing**: Ensures existing features still work

## Dependencies

Added to `requirements.txt`:
```
pytest
```

Optional for enhanced testing:
```
pytest-cov  # For coverage reports
pytest-xdist  # For parallel test execution
```

## Files Modified

1. `requirements.txt` - Added pytest dependency
2. Created `tests/` directory structure
3. Created test files and documentation

## Next Steps

1. **Verify tests fail**: Run `pytest tests/test_plan_first_mode.py -v`
2. **Implement features**: Follow design document and implementation plan
3. **Watch tests pass**: Incremental implementation guided by failing tests
4. **Achieve 100% pass**: All 30 tests green
5. **Run full test suite**: Ensure no regressions in existing functionality

## Questions or Issues?

Refer to:
- `tests/README_PLAN_TESTS.md` - Detailed test documentation
- `tests/TEST_SUMMARY.md` - Quick reference
- `tests/EXPECTED_OUTPUT.txt` - Example test runs
- Design document - Original specifications

## Success Criteria

✅ All 30 tests pass
✅ No regressions in existing tests
✅ Coverage > 90% for new code
✅ All design requirements met
✅ Ready for code review and merge
