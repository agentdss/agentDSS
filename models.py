"""
AgentDSS — Track B — Database Models

Schema matches the Decision Event Schema (proposal Section VI):
event_id, agent_role, options_presented, decision_type, decision_text,
override_flag, preview_shown, timestamp.

Adds session/agent/scenario_run tables needed to actually run the pipeline
and the eval harness (baseline vs. override comparison).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, JSON, Enum, Integer, Float, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


class AgentRole(str, enum.Enum):
    SUPPLIER = "supplier"
    INVENTORY = "inventory"
    LOGISTICS = "logistics"
    FINANCE = "finance"


class DecisionType(str, enum.Enum):
    ACCEPTED_OPTION = "accepted_option"
    OVERRIDE = "override"


class RunCondition(str, enum.Enum):
    """Which side of the eval harness comparison this session belongs to."""
    BASELINE_NO_OVERRIDE = "baseline_no_override"
    OVERRIDE_ENABLED = "override_enabled"
    LIVE_DEMO = "live_demo"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    role = Column(Enum(AgentRole), nullable=False)
    description = Column(Text, nullable=True)
    dataset_path = Column(String, nullable=True)
    prompt_template_version = Column(String, nullable=False, default="v1")
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    """One full run of the 4-agent pipeline against one scenario."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    scenario_id = Column(String, ForeignKey("scenario_runs.id"), nullable=True)
    problem_statement = Column(Text, nullable=False)
    run_condition = Column(Enum(RunCondition), nullable=False, default=RunCondition.LIVE_DEMO)
    random_seed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    decisions = relationship("Decision", back_populates="session", order_by="Decision.step_index")


class Decision(Base):
    """
    Matches the Decision Event Schema from proposal Section VI exactly:
    event_id, agent_role, options_presented, decision_type, decision_text,
    override_flag, preview_shown, timestamp.
    """
    __tablename__ = "decisions"

    event_id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=False)
    step_index = Column(Integer, nullable=False)
    agent_role = Column(Enum(AgentRole), nullable=False)

    options_presented = Column(JSON, nullable=False)
    decision_type = Column(Enum(DecisionType), nullable=False)
    decision_text = Column(Text, nullable=False)
    override_flag = Column(Boolean, nullable=False, default=False)
    preview_shown = Column(JSON, nullable=True)

    confidence_score = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="decisions")


class ScenarioRun(Base):
    """Eval harness: one synthetic disruption scenario definition."""
    __tablename__ = "scenario_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    disruption_type = Column(String, nullable=False)
    severity = Column(Float, nullable=False)
    affected_node = Column(String, nullable=False)
    time_horizon_days = Column(Integer, nullable=False)
    generation_seed = Column(Integer, nullable=False)
    problem_statement_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PreviewLog(Base):
    """Raw heuristic Impact Preview computation log (reproducibility: Section XI)."""
    __tablename__ = "preview_log"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    decision_event_id = Column(UUID(as_uuid=False), ForeignKey("decisions.event_id"), nullable=False)
    input_features = Column(JSON, nullable=False)
    risk_score = Column(Float, nullable=False)
    warning_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
