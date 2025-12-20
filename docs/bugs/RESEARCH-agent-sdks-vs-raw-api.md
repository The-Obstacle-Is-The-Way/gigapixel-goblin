# Research: Agent SDKs vs Raw API Calls

> **Question**: Should GIANT use an Agent SDK instead of hand-rolling LLM orchestration?

## TL;DR

**No, switching to an Agent SDK is not a root-cause fix for BUG-025** (the `input_text` vs `output_text` issue). It's an OpenAI Responses API content-type requirement; any wrapper still has to satisfy it.

**However**, adopting an SDK could reduce future bugs and maintenance burden for:
- Multi-turn conversation state management
- Tool calling orchestration
- Error handling and retries
- Provider abstraction

---

## Available SDKs (December 2025)

### 1. OpenAI Agents SDK

- **Repo**: [openai/openai-agents-python](https://github.com/openai/openai-agents-python)
- **Install**: `pip install openai-agents`
- **What it does**: Provides agent loop, handoffs, guardrails, sessions, tracing
- **Key feature**: Structured output via Pydantic models with `output_type` parameter

```python
from agents import Agent, Runner

agent = Agent(
    name="GIANT",
    instructions="Navigate WSI slides...",
    tools=[crop_tool, answer_tool],
    output_type=StepResponse,  # Pydantic model
)

result = await Runner.run(agent, messages)
```

**Pros**:
- Built-in agent loop (no manual orchestration)
- Automatic structured output parsing
- Provider-agnostic (supports 100+ LLMs)
- Built-in tracing for debugging

**Cons**:
- Another dependency to maintain
- May not fit our specific WSI navigation loop exactly
- Learning curve

### 2. Claude Agent SDK

- **Repo**: [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
- **Install**: `pip install claude-agent-sdk`
- **What it does**: Same harness that powers Claude Code
- **Architecture**: Communicates via the (bundled) Claude Code CLI process

```python
from claude_agent_sdk import ClaudeSDKClient

client = ClaudeSDKClient()
result = await client.query(
    prompt="Navigate this slide...",
    tools=[crop_tool, answer_tool],
)
```

**Pros**:
- Battle-tested (powers Claude Code)
- Built-in memory management for long-running tasks
- MCP (Model Context Protocol) integration

**Cons**:
- Subprocess-based architecture (CLI orchestration)
- Anthropic-specific (not provider-agnostic)

### 3. LangChain / LangGraph

- **Install**: `pip install langchain langgraph`
- **What it does**: General-purpose LLM framework with agent orchestration

**Pros**:
- Mature ecosystem
- Provider-agnostic
- Graph-based workflow definition (LangGraph)

**Cons**:
- Heavy abstraction layer
- Frequent breaking changes historically
- Overkill for our simple loop

### 4. LlamaIndex

- **Focus**: RAG and data retrieval, not agent orchestration
- **Not relevant** for GIANT's use case (we're doing navigation, not retrieval)

---

## What We Hand-Rolled vs What SDKs Provide

| Component | GIANT (Current) | OpenAI Agents SDK | Claude Agent SDK |
|-----------|-----------------|-------------------|------------------|
| Agent loop | `GIANTAgent.run()` | `Runner.run()` | `client.query()` |
| Multi-turn state | `ContextManager` | `Sessions` | Built-in memory |
| Structured output | Manual JSON schema | `output_type` Pydantic | Tool responses |
| Tool calling | Manual in prompt | `tools` parameter | MCP tools |
| Retries | `tenacity` decorator | Built-in | Built-in |
| Circuit breaker | `CircuitBreaker` class | Not included | Not included |
| Provider abstraction | `LLMProvider` Protocol | Provider-agnostic | Anthropic-only |
| Tracing | `structlog` | Built-in tracing | Built-in |

---

## Would an SDK Have Prevented BUG-025?

**Not inherently.** BUG-025 is about the OpenAI Responses API requiring different content types for user vs assistant messages (`input_text` vs `output_text`). This is:

1. A low-level API format issue
2. Specific to the Responses API (not Chat Completions)
3. Would still need to be handled correctly in any SDK

An SDK *could* have avoided us writing the buggy conversion layer (because the SDK already implements the correct wire format), but the underlying constraint still exists and must be satisfied by the SDK/wrapper.

---

## Recommendation

### Keep Current Architecture (For Now)

**Reasons**:
1. **We're 90% done** - All 12 specs implemented, one P0 bug to fix
2. **Simple loop** - GIANT's navigation loop is straightforward (crop → observe → decide)
3. **Provider flexibility** - We need Anthropic, OpenAI, AND Gemini support
4. **Control** - Our custom implementation lets us optimize for WSI-specific needs

### Consider SDK Migration Later If:
1. We add complex multi-agent coordination (e.g., CONCH tool)
2. We need persistent memory across sessions
3. Maintenance burden of raw API calls becomes excessive
4. We want to leverage SDK-specific features (tracing, guardrails)

### Immediate Action: Fix BUG-025
The fix is simple (pass `role` to `message_content_to_openai()`). No architectural change needed.

---

## References

- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK GitHub](https://github.com/openai/openai-agents-python)
- [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Claude Agent SDK GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Comparing Open-Source AI Agent Frameworks](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- [LangChain vs LlamaIndex Comparison](https://xenoss.io/blog/langchain-langgraph-llamaindex-llm-frameworks)
