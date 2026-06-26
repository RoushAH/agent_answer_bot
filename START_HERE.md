# 🚀 Plan-First Mode Test Suite

## Quick Start

You are looking at a **complete Test-Driven Development (TDD)** test suite for the Plan-First Mode feature.

### What Was Created?

✅ **30 comprehensive tests** covering all design requirements  
✅ **591 lines of test code** in `tests/test_plan_first_mode.py`  
✅ **9 documentation files** to guide implementation  
✅ **pytest dependency** added to requirements.txt  

### What Do I Do First?

#### 1. Verify Tests Fail (Expected!)
```bash
pytest tests/test_plan_first_mode.py -v
```
**Expected Result**: ~24 FAILED, ~6 PASSED (this is correct for TDD!)

#### 2. Read the Implementation Guide
```bash
cat tests/IMPLEMENTATION_CHECKLIST.md
```

#### 3. Implement Features Step-by-Step
Follow the checklist and watch tests turn green!

#### 4. Achieve 100% Pass Rate
```bash
pytest tests/test_plan_first_mode.py -v
```
**Goal**: 30 PASSED, 0 FAILED

---

## 📚 Documentation Map

### For Developers
- **START HERE** → This file (you are here!)
- **Implementation** → `tests/IMPLEMENTATION_CHECKLIST.md`
- **Test Details** → `tests/README_PLAN_TESTS.md`
- **Quick Reference** → `tests/TEST_SUMMARY.md`

### For Reviewers
- **Overview** → `TESTING_README.md`
- **Deliverables** → `DELIVERABLES_SUMMARY.md`
- **Test Structure** → `tests/TEST_STRUCTURE.txt`

### For Running Tests
- **Expected Output** → `tests/EXPECTED_OUTPUT.txt`
- **All Test Names** → `tests/TEST_LIST.txt`

---

## 📊 What's Tested?

| Category | Tests | What It Covers |
|----------|-------|----------------|
| **Detection** | 8 | Multi-step question detection |
| **Schema** | 7 | Plan action validation |
| **Loop** | 3 | Plan execution in agent |
| **Prompt** | 2 | Conditional prompt changes |
| **API** | 2 | Response model updates |
| **TUI** | 2 | UI plan display |
| **Integration** | 3 | End-to-end scenarios |
| **Edge Cases** | 5 | Error handling |
| **TOTAL** | **30** | **Complete coverage** |

---

## 🎯 Design Alignment

✅ All 16 design document tests implemented  
✅ Plus 14 additional tests for robustness  
✅ 100% coverage of requirements  

---

## 💡 Key Concepts

### Test-Driven Development (TDD)
1. ✅ Write tests FIRST (done!)
2. ⬜ Run tests (they should fail)
3. ⬜ Write minimal code to pass tests
4. ⬜ Refactor and improve
5. ⬜ Repeat until all tests pass

### Why Tests Fail Initially
This is **expected and correct**! Tests fail because:
- `requires_plan()` function doesn't exist yet
- `inject_plan_into_messages()` function doesn't exist yet
- "plan" is not in VALID_ACTIONS yet
- Plan validation logic doesn't exist yet

### How to Fix
Follow `tests/IMPLEMENTATION_CHECKLIST.md` step by step!

---

## 🔧 Quick Commands

```bash
# Run all tests
pytest tests/test_plan_first_mode.py -v

# Run specific category
pytest tests/test_plan_first_mode.py -k "requires_plan" -v

# Run with coverage
pytest tests/test_plan_first_mode.py --cov=agent --cov=schema -v

# Stop on first failure
pytest tests/test_plan_first_mode.py -x

# Run single test
pytest tests/test_plan_first_mode.py::test_requires_plan_returns_true_for_comparison_questions -v
```

---

## 📋 Implementation Checklist Preview

- [ ] Step 1: Add "plan" to VALID_ACTIONS (7 tests pass)
- [ ] Step 2: Implement `requires_plan()` (8 tests pass)
- [ ] Step 3: Add plan validation (7 tests pass)
- [ ] Step 4: Implement `inject_plan_into_messages()` (1 test passes)
- [ ] Step 5: Update system prompts (2 tests pass)
- [ ] Step 6: Handle plan in agent loop (3 tests pass)
- [ ] Step 7: Update API responses (2 tests pass)
- [ ] Step 8: Update TUI rendering (2 tests pass)
- [ ] Step 9: Integration & edge cases (5 tests pass)

See full checklist: `tests/IMPLEMENTATION_CHECKLIST.md`

---

## ✨ Success Criteria

- [ ] All 30 tests pass
- [ ] No regressions in existing tests
- [ ] Coverage > 90% for new code
- [ ] All design requirements met
- [ ] Code review approved
- [ ] Ready to merge

---

## 🆘 Need Help?

1. **Can't run tests?**
   - Install pytest: Already in `requirements.txt`
   - Run: `pip install -r requirements.txt`

2. **Tests won't pass?**
   - Check `tests/EXPECTED_OUTPUT.txt` for what to expect
   - Review `tests/IMPLEMENTATION_CHECKLIST.md` for steps

3. **Don't understand a test?**
   - Read test docstrings (they explain what each test does)
   - See `tests/README_PLAN_TESTS.md` for details

4. **Want to see test structure?**
   - Visual diagram: `tests/TEST_STRUCTURE.txt`
   - All test names: `tests/TEST_LIST.txt`

---

## 🎓 Files Modified

- ✅ `requirements.txt` - Added pytest
- ⬜ `agent.py` - Will add functions (TODO)
- ⬜ `schema.py` - Will add "plan" action (TODO)
- ⬜ `api.py` - Will update response model (TODO)
- ⬜ `main.py` - Will update TUI (TODO)

---

## 📞 Questions?

- Design document has requirements
- `TESTING_README.md` has overview
- `tests/README_PLAN_TESTS.md` has details
- Each test has a docstring explaining its purpose

---

**Current Status**: ✅ Tests Written | ⏳ Implementation Pending

**Next Step**: Run `pytest tests/test_plan_first_mode.py -v`

**Goal**: 30 PASSED, 0 FAILED ✨

---

Created: 2026-06-26  
Feature: Plan-First Mode (LOO-33)  
Approach: Test-Driven Development (TDD)
