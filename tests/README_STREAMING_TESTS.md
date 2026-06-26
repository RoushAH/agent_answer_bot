# Streaming Response Tests

This document describes the test suite for the streaming responses feature (LOO-31).

## Test File
`tests/test_streaming.py` - 577 lines, 20 comprehensive tests

## Test Coverage

The test suite covers all aspects of the streaming implementation as specified in the design document:

### Core Streaming Functionality (Tests 1-5)
1. **test_call_ollama_accumulates_full_response_from_stream** - Verifies token accumulation
2. **test_streaming_callback_called_once_per_token** - Validates callback invocation
3. **test_streaming_callback_none_does_not_crash** - Tests optional callback parameter
4. **test_keyboard_interrupt_during_streaming_closes_connection** - Ensures proper cleanup
5. **test_malformed_stream_returns_accumulated_text** - Handles incomplete streams gracefully

### Agent Integration (Tests 6-7)
6. **test_run_agent_passes_streaming_callback_to_call_ollama** - Threading callback through agent
7. **test_bedrock_backend_ignores_streaming_callback** - Backend-specific behavior

### Display Layer (Tests 8-9)
8. **test_make_streaming_callback_appends_tokens** - Display buffer accumulation
9. **test_live_display_reverts_after_streaming** - Cleanup after completion

### API Integration (Test 10)
10. **test_api_endpoint_with_streaming_returns_correct_answer** - Silent accumulation for API

### Edge Cases (Tests 11-15)
11. **test_streaming_handles_empty_content_chunks** - Empty token handling
12. **test_streaming_works_across_multiple_turns** - Multi-turn streaming
13. **test_request_exception_during_streaming_is_raised** - Error propagation
14. **test_streaming_display_shows_partial_json** - Incremental JSON display
15. **test_very_long_streaming_content_is_truncated** - Display limits

### UI Integration (Tests 16-17)
16. **test_progress_display_updates_during_streaming** - Live update calls
17. **test_streaming_not_used_for_bedrock** - Backend-specific disable

### Function Signatures (Tests 18-19)
18. **test_call_ollama_signature_accepts_streaming_callback** - Parameter validation
19. **test_run_agent_signature_accepts_streaming_callback** - Parameter validation

### End-to-End Integration (Test 20)
20. **test_integration_streaming_end_to_end** - Full workflow test

## Test Status

**Current Status:** All tests failing (as expected - TDD approach)

```
17 failed, 3 passed, 1 warning in 0.73s
```

The 3 passing tests check existing functionality that's unaffected by streaming:
- `test_live_display_reverts_after_streaming` - Tests existing ProgressDisplay
- `test_api_endpoint_with_streaming_returns_correct_answer` - Tests existing API
- `test_progress_display_updates_during_streaming` - Tests existing Live display

The 17 failing tests are checking for streaming features that don't exist yet:
- Missing `streaming_callback` parameter in `call_ollama()` and `run_agent()`
- Missing `make_streaming_callback()` function in main.py
- Missing streaming implementation (stream=True, iter_lines, etc.)
- Missing `update_streaming_text()` method on ProgressDisplay

## Running Tests

Run all streaming tests:
```bash
py -m pytest tests/test_streaming.py -v
```

Run a specific test:
```bash
py -m pytest tests/test_streaming.py::test_call_ollama_accumulates_full_response_from_stream -v
```

Run with full traceback:
```bash
py -m pytest tests/test_streaming.py -v --tb=long
```

## Implementation Checklist

When implementing the streaming feature, these tests will verify:

- [ ] call_ollama() accepts streaming_callback parameter (default None)
- [ ] call_ollama() uses stream=True and iter_lines() for Ollama requests
- [ ] call_ollama() accumulates tokens into full_response string
- [ ] call_ollama() calls streaming_callback(token) for each chunk if provided
- [ ] call_ollama() handles KeyboardInterrupt and closes connection
- [ ] call_ollama() handles RequestException during streaming
- [ ] call_ollama() returns accumulated text even if stream ends without done=true
- [ ] run_agent() accepts streaming_callback parameter (default None)
- [ ] run_agent() passes streaming_callback to call_ollama() (Ollama backend only)
- [ ] call_bedrock() doesn't receive streaming_callback (incompatible)
- [ ] make_streaming_callback() factory function in main.py
- [ ] make_streaming_callback() returns closure that updates Live display
- [ ] ProgressDisplay.update_streaming_text() method for token accumulation
- [ ] ProgressDisplay.render() displays streaming buffer (capped at ~20 lines)
- [ ] process_query() creates and uses streaming callback for Ollama
- [ ] Streaming buffer is cleared after agent completes
- [ ] API endpoint uses streaming_callback=None (silent accumulation)

## Test Quality Features

All tests follow best practices:
- Use modern mocking with unittest.mock (Mock, MagicMock, patch)
- Test both success and error paths
- Verify both behavior and side effects
- Include edge cases (empty streams, interrupts, errors)
- Test integration points between modules
- Validate function signatures
- Include end-to-end integration test

## Notes

- Tests use Ollama's `/api/chat` response format with `message.content` and `done` fields
- Streaming callback is optional (None = silent accumulation)
- Bedrock backend doesn't support streaming (callback is ignored)
- Display truncates at ~20 lines to prevent terminal thrashing
- Empty content chunks are handled gracefully (not passed to callback)
- KeyboardInterrupt must properly close the response connection
