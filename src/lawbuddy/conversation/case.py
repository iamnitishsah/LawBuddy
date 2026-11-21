"""The case file: what LawBuddy knows about the user's problem, built up over the conversation.

The model extracts facts from the user's messages (triage.analyze); code decides which facts are still missing and
whether to ask for them. The fact lists per category are the questions a lawyer would ask first.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

IN_SCOPE = ("deposit", "consumer", "salary")

# key -> what to ask for. The model fills these keys; None means not known yet.
FACTS: dict[str, dict[str, str]] = {
    "deposit": {
        "deposit_amount": "how much deposit (advance) you paid",
        "move_out_date": "when you moved out and handed over the keys",
        "written_agreement": "whether you have a written rental agreement",
        "city": "the city or town where the house is",
        "landlord_reason": "what reason the landlord gives for not returning it",
        "deposit_proof": "how you paid the deposit (bank transfer, UPI, cash with receipt)",
    },
    "consumer": {
        "product_or_service": "what you bought or which service you used",
        "seller": "who sold it (company, shop or app)",
        "amount_paid": "how much you paid",
        "purchase_date": "when you bought it",
        "problem": "what went wrong",
        "complaint_made": "whether you complained to the seller and what they said",
    },
    "salary": {
        "employer": "the name of your employer",
        "monthly_salary": "your monthly salary",
        "unpaid_period": "which months (or which dues) are unpaid",
        "employment_status": "whether you still work there, or your last working day",
        "city": "the city where you work",
        "proof_of_employment": "what proof of employment you have (offer letter, payslips, bank credits)",
    },
}

# Facts needed before advice is useful; the rest are nice to have.
CRITICAL: dict[str, tuple[str, ...]] = {
    "deposit": ("deposit_amount", "move_out_date"),
    "consumer": ("product_or_service", "seller", "problem", "purchase_date"),
    "salary": ("employer", "unpaid_period", "employment_status"),
}


PARTY_KEYS = ("user_name", "user_address", "other_name", "other_address")


@dataclass
class CaseFile:
    category: str | None = None                  # deposit | consumer | salary, once known
    facts: dict[str, str | None] = field(default_factory=dict)
    timeline: list[dict] = field(default_factory=list)          # [{"date": ..., "event": ...}]
    evidence_have: list[str] = field(default_factory=list)
    evidence_missing: list[str] = field(default_factory=list)
    other_party: str | None = None
    user_goal: str | None = None
    state: str | None = None                     # Indian state of the problem, if known
    summary: str = ""                            # neutral English summary, rewritten every turn
    parties: dict[str, str] = field(default_factory=dict)   # user_name, user_address, other_name, other_address

    def set_category(self, category: str) -> None:
        """Switching to another problem type starts that type's facts afresh."""
        if category != self.category:
            self.category = category
            self.facts = {k: None for k in FACTS[category]}

    def merge(self, update: dict) -> None:
        """Fold one analysis into the case. Known values are never erased by a later null."""
        for k, v in (update.get("facts") or {}).items():
            if self.category and k in FACTS[self.category] and _known(v):
                self.facts[k] = str(v).strip()
        for item in update.get("timeline") or []:
            if isinstance(item, dict) and _known(item.get("event")) and item not in self.timeline:
                self.timeline.append({"date": str(item.get("date") or "unknown"), "event": str(item["event"])})
        for key in ("evidence_have", "evidence_missing"):
            current = getattr(self, key)
            for e in update.get(key) or []:
                if _known(e) and e not in current:
                    current.append(str(e))
        self.evidence_missing = [e for e in self.evidence_missing if e not in self.evidence_have]
        for key in ("other_party", "user_goal", "state"):
            if _known(update.get(key)):
                setattr(self, key, str(update[key]).strip())
        if _known(update.get("summary")):
            self.summary = str(update["summary"]).strip()
        for k, v in (update.get("parties") or {}).items():
            if k in PARTY_KEYS and _known(v):
                self.parties[k] = str(v).strip()

    def missing(self, critical_only: bool = False) -> list[str]:
        """Fact keys still unknown, critical ones first."""
        if not self.category:
            return []
        keys = CRITICAL[self.category] if critical_only else (
            list(CRITICAL[self.category]) + [k for k in FACTS[self.category] if k not in CRITICAL[self.category]])
        return [k for k in keys if not _known(self.facts.get(k))]

    def outside_karnataka(self) -> bool:
        return bool(self.state) and "karnataka" not in self.state.lower() and self.state.lower() != "unknown"

    def to_dict(self) -> dict:
        return asdict(self)

    def for_prompt(self) -> dict:
        """The case as the advice model should see it: what the user said, and what has not come up yet.
        No nulls: a model reading `"written_agreement": null` told a user they had no agreement (chat smoke 01)."""
        cat = self.category
        view = {
            "problem_type": cat,
            "what_the_user_told_us": {FACTS[cat][k]: v for k, v in self.facts.items() if _known(v)} if cat else {},
            "not_discussed_yet": [FACTS[cat][k] for k in self.missing()] if cat else [],
            "timeline": self.timeline,
            "proof_the_user_has": self.evidence_have,
            "proof_the_user_said_they_lack": self.evidence_missing,
            "other_party": self.other_party,
            "what_the_user_wants": self.user_goal,
            "state": self.state,
            "summary": self.summary,
        }
        # "not_discussed_yet" stays even when empty; everything else is shown only when known.
        return {k: v for k, v in view.items() if k == "not_discussed_yet" or (v not in (None, "", [], {}))}


def _known(v) -> bool:
    return v is not None and str(v).strip().lower() not in ("", "null", "none", "unknown", "n/a", "not known")
