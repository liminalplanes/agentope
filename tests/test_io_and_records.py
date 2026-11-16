import gzip
import json

import pytest

from agentope import DataError, load_decisions, load_outcomes
from agentope.io import format_duration, parse_duration, parse_time
from agentope.outcomes import Outcome, join_outcomes

BASE = {
    "decision_id": "a",
    "t": 100.0,
    "decision_point": "tool_choice",
    "context": {"intent": "refund"},
    "candidates": ["search", "escalate"],
    "chosen": "search",
    "join_key": "k",
}


def dec(**kw):
    return BASE | kw


def test_parse_duration():
    assert parse_duration("7d") == 7 * 86400
    assert parse_duration("12h") == 12 * 3600
    assert parse_duration("1.5m") == 90
    assert parse_duration(30) == 30
    assert format_duration(7 * 86400) == "1w"
    assert format_duration(3 * 86400) == "3d"
    for bad in ("", "7x", "-1d", 0, True):
        with pytest.raises(DataError):
            parse_duration(bad)


def test_parse_time():
    assert parse_time(5, "w") == 5.0
    assert parse_time("5.5", "w") == 5.5
    assert parse_time("1970-01-01T00:01:00Z", "w") == 60.0
    with pytest.raises(DataError, match="no timezone"):
        parse_time("2026-01-01T00:00:00", "w")
    with pytest.raises(DataError):
        parse_time(True, "w")


def test_jsonl_and_gzip_detected_by_content(tmp_path):
    rows = [dec(decision_id="a"), dec(decision_id="b")]
    plain = tmp_path / "d.jsonl"
    plain.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n")
    packed = tmp_path / "d.data"  # no .gz extension on purpose
    with gzip.open(packed, "wt") as f:
        f.write("\n".join(json.dumps(r) for r in rows))
    assert [d.decision_id for d in load_decisions(plain)] == ["a", "b"]
    assert [d.decision_id for d in load_decisions(packed)] == ["a", "b"]


def test_unknown_fields_ignored_and_errors_have_locations(tmp_path):
    assert load_decisions([dec(future_field=1)])[0].chosen == "search"
    p = tmp_path / "d.jsonl"
    p.write_text(json.dumps(dec()) + "\n{not json\n")
    with pytest.raises(DataError, match=r"d\.jsonl:2"):
        load_decisions(p)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"chosen": "lookup"}, "not among candidates"),
        ({"context": {"nested": {"x": 1}}}, "flat dict"),
        ({"propensity": 0}, r"\(0, 1\]"),
        ({"candidates": ["a", "a"], "chosen": "a"}, "duplicates"),
        ({"propensity_source": "guessed"}, "propensity_source"),
        ({"join_key": None}, "join_key"),
        ({"explored": True, "propensity": 0.9}, "uniform exploration"),
        ({"logging_probs": {"search": 0.5, "escalate": 0.6}}, "sum to"),
        ({"logging_probs": {"search": 0.4, "escalate": 0.6}, "propensity": 0.5}, "disagrees"),
    ],
)
def test_decision_validation(override, message):
    with pytest.raises(DataError, match=message):
        load_decisions([dec(**override)])


def test_duplicate_ids_rejected():
    with pytest.raises(DataError, match="duplicate decision_id"):
        load_decisions([dec(), dec()])


def test_propensity_rules():
    explored = load_decisions(
        [
            dec(
                explored=True,
                candidates=["search", "escalate", "x"],
                safe_candidates=["search", "escalate"],
            )
        ]
    )[0]
    assert explored.propensity == 0.5
    assert explored.propensity_source == "logged"
    assert explored.logging_probs == {"search": 0.5, "escalate": 0.5, "x": 0.0}

    from_probs = load_decisions([dec(logging_probs={"search": 0.25, "escalate": 0.75})])[0]
    assert from_probs.propensity == 0.25 and from_probs.has_logged_propensity

    unsourced = load_decisions([dec(propensity=0.3)])[0]
    assert unsourced.propensity_source == "logged"

    none = load_decisions([dec()])[0]
    assert not none.has_logged_propensity


def test_outcomes_csv_and_jsonl(tmp_path):
    csv_path = tmp_path / "o.csv"
    csv_path.write_text("join_key,t,value\nk,150,1\nk,160,0.5\n")
    jsonl_path = tmp_path / "o.jsonl"
    jsonl_path.write_text('{"join_key": "k", "t": 150, "value": 1}\n')
    assert load_outcomes(csv_path) == [Outcome("k", 150.0, 1.0), Outcome("k", 160.0, 0.5)]
    assert load_outcomes(jsonl_path) == [Outcome("k", 150.0, 1.0)]
    bad = tmp_path / "bad.csv"
    bad.write_text("key,t,value\nk,1,1\n")
    with pytest.raises(DataError, match="missing columns: join_key"):
        load_outcomes(bad)


def test_join_rules():
    decisions = load_decisions(
        [
            dec(decision_id="a", t=100.0),
            dec(decision_id="b", t=200.0),
            dec(decision_id="c", join_key="z"),
        ]
    )
    outcomes = [
        Outcome("k", 99.0, 5.0),  # before every decision: unused
        Outcome("k", 150.0, 1.0),  # first in a's window
        Outcome("k", 160.0, 2.0),  # second in a's window: ignored
        Outcome("k", 300.0, 3.0),  # exactly b.t + horizon: outside (half-open)
        Outcome("nope", 100.0, 1.0),  # matches no decision
    ]
    result = join_outcomes(decisions, outcomes, horizon=100.0, default_reward=-1.0)
    # a gets the first outcome in [100, 200); b's window [200, 300) excludes t=300
    assert result.rewards == [1.0, -1.0, -1.0]
    assert result.rewarded == [True, False, False]
    assert result.unmatched == 4
