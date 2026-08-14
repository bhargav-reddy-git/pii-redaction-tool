# Evaluation Report

## Methodology

We do not have a pre-labelled PII dataset for the supplied Red Herring
Prospectus. Therefore we manually reviewed representative sections of
the real document and built a gold-standard set of PII entities by
hand — every entity's text was checked to actually appear verbatim in
the document before being included (see "Gold-set methodology" below).
We then ran our detector (`redact.py`) on each gold entity's real
surrounding paragraph/table-cell text — the same text the app would see
when processing this document for real — and compared predictions
against the gold entities.

**Matching rule**: a prediction counts as correct only if it has the
**same type** as the gold entity **and** its span overlaps the gold
entity's span in that same context. A `COMPANY` prediction on a
`PERSON` gold entity (or vice versa) is not a match, regardless of text
overlap.

- **TP**: predicted type + span matches a gold entity.
- **FP**: a prediction with no corresponding gold entity of that type
  in that context.
- **FN**: a gold entity with no matching prediction.

## Gold-set methodology

**Target gold-set size: 200 entities.**
**Actual gold-set size: 80 entities.**

We did not fabricate entities to reach 200. The actual document simply
does not contain 200 suitable, unambiguous, hand-verifiable PII
instances of the required types combined (in particular it contains
**zero** SSNs, credit card numbers, dates of birth, or IP addresses —
confirmed by direct search of the extracted document text).
80 real, manually verified entities were collected instead, and that
actual number is reported here 

Entities were drawn from representative sections rather than one small
paragraph: the cover-page contact/registered-office/corporate-office
block, the promoters banner, the full directors table (names +
addresses), the shareholding table, and the bankers/lead-managers/legal-
counsel contact blocks (emails and phone numbers). Each entity in
`evaluation/gold.json` records its `text`, `type`, and a `section` label
(exact page numbers weren't tracked — the document has no stable page
numbering in the DOCX itself — so a section description is used instead,
as the closest practical equivalent).

**Target distribution vs. actual:**

| Type | Target | Actual |
|---|---|---|
| PERSON | 50 | 13 |
| EMAIL | 25 | 26 |
| PHONE | 25 | 20 |
| COMPANY | 30 | 14 |
| ADDRESS | 30 | 7 |
| DOB | 10 | 0 |
| SSN | 10 | 0 |
| CREDIT_CARD | 10 | 0 |
| IP_ADDRESS | 10 | 0 |
| **TOTAL** | **200** | **80** |

EMAIL and PHONE came close to target because the document's
banker/lead-manager contact tables contain many of them. PERSON,
COMPANY, and ADDRESS fell well short of target because manually
verifying each one (confirming it's really a person/company/address,
not just a capitalized phrase) is slow, and because this document
simply has a bounded number of clearly-disclosed individuals, companies,
and addresses. DOB/SSN/CREDIT_CARD/IP_ADDRESS are 0 because the
document contains none — not a sampling failure.

## TP / FP / FN, Precision, Recall, F1

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × Precision × Recall / (Precision + Recall)
```
Division by zero is handled by reporting **N/A**, never a fabricated 0
or 1.

## Accuracy — explicitly defined

Ordinary character-level accuracy would be misleading here (the vast
majority of the document's characters are not PII, so predicting "not
PII" everywhere would score unrealistically high and say nothing about
detector quality). Instead we use an **entity-level** measure:

```
Accuracy = TP / (TP + FP + FN)
```

This is **not** conventional document/character accuracy — it does not
count the large number of ordinary non-PII characters as true
negatives. It only asks: of every PII instance the detector should have
found or did claim to find, what fraction did it get right.

## Per-PII-type results (actual run of `evaluate.py`)

| PII Type | Gold Count | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| PERSON | 13 | 2 | 0 | 11 | 1.00 | 0.15 | 0.27 |
| EMAIL | 26 | 26 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| PHONE | 20 | 20 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| COMPANY | 14 | 8 | 0 | 6 | 1.00 | 0.57 | 0.73 |
| ADDRESS | 7 | 0 | 0 | 7 | N/A | 0.00 | N/A |
| DOB | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| SSN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| CREDIT_CARD | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| IP_ADDRESS | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| **TOTAL** | **80** | **56** | **0** | **24** | — | — | — |

**Overall Precision: 100.0%**
**Overall Recall: 70.0%**
**Overall F1: 82.4%**
**Entity-level Accuracy: 70.0%**

## Error analysis

**Zero false positives across the entire gold set.** Every prediction
the detector made on these 80 gold contexts corresponded to a real
gold entity of the same type. This is a direct result of how narrow the
context rules are (see README "Design tradeoffs") — the detector simply
doesn't fire unless a strong, explicit trigger is present.

**PERSON — the weakest type (recall 0.15).** All 11 misses are director/
promoter names sitting alone in a table cell (the "Name" column), with
no "Mr."/"Director:"/"Contact Person:" text in that same cell — the
role/title is in a *different* column. Our PERSON rule requires the
marker in the same text, so it has nothing to trigger on. The 2 hits
were the cover-page contact person and a banker contact, both of which
do have "Contact Person:" in the same cell.

**ADDRESS — 0/7 caught.** All 7 misses are real addresses (2 office
addresses, 4 director home addresses, 1 banker address) where either
the anchor phrase ("Registered Office", etc.) is in a different cell
than the address text, or — for the banker address — the block has a
city but no PIN-code/keyword match within the block-extraction window.

**COMPANY — 8/14 caught, all 6 misses are the promoter family trusts**
("DHAULAGIRI FAMILY TRUST" etc.) — "Trust" is not in the suffix list by
design (see README), so this is an expected, not surprising, result.

## Limitations

- DOB/SSN/CREDIT_CARD/IP_ADDRESS metrics are N/A because the source
  document has zero real instances of these types — their correctness
  as regex/Luhn/octet logic has to be judged by inspection and small
  hand-run examples, not by this evaluation.

- Matching requires the same type; a correct span with the wrong type
  is counted as both an FN (for the correct type) and would count as an
  FP if a same-typed gold entity for that wrong type existed nearby
  (none did in this gold set, so this scenario didn't arise in practice
  here).
