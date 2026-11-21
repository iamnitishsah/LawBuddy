# Legal sources

The official texts behind the knowledge base. The PDFs live in `data/sources/` (gitignored); this file records
where each came from, so every KB chunk can be traced back to its source. Scope: **central law + Karnataka**.

`sha256` is the first 16 hex characters of the file's SHA-256 hash.

## Downloaded

| File | Document | Version / as on | Source | Retrieved | sha256 |
|---|---|---|---|---|---|
| `IndianConstitution.pdf` | Constitution of India (diglot) | as on 10 Sep 2026 | Legislative Department, Ministry of Law & Justice (provided by the user) | 2026-11-21 | `c2e0f5f7a670d362` |
| `central_consumer-protection-act-2019.pdf` | Consumer Protection Act, 2019 (No. 35 of 2019) | as enacted | [PRS India](https://prsindia.org/files/bills_acts/bills_parliament/2021/Consumer%20Protection%20Act%202019.pdf) (India Code blocks scripted downloads) | 2026-11-21 | `0ae7f82ab5b77d50` |
| `central_cp-jurisdiction-rules-2021.pdf` | CP (Jurisdiction of the District, State and National Commission) Rules, 2021: money limits ₹50 lakh / ₹2 crore | Gazette notification | [thc.nic.in](https://www.thc.nic.in/Central%20Governmental%20Rules/Consumer%20Protection%20(Jurisdiction%20of%20the%20District%20Commission,%20the%20State%20Commission%20and%20the%20National%20Commission)%20Rules,%202021.pdf) | 2026-11-21 | `2c10f5a312064d5d` |
| `central_cp-ecommerce-rules-2020.pdf` | CP (E-Commerce) Rules, 2020, G.S.R. 462(E) | Gazette, 23 Jul 2020 | [PRS India](https://prsindia.org/files/bills_acts/bills_parliament/2021/Consumer%20Protection%20(E-Commerce)%20Rules,%202020.pdf) | 2026-11-21 | `3012b37f6f6dba2d` |
| `central_code-on-wages-2019.pdf` | Code on Wages, 2019 (No. 29 of 2019) | as on 21 Nov 2025 | [India Code](https://www.indiacode.nic.in/bitstream/123456789/15793/1/aA2019-29.pdf) | 2026-11-21 | `846f2e2745d8a9bc` |
| `central_legal-services-authorities-act-1987.pdf` | Legal Services Authorities Act, 1987 (No. 39 of 1987) | amended to 2002 | [Government S3WaaS site](https://cdnbbsr.s3waas.gov.in/s3100d9f30ca54b18d14821dc88fea0631/uploads/2025/06/20250612538111215.pdf) | 2026-11-21 | `c66c587e819de7e2` |
| `karnataka_rent-amendment-act-2025_as-passed.pdf` | Karnataka Rent (Amendment) Bill, 2025 (LA Bill 67 of 2025), as passed by the Assembly; enacted as Karnataka Act 07 of 2026 | as passed | [Karnataka Legislative Council](https://kla.kar.nic.in/council/house/bills/157/02eng.pdf) | 2026-11-21 | `073689cb6ddd031d` |
| `karnataka_rent-act-1999.pdf` | Karnataka Rent Act, 1999 (Karnataka Act 34 of 2001) | amended by Acts 17 of 2007 and 28 of 2011 | [India Code](https://www.indiacode.nic.in/handle/123456789/7810?locale=en), downloaded by hand (India Code blocks scripts) | 2026-11-21 | `b13c323b9cadba87` |
| `central_limitation-act-1963.pdf` | Limitation Act, 1963 (No. 36 of 1963) | India Code version | [India Code](https://www.indiacode.nic.in), downloaded by hand | 2026-11-21 | `8c54246c5c981e89` |
| `central_indian-contract-act-1872.pdf` | Indian Contract Act, 1872 (No. 9 of 1872) | India Code version | [India Code](https://www.indiacode.nic.in), downloaded by hand | 2026-11-21 | `85a7a066098255c9` |

Text extraction: `data/text/*.txt` (one file per PDF, page markers `<<<PAGE n>>>`). The Karnataka Rent Act PDF
encodes its text as glyph codes (`/G75/G65...`), which are decimal character codes and decode to plain text.

## Web pages (read while writing the KB in Phase 1)

| Page | Use |
|---|---|
| [e-Jagriti](https://e-jagriti.gov.in) | Filing a consumer complaint online |
| [National Consumer Helpline](https://consumerhelpline.gov.in) (1915) | Pre-litigation grievance redressal |
| [Karnataka State Legal Services Authority](https://kslsa.kar.nic.in) | Free legal aid and Lok Adalat in Karnataka |
| [NALSA](https://nalsa.gov.in) | Who qualifies for free legal aid |
| Karnataka Labour Department | Wage claims in Karnataka |

## Findings and open questions

- **No deposit cap in Karnataka (resolved from the texts).** The Karnataka Rent Act, 1999 has no provision limiting
  a security deposit; "deposit" in the Act means depositing rent with the Controller (ss. 17 to 19). The 2025
  amendment changes only ss. 24, 53, 54 and 55 (Controller's powers, offences, penalties). A blog's "2-month cap" claim
  is therefore wrong for Karnataka. Kept as a hallucination test case.
- **The Rent Act rarely applies to modern tenancies (from s. 2(3)).** It excludes premises with rent above Rs. 3,500
  a month in city-corporation areas (Rs. 2,000 elsewhere) and buildings built or substantially renovated in the last
  15 years. Most deposit disputes are therefore contract claims (Indian Contract Act ss. 73 and 74; Limitation Act
  Art. 55).
- **Karnataka Rent (Amendment) Act, 2025**: the text we have is the Bill as passed by the Assembly. Publication as
  Karnataka Act 07 of 2026 (Gazette Extraordinary No. 21, 8 Jan 2026) is per secondary sources; confirm from the
  Gazette.
- **Free legal aid income limit in Karnataka**: s. 12(h) of the LSA Act lets the State set it; the current Karnataka
  figure is not in our sources, so the KB tells users to ask the DLSA.
- **Helplines** checked on the official sites on 2026-11-21: National Consumer Helpline 1915 / 1800-11-4000 /
  WhatsApp 8800001915 (consumerhelpline.gov.in); NALSA 15100 (nalsa.gov.in). The emergency reply also uses 112
  (emergency), 181 (women), 1098 (child) and 14416 (Tele-MANAS) from general knowledge: verify them on official
  sites before release (configs/conversation.yaml).
- **Code on Wages in Karnataka**: the Code has been in force since 21 Nov 2025. Karnataka's state rules were still in draft (notification of 23 Jan 2026) per secondary sources. The KB should rely on the Code itself and say that state rules may add procedure.
