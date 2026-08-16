"""
AgentDSS — Track B — Scenario Suite Generator (Week 1 task 5 / Week 2-3 build-out)

Generates 20-30 synthetic disruption scenarios by templating across
disruption type and parameter ranges, using a FIXED SEED so the same
suite can be regenerated identically by anyone re-running this file —
this is the reproducibility commitment from proposal Section XI, not
optional polish.

Each scenario becomes one row in the scenario_runs table (models.py)
and gets run under both RunCondition.BASELINE_NO_OVERRIDE and
RunCondition.OVERRIDE_ENABLED during the Week 6 eval harness run.
"""

import random
from dataclasses import dataclass, asdict

# Fixed seed — do not change this without noting it explicitly in the
# report. Changing it silently breaks the reproducibility claim in
# Section XI ("the same seed reproduces the same 20-30 scenarios").
SCENARIO_GENERATION_SEED = 42

DISRUPTION_TYPES = [
    "supplier_delay",
    "demand_spike",
    "logistics_failure",
    "combined",
]

# Nodes drawn from the Southern California logistics backbone dataset's
# supplier/route fields — placeholder names here; swap for real dataset
# entity IDs once Track A finalizes the CSV partition.
AFFECTED_NODES = [
    "supplier_a", "supplier_b", "supplier_c",
    "route_north", "route_coastal", "route_inland",
    "warehouse_1", "warehouse_2",
]

SEVERITY_RANGE = (0.2, 0.95)       # 0.0-1.0, avoid trivial (near-zero) scenarios
TIME_HORIZON_RANGE_DAYS = (3, 21)  # short delay to a 3-week disruption


@dataclass
class Scenario:
    scenario_index: int
    disruption_type: str
    severity: float
    affected_node: str
    time_horizon_days: int
    problem_statement_text: str
    generation_seed: int = SCENARIO_GENERATION_SEED


def _problem_statement(disruption_type: str, node: str, severity: float, horizon: int) -> str:
    """
    Turns generated parameters into the free-text problem statement
    Agent 1 actually reads. Kept templated rather than hand-written so
    scenario count can scale without linearly scaling authoring effort.
    """
    severity_word = "minor" if severity < 0.4 else "moderate" if severity < 0.7 else "severe"

    templates = {
        "supplier_delay": f"{node.replace('_', ' ').title()} has a {severity_word} delay of {horizon} days due to unforeseen disruption.",
        "demand_spike": f"Demand at {node.replace('_', ' ').title()} has spiked {severity_word}ly, expected to persist for {horizon} days.",
        "logistics_failure": f"{node.replace('_', ' ').title()} is experiencing a {severity_word} logistics failure affecting shipments for approximately {horizon} days.",
        "combined": f"{node.replace('_', ' ').title()} is facing a {severity_word} combined disruption (supply and logistics) expected to last {horizon} days.",
    }
    return templates[disruption_type]


def generate_scenario_suite(n_scenarios: int = 25, seed: int = SCENARIO_GENERATION_SEED) -> list[Scenario]:
    """
    Deterministic given (n_scenarios, seed). Re-running this function
    with the same arguments must always produce the identical suite —
    that determinism IS the reproducibility guarantee, so don't call
    random.seed() anywhere else in the codebase using this same RNG state
    without resetting it first.

    Uses STRATIFIED sampling for disruption_type: cycles evenly through
    DISRUPTION_TYPES rather than drawing each independently at random.
    Pure random choice at n=25 produced a lopsided suite in practice
    (9 'combined' vs. 4 'supplier_delay' scenarios out of 25) — stratifying
    guarantees near-even coverage across types regardless of seed.
    """
    rng = random.Random(seed)
    scenarios = []

    base_types = list(DISRUPTION_TYPES) * (n_scenarios // len(DISRUPTION_TYPES) + 1)
    type_sequence = base_types[:n_scenarios]
    rng.shuffle(type_sequence)

    base_nodes = list(AFFECTED_NODES) * (n_scenarios // len(AFFECTED_NODES) + 1)
    node_sequence = base_nodes[:n_scenarios]
    rng.shuffle(node_sequence)

    for i in range(n_scenarios):
        disruption_type = type_sequence[i]
        node = node_sequence[i]
        severity = round(rng.uniform(*SEVERITY_RANGE), 2)
        horizon = rng.randint(*TIME_HORIZON_RANGE_DAYS)

        scenarios.append(Scenario(
            scenario_index=i,
            disruption_type=disruption_type,
            severity=severity,
            affected_node=node,
            time_horizon_days=horizon,
            problem_statement_text=_problem_statement(disruption_type, node, severity, horizon),
        ))

    return scenarios


def suite_coverage_report(scenarios: list[Scenario]) -> dict:
    """
    Sanity check: are scenarios actually varied, or did randomness
    collapse onto a few repeated combinations? Run this before
    finalizing the suite (Week 4 task).
    """
    from collections import Counter
    type_counts = Counter(s.disruption_type for s in scenarios)
    node_counts = Counter(s.affected_node for s in scenarios)
    severities = [s.severity for s in scenarios]

    return {
        "total_scenarios": len(scenarios),
        "disruption_type_distribution": dict(type_counts),
        "affected_node_distribution": dict(node_counts),
        "severity_min": min(severities),
        "severity_max": max(severities),
        "severity_mean": round(sum(severities) / len(severities), 3),
    }


if __name__ == "__main__":
    suite = generate_scenario_suite(n_scenarios=25)

    print(f"Generated {len(suite)} scenarios with seed={SCENARIO_GENERATION_SEED}\n")
    for s in suite[:3]:
        print(f"[{s.scenario_index}] {s.disruption_type} | severity={s.severity} | {s.problem_statement_text}")
    print("...\n")

    report = suite_coverage_report(suite)
    print("Coverage report:")
    for k, v in report.items():
        print(f"  {k}: {v}")

    suite_again = generate_scenario_suite(n_scenarios=25)
    assert [asdict(s) for s in suite] == [asdict(s) for s in suite_again], \
        "Reproducibility broken — same seed produced a different suite!"
    print("\nReproducibility verified: regenerating with the same seed produces an identical suite.")
