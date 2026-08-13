# PII Redaction Tool (Lightweight, Rule-Based)

 tool that finds and redacts personal
information (names, emails, phones, companies, addresses, SSNs, credit
cards, DOBs, IP addresses) in DOCX/PDF/TXT files, replacing each with a
synthetic value. Tested against a real ~125-page Indian IPO Red Herring
Prospectus.

**This is a rule-based project by design** — regular expressions and
small context rules, no NER model, no ML library.

## Architecture

```
pii-redaction-tool/
├── app.py              Flask web app (upload / redact / summary / download)
├── redact.py            ALL detection, replacement, and document
│                         processing logic — the core of the project
├── evaluate.py           simple evaluation script (reads evaluation/gold.json)
├── evaluation/
│   └── gold.json          manually verified gold-standard PII entities
├── templates/index.html  one-page UI
├── static/style.css
├── outputs/               redacted DOCX output
├── audit/                 audit JSON output
├── requirements.txt
└── render.yaml
```

## Installation

```bash
pip install -r requirements.txt
```

## Dependencies

```
Flask          — web app
python-docx    — read/write DOCX
pypdf          — extract text from PDF
gunicorn       — production server
```


## Detection strategy

All detectors live in `redact.py`, in two groups:

**Structured (pure regex):**
- EMAIL — standard pattern.
- PHONE — Indian mobile/landline (with or without `+91`) plus a generic
  US-style fallback.
- SSN — `DDD-DD-DDDD` with basic plausibility checks.
- CREDIT_CARD — 13–19 digit candidates, accepted only if **Luhn-valid**
  (this avoids flagging arbitrary long document numbers).
- IP_ADDRESS — dotted-quad with each octet validated 0–255.
- DOB — a date is only tagged DOB if a nearby keyword ("date of birth",
  "DOB", "born", ...) appears within 40 characters — an ordinary date
  with no such context is correctly left alone.

**Context-rule (regex + surrounding words, no NER model):**
- PERSON — only fires next to an explicit marker: `Mr./Mrs./Ms./Dr. Name`
  or `Director:`/`Contact Person:`/`Company Secretary:` followed by a
  name. This is intentionally narrow — see Limitations.
- COMPANY — a capitalized phrase followed by a legal suffix (Limited,
  Ltd, Private Limited, Pvt Ltd, LLP, LLC, Inc, Corp, Corporation).
  Leading connector words ("of", "and", "the", "company") are trimmed;
  a bare suffix with no real name is rejected.
- ADDRESS — text following an anchor ("Registered Office", "Corporate
  Office", "Address:") that also contains a PIN code or an address
  keyword (Road/Street/Lane/Nagar/Marg/Plot/Society/Colony).

## Replacement strategy

`redact.py`'s `Replacer` class is a plain Python dictionary:
`original_value -> fake_value`, built fresh for every redaction run and
never written to disk. The same original always maps to the same fake
within one run (e.g. every mention of the same email gets the same
replacement). Fake values are small, hand-written generators — a short
list of first/last names, a template for phone/SSN/credit-card/IP
formats — no external library.

## Document processing

- **DOCX**: read with python-docx; PII is replaced **inside existing
  runs**, not by rebuilding the document, so tables/headers/footers/
  formatting survive unchanged (verified: identical paragraph/table/
  section counts before and after, and the docx skill's structural
  validator passes). Table cells are deduplicated by internal cell id
  so a merged cell (spanning several grid columns) is only processed
  once.
- **PDF/TXT**: text is extracted (pypdf per page, or line-by-line for
  TXT) and redacted the same way, but written into a **new DOCX** —
  original PDF layout is not reconstructed. This is a stated scope
  simplification.

## Web application

One Flask page (`app.py` + `templates/index.html`): choose a file,
click **Redact PII**, see a per-type count table, download the redacted
DOCX and the audit JSON. No JavaScript framework, no database, no
background workers — a single synchronous request does the work.
`GET /health` returns `{"status": "ok"}` for basic monitoring/Render's
health check.

## Local execution

```bash
pip install -r requirements.txt
python app.py                          # http://127.0.0.1:5000
```

## Render deployment

`render.yaml`:
```yaml
services:
  - type: web
    name: pii-redaction-tool
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT
    healthCheckPath: /health
```
Push to a Git provider, create a Render Blueprint pointing at the repo,
and Render builds and starts it automatically. No Docker, no database,
no external services required.

## Limitations

This is the most important section to understand before reading the
evaluation numbers — the detector is simple **on purpose**, and its
weak points are direct, predictable consequences of that simplicity:

- **PERSON recall is low for names with no title/role marker next to
  them.** A director's name sitting alone in a table cell (no "Mr." or
  "Director:" text in the *same* cell — the label is in a different
  column) will be missed. Confirmed on the real prospectus: 11 of 13
  gold PERSON entities were missed for exactly this reason.
- **ADDRESS recall is very low** for the same reason — several real
  addresses (e.g. a director's home address) have no anchor phrase
  ("Registered Office", "Address:") in the same cell as the address
  text, so the anchor-based rule has nothing to trigger on. Confirmed:
  0 of 7 gold ADDRESS entities were caught.
- **COMPANY suffix list is intentionally short** (Limited/Ltd/Private
  Limited/Pvt Ltd/LLP/LLC/Inc/Corp/Corporation) — it does not include
  "Trust", so promoter family trusts (e.g. "DHAULAGIRI FAMILY TRUST")
  are not detected as COMPANY. This is a direct, explicit tradeoff for
  keeping the suffix list small and explainable.
- **No general-purpose name detection** — this was an explicit design
  choice (see "Detection strategy"), not an oversight.
- **PDF/TXT output doesn't preserve original layout** — always a fresh
  DOCX with plain paragraphs.
- SSN/CREDIT_CARD/DOB/IP_ADDRESS have **zero real instances** in the
  supplied document (a real Indian IPO filing doesn't contain any of
  these concepts), so there is nothing to measure recall against for
  those types in this evaluation — see `evaluation_report.md`.

## False positives / false negatives

See `evaluation_report.md` for the full, real per-type breakdown. In
short: **on the 80-entity gold set, this detector produced zero false
positives** — every false positive from the earlier, spaCy-based
version of this project (place-name fragments mistagged as names,
regulatory jargon mistagged as names) disappeared once name detection
was narrowed to explicit title/role markers only. The tradeoff is lower
recall (PERSON and ADDRESS specifically), which is the correct and
expected result of a narrower, simpler rule set.

## Design tradeoffs

- **Precision over recall, everywhere.** Every context-rule detector
  (PERSON, COMPANY, ADDRESS) requires an explicit trigger (a title, a
  suffix, an anchor phrase) rather than guessing from capitalization
  alone. This is why recall is uneven across types but false positives
  are essentially zero on the gold set.
- **One file for the core logic** (`redact.py`) instead of a package of
  small modules — easier for a student to read top-to-bottom and
  explain in a viva, at the cost of it being a longer single file.
- **No test framework** — correctness is demonstrated by actually
  running the tool against the real prospectus and by `evaluate.py`,
  rather than a separate unit-test suite, to keep the file count small.
- **Simple in-memory replacement dictionary**, discarded after each
  run, instead of a persisted mapping — nothing to secure or clean up
  beyond the job's temporary files.
