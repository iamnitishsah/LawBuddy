"""Tests for the citation helpers (no network)."""

from lawbuddy.guard.citations import check_citations, format_passages, normalize_citations, split_sentences


def hit(n: int) -> dict:
    return {"chunk_id": f"deposit_{n:03d}", "header": f"Security deposit | Part {n}", "text": f"Passage {n} text."}


def test_valid_citations():
    text = "The landlord must return the deposit after you vacate [1]. Deductions need a written reason [2][3]."
    assert check_citations(text, 3) == ([1, 2, 3], [], [])


def test_invalid_and_missing_citations_are_flagged():
    text = "You can file a complaint at the District Commission [4]. The company will probably settle within a week."
    valid, invalid, uncited = check_citations(text, 2)
    assert valid == [] and invalid == [4]
    assert len(uncited) == 1 and "settle" in uncited[0]


def test_check_citations_handles_bullets_and_headings():
    text = "**Your options:**\n- Send a written demand first [1].\n- Then file on the online portal [2]."
    assert check_citations(text, 2) == ([1, 2], [], [])


def test_other_citation_styles_are_normalized():
    # gpt-oss writes 【1】 / 【4†L5-L9】; others write [1, 2]
    text = "Keep the bank statement 【1】. Send the notice 【2†L5-L9】. Both help [1, 3]."
    out = normalize_citations(text)
    assert "【" not in out and "[1][3]" in out and "[2]" in out


def test_indian_abbreviations_do_not_split_sentences():
    text = "Your landlord holds Rs. 50,000 as deposit and Sec. 12 of your agreement sets the refund date [1]."
    assert check_citations(text, 1) == ([1], [], [])
    assert len(split_sentences("Mr. Sharma paid Rs. 20,000. He wants it back.")) == 2


def test_devanagari_full_stop_splits_sentences():
    assert split_sentences("मकान मालिक ने पैसे नहीं लौटाए। अब क्या करें?") == ["मकान मालिक ने पैसे नहीं लौटाए।", "अब क्या करें?"]


def test_passages_are_numbered_and_delimited():
    block = format_passages([hit(1), hit(2)])
    assert '<passage id="1" source="Security deposit | Part 1">' in block
    assert '<passage id="2"' in block and block.count("</passage>") == 2
