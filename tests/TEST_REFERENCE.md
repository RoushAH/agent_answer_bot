# Test Reference: Streaming Implementation (LOO-31)

## Test File Location
`tests/test_streaming.py` - 506 lines, 17 test functions

## Test-to-Design Mapping

### Design Test Plan → Actual Tests

| Design Plan Test | Implemented Test | Status |
|-----------------|------------------|---------|
| Test 1: call_ollama accumulates full response | `test_call_ollama_accumulates_full_response_from_stream` | ✅ |
| Test 2: streaming_callback called once per token | `test_streaming_callback_called_once_per_token` | ✅ |
| Test 3: streaming_callback=None does not crash | `test_streaming_callback_none_does_not_crash` | ✅ |
| Test 4: KeyboardInterrupt closes connection | `test_keyboard_interrupt_during_streaming_closes_connection` | ✅ |
| Test 5: Malformed stream returns accumulated text | `test_malformed_stream_returns_accumulated_text` | ✅ |
| Test 6: run_agent passes callback through | `test_run_agent_passes_streaming_callback_to_call_ollama` | ✅ |
| Test 7: Bedrock backend ignores callback | `test_bedrock_backend_ignores_streaming_callback` | ✅ |
| Test 8: make_streaming_callback appends tokens | `test_make_streaming_callback_appends_tokens_to_display_buffer` | ✅ |
| Test 9: Live display reverts after streaming | `test_live_display_reverts_to_normal_after_streaming` | ✅ |
| Test 10: API endpoint returns correct answer | `test_api_endpoint_returns_correct_answer_with_streaming` | ✅ |

### Bonus Tests (Beyond Design Plan)

| Test | Purpose |
|------|---------|
| `test_full_streaming_workflow_with_ollama` | Integration test for complete streaming workflow |
| `test_streaming_with_progress_display_integration` | UI integration test |
| `test_streaming_with_empty_tokens` | Edge case: empty chunks |
| `test_streaming_with_malformed_json_chunk` | Edge case: bad JSON |
| `test_streaming_callback_that_raises_exception` | Edge case: callback errors |
| `test_streaming_with_very_long_response` | Performance test with 100 tokens |
| `test_streaming_display_respects_line_limit` | UI constraint test |

## Key Test Patterns Used

### 1. Mocking Streaming Responses
```python
mock_response = Mock()
mock_response.iter_lines = Mock(return_value=[
    b'{"message": {"content": "Hello"}, "done": false}',
    b'{"message": {"content": " world"}, "done": false}',
    b'{"message": {"content": ""}, "done": true}',
])
```

### 2. Callback Testing
```python
received_tokens = []
callback = lambda token: received_tokens.append(token)

with patch('agent.requests.post', return_value=mock_response):
    result = call_ollama(messages, system, streaming_callback=callback)

assert len(received_tokens) == 2
```

### 3. KeyboardInterrupt Handling
```python
def iter_side_effect():
    yield b'{"message": {"content": "Start"}, "done": false}'
    raise KeyboardInterrupt("User cancelled")

mock_response.iter_lines = Mock(side_effect=iter_side_effect)
mock_response.close = Mock()

with pytest.raises(KeyboardInterrupt):
    call_ollama(messages, system)

mock_response.close.assert_called_once()
```

### 4. Integration with Agent Loop
```python
with patch('agent.call_ollama') as mock_ollama, \
     patch('agent.query_db') as mock_db, \
     patch('agent.BACKEND', 'ollama'):
    
    dummy_callback = Mock()
    result = run_agent("Question?", streaming_callback=dummy_callback)
    
    # Verify callback was passed through
    assert 'streaming_callback' in mock_ollama.call_args[1]
```

## Running Tests

### Run all streaming tests:
```bash
pytest tests/test_streaming.py -v
```

### Run specific test:
```bash
pytest tests/test_streaming.py::test_call_ollama_accumulates_full_response_from_stream -v
```

### Run with coverage:
```bash
pytest tests/test_streaming.py --cov=agent --cov=main --cov-report=term-missing
```

## Code Quality Notes

✅ **Modern pytest patterns**: Using fixtures, parametrization where appropriate
✅ **Comprehensive mocking**: unittest.mock for external dependencies
✅ **Clear test names**: Descriptive function names following TDD best practices
✅ **Good documentation**: Docstrings explain what each test verifies
✅ **Edge cases covered**: Empty tokens, malformed JSON, exceptions, long responses
✅ **Follows existing patterns**: Matches style from test_plan_first_mode.py

## Next Steps

1. Run tests to confirm they fail (expected - no implementation yet)
2. Implement streaming in `call_ollama()` in agent.py
3. Add `streaming_callback` parameter to `run_agent()`
4. Implement `make_streaming_callback()` in main.py
5. Update ProgressDisplay for streaming text
6. Wire callback into `process_query()` in main.py
7. Re-run tests to verify they pass

## Test Execution Timeline

- **Before implementation**: All 17 tests should FAIL
- **After agent.py changes**: Tests 1-7 should PASS
- **After main.py changes**: Tests 8-9 should PASS  
- **After integration**: Tests 10-17 should PASS
- **Final state**: All 17 tests PASS
