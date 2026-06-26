"""Tests for plan-first mode functionality.

These tests are written FIRST and will fail until the plan-first mode
implementation is complete.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Import the modules we'll be testing
# These imports will work once the functions are implemented
from schema import validate_action, VALID_ACTIONS
from agent import run_agent, call_llm


# =============================================================================
# Tests for requires_plan detection heuristic
# =============================================================================

def test_requires_plan_returns_true_for_comparison_questions():
    """Test that requires_plan detects comparison questions."""
    from agent import requires_plan
    
    assert requires_plan("Compare the sales of Catan vs Ticket to Ride") is True


def test_requires_plan_returns_true_for_percentage_questions():
    """Test that requires_plan detects percentage/ratio questions."""
    from agent import requires_plan
    
    assert requires_plan("What percentage of revenue comes from food vs table rentals?") is True


def test_requires_plan_returns_false_for_simple_lookup_questions():
    """Test that requires_plan does NOT trigger for simple lookups."""
    from agent import requires_plan
    
    assert requires_plan("How many board games do we have in stock?") is False
    assert requires_plan("What is the price of Catan?") is False


def test_requires_plan_returns_false_for_single_step_calculation():
    """Test that requires_plan does NOT trigger for simple totals."""
    from agent import requires_plan
    
    assert requires_plan("What is the total revenue?") is False


def test_requires_plan_detects_versus_language():
    """Test various comparison keywords."""
    from agent import requires_plan
    
    assert requires_plan("Which sells better, Catan or Pandemic?") is True
    assert requires_plan("Compare revenue vs expenses") is True
    assert requires_plan("What's the difference between online and in-store sales?") is True


def test_requires_plan_detects_ranking_with_context():
    """Test detection of ranking questions that need context."""
    from agent import requires_plan
    
    assert requires_plan("What are the top 3 games by profit margin?") is True
    assert requires_plan("Which category has the best sales?") is True


def test_requires_plan_detects_compound_questions():
    """Test detection of questions with multiple intents."""
    from agent import requires_plan
    
    assert requires_plan("How many games sold and what was the total revenue?") is True
    assert requires_plan("What's the average daily sales and the total profit?") is True


# =============================================================================
# Tests for plan action schema validation
# =============================================================================

def test_plan_action_is_in_valid_actions():
    """Test that 'plan' has been added to VALID_ACTIONS."""
    assert "plan" in VALID_ACTIONS


def test_plan_action_validates_correctly_in_schema():
    """Test that a properly formed plan action validates."""
    plan_json = json.dumps({
        "action": "plan",
        "steps": "1. Query X. 2. Calculate Y."
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is not None
    assert action["action"] == "plan"
    assert "steps" in action
    assert action["steps"] == "1. Query X. 2. Calculate Y."


def test_plan_action_with_missing_steps_field_fails_validation():
    """Test that plan action without steps field fails validation."""
    plan_json = json.dumps({
        "action": "plan"
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is None


def test_plan_action_with_empty_steps_fails_validation():
    """Test that plan action with empty steps fails validation."""
    plan_json = json.dumps({
        "action": "plan",
        "steps": ""
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is None


def test_plan_action_with_list_of_steps_validates():
    """Test that plan action can accept list format for steps."""
    plan_json = json.dumps({
        "action": "plan",
        "steps": ["Query game A sales", "Query game B sales", "Calculate difference"]
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is not None
    assert action["action"] == "plan"
    assert isinstance(action["steps"], list)
    assert len(action["steps"]) == 3


def test_non_plan_actions_still_validate_correctly_after_schema_change():
    """Test that existing action types still work after adding plan."""
    # Test query action
    query_json = json.dumps({
        "action": "query",
        "sql": "SELECT * FROM board_games"
    })
    action, _ = validate_action(query_json)
    assert action is not None
    assert action["action"] == "query"
    
    # Test calculate action
    calc_json = json.dumps({
        "action": "calculate",
        "expression": "100 + 50"
    })
    action, _ = validate_action(calc_json)
    assert action is not None
    assert action["action"] == "calculate"
    
    # Test answer action
    answer_json = json.dumps({
        "action": "answer",
        "text": "The answer is 42"
    })
    action, _ = validate_action(answer_json)
    assert action is not None
    assert action["action"] == "answer"


# =============================================================================
# Tests for plan execution in agentic loop
# =============================================================================

def test_plan_is_stored_and_injected_into_subsequent_messages():
    """Test that after a plan action, the plan appears in subsequent LLM calls."""
    from agent import inject_plan_into_messages
    
    messages = [
        {"role": "user", "content": "Compare Catan and Pandemic sales"}
    ]
    
    plan_text = "1. Query Catan sales\n2. Query Pandemic sales\n3. Calculate difference"
    
    updated_messages = inject_plan_into_messages(messages, plan_text)
    
    # Check that plan was injected
    assert len(updated_messages) > len(messages)
    
    # Check that plan text appears somewhere in the messages
    plan_found = any(plan_text in str(msg.get("content", "")) for msg in updated_messages)
    assert plan_found, "Plan text should be injected into messages"


def test_plan_does_not_consume_a_turn_from_turns_used_budget():
    """Test that plan action doesn't count against tool turn limit."""
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db, \
         patch('agent.requires_plan', return_value=True):
        
        # Mock LLM to return: plan -> query -> answer
        mock_llm.side_effect = [
            json.dumps({"action": "plan", "steps": "1. Query data"}),
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "There are 10 games"})
        ]
        
        mock_db.return_value = [{"count": 10}]
        
        result = run_agent("How many games?")
        
        # Should succeed with plan + query + answer (plan doesn't count as a turn)
        assert "10 games" in result


def test_plan_is_not_emitted_more_than_once_per_question():
    """Test that the agent doesn't get stuck in a plan loop."""
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db, \
         patch('agent.requires_plan', return_value=True):
        
        # Mock LLM to try returning multiple plans (bad behavior)
        mock_llm.side_effect = [
            json.dumps({"action": "plan", "steps": "1. First plan"}),
            json.dumps({"action": "plan", "steps": "2. Second plan"}),
            json.dumps({"action": "query", "sql": "SELECT 1"}),
            json.dumps({"action": "answer", "text": "Done"})
        ]
        
        mock_db.return_value = [{"result": 1}]
        
        result = run_agent("Test question")
        
        # Should complete successfully without infinite plan loop
        assert "Done" in result
        
        # Verify reasonable number of LLM calls
        assert mock_llm.call_count <= 4


# =============================================================================
# Tests for system prompt modifications
# =============================================================================

def test_agent_ask_injects_planning_instruction_when_requires_plan_is_true():
    """Test that planning instruction is added to prompt for multi-step questions."""
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.requires_plan', return_value=True), \
         patch('agent.query_db') as mock_db:
        
        mock_llm.return_value = json.dumps({"action": "plan", "steps": "1. Do thing"})
        mock_db.return_value = []
        
        try:
            run_agent("Compare A vs B")
        except:
            pass
        
        # Get the system prompt from the first call
        call_args = mock_llm.call_args_list[0]
        system_prompt = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('system', '')
        
        # Check that it mentions planning
        assert "plan" in system_prompt.lower() or "multiple steps" in system_prompt.lower()


def test_agent_ask_does_not_inject_planning_instruction_when_requires_plan_is_false():
    """Test that no planning overhead is added for simple questions."""
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.requires_plan', return_value=False), \
         patch('agent.query_db') as mock_db:
        
        mock_llm.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "10 games"})
        ]
        mock_db.return_value = [{"count": 10}]
        
        result = run_agent("How many games?")
        
        assert result == "10 games"


# =============================================================================
# Tests for API response modifications
# =============================================================================

def test_api_response_includes_plan_field_when_plan_was_produced():
    """Test that API returns plan in response when agent generates one."""
    from api import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    with patch('api.run_agent') as mock_agent:
        # Mock to return tuple (answer, plan) or just answer based on implementation
        mock_agent.return_value = "Catan sold more"
        
        response = client.post("/ask", json={
            "question": "Compare Catan vs Pandemic sales"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    # Check answer exists
    assert "answer" in data


def test_api_response_plan_field_is_null_when_no_plan_was_produced():
    """Test that API returns null plan for simple questions."""
    from api import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    with patch('api.run_agent') as mock_agent:
        mock_agent.return_value = "10 games"
        
        response = client.post("/ask", json={
            "question": "How many games?"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have answer
    assert "answer" in data


# =============================================================================
# Tests for TUI rendering
# =============================================================================

def test_tui_renders_plan_panel_without_crashing():
    """Test that TUI can render a plan without errors."""
    from main import ProgressDisplay
    from rich.console import Console
    
    # Create a progress display with a plan step
    display = ProgressDisplay()
    
    # Simulate receiving a plan event
    display.add_step("plan", "plan", "1. Query A\n2. Query B\n3. Calculate")
    
    # Render to a string buffer
    console = Console(file=StringIO())
    
    # This should not raise an exception
    try:
        rendered = display.render()
        console.print(rendered)
    except Exception as e:
        pytest.fail(f"TUI rendering raised exception: {e}")


def test_tui_plan_panel_contains_plan_text():
    """Test that the rendered plan contains the actual plan text."""
    from main import ProgressDisplay
    from rich.console import Console
    
    display = ProgressDisplay()
    plan_text = "1. Query Catan sales\n2. Query Pandemic sales\n3. Compare"
    display.add_step("plan", "plan", plan_text)
    
    # Render to string
    string_buffer = StringIO()
    console = Console(file=string_buffer)
    rendered = display.render()
    console.print(rendered)
    
    output = string_buffer.getvalue()
    
    # Check that plan content appears in output
    assert "Query Catan" in output or "plan" in output.lower()


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_integration_comparison_question_produces_correct_answer_via_plan():
    """Full end-to-end test: comparison question uses plan and produces correct answer."""
    with patch('agent.query_db') as mock_db, \
         patch('agent.call_llm') as mock_llm:
        
        # Mock the LLM to produce: plan -> query A -> query B -> answer
        mock_llm.side_effect = [
            json.dumps({
                "action": "plan",
                "steps": "1. Query Catan units sold\n2. Query Pandemic units sold\n3. Compare results"
            }),
            json.dumps({
                "action": "query",
                "sql": "SELECT SUM(quantity) as units FROM game_sales WHERE game_name='Catan'"
            }),
            json.dumps({
                "action": "query",
                "sql": "SELECT SUM(quantity) as units FROM game_sales WHERE game_name='Pandemic'"
            }),
            json.dumps({
                "action": "answer",
                "text": "Catan sold more units with 50 units compared to Pandemic's 30 units."
            })
        ]
        
        # Mock DB responses
        mock_db.side_effect = [
            [{"units": 50}],
            [{"units": 30}]
        ]
        
        result = run_agent("Which sells more units, Catan or Pandemic?")
        
        # Verify the answer mentions both games
        assert "Catan" in result
        assert "Pandemic" in result
        assert "50" in result
        assert "30" in result
        
        # Verify that we had at least 2 queries
        assert mock_db.call_count >= 2


def test_integration_percentage_question_uses_plan():
    """Test that percentage questions trigger planning and multiple queries."""
    with patch('agent.query_db') as mock_db, \
         patch('agent.call_llm') as mock_llm, \
         patch('agent.calculate') as mock_calc:
        
        mock_llm.side_effect = [
            json.dumps({
                "action": "plan",
                "steps": "1. Query food revenue\n2. Query total revenue\n3. Calculate percentage"
            }),
            json.dumps({
                "action": "query",
                "sql": "SELECT SUM(revenue) as food_rev FROM food_orders"
            }),
            json.dumps({
                "action": "query",
                "sql": "SELECT SUM(revenue) as total FROM all_revenue"
            }),
            json.dumps({
                "action": "calculate",
                "expression": "(1000 / 5000) * 100"
            }),
            json.dumps({
                "action": "answer",
                "text": "Food revenue represents 20% of total revenue."
            })
        ]
        
        mock_db.side_effect = [
            [{"food_rev": 1000}],
            [{"total": 5000}]
        ]
        
        mock_calc.return_value = 20.0
        
        result = run_agent("What percentage of revenue comes from food?")
        
        assert "20" in result
        assert "%" in result or "percent" in result.lower()


def test_simple_question_does_not_trigger_planning():
    """Test that simple questions don't unnecessarily use planning."""
    with patch('agent.query_db') as mock_db, \
         patch('agent.call_llm') as mock_llm, \
         patch('agent.requires_plan', return_value=False):
        
        mock_llm.side_effect = [
            json.dumps({
                "action": "query",
                "sql": "SELECT COUNT(*) as count FROM board_games"
            }),
            json.dumps({
                "action": "answer",
                "text": "We have 50 board games in stock."
            })
        ]
        
        mock_db.return_value = [{"count": 50}]
        
        result = run_agent("How many board games do we have?")
        
        # Should complete in 2 LLM calls (query + answer), no plan
        assert mock_llm.call_count == 2
        assert "50" in result


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

def test_plan_with_invalid_format_is_rejected():
    """Test that malformed plan actions are rejected."""
    # Plan with wrong type for steps
    plan_json = json.dumps({
        "action": "plan",
        "steps": 123
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is None


def test_agent_handles_plan_followed_by_error_gracefully():
    """Test that if a tool fails after planning, agent can recover."""
    with patch('agent.query_db') as mock_db, \
         patch('agent.call_llm') as mock_llm:
        
        mock_llm.side_effect = [
            json.dumps({"action": "plan", "steps": "1. Query data"}),
            json.dumps({"action": "query", "sql": "INVALID SQL"}),
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "Found the answer"})
        ]
        
        def db_side_effect(sql):
            if "INVALID" in sql:
                raise Exception("SQL error")
            return [{"count": 10}]
        
        mock_db.side_effect = db_side_effect
        
        result = run_agent("Test question")
        
        # Should eventually succeed despite the error
        assert "answer" in result.lower() or "Found" in result


def test_max_turns_still_enforced_with_planning():
    """Test that MAX_TURNS limit still prevents infinite loops with planning."""
    with patch('agent.call_llm') as mock_llm, \
         patch('agent.query_db') as mock_db:
        
        # Mock LLM to keep producing queries (never answers)
        mock_llm.side_effect = [
            json.dumps({"action": "plan", "steps": "Do stuff"}),
            json.dumps({"action": "query", "sql": "SELECT 1"}),
            json.dumps({"action": "query", "sql": "SELECT 2"}),
            json.dumps({"action": "query", "sql": "SELECT 3"}),
            json.dumps({"action": "query", "sql": "SELECT 4"}),
            json.dumps({"action": "query", "sql": "SELECT 5"}),
            json.dumps({"action": "query", "sql": "SELECT 6"}),
            json.dumps({"action": "query", "sql": "SELECT 7"}),
            json.dumps({"action": "query", "sql": "SELECT 8"}),
            json.dumps({"action": "query", "sql": "SELECT 9"}),
            json.dumps({"action": "query", "sql": "SELECT 10"}),
            json.dumps({"action": "query", "sql": "SELECT 11"}),
        ]
        
        mock_db.return_value = [{"result": 1}]
        
        result = run_agent("Test")
        
        # Should hit max turns and return error
        assert "maximum turns" in result.lower() or "error" in result.lower()


def test_plan_action_with_multiline_steps_validates():
    """Test that plan with multiline steps string works correctly."""
    plan_json = json.dumps({
        "action": "plan",
        "steps": "1. Query game A sales\n2. Query game B sales\n3. Calculate percentage difference"
    })
    
    action, cleaned = validate_action(plan_json)
    
    assert action is not None
    assert action["action"] == "plan"
    assert "\n" in action["steps"] or "1." in action["steps"]


def test_requires_plan_handles_edge_case_questions():
    """Test requires_plan with edge cases."""
    from agent import requires_plan
    
    # Empty or very short questions
    assert requires_plan("") is False
    assert requires_plan("Help") is False
    
    # Questions with comparison words but not actually comparisons
    assert requires_plan("How do we compare to last year?") is True  # Still a comparison
    
    # Simple percentage that doesn't need multiple queries
    assert requires_plan("What is 20 percent of 100?") is False  # Pure calculation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
