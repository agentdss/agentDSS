"""
AgentDSS — Track B — Context Manager DB persistence (Week 2 task 3)

The Week 1 ContextManager is pure in-memory logic, kept storage-agnostic
on purpose so it's unit-testable without a DB (see test_context_manager.py).
This module is the thin layer that saves/loads that state to Postgres,
so a session survives across API requests instead of living only inside
one Python process's memory — required the moment Track C's FastAPI
endpoints are stateless per-request, which they will be.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Session as SessionRow, Decision as DecisionRow, DecisionType
from context_manager import ContextManager, DecisionEvent

def create_session(problem_statement: str, run_condition: str = "live_demo", random_seed: int | None = None) -> str:
    """Creates a new session row and returns its id. Call once per scenario run."""
    with get_db() as db:
        session_row = SessionRow(
            id=str(uuid.uuid4()),
            problem_statement=problem_statement,
            run_condition=run_condition,
            random_seed=random_seed,
        )
        db.add(session_row)
        db.flush()
        return session_row.id


def load_context_manager(session_id: str) -> ContextManager:
    """
    Rebuilds a ContextManager from whatever decisions are already
    persisted for this session — e.g. after a server restart, or when
    a different API worker process picks up an in-progress session.
    """
    with get_db() as db:
        session_row = db.query(SessionRow).filter(SessionRow.id == session_id).first()
        if session_row is None:
            raise ValueError(f"No session found with id={session_id}")

        cm = ContextManager(session_id=session_id, problem_statement=session_row.problem_statement)

        decisions = (
            db.query(DecisionRow)
            .filter(DecisionRow.session_id == session_id)
            .order_by(DecisionRow.step_index)
            .all()
        )
        for d in decisions:
            cm.decision_chain.append(DecisionEvent(
                event_id=str(d.event_id),
                agent_role=d.agent_role.value,
                options_presented=d.options_presented,
                decision_type=d.decision_type.value,
                decision_text=d.decision_text,
                override_flag=d.override_flag,
                preview_shown=d.preview_shown,
                confidence_score=d.confidence_score,
                timestamp=d.timestamp,
            ))
        return cm


def persist_decision(session_id: str, step_index: int, event: DecisionEvent) -> None:
    """
    Writes one DecisionEvent (produced by ContextManager.record_decision)
    to the decisions table. Called immediately after record_decision so
    a crash mid-session loses at most the one in-flight decision, not
    the whole chain.
    """
    with get_db() as db:
        db.add(DecisionRow(
            event_id=event.event_id,
            session_id=session_id,
            step_index=step_index,
            agent_role=event.agent_role,
            options_presented=event.options_presented,
            decision_type=DecisionType(event.decision_type),
            decision_text=event.decision_text,
            override_flag=event.override_flag,
            preview_shown=event.preview_shown,
            confidence_score=event.confidence_score,
            timestamp=event.timestamp,
        ))


if __name__ == "__main__":
    # Smoke test: create a session, record two decisions, "restart"
    # (simulated by loading a fresh ContextManager from the DB only),
    # and confirm the reloaded state matches what was written.
    from database import init_db
    init_db()

    session_id = create_session(problem_statement="Supplier A delayed 2 weeks.", run_condition="live_demo")
    print(f"Created session: {session_id}")

    cm = ContextManager(session_id=session_id, problem_statement="Supplier A delayed 2 weeks.")

    event1 = cm.record_decision(
        agent_role="supplier",
        options_presented=[{"text": "Switch to Supplier B", "confidence": 0.87}],
        chosen_text="Switch to Supplier B",
    )
    persist_decision(session_id, step_index=0, event=event1)

    event2 = cm.record_decision(
        agent_role="inventory",
        options_presented=[{"text": "Reduce orders 20%", "confidence": 0.7}],
        chosen_text="Arrange local stock manually — treat as normal",
    )
    persist_decision(session_id, step_index=1, event=event2)

    # Simulate a restart: forget the in-memory cm, reload purely from DB.
    reloaded_cm = load_context_manager(session_id)

    assert len(reloaded_cm.decision_chain) == 2, "Reload lost a decision"
    assert reloaded_cm.decision_chain[1].override_flag is True, "Override flag lost on reload"
    assert reloaded_cm.get_context_for_next_agent()["prior_decisions"][1]["was_override"] is True

    print("Reload verified: 2 decisions persisted and reloaded correctly, override flag intact.")
    print(reloaded_cm.get_context_for_next_agent()) 
