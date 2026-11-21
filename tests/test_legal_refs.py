"""Tests for the legal-reference guard, on the real registry (no network)."""

import pytest

from lawbuddy.guard.legal_refs import UNVERIFIED_NOTE, check_answer, find_refs, LawIndex, remove_problem_sentences
from lawbuddy.kb.loader import load_registry

REGISTRY = load_registry()


def passage(text: str) -> dict:
    return {"chunk_id": "p", "header": "h", "text": text}


def kinds(answer: str, passages=None) -> list[str]:
    return [p.kind for p in check_answer(answer, passages or [passage("x")], REGISTRY).problems]


# --- what must pass ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    "Wages must be paid before the seventh day of the next month (Code on Wages, 2019, s. 17(1)) [1].",
    "Under section 17 of the Code on Wages, wages are due within two working days of resigning [1].",
    "You can file where you live (Consumer Protection Act, 2019, s. 34(2)) [1].",
    "The Act excludes premises with higher rent (Karnataka Rent Act, 1999, s. 2(3)) [1].",
    "The amendment changed only offences (Karnataka Rent (Amendment) Act, 2025, ss. 2 to 5) [1].",
    "A suit for breach must be filed within three years (Limitation Act, 1963, Schedule, Article 55) [1].",
    "Free legal aid is a constitutional goal (Constitution of India, Article 39A) [1].",
    "Platforms must reply within 48 hours (E-Commerce Rules, 2020, r. 4(5)) [1].",
    "Compensation is limited to loss that naturally arises (Indian Contract Act, 1872, ss. 73 and 74) [1].",
    "The IPC was replaced by the Bharatiya Nyaya Sanhita in 2024 [1].",
    "You will have to pay Rs. 500 as a fee, and the hearing is in 2 weeks [1].",
])
def test_grounded_references_pass(answer):
    assert kinds(answer) == []


def test_a_law_named_in_the_passages_is_grounded_even_if_not_registered():
    p = [passage("Part A covers cities under the Karnataka Municipal Corporation Act 1976.")]
    assert kinds("Bengaluru is a city under the Karnataka Municipal Corporation Act [1].", p) == []
    assert kinds("Bengaluru is a city under the Karnataka Municipal Corporation Act [1].") == ["unknown_law"]


def test_a_section_named_in_the_passages_is_grounded():
    p = [passage("a victim of trafficking as referred in article 23 of the Constitution")]
    assert kinds("Trafficking victims are covered (Constitution, Article 23) [1].", p) == []
    assert kinds("Trafficking victims are covered (Constitution, Article 23) [1].") == ["unlisted_section"]


# --- what must be caught -------------------------------------------------------------------------------------

@pytest.mark.parametrize("answer, expected", [
    ("You can file a cheating case under Section 420 IPC [1].", "repealed_law"),
    ("File a case u/s 420 of the IPC [1].", "repealed_law"),
    ("The landlord must refund within 30 days under Section 21 of the Karnataka Rent Act [1].", "unlisted_section"),
    ("The Model Tenancy Act, 2021 caps deposits at two months [1].", "unknown_law"),
    ("Complain under the Consumer Protection Act, 1986 [1].", "repealed_law"),
    ("Your claim is under the Payment of Wages Act [1].", "repealed_law"),
    ("The time limit is set by the Limitation Act, 1908 [1].", "wrong_year"),
    ("As held in Sharma v. State of Karnataka, deposits must be returned [1].", "case_law"),
    ("See AIR 2019 SC 123 on this point [1].", "case_law"),
    ("This was settled in (2020) 3 SCC 45 [1].", "case_law"),
    ("The Supreme Court has held that tenants get interest [1].", "case_law"),
    ("Section 12 says you must be paid [1].", "unanchored_section"),
    ("Employers must keep registers under section 50 of the Code on Wages [1].", "unlisted_section"),
    ("You can also sue under Section 9 of the BNS [1].", "unlisted_section"),
    ("This is supported by the passages [7].", "invalid_citation"),
])
def test_untraceable_references_are_caught(answer, expected):
    assert expected in kinds(answer)


def test_repealed_law_mentioned_as_replaced_is_fine_but_its_sections_are_not():
    assert kinds("The Payment of Wages Act, 1936 was repealed by the Code on Wages, 2019 (s. 69) [1].") == []
    assert "repealed_law" in kinds("The old Payment of Wages Act section 5 says wages are due on the 7th [1].")


def test_sections_are_anchored_to_the_nearest_law():
    laws = LawIndex(REGISTRY)
    _, refs = find_refs("Under the Code on Wages, s. 17 applies; the Consumer Protection Act, s. 69 sets the limit.",
                        laws)
    assert [(r["doc"], r["section"]) for r in refs] == [("code-on-wages-2019", "17"), ("cpa-2019", "69")]


def test_section_ranges_and_lists_are_expanded():
    laws = LawIndex(REGISTRY)
    _, refs = find_refs("Karnataka Rent (Amendment) Act, 2025, ss. 2 to 5", laws)
    assert [r["section"] for r in refs] == ["2", "3", "4", "5"]
    _, refs = find_refs("Indian Contract Act, sections 73 and 74", laws)
    assert [r["section"] for r in refs] == ["73", "74"]


def test_hindi_section_reference_is_checked():
    assert "unanchored_section" in kinds("धारा 420 के तहत शिकायत करें [1]।")


def test_uncited_sentences_are_reported_but_are_not_problems():
    r = check_answer("Your landlord must return the deposit after you vacate the house.", [passage("x")], REGISTRY)
    assert r.ok and r.uncited_sentences


def test_remove_problem_sentences_keeps_the_rest_and_adds_a_note():
    answer = ("Send a legal notice first [1]. As held in Sharma v. State, you also get interest [2].\n"
              "- File within two years [2].\n- Section 420 IPC also applies [1].")
    report = check_answer(answer, [passage("x"), passage("y")], REGISTRY)
    cleaned = remove_problem_sentences(answer, report)
    assert "Send a legal notice first [1]." in cleaned and "- File within two years [2]." in cleaned
    assert "Sharma" not in cleaned and "420" not in cleaned and cleaned.endswith(UNVERIFIED_NOTE)
    assert check_answer(cleaned.replace(UNVERIFIED_NOTE, ""), [passage("x"), passage("y")], REGISTRY).ok


def test_every_kb_chunk_passes_the_guard_against_itself():
    """The KB is the ground truth: its own text must not trip the guard when shown as the passage.
    The title is included because the model sees it as the passage header (some statute extracts name the Act
    only in the title)."""
    from lawbuddy.kb.loader import load_kb
    for c in load_kb():
        text = f"{c.title}\n\n{c.text}"
        report = check_answer(text, [passage(text)], REGISTRY)
        assert report.ok, f"{c.id}: {report.summary()}"


def test_removing_a_whole_bullet_leaves_no_empty_bullet():
    answer = "**Where you stand**\n- As held in Sharma v. State, you get interest [1].\n- Send a notice [1]."
    cleaned = remove_problem_sentences(answer, check_answer(answer, [passage("x")], REGISTRY))
    assert "\n- \n" not in cleaned and not any(line.strip() == "-" for line in cleaned.splitlines())
    assert "- Send a notice [1]." in cleaned
