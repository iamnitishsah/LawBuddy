"""Tests for the conversation engine with a scripted fake LLM and a fake retriever (no network)."""

import json

import pytest

from lawbuddy.conversation.engine import Engine, Session, load_config
from lawbuddy.conversation.triage import emergency_rule, normalize
from lawbuddy.guard.legal_refs import UNVERIFIED_NOTE
from lawbuddy.kb.loader import load_registry
from lawbuddy.llm.base import LLMResponse

REGISTRY = load_registry()


class ScriptedLLM:
    """Returns the scripted replies in order (a reply may be (text, finish_reason)); records prompts and budgets."""

    def __init__(self, *replies):
        self.replies, self.calls, self.max_tokens = list(replies), [], []

    def chat(self, messages, temperature=0.0, max_tokens=800):
        self.calls.append(messages)
        self.max_tokens.append(max_tokens)
        if not self.replies:
            raise RuntimeError("the fake LLM ran out of replies")
        reply = self.replies.pop(0)
        text, finish = reply if isinstance(reply, tuple) else (reply, "stop")
        return LLMResponse(text, "fake", 100, 20, 0.1, finish_reason=finish)


class FakeRetriever:
    def __init__(self, hits, mode="primary"):
        self.hits, self.last_mode, self.last_error, self.calls = hits, mode, "", []

    def search(self, query, k=5, category=None):
        self.calls.append({"query": query, "k": k, "category": category})
        return [h for h in self.hits if not category or h["category"] in category][:k]


def hit(cid, category, score, text, title="T"):
    return {"chunk_id": cid, "category": category, "score": score, "title": title, "header": title, "text": text,
            "sources": [{"url": "https://x"}]}


DEPOSIT_HITS = [hit("deposit-steps", "deposit", 0.11, "Send a legal notice; a suit for breach must be filed within "
                    "three years (Limitation Act, 1963, Schedule, Article 55)."),
                hit("general-legal-aid", "general", 0.08, "The DLSA gives free legal aid."),
                hit("salary-claim", "salary", 0.05, "Wage claims go to the authority.")]


def analysis(**kw):
    base = {"emergency": False, "category": "deposit", "intent": "story", "language": "English", "state": "",
            "facts": {}, "timeline": [], "evidence_have": [], "evidence_missing": [], "summary": "s",
            "search_query": "landlord not returning security deposit"}
    base.update(kw)
    return json.dumps(base)


FULL_FACTS = {"deposit_amount": "Rs. 2,00,000", "move_out_date": "October 2026"}
GOOD_ADVICE = ("**Where you stand**\nYour landlord should return the deposit; send a legal notice first [1]. "
               "A suit must be filed within three years (Limitation Act, 1963, Schedule, Article 55) [1].")


def engine(llm, hits=DEPOSIT_HITS, mode="primary", min_score=0.035):
    return Engine(llm, FakeRetriever(hits, mode), REGISTRY, load_config(), min_score=min_score)


# --- layer 1 and 2: classification ------------------------------------------------------------------------

@pytest.mark.parametrize("message", ["my husband beats me every night", "he threatened to kill me",
                                     "I want to end my life", "landlord bola jaan se maar dunga",
                                     "मकान मालिक ने मारपीट की"])
def test_emergency_rule_fires_without_any_model_call(message):
    llm = ScriptedLLM()
    r = engine(llm).turn(Session(), message)
    assert r.kind == "emergency" and "112" in r.text and llm.calls == []


@pytest.mark.parametrize("message", ["my landlord is not returning my deposit", "the phone hit the floor and broke",
                                     "my boss killed the project and stopped my salary"])
def test_emergency_rule_does_not_fire_on_ordinary_messages(message):
    assert emergency_rule(message) is None


def test_emergency_flagged_by_the_analysis():
    r = engine(ScriptedLLM(analysis(emergency=True))).turn(Session(), "he is outside my door with a knife")
    assert r.kind == "emergency"


def test_out_of_scope_gets_a_fixed_referral_and_no_legal_content():
    llm = ScriptedLLM(analysis(category="out_of_scope", out_of_scope_topic="divorce and custody"))
    r = engine(llm).turn(Session(), "I want a divorce")
    assert r.kind == "escalate" and "divorce and custody" in r.text and "15100" in r.text and len(llm.calls) == 1


def test_hindi_users_get_the_hindi_template():
    llm = ScriptedLLM(analysis(category="out_of_scope", language="Hindi"))
    assert "माफ़ कीजिए" in engine(llm).turn(Session(), "तलाक कैसे लें").text


def test_unclear_first_message_asks_to_clarify_with_a_rerank_hint():
    llm = ScriptedLLM(analysis(category="unclear", intent="other", search_query="owner keeping my money"),
                      "Could you tell me what happened?")
    e = engine(llm)
    r = e.turn(Session(), "owner is keeping my money")
    assert r.kind == "clarify" and e.retriever.calls[0]["category"] is None
    assert "a deposit your landlord has not returned" in llm.calls[1][0]["content"]


def test_analysis_output_is_normalized_defensively():
    a = normalize({"category": "Landlord stuff", "intent": "rant", "facts": "none", "timeline": None,
                   "emergency": "false"})
    assert (a.category, a.intent, a.emergency, a.update["facts"], a.update["timeline"]) == \
        ("unclear", "other", False, {}, [])


# --- follow-ups -------------------------------------------------------------------------------------------

def test_story_with_missing_facts_gets_follow_up_questions_then_advice():
    llm = ScriptedLLM(analysis(facts={"city": "Bengaluru"}), "Sorry to hear that. 1. How much? 2. When?",
                      analysis(facts=FULL_FACTS, intent="other"), GOOD_ADVICE)
    e, s = engine(llm), Session()
    r1 = e.turn(s, "landlord in Bengaluru not returning my deposit")
    assert r1.kind == "follow_up" and s.followup_turns == 1 and s.case.facts["city"] == "Bengaluru"
    asked = llm.calls[1][1]["content"]
    assert "how much deposit" in asked and "when you moved out" in asked        # critical facts first
    r2 = e.turn(s, "2 lakh, moved out in October")
    assert r2.kind == "advice" and s.case.facts["deposit_amount"] == "Rs. 2,00,000"
    assert s.case.facts["city"] == "Bengaluru"                                   # earlier facts are kept


def test_follow_ups_stop_after_the_limit():
    cfg_turns = load_config()["max_followup_turns"]
    replies = []
    for _ in range(cfg_turns):
        replies += [analysis(), "question?"]
    replies += [analysis(), GOOD_ADVICE]
    e, s = engine(ScriptedLLM(*replies)), Session()
    replies_out = [e.turn(s, "still not paid") for _ in range(cfg_turns + 1)]
    assert [r.kind for r in replies_out] == ["follow_up"] * cfg_turns + ["advice"]
    assert any("follow-up limit" in t for t in replies_out[-1].trace)


def test_a_general_question_is_answered_without_follow_ups():
    llm = ScriptedLLM(analysis(intent="question"), GOOD_ADVICE)
    r = engine(llm).turn(Session(), "what is the time limit to sue for a deposit?")
    assert r.kind == "advice" and any("advising without" in t for t in r.trace)


# --- layer 3: retrieval as the evidence check -------------------------------------------------------------

def test_retrieval_is_limited_to_the_category_and_general():
    e = engine(ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE))
    r = e.turn(Session(), "deposit not returned")
    assert e.retriever.calls[0]["category"] == ["deposit", "general"]
    assert [p["chunk_id"] for p in r.passages] == ["deposit-steps", "general-legal-aid"]


def test_nothing_above_the_floor_means_no_answer():
    weak = [hit("deposit-steps", "deposit", 0.02, "text")]
    llm = ScriptedLLM(analysis(facts=FULL_FACTS))
    r = engine(llm, hits=weak).turn(Session(), "deposit question")
    assert r.kind == "not_found" and "won't guess" in r.text and len(llm.calls) == 1


def test_the_floor_is_not_applied_to_keyword_fallback_scores():
    weak = [hit("deposit-steps", "deposit", 0.02, "text")]
    r = engine(ScriptedLLM(analysis(facts=FULL_FACTS), "Send a notice [1]."), hits=weak, mode="fallback") \
        .turn(Session(), "deposit question")
    assert r.kind == "advice" and r.retrieval["floor"] is None


# --- advice and the guard ---------------------------------------------------------------------------------

def test_clean_advice_passes_the_guard_and_gets_a_disclaimer():
    r = engine(ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE)).turn(Session(), "deposit not returned")
    assert r.kind == "advice" and r.cited == [1] and r.guard["problems"] == [] and not r.guard["regenerated"]
    assert r.text.endswith("*LawBuddy gives legal information, not legal advice.*")


def test_invented_law_is_regenerated_once():
    bad = "You can also file under Section 420 IPC [1]. Send a legal notice [1]."
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), bad, GOOD_ADVICE)
    r = engine(llm).turn(Session(), "deposit not returned")
    assert r.guard["regenerated"] and not r.guard["removed"] and r.guard["problems"] == []
    assert "420" not in r.text and "420 IPC" in llm.calls[2][1]["content"]     # the feedback names it


def test_invented_law_twice_is_removed_with_a_note():
    bad = "As held in Sharma v. State, you get interest [1]. Send a legal notice [1]."
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), bad, bad)
    r = engine(llm).turn(Session(), "deposit not returned")
    assert r.guard["removed"] and r.guard["problems"] == []
    assert "Sharma" not in r.text and "Send a legal notice [1]." in r.text and UNVERIFIED_NOTE in r.text


def test_outside_karnataka_gets_a_note():
    llm = ScriptedLLM(analysis(facts=FULL_FACTS, state="Maharashtra"), GOOD_ADVICE)
    r = engine(llm).turn(Session(), "my landlord in Pune kept my deposit")
    assert "you mentioned Maharashtra" in r.text


# --- robustness -------------------------------------------------------------------------------------------

def test_an_api_failure_becomes_an_error_reply_and_the_session_continues():
    llm = ScriptedLLM()                                                  # raises on the first call
    e, s = engine(llm), Session()
    r = e.turn(s, "deposit not returned")
    assert r.kind == "error" and "try again" in r.text and len(s.messages) == 2
    llm.replies = [analysis(facts=FULL_FACTS), GOOD_ADVICE]
    assert e.turn(s, "deposit not returned").kind == "advice"


def test_invalid_json_from_the_model_is_retried_once():
    llm = ScriptedLLM("Sure! Here is the analysis: category deposit", analysis(facts=FULL_FACTS), GOOD_ADVICE)
    r = engine(llm).turn(Session(), "deposit not returned")
    assert r.kind == "advice" and r.usage["llm_calls"] == 3


def test_switching_problem_resets_facts_and_follow_ups():
    llm = ScriptedLLM(analysis(facts={"city": "Mysuru"}), "q?",
                      analysis(category="salary", facts={"employer": "Acme"}), "q2?")
    e, s = engine(llm), Session()
    e.turn(s, "deposit issue")
    e.turn(s, "actually my real problem is salary from Acme")
    assert s.case.category == "salary" and s.case.facts["employer"] == "Acme" and "city" in s.case.facts
    assert s.case.facts["city"] is None and s.followup_turns == 1


# --- fixes from the first chat smoke run (outputs/chat_smoke, 2026-11-21) ---------------------------------

def test_an_empty_answer_is_retried_with_a_bigger_budget():
    """Smoke 01 turn 3: gpt-oss spent its token budget reasoning and returned an empty answer."""
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), ("", "length"), GOOD_ADVICE)
    r = engine(llm).turn(Session(), "deposit not returned")
    assert r.kind == "advice" and "Where you stand" in r.text
    assert llm.max_tokens[2] == 2 * llm.max_tokens[1] and any("empty at" in t for t in r.trace)


def test_an_empty_answer_twice_is_an_error_not_a_blank_reply():
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), ("", "length"), ("", "stop"))
    r = engine(llm).turn(Session(), "deposit not returned")
    assert r.kind == "error" and r.text.strip()


def test_the_advice_prompt_never_shows_unknown_facts_as_null():
    """Smoke 01 turn 2: shown "written_agreement": null, the model told the user they had no agreement."""
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE)
    engine(llm).turn(Session(), "deposit not returned")
    prompt = llm.calls[1][1]["content"]
    case_part = prompt.split("USER'S LATEST MESSAGE")[0]
    assert "null" not in case_part and "not_discussed_yet" in case_part
    assert "whether you have a written rental agreement" in case_part
    assert "never" in llm.calls[1][0]["content"] and "not_discussed_yet" in llm.calls[1][0]["content"]


def test_hinglish_replies_are_asked_for_in_latin_script():
    """Smoke 01 turn 1: a Hinglish message got a Devanagari reply."""
    llm = ScriptedLLM(analysis(language="Hinglish"), "theek hai, kitna deposit tha?")
    engine(llm).turn(Session(), "owner deposit wapas nahi kar raha")
    system = llm.calls[1][0]["content"]
    assert "Latin" in system and "Do not use Devanagari" in system


def test_a_greeting_does_not_trigger_a_search():
    """Smoke 05: "hi" spent 35 s on a failing embedding API before asking what happened."""
    llm = ScriptedLLM(analysis(category="unclear", intent="other", search_query=""), "Hi! What happened?")
    e = engine(llm)
    r = e.turn(Session(), "hi")
    assert r.kind == "clarify" and e.retriever.calls == []


def test_no_break_hyphens_from_the_model_do_not_trip_the_guard():
    """Smoke 02: "E‑Commerce" (no-break hyphen) was flagged as an unknown law and forced a 60 s regeneration."""
    answer = "The platform must reply within 48 hours (Consumer Protection (E‑Commerce) Rules, 2020, r. 4(5)) [1]."
    llm = ScriptedLLM(analysis(category="consumer", intent="question"), answer)
    hits = [hit("consumer-ecommerce-refunds", "consumer", 0.07, "Rule 4(5): acknowledge within 48 hours.")]
    r = engine(llm, hits=hits).turn(Session(), "amazon not refunding")
    assert r.guard["first_problems"] == [] and not r.guard["regenerated"] and "E-Commerce" in r.text


def test_turn_time_is_split_into_llm_and_retrieval():
    r = engine(ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE)).turn(Session(), "deposit not returned")
    assert r.usage["llm_s"] == 0.2 and r.usage["llm_calls"] == 2                 # 0.1 s per fake call
    assert r.usage["retrieval_s"] >= 0 and "seconds" in r.retrieval


def test_the_advice_prompt_forbids_mentioning_passages_to_the_user():
    """Smoke run 2: "There is no passage that records a Supreme Court judgment"."""
    llm = ScriptedLLM(analysis(facts=FULL_FACTS), GOOD_ADVICE)
    engine(llm).turn(Session(), "deposit not returned")
    assert 'Never say "passage"' in llm.calls[1][0]["content"]
