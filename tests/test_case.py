"""Tests for the case file (no network)."""

from lawbuddy.conversation.case import CRITICAL, FACTS, CaseFile


def test_every_critical_fact_is_a_known_fact():
    for cat, keys in CRITICAL.items():
        assert set(keys) <= set(FACTS[cat]), cat


def test_merge_keeps_known_values_and_ignores_placeholders():
    c = CaseFile()
    c.set_category("deposit")
    c.merge({"facts": {"deposit_amount": "50000", "city": "null", "not_a_key": "x"}, "summary": "first"})
    c.merge({"facts": {"deposit_amount": None, "city": "Mysuru"}, "summary": ""})
    assert c.facts["deposit_amount"] == "50000" and c.facts["city"] == "Mysuru" and "not_a_key" not in c.facts
    assert c.summary == "first"


def test_merge_appends_timeline_and_evidence_without_duplicates():
    c = CaseFile()
    c.set_category("salary")
    upd = {"timeline": [{"date": "2026-08-31", "event": "resigned"}, {"date": None, "event": None}],
           "evidence_have": ["payslips"], "evidence_missing": ["offer letter", "payslips"]}
    c.merge(upd)
    c.merge(upd)
    assert c.timeline == [{"date": "2026-08-31", "event": "resigned"}]
    assert c.evidence_have == ["payslips"] and c.evidence_missing == ["offer letter"]


def test_missing_lists_critical_facts_first():
    c = CaseFile()
    c.set_category("consumer")
    c.merge({"facts": {"seller": "Amazon"}})
    assert c.missing(critical_only=True) == ["product_or_service", "problem", "purchase_date"]
    assert c.missing()[:3] == ["product_or_service", "problem", "purchase_date"]
    assert "seller" not in c.missing()


def test_outside_karnataka():
    c = CaseFile()
    assert not c.outside_karnataka()
    c.state = "Karnataka"
    assert not c.outside_karnataka()
    c.state = "Tamil Nadu"
    assert c.outside_karnataka()
