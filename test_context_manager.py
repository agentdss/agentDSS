"""
AgentDSS — Track B — Unit tests for ContextManager (Week 2 task 4)

Deliberately test the in-memory ContextManager (context_manager.py),
not context_presistence.py — this class was kept storage-agnostic
specifically so its core logic (override detection, context packaging)
can be tested fast, without spinning up a database.

Run with: pytest test_context_manager.py -v
"""

import pytest
from context_manager import ContextManager


def make_options(*texts_and_confidences):
    """Helper: [('Switch to B', 0.87), ('Wait', 0.4)] -> options list."""
    return [{"text": t, "confidence": c} for t, c in texts_and_confidences]


class TestAcceptedOption:
    def test_accepting_a_presented_option_is_not_an_override(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        options = make_options(("Switch to Supplier B", 0.87), ("Wait", 0.4))

        event = cm.record_decision(
            agent_role="supplier",
            options_presented=options,
            chosen_text="Switch to Supplier B",
        )

        assert event.override_flag is False
        assert event.decision_type == "accepted_option"
        assert event.confidence_score == 0.87

    def test_accepted_option_confidence_is_pulled_from_matching_option(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        options = make_options(("Option A", 0.6), ("Option B", 0.9))

        event = cm.record_decision(
            agent_role="logistics",
            options_presented=options,
            chosen_text="Option B",
        )

        assert event.confidence_score == 0.9


class TestOverride:
    def test_free_text_not_matching_any_option_is_an_override(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        options = make_options(("Reduce orders 20%", 0.7), ("Maintain orders", 0.5))

        event = cm.record_decision(
            agent_role="inventory",
            options_presented=options,
            chosen_text="Arrange local stock manually — treat as normal",
        )

        assert event.override_flag is True
        assert event.decision_type == "override"

    def test_override_has_no_confidence_score(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        options = make_options(("Option A", 0.6))

        event = cm.record_decision(
            agent_role="finance",
            options_presented=options,
            chosen_text="Something not in the options at all",
        )

        assert event.confidence_score is None


class TestContextPropagation:
    """
    These tests protect the single highest-risk assumption in the whole
    project: that an override actually changes what the next agent sees.
    """

    def test_context_for_next_agent_includes_prior_decisions_in_order(self):
        cm = ContextManager(session_id="s1", problem_statement="Supplier A delayed.")
        cm.record_decision(
            agent_role="supplier",
            options_presented=make_options(("Switch to B", 0.8)),
            chosen_text="Switch to B",
        )
        cm.record_decision(
            agent_role="inventory",
            options_presented=make_options(("Reduce orders", 0.6)),
            chosen_text="Reduce orders",
        )

        context = cm.get_context_for_next_agent()

        assert context["problem_statement"] == "Supplier A delayed."
        assert len(context["prior_decisions"]) == 2
        assert context["prior_decisions"][0]["agent_role"] == "supplier"
        assert context["prior_decisions"][1]["agent_role"] == "inventory"

    def test_override_is_visible_to_next_agent_context(self):
        """
        The core mechanism: if a human overrides Agent 2, Agent 3's
        context must reflect that override, not the option that was
        originally offered.
        """
        cm = ContextManager(session_id="s1", problem_statement="Supplier A delayed.")
        cm.record_decision(
            agent_role="inventory",
            options_presented=make_options(("Reduce orders 20%", 0.7)),
            chosen_text="Arrange local stock manually — treat as normal",
        )

        context = cm.get_context_for_next_agent()
        prior = context["prior_decisions"][0]

        assert prior["was_override"] is True
        assert prior["decision_text"] == "Arrange local stock manually — treat as normal"
        assert prior["decision_text"] != "Reduce orders 20%"

    def test_empty_chain_produces_empty_prior_decisions(self):
        cm = ContextManager(session_id="s1", problem_statement="No decisions yet.")
        context = cm.get_context_for_next_agent()
        assert context["prior_decisions"] == []


class TestDecisionLog:
    def test_full_log_matches_decision_event_schema_fields(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        cm.record_decision(
            agent_role="supplier",
            options_presented=make_options(("Switch to B", 0.8)),
            chosen_text="Switch to B",
        )

        log = cm.get_full_log()

        assert len(log) == 1
        required_fields = {
            "event_id", "agent_role", "options_presented", "decision_type",
            "decision_text", "override_flag", "preview_shown",
            "confidence_score", "timestamp",
        }
        assert required_fields.issubset(log[0].keys())

    def test_multiple_decisions_preserve_order_in_log(self):
        cm = ContextManager(session_id="s1", problem_statement="Test disruption")
        cm.record_decision(agent_role="supplier", options_presented=make_options(("A", 0.5)), chosen_text="A")
        cm.record_decision(agent_role="inventory", options_presented=make_options(("B", 0.5)), chosen_text="B")
        cm.record_decision(agent_role="logistics", options_presented=make_options(("C", 0.5)), chosen_text="C")

        log = cm.get_full_log()
        roles_in_order = [entry["agent_role"] for entry in log]

        assert roles_in_order == ["supplier", "inventory", "logistics"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
