"""Tests for legal-notice drafting (no network)."""

import json
from datetime import date

import pytest

from lawbuddy.chat import save_draft
from lawbuddy.conversation.case import CaseFile
from lawbuddy.conversation.engine import Session
from lawbuddy.conversation.respond import draft_intro
from lawbuddy.drafting import notice as N
from lawbuddy.guard.legal_refs import check_answer
from lawbuddy.kb.loader import load_kb, load_registry
from tests.test_engine import FULL_FACTS, GOOD_ADVICE, ScriptedLLM, analysis, engine

REGISTRY = load_registry()
KB = {c.id: c for c in load_kb()}
TODAY = date(2026, 11, 21)


def every_paragraph():
    paras = [p for ps in N.LEGAL_BASIS.values() for p in ps]
    paras += [N.WAGES_ON_LEAVING, N.WAGES_MONTHLY, N.WAGES_CLAIM, N.ECOMMERCE_REFUND]
    paras += [N.Paragraph(text, N.CONSEQUENCE_CHUNKS[cat]) for cat, text in N.CONSEQUENCE.items()]
    return paras


@pytest.mark.parametrize("para", every_paragraph(), ids=lambda p: p.text[:40])
def test_every_legal_sentence_in_a_notice_is_traced_to_its_kb_chunks(para):
    assert set(para.chunks) <= set(KB), para.chunks
    passages = [{"title": KB[c].title, "text": KB[c].text} for c in para.chunks]
    report = check_answer(para.text, passages, REGISTRY)
    assert report.ok, report.summary()


def case(category, facts=None, parties=None, **kw):
    c = CaseFile()
    c.set_category(category)
    c.merge({"facts": facts or {}, "parties": parties or {}, **kw})
    return c


def facts_json(*paras):
    return json.dumps({"paragraphs": list(paras)})


USER = [{"role": "user", "content": "I paid 2 lakh deposit and moved out on 30 September, HSR Layout Bangalore"}]


# --- numbers ------------------------------------------------------------------------------------------------

def test_amounts_in_lakh_and_digits_match():
    assert N.numbers_in("2 lakh") == N.numbers_in("Rs. 2,00,000") == {200000}
    assert 32000 in N.numbers_in("₹32,000") and 28000 in N.numbers_in("२८,०००")
    assert N.numbers_in("1.5 lakh and 30k") == {150000, 30000}


def test_unsupported_numbers_ignore_placeholders_and_catch_invented_ones():
    known = "deposit 2 lakh, moved out 30 September"
    assert N.unsupported_numbers("I paid Rs. 2,00,000 and left on 30 September.", known) == []
    assert N.unsupported_numbers("I left on 30 September 2026.", known) == [2026]
    assert N.unsupported_numbers("Rent was [● fill: monthly rent of 25000].", known) == []


# --- assembly -----------------------------------------------------------------------------------------------

def test_deposit_notice_has_code_written_legal_parts_and_placeholders_for_the_unknown():
    llm = ScriptedLLM(facts_json("1. I rented the flat in HSR Layout, Bangalore and paid a deposit of Rs. 2,00,000.",
                                 "I vacated on 30 September and handed over the keys."))
    c = case("deposit", {"deposit_amount": "Rs. 2,00,000", "move_out_date": "30 September"})
    d = N.build_notice(llm, c, USER, REGISTRY, today=TODAY)
    assert d.text.startswith("**LEGAL NOTICE**") and "Date: 21 November 2026" in d.text
    assert "1. I rented the flat" in d.text and "1. 1." not in d.text             # code numbers the paragraphs
    assert "section 73 of the Indian Contract Act, 1872" in d.text
    assert "refund the security deposit of Rs. 2,00,000" in d.text and "15 (fifteen) days" in d.text
    assert d.placeholders == ["your full name", "your full address", "landlord's full name", "their full address"]
    assert d.warnings == [] and "deposit-overview" in d.chunks
    assert check_answer(d.text, [{"title": KB[c].title, "text": KB[c].text} for c in d.chunks], REGISTRY).ok


def test_known_names_and_addresses_fill_the_header():
    c = case("deposit", FULL_FACTS, {"user_name": "Asha Rao", "other_name": "R. Kumar"})
    d = N.build_notice(ScriptedLLM(facts_json("I paid a deposit of Rs. 2,00,000.")), c,
                       [{"role": "user", "content": "2 lakh deposit"}], REGISTRY, today=TODAY)
    assert "**From:** Asha Rao" in d.text and "**To:** R. Kumar" in d.text and d.text.rstrip().endswith("Asha Rao")
    assert "your full name" not in d.placeholders


def test_law_in_the_facts_is_regenerated_once():
    llm = ScriptedLLM(facts_json("Under Section 420 IPC you cheated me of the deposit of 2 lakh."),
                      facts_json("I paid a deposit of 2 lakh."))
    d = N.build_notice(llm, case("deposit", FULL_FACTS), USER, REGISTRY, today=TODAY)
    assert "420" not in d.text and any("attempt 1" in t for t in d.trace)
    assert "420 IPC" in llm.calls[1][1]["content"]                                 # the feedback names it


def test_law_in_the_facts_twice_is_removed():
    bad = facts_json("Under Section 420 IPC you cheated me. I paid a deposit of 2 lakh.")
    d = N.build_notice(ScriptedLLM(bad, bad), case("deposit", FULL_FACTS), USER, REGISTRY, today=TODAY)
    facts = d.text.split("**Facts**")[1].split("**Legal position**")[0]
    assert "420" not in facts and "I paid a deposit of 2 lakh." in facts


def test_an_invented_number_twice_becomes_a_warning():
    bad = facts_json("I paid a deposit of Rs. 2,50,000 on 3 March.")
    d = N.build_notice(ScriptedLLM(bad, bad), case("deposit", FULL_FACTS), USER, REGISTRY, today=TODAY)
    assert d.warnings and "250,000" in d.warnings[0] and "3" in d.warnings[0]


@pytest.mark.parametrize("status, expected", [("resigned in August", ["17(2)", "45"]),
                                              ("still working there", ["17(1)", "45"]),
                                              (None, ["17(2)", "17(1)", "45"])])
def test_salary_notice_cites_the_right_payment_rule(status, expected):
    c = case("salary", {"employer": "Acme", "employment_status": status} if status else {"employer": "Acme"})
    texts = " | ".join(p.text for p in N.legal_basis(c))
    for s in ["17(2)", "17(1)"]:
        assert (s in texts) == (s in expected)


def test_consumer_notice_adds_the_ecommerce_rule_only_for_online_purchases():
    online = case("consumer", {"seller": "Amazon", "product_or_service": "phone"})
    offline = case("consumer", {"seller": "a shop on MG Road", "product_or_service": "fridge"})
    assert N.ECOMMERCE_REFUND in N.legal_basis(online) and N.ECOMMERCE_REFUND not in N.legal_basis(offline)


def test_salary_total_is_never_computed_by_code_or_model():
    c = case("salary", {"employer": "Acme", "unpaid_period": "June to August", "monthly_salary": "28,000"})
    assert "[● fill: total amount due]" in N.demand(c)


# --- conversation -------------------------------------------------------------------------------------------

def test_asking_for_a_notice_in_conversation_returns_a_draft():
    llm = ScriptedLLM(analysis(facts=FULL_FACTS, intent="draft"), facts_json("I paid a deposit of Rs. 2,00,000."))
    r = engine(llm).turn(Session(), "please draft the notice")
    assert r.kind == "draft" and r.draft["text"].startswith("**LEGAL NOTICE**")
    assert "Before you send it" in r.text and "your full name" in r.text and r.draft["chunks"]


def test_advice_offers_to_draft_a_notice():
    r = engine(ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE)).turn(Session(), "deposit not returned")
    assert 'draft the notice' in r.text


def test_hindi_intro_and_step_numbering():
    text = draft_intro("Hindi", [], ["Check these numbers"])
    assert text.count("1. ") == 1 and "भेजने से पहले" in text and "कृपया जाँचें" in text


def test_drafts_are_saved_without_overwriting(tmp_path):
    a = save_draft("s1", "first", tmp_path)
    b = save_draft("s1", "second", tmp_path)
    assert a.name == "s1-1.md" and b.name == "s1-2.md" and a.read_text() == "first\n"


def test_the_employer_or_seller_from_the_facts_fills_the_to_line():
    c = case("salary", {"employer": "Brightwave Solutions", "employment_status": "resigned"})
    d = N.build_notice(ScriptedLLM(facts_json("I worked for you.")), c, [], REGISTRY, today=TODAY)
    assert "**To:** Brightwave Solutions" in d.text and not any("employer" in p for p in d.placeholders)


@pytest.mark.parametrize("raw, shown", [("150000", "Rs. 1,50,000"), ("24999", "Rs. 24,999"), ("Rs 28000", "Rs. 28,000"),
                                        ("₹1,50,000", "Rs. 1,50,000"), ("10000000", "Rs. 1,00,00,000"),
                                        ("999", "Rs. 999"), ("2 lakh", "2 lakh"),
                                        ("Rs. 28,000 per month", "Rs. 28,000 per month")])
def test_bare_amounts_are_shown_as_rupees_with_indian_grouping(raw, shown):
    """Run 3: the notices said "refund the security deposit of 150000"."""
    assert N.rupees(raw) == shown


def test_amounts_in_the_subject_and_demand_are_formatted():
    c = case("deposit", {"deposit_amount": "150000", "move_out_date": "31 October"})
    d = N.build_notice(ScriptedLLM(facts_json("I paid a deposit of Rs. 1,50,000.")), c,
                       [{"role": "user", "content": "deposit Rs. 1,50,000"}], REGISTRY, today=TODAY)
    assert "deposit of Rs. 1,50,000" in d.text and "150000" not in d.text


def test_the_facts_prompt_forbids_embellishment():
    """Run 3: "returned the premises in good condition" and "fulfilling my obligations", which the user never said."""
    assert "good condition" in N.FACTS_SYSTEM and "conclusions" in N.FACTS_SYSTEM
