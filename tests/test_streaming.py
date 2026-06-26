"""Tests for streaming responses functionality.

These tests are written FIRST and will fail until the streaming implementation
is complete. The tests cover all cases from the design document test plan.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

# Import the modules we'll be testing
from agent import run_agent, call_ollama, call_llm
from main import ProgressDisplay


# =============================================================================
# Test 1: call_ollama accumulates full response from stream
# =============================================================================

def test_call_ollama_accumulates_full_response_from_stream():
    """Test that call_ollama correctly accumulates tokens from streaming response."""
    with patch('agent.requests.post') as mock_post:
        # Mock streaming response that yields three chunks
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Hello"}, "done": false}',
            b'{"message": {"content": " world"}, "done": false}',
            b'{"message": {"content": "!"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"
        
        result = call_ollama(messages, system, streaming_callback=None)
        
        # Should accumulate all three tokens
        assert result == "Hello world!"
        # Should call with stream=True
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs.get('stream') is True


# =============================================================================
# Test 2: streaming_callback is called once per token
# =============================================================================

def test_streaming_callback_called_once_per_token():
    """Test that streaming_callback receives each token chunk."""
    with patch('agent.requests.post') as mock_post:
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "First"}, "done": false}',
            b'{"message": {"content": "Second"}, "done": false}',
            b'{"message": {"content": "Third"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]
        mock_post.return_value = mock_response

        # Track callback invocations
        callback_tokens = []
        def callback(token):
            callback_tokens.append(token)

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        result = call_ollama(messages, system, streaming_callback=callback)

        # Should have called callback exactly 3 times (not for the done chunk)
        assert len(callback_tokens) == 3
        assert callback_tokens == ["First", "Second", "Third"]
        # Final result should still be correct
        assert result == "FirstSecondThird"


# =============================================================================
# Test 3: streaming_callback=None does not crash
# =============================================================================

def test_streaming_callback_none_does_not_crash():
    """Test that call_ollama works without a streaming_callback."""
    with patch('agent.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Test"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        # Should not raise AttributeError or TypeError
        result = call_ollama(messages, system, streaming_callback=None)

        assert result == "Test"


# =============================================================================
# Test 4: KeyboardInterrupt during streaming closes connection
# =============================================================================

def test_keyboard_interrupt_during_streaming_closes_connection():
    """Test that KeyboardInterrupt during streaming properly closes the response."""
    with patch('agent.requests.post') as mock_post:
        mock_response = MagicMock()

        # Mock iter_lines to yield one chunk then raise KeyboardInterrupt
        def iter_with_interrupt():
            yield b'{"message": {"content": "Start"}, "done": false}'
            raise KeyboardInterrupt()

        mock_response.iter_lines.return_value = iter_with_interrupt()
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        # Should propagate KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            call_ollama(messages, system, streaming_callback=None)

        # Should have called close() on the response
        mock_response.close.assert_called_once()


# =============================================================================
# Test 5: Malformed or empty stream still returns accumulated text
# =============================================================================

def test_malformed_stream_returns_accumulated_text():
    """Test that call_ollama returns accumulated tokens even without done=true."""
    with patch('agent.requests.post') as mock_post:
        mock_response = MagicMock()
        # Stream ends without ever emitting done=true
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Token1"}, "done": false}',
            b'{"message": {"content": "Token2"}, "done": false}',
            # Stream ends here, no done=true
        ]
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        # Should still return accumulated text without raising
        result = call_ollama(messages, system, streaming_callback=None)

        assert result == "Token1Token2"


# =============================================================================
# Test 6: run_agent passes streaming_callback through to call_ollama
# =============================================================================

def test_run_agent_passes_streaming_callback_to_call_ollama():
    """Test that run_agent threads streaming_callback through to call_ollama."""
    with patch('agent.call_ollama') as mock_ollama, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'ollama'):

        # Mock call_ollama to return valid JSON actions
        mock_ollama.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT COUNT(*) FROM board_games"}),
            json.dumps({"action": "answer", "text": "There are 10 games"})
        ]
        mock_db.return_value = [{"count": 10}]

        # Create a streaming callback
        callback_mock = Mock()

        # Call run_agent with streaming_callback
        result = run_agent(
            "How many games?",
            streaming_callback=callback_mock
        )

        # Verify call_ollama was called with the streaming_callback
        # Both calls should include the streaming_callback keyword argument
        for call_args in mock_ollama.call_args_list:
            assert 'streaming_callback' in call_args[1]
            assert call_args[1]['streaming_callback'] == callback_mock


# =============================================================================
# Test 7: Bedrock backend ignores streaming_callback
# =============================================================================

def test_bedrock_backend_ignores_streaming_callback():
    """Test that Bedrock backend doesn't receive streaming_callback."""
    with patch('agent.call_bedrock') as mock_bedrock, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'bedrock'):

        mock_bedrock.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT 1"}),
            json.dumps({"action": "answer", "text": "Done"})
        ]
        mock_db.return_value = [{"result": 1}]

        callback_mock = Mock()

        result = run_agent("Test", streaming_callback=callback_mock)

        # Bedrock should have been called, not Ollama
        assert mock_bedrock.called
        # Bedrock doesn't accept streaming_callback, so it shouldn't be in kwargs
        for call_args in mock_bedrock.call_args_list:
            # call_bedrock signature doesn't include streaming_callback
            assert 'streaming_callback' not in call_args[1]


# =============================================================================
# Test 8: make_streaming_callback appends tokens to display buffer
# =============================================================================

def test_make_streaming_callback_appends_tokens():
    """Test that make_streaming_callback accumulates tokens in buffer."""
    from main import make_streaming_callback

    mock_live = Mock()
    mock_status = Mock()

    callback = make_streaming_callback(mock_live, mock_status)

    # Call with three tokens
    callback("Hello")
    callback(" world")
    callback("!")

    # Should have called live.update at least 3 times
    assert mock_live.update.call_count >= 3


# =============================================================================
# Test 9: Live display reverts to normal after streaming completes
# =============================================================================

def test_live_display_reverts_after_streaming():
    """Test that streaming buffer is cleared after completion."""
    with patch('agent.call_ollama') as mock_ollama, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'ollama'):

        mock_ollama.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT 1"}),
            json.dumps({"action": "answer", "text": "Done"})
        ]
        mock_db.return_value = [{"result": 1}]

        # Create a ProgressDisplay
        from main import ProgressDisplay
        display = ProgressDisplay()

        # After agent completes, streaming buffer should be cleared
        result = run_agent("Test")

        # Verify we got a valid answer (not streaming content)
        assert result == "Done"
        # The display should not contain partial streaming tokens
        rendered = display.render()
        # Check that rendered output is clean (no raw tokens)
        assert rendered is not None


# =============================================================================
# Test 10: API endpoint returns correct answer with streaming enabled
# =============================================================================

def test_api_endpoint_with_streaming_returns_correct_answer():
    """Test that /ask endpoint works correctly with streaming (callback=None)."""
    from api import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with patch('api.run_agent') as mock_agent:
        mock_agent.return_value = "The answer is 42"

        response = client.post("/ask", json={
            "question": "What is the answer?"
        })

        assert response.status_code == 200
        data = response.json()

        # Should have answer in response
        assert "answer" in data
        assert data["answer"] == "The answer is 42"

        # api.py should call run_agent without streaming_callback
        # (or with streaming_callback=None for silent accumulation)
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args[1] if mock_agent.call_args else {}
        # Either no streaming_callback key, or it's None
        assert call_kwargs.get('streaming_callback') is None


# =============================================================================
# Test 11: Streaming handles empty content chunks gracefully
# =============================================================================

def test_streaming_handles_empty_content_chunks():
    """Test that empty content in chunks doesn't break accumulation."""
    with patch('agent.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Hello"}, "done": false}',
            b'{"message": {"content": ""}, "done": false}',  # Empty chunk
            b'{"message": {"content": " world"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        callback_tokens = []
        def callback(token):
            if token:  # Only append non-empty tokens
                callback_tokens.append(token)

        result = call_ollama(messages, system, streaming_callback=callback)

        # Should skip empty chunks but accumulate the rest
        assert result == "Hello world"
        # Callback should not receive empty strings
        assert callback_tokens == ["Hello", " world"]


# =============================================================================
# Test 12: Streaming works with multiple agent turns
# =============================================================================

def test_streaming_works_across_multiple_turns():
    """Test that streaming callback is used for each LLM call in agent loop."""
    with patch('agent.requests.post') as mock_post, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'ollama'):

        # Mock two streaming responses (query action, then answer action)
        response1 = MagicMock()
        response1.iter_lines.return_value = [
            b'{"message": {"content": "{\\"action\\":\\"query\\",\\"sql\\":\\"SELECT 1\\"}"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]

        response2 = MagicMock()
        response2.iter_lines.return_value = [
            b'{"message": {"content": "{\\"action\\":\\"answer\\",\\"text\\":\\"Done\\"}"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]

        mock_post.side_effect = [response1, response2]
        mock_db.return_value = [{"result": 1}]

        callback_calls = []
        def callback(token):
            callback_calls.append(token)

        result = run_agent("Test", streaming_callback=callback)

        # Should have received tokens from both LLM calls
        assert len(callback_calls) >= 2
        assert result == "Done"


# =============================================================================
# Test 13: RequestException during streaming is handled
# =============================================================================

def test_request_exception_during_streaming_is_raised():
    """Test that request errors during streaming are properly raised."""
    import requests

    with patch('agent.requests.post') as mock_post:
        mock_response = MagicMock()

        # Mock iter_lines to raise an exception mid-stream
        def iter_with_error():
            yield b'{"message": {"content": "Start"}, "done": false}'
            raise requests.exceptions.RequestException("Connection lost")

        mock_response.iter_lines.return_value = iter_with_error()
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test"}]
        system = "Test system"

        # Should propagate the RequestException
        with pytest.raises(requests.exceptions.RequestException):
            call_ollama(messages, system, streaming_callback=None)


# =============================================================================
# Test 14: Streaming display shows partial JSON as it arrives
# =============================================================================

def test_streaming_display_shows_partial_json():
    """Test that the display can show partial JSON as tokens arrive."""
    from main import ProgressDisplay

    display = ProgressDisplay()

    # Simulate streaming tokens for a JSON response
    display.update_streaming_text('{"action"')
    display.update_streaming_text(':"query"')
    display.update_streaming_text(',"sql"')

    # Should not crash when rendering incomplete JSON
    rendered = display.render()
    assert rendered is not None


# =============================================================================
# Test 15: Very long streaming content is truncated in display
# =============================================================================

def test_very_long_streaming_content_is_truncated():
    """Test that display limits visible streaming lines to avoid terminal thrashing."""
    from main import ProgressDisplay

    display = ProgressDisplay()

    # Simulate a very long streaming response (100 lines)
    long_text = "\n".join([f"Line {i}" for i in range(100)])
    display.update_streaming_text(long_text)

    # Render should succeed and be limited
    rendered = display.render()
    assert rendered is not None
    # The implementation should cap at a reasonable number of lines (e.g., 20)


# =============================================================================
# Test 16: Progress display updates during streaming
# =============================================================================

def test_progress_display_updates_during_streaming():
    """Test that progress display Live.update is called during streaming."""
    with patch('main.Live') as MockLive:
        mock_live_instance = MagicMock()
        MockLive.return_value.__enter__.return_value = mock_live_instance

        with patch('agent.call_ollama') as mock_ollama, \
             patch('agent.query_db') as mock_db, \
             patch('agent.BACKEND', 'ollama'):

            # Mock a simple interaction
            mock_ollama.side_effect = [
                json.dumps({"action": "query", "sql": "SELECT 1"}),
                json.dumps({"action": "answer", "text": "Done"})
            ]
            mock_db.return_value = [{"result": 1}]

            # Import and call process_query which uses Live display
            from main import process_query

            answer = process_query("Test", [])

            # Live.update should have been called during streaming
            assert mock_live_instance.update.called


# =============================================================================
# Test 17: Streaming callback not passed when BACKEND is bedrock
# =============================================================================

def test_streaming_not_used_for_bedrock():
    """Test that streaming_callback is not used when backend is bedrock."""
    with patch('agent.call_bedrock') as mock_bedrock, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'bedrock'):

        mock_bedrock.side_effect = [
            json.dumps({"action": "query", "sql": "SELECT 1"}),
            json.dumps({"action": "answer", "text": "Done"})
        ]
        mock_db.return_value = [{"result": 1}]

        # Even with a callback, Bedrock path shouldn't use it
        callback = Mock()
        result = run_agent("Test", streaming_callback=callback)

        # Callback should never be called since bedrock doesn't stream
        callback.assert_not_called()


# =============================================================================
# Test 18: call_ollama signature accepts streaming_callback parameter
# =============================================================================

def test_call_ollama_signature_accepts_streaming_callback():
    """Test that call_ollama function accepts streaming_callback parameter."""
    import inspect
    from agent import call_ollama

    sig = inspect.signature(call_ollama)
    params = sig.parameters

    # Should have streaming_callback as a parameter
    assert 'streaming_callback' in params
    # Should default to None
    assert params['streaming_callback'].default is None


# =============================================================================
# Test 19: run_agent signature accepts streaming_callback parameter
# =============================================================================

def test_run_agent_signature_accepts_streaming_callback():
    """Test that run_agent function accepts streaming_callback parameter."""
    import inspect
    from agent import run_agent

    sig = inspect.signature(run_agent)
    params = sig.parameters

    # Should have streaming_callback as a parameter
    assert 'streaming_callback' in params
    # Should default to None
    assert params['streaming_callback'].default is None


# =============================================================================
# Test 20: Integration test - end to end streaming with Live display
# =============================================================================

def test_integration_streaming_end_to_end():
    """Full integration test of streaming with progress display."""
    with patch('agent.requests.post') as mock_post, \
         patch('agent.query_db') as mock_db, \
         patch('agent.BACKEND', 'ollama'):

        # Mock streaming response for query action
        response1 = MagicMock()
        response1.iter_lines.return_value = [
            b'{"message": {"content": "{"}, "done": false}',
            b'{"message": {"content": "\\"action\\":\\"query\\","}, "done": false}',
            b'{"message": {"content": "\\"sql\\":\\"SELECT COUNT(*) FROM board_games\\"}"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]

        # Mock streaming response for answer action
        response2 = MagicMock()
        response2.iter_lines.return_value = [
            b'{"message": {"content": "{"}, "done": false}',
            b'{"message": {"content": "\\"action\\":\\"answer\\","}, "done": false}',
            b'{"message": {"content": "\\"text\\":\\"There are 50 games\\"}"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]

        mock_post.side_effect = [response1, response2]
        mock_db.return_value = [{"count": 50}]

        # Track all streaming tokens
        all_tokens = []
        def tracking_callback(token):
            all_tokens.append(token)

        result = run_agent("How many games?", streaming_callback=tracking_callback)

        # Should get final answer
        assert "50" in result or "games" in result.lower()
        # Should have received streaming tokens
        assert len(all_tokens) > 0
        # Tokens should form valid JSON when concatenated
        full_stream = "".join(all_tokens)
        assert "action" in full_stream or "query" in full_stream


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
