"""
AgentDSS — Track B — Context Manager (in-memory version, Week 1)

Responsibility: hold the growing decision chain for one session and
package the right context for the next agent to call. DB persistence
(Week 2 task) wraps this later — this class is the core logic, kept
independent of storage so it's unit-testable without a database.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid
from datetime import datetime, timezone


@dataclass
class DecisionEvent:
    """Mirrors the Decision Event Schema (proposal Section VI) exactly."""
    agent_role: str
    options_presented: list  # [{"text": str, "confidence": float}, ...]
    decision_type: str       # "accepted_option" | "override"
    decision_text: str
    override_flag: bool
    preview_shown: Optional[dict] = None
    confidence_score: Optional[float] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ContextManager:
    """
    One instance per session (one full 4-agent run against one scenario).
    Not thread-safe across sessions by design — each session gets its own
    instance; concurrency across sessions is the API layer's problem, not this class's.
    """

    def __init__(self, session_id: str, problem_statement: str):
        self.session_id = session_id
        self.problem_statement = problem_statement
        self.decision_chain: list[DecisionEvent] = []

    def record_decision(
        self,
        agent_role: str,
        options_presented: list,
        chosen_text: str,
        preview_shown: Optional[dict] = None,
    ) -> DecisionEvent:
        """
        Records a human decision. Detects override automatically by checking
        whether chosen_text matches one of the presented option texts.
        """
        matched_option = next(
            (opt for opt in options_presented if opt["text"] == chosen_text), None
        )
        is_override = matched_option is None

        event = DecisionEvent(
            agent_role=agent_role,
            options_presented=options_presented,
            decision_type="override" if is_override else "accepted_option",
            decision_text=chosen_text,
            override_flag=is_override,
            preview_shown=preview_shown,
            confidence_score=None if is_override else matched_option.get("confidence"),
        )
        self.decision_chain.append(event)
        return event

    def get_context_for_next_agent(self) -> dict:
        """
        Packages everything the next agent needs: the original disruption
        description plus every confirmed decision so far, in order.
        """
        return {
            "problem_statement": self.problem_statement,
            "prior_decisions": [
                {
                    "agent_role": e.agent_role,
                    "decision_text": e.decision_text,
                    "was_override": e.override_flag,
                }
                for e in self.decision_chain
            ],
        }

    def get_full_log(self) -> list[dict]:
        """Full decision log for export (Decision Log Engine, Week 3)."""
        return [
            {
                "event_id": e.event_id,
                "agent_role": e.agent_role,
                "options_presented": e.options_presented,
                "decision_type": e.decision_type,
                "decision_text": e.decision_text,
                "override_flag": e.override_flag,
                "preview_shown": e.preview_shown,
                "confidence_score": e.confidence_score,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self.decision_chain
        ]


if __name__ == "__main__":
    # Minimal smoke test — proves context changes after an override,
    # which is the core mechanism the whole project depends on.
    cm = ContextManager(session_id="test-1", problem_statement="Supplier A delayed 2 weeks.")

    cm.record_decision(
        agent_role="supplier",
        options_presented=[
            {"text": "Switch to Supplier B", "confidence": 0.87},
            {"text": "Wait for Supplier A", "confidence": 0.4},
        ],
        chosen_text="Switch to Supplier B",
    )

    cm.record_decision(
        agent_role="inventory",
        options_presented=[
            {"text": "Reduce orders 20%", "confidence": 0.7},
            {"text": "Maintain orders", "confidence": 0.5},
        ],
        chosen_text="Arrange local stock manually — treat as normal",
    )

    context = cm.get_context_for_next_agent()
    print("Context for Agent 3 (Logistics):")
    print(context)
    assert context["prior_decisions"][1]["was_override"] is True
    print("\nOverride correctly detected. Smoke test passed.")
