"""Agent execution tracker modeling multi-turn decisions and tool execution flows."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStepType(str, Enum):
    """Classification of an agent execution step in a multi-turn graph."""

    USER_INPUT = "user_input"
    LLM_DECISION = "llm_decision"
    TOOL_EXECUTION = "tool_execution"
    TOOL_RESULT = "tool_result"
    FINAL_ANSWER = "final_answer"


class AgentStep(BaseModel):
    """Single transition node within an agent reasoning and execution graph."""

    model_config = ConfigDict(frozen=True)

    step_index: int
    step_type: AgentStepType
    name: str
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=_utc_now)


class AgentTracker:
    """Models and validates multi-turn autonomous AI agent execution graphs.

    Graph flow:
        User Input -> LLM Decision -> Tool Execution -> Tool Result -> Next Decision -> Final Answer
    """

    def __init__(self, agent_name: str = "default_agent") -> None:
        self.agent_name = agent_name
        self.steps: list[AgentStep] = []

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    def add_step(
        self,
        step_type: AgentStepType,
        name: str,
        data: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> AgentStep:
        """Append a new execution step to the graph."""
        step = AgentStep(
            step_index=len(self.steps),
            step_type=step_type,
            name=name,
            data=data or {},
            duration_ms=duration_ms,
        )
        self.steps.append(step)
        return step

    def add_user_input(
        self,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Record the initial or follow-up user prompt initiating a reasoning turn."""
        data: dict[str, Any] = {"prompt": prompt}
        if metadata:
            data.update(metadata)
        return self.add_step(AgentStepType.USER_INPUT, name="user_input", data=data)

    def add_llm_decision(
        self,
        decision: Any,
        tool_calls: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Record an LLM reasoning output or tool invocation decision."""
        data: dict[str, Any] = {"decision": str(decision)}
        if tool_calls is not None:
            data["tool_calls"] = tool_calls
        if metadata:
            data.update(metadata)
        return self.add_step(AgentStepType.LLM_DECISION, name="llm_decision", data=data)

    def add_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Record the invocation of an external or local tool with arguments."""
        data: dict[str, Any] = {"tool_name": tool_name, "arguments": arguments}
        if metadata:
            data.update(metadata)
        return self.add_step(
            AgentStepType.TOOL_EXECUTION,
            name=f"execute_{tool_name}",
            data=data,
        )

    def add_tool_result(
        self,
        tool_name: str,
        result: Any,
        duration_ms: float = 0.0,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Record the return value or failure of a completed tool execution."""
        data: dict[str, Any] = {"tool_name": tool_name, "result": result}
        if error:
            data["error"] = error
        if metadata:
            data.update(metadata)
        return self.add_step(
            AgentStepType.TOOL_RESULT,
            name=f"result_{tool_name}",
            data=data,
            duration_ms=duration_ms,
        )

    def add_final_answer(
        self,
        answer: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Record the agent's completed final response returned to the user."""
        data: dict[str, Any] = {"answer": answer}
        if metadata:
            data.update(metadata)
        return self.add_step(AgentStepType.FINAL_ANSWER, name="final_answer", data=data)

    def visualize_flow(self) -> str:
        """Generate a human-readable diagram of the agent's execution flow."""
        if not self.steps:
            return f"Agent Flow [{self.agent_name}]: (empty)"

        lines: list[str] = [f"Agent Flow [{self.agent_name}]:"]
        for i, step in enumerate(self.steps):
            detail = ""
            if step.step_type == AgentStepType.USER_INPUT:
                prompt_preview = str(step.data.get("prompt", ""))[:40]
                detail = f'prompt="{prompt_preview}"'
            elif step.step_type == AgentStepType.LLM_DECISION:
                calls = step.data.get("tool_calls")
                detail = f"invokes {len(calls)} tool(s)" if calls else "generates response"
            elif step.step_type == AgentStepType.TOOL_EXECUTION:
                tname = step.data.get("tool_name", "")
                args = step.data.get("arguments", {})
                detail = f"{tname}({args})"
            elif step.step_type == AgentStepType.TOOL_RESULT:
                tname = step.data.get("tool_name", "")
                res = str(step.data.get("result", ""))[:30]
                detail = f"{tname} -> {res} ({step.duration_ms:.1f}ms)"
            elif step.step_type == AgentStepType.FINAL_ANSWER:
                ans_preview = str(step.data.get("answer", ""))[:40]
                detail = f'answer="{ans_preview}"'

            step_line = f"  [{step.step_index}] {step.step_type.value.upper()}: {detail}"
            lines.append(step_line)
            if i < len(self.steps) - 1:
                lines.append("       |")
                lines.append("       v")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete agent execution trace to dictionary format."""
        return {
            "agent_name": self.agent_name,
            "steps": [step.model_dump(mode="json") for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTracker:
        """Reconstruct an AgentTracker instance from serialized dictionary data."""
        tracker = cls(agent_name=data.get("agent_name", "default_agent"))
        for s in data.get("steps", []):
            tracker.steps.append(AgentStep.model_validate(s))
        return tracker
