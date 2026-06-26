# Plan-First Mode Implementation Checklist

Use this checklist to track implementation progress. Run tests after each step to see progress.

## Pre-Implementation

- [x] Tests written and committed
- [x] Design document reviewed
- [x] Dependencies installed (pytest)
- [ ] Initial test run completed (verify they fail)

Run: `pytest tests/test_plan_first_mode.py -v`
Expected: ~24 FAILED, ~6 PASSED

---

## Step 1: Schema Updates (schema.py)

- [ ] Add "plan" to VALID_ACTIONS constant
- [ ] Update `_validate_fields()` to handle "plan" action
- [ ] Add validation for "steps" field (string or list)
- [ ] Add validation to reject empty steps
- [ ] Add validation to reject non-string/non-list steps

**Tests to Pass**: 7
- test_plan_action_is_in_valid_actions
- test_plan_action_validates_correctly_in_schema
- test_plan_action_with_missing_steps_field_fails_validation
- test_plan_action_with_empty_steps_fails_validation
- test_plan_action_with_list_of_steps_validates
- test_plan_action_with_multiline_steps_validates
- test_plan_with_invalid_format_is_rejected

Run: `pytest tests/test_plan_first_mode.py -k "plan_action" -v`

---

## Step 2: Detection Heuristic (agent.py)

- [ ] Add `requires_plan(question: str) -> bool` function
- [ ] Implement comparison keyword detection ("compare", "vs", "versus", "difference")
- [ ] Implement percentage keyword detection ("percentage", "percent", "%", "ratio")
- [ ] Implement ranking detection ("top X by", "best", "worst")
- [ ] Implement compound question detection ("and" with numeric intent)
- [ ] Handle edge cases (empty string, simple questions)

**Tests to Pass**: 8
- test_requires_plan_returns_true_for_comparison_questions
- test_requires_plan_returns_true_for_percentage_questions
- test_requires_plan_returns_false_for_simple_lookup_questions
- test_requires_plan_returns_false_for_single_step_calculation
- test_requires_plan_detects_versus_language
- test_requires_plan_detects_ranking_with_context
- test_requires_plan_detects_compound_questions
- test_requires_plan_handles_edge_case_questions

Run: `pytest tests/test_plan_first_mode.py -k "requires_plan" -v`

---

## Step 3: Plan Injection Helper (agent.py)

- [ ] Add `inject_plan_into_messages(messages: list, plan_text: str) -> list` function
- [ ] Insert plan as assistant or system message
- [ ] Position plan early in message list for context
- [ ] Format plan text clearly (e.g., "Plan: ...")

**Tests to Pass**: 1
- test_plan_is_stored_and_injected_into_subsequent_messages

Run: `pytest tests/test_plan_first_mode.py::test_plan_is_stored_and_injected_into_subsequent_messages -v`

---

## Step 4: System Prompt Updates (agent.py)

- [ ] Update `get_system_prompt()` or equivalent
- [ ] Add section describing "plan" action to LLM
- [ ] Explain when to use plan (multi-step questions)
- [ ] Clarify plan format (numbered steps)
- [ ] Note that plan is not the final answer

**Tests to Pass**: 2
- test_agent_ask_injects_planning_instruction_when_requires_plan_is_true
- test_agent_ask_does_not_inject_planning_instruction_when_requires_plan_is_false

Run: `pytest tests/test_plan_first_mode.py -k "planning_instruction" -v`

---

## Step 5: Agentic Loop Updates (agent.py)

- [ ] Add plan handling to `run_agent()` function
- [ ] Detect when action type is "plan"
- [ ] Extract and store plan steps
- [ ] Inject plan into subsequent LLM calls
- [ ] Track plan_recorded flag to prevent re-planning
- [ ] Ensure plan action doesn't count as a tool turn
- [ ] Update turns_used vs total_iterations tracking

**Tests to Pass**: 3
- test_plan_is_stored_and_injected_into_subsequent_messages (if not already passing)
- test_plan_does_not_consume_a_turn_from_turns_used_budget
- test_plan_is_not_emitted_more_than_once_per_question

Run: `pytest tests/test_plan_first_mode.py -k "plan_does_not_consume or plan_is_not_emitted" -v`

---

## Step 6: Entry Point Updates (agent.py)

- [ ] Update `run_agent()` entry point
- [ ] Call `requires_plan()` before agentic loop
- [ ] Conditionally add planning instruction to initial prompt
- [ ] Ensure no overhead for simple questions

**Tests to Pass**: Already covered by Step 4 tests

---

## Step 7: API Updates (api.py)

- [ ] Update `Answer` response model to include optional "plan" field
- [ ] Modify `ask_question()` to capture plan from agent
- [ ] Return plan in response when present
- [ ] Return null/empty plan when not present

**Tests to Pass**: 2
- test_api_response_includes_plan_field_when_plan_was_produced
- test_api_response_plan_field_is_null_when_no_plan_was_produced

Run: `pytest tests/test_plan_first_mode.py -k "api_response" -v`

---

## Step 8: TUI Updates (main.py)

- [ ] Update `ProgressDisplay` class to handle "plan" events
- [ ] Add plan rendering in `add_step()` method
- [ ] Add plan panel styling in `render()` method
- [ ] Use Rich Panel or Rule for visual distinction
- [ ] Style plan differently from tool results (e.g., dim blue)

**Tests to Pass**: 2
- test_tui_renders_plan_panel_without_crashing
- test_tui_plan_panel_contains_plan_text

Run: `pytest tests/test_plan_first_mode.py -k "tui" -v`

---

## Step 9: MAX_TURNS Accounting (agent.py)

- [ ] Review MAX_TURNS = 10 constant
- [ ] Separate turns_used from total_iterations
- [ ] Only increment turns_used for actual tool calls
- [ ] Plan action increments total_iterations but not turns_used
- [ ] Ensure MAX_TURNS enforcement still works

**Tests to Pass**: 1
- test_max_turns_still_enforced_with_planning

Run: `pytest tests/test_plan_first_mode.py::test_max_turns_still_enforced_with_planning -v`

---

## Integration Testing

- [ ] Run all integration tests
- [ ] Verify comparison questions work end-to-end
- [ ] Verify percentage questions work end-to-end
- [ ] Verify simple questions don't use planning

**Tests to Pass**: 3
- test_full_integration_comparison_question_produces_correct_answer_via_plan
- test_integration_percentage_question_uses_plan
- test_simple_question_does_not_trigger_planning

Run: `pytest tests/test_plan_first_mode.py -k "integration" -v`

---

## Edge Cases and Error Handling

- [ ] Verify plan followed by error recovers gracefully
- [ ] Verify MAX_TURNS still enforced with planning
- [ ] Test all edge cases pass

**Tests to Pass**: 2
- test_agent_handles_plan_followed_by_error_gracefully
- test_max_turns_still_enforced_with_planning (if not already passing)

Run: `pytest tests/test_plan_first_mode.py -k "error or max_turns" -v`

---

## Final Verification

- [ ] All 30 tests pass
- [ ] No regressions in existing tests
- [ ] Manual testing of comparison questions
- [ ] Manual testing of percentage questions
- [ ] Manual testing of simple questions (no planning)
- [ ] Check TUI displays plans correctly
- [ ] Check API returns plan field correctly
- [ ] Code review ready

Run: `pytest tests/test_plan_first_mode.py -v`
Expected: **30 PASSED, 0 FAILED**

---

## Post-Implementation

- [ ] Update CLAUDE.md with new feature
- [ ] Update README.md with plan-first mode info
- [ ] Add example questions to documentation
- [ ] Create PR for review
- [ ] Merge to main branch

---

## Progress Tracking

Current Status: **NOT STARTED**

Tests Passing: 0 / 30
Implementation Steps Complete: 0 / 9

Last Updated: 2026-06-26

---

## Notes

- Run tests frequently during implementation
- Use `-v` flag for verbose output
- Use `-x` flag to stop on first failure
- Use `-s` flag to see print statements
- Commit after each successful step
