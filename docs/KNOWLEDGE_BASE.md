# Knowledge base

LawBuddy answers only from these articles. They live in `kb/`, are written from the official texts listed in
[SOURCES.md](SOURCES.md), and every one has been checked against its source by a person (`verified_on`).

## Scope

- **Where:** Karnataka. Central law plus Karnataka state law.
- **Problems:** security deposit not returned (`deposit`), refund / faulty product or service (`consumer`), unpaid
  salary or final dues (`salary`), plus what applies to all three (`general`: free legal aid, Lok Adalat, legal
  notices, when to get a lawyer, replaced laws).
- **Not covered:** criminal matters, police / FIR, arrest or bail, family matters, property title, eviction cases,
  cheque bounce, PF, bank or loan disputes, tax, insurance, government service matters, other states' rent law.
  LawBuddy refers these to a lawyer or the DLSA.

## The 32 articles

| Category | Guides (plain language) | Statute extracts (verbatim) | Practice notes |
|---|---|---|---|
| deposit (10) | overview · rent-act-scope · no-cap · deductions · steps · rent-act-tenants | Contract Act ss. 73-74 · Rent Act s. 2(3) + First Schedule · Limitation Act Arts. 22, 55, 113 | evidence |
| consumer (10) | overview · who-is-consumer · ecommerce-refunds · commission-complaint · after-filing · time-limit | CPA ss. 34(2), 35(1), 69 · Jurisdiction Rules rr. 3-5 · E-Commerce Rules rr. 4(5), 4(10), 6(3) | helpline (1915) |
| salary (6) | overview · claim · steps | Code on Wages s. 17 · s. 45 | evidence |
| general (6) | legal-aid · lok-adalat · old-laws | LSA Act ss. 12, 21 + Constitution Art. 39A | legal-notice · when-to-get-a-lawyer |

Key facts the articles establish (each traced to its section in the article itself):
- The Karnataka Rent Act, 1999 has **no deposit cap**, and the 2025 amendment changed only offences and penalties.
- The Rent Act excludes premises with rent above Rs. 3,500/month in city-corporation areas (Rs. 2,000 elsewhere) and
  buildings less than 15 years old, so most deposit disputes are contract claims (Contract Act ss. 73-74; 3 years).
- Consumer complaints: within 2 years; District Commission up to Rs. 50 lakh; can be filed where the consumer lives;
  e-commerce platforms must acknowledge a complaint in 48 hours and resolve it in a month.
- Wages: monthly wages before the 7th of the next month; within 2 working days of leaving; claims within 3 years
  before the wage authority, which can add compensation up to 10 times the claim.

## Files

```
kb/
  deposit/ consumer/ salary/ general/   one article per .md file
  registry.yaml                         the only laws and sections that may be named
  index/vectors.npz, index/chunks.json  the search index (built; committed)
```

### An article

```markdown
---
id: deposit-no-cap
title: Is there a legal limit on the security deposit in Karnataka?
category: deposit            # deposit | consumer | salary | general (must match the folder)
kind: guide                  # guide | statute (verbatim text) | practice (no legal provision)
jurisdiction: karnataka      # karnataka | central
cites:                       # every law the body relies on; each must be in the registry
  - {doc: karnataka-rent-act-1999, section: "17"}
  - {doc: karnataka-rent-amendment-2025, section: "2"}
verified_on: 2026-11-21      # when a person last checked it against the source
---
Plain-language body, at most 450 words, citing law inline as (Karnataka Rent Act, 1999, s. 17).
```

Titles containing a colon must be quoted. Guides and statute extracts must cite at least one law; practice notes may
cite none.

### The registry (`kb/registry.yaml`)

For each law: `title`, `number`, `jurisdiction`, `status` (`in_force` / `repealed`), `aliases` (including Hindi
names, so Hindi answers are checked too), the `sections` the KB relies on, the source `file` and `url`. A `repealed`
list names old laws and what replaced them (IPC, CrPC, Evidence Act, Consumer Protection Act 1986, Payment of Wages
Act and three other labour laws, Karnataka Rent Control Act 1961). BNS, BNSS and BSA are listed with no sections, so
"IPC was replaced by the BNS" passes but any BNS section is flagged as out of scope.

## Adding or changing an article

```bash
python -m lawbuddy.kb.extract                 # 1. PDFs in data/sources/ -> data/text/*.txt (page-marked)
# 2. write or edit kb/<category>/<name>.md from the text; add any new law/section to kb/registry.yaml
make kb                                       # 3. validate: unknown law, unlisted section, repealed law, length...
python -m lawbuddy.kb.verify <id> [<id> ...]  # 4. after checking it against the source: sets verified_on
make kb-build                                 # 5. embed new/changed articles (embedding API; unchanged ones reused)
make test                                     # 6. fails if the index is out of date or the KB trips its own guard
make smoke                                    # 7. optional: does retrieval still find the right article?
```

The validator refuses: an unknown law, a section the registry does not list, a repealed law, a category that does
not match the folder, a guide or statute without a citation, more than 450 words, duplicate ids. Tests also check
that every article passes the legal-reference guard against itself and that the index matches the KB (hashes and
`verified_on` dates).

## Adding a state or a problem type

Content work, not code: collect the official texts (add to [SOURCES.md](SOURCES.md)), add the laws to the
registry, write and verify the articles, rebuild the index, add retrieval smoke questions, and (for a new problem
type) add its fact list in `conversation/case.py` and, if notices are wanted, a template in `drafting/notice.py`.
