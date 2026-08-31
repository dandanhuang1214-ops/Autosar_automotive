# AI engineering review conflict, Markdown citation, and evaluation research

Date: 2026-08-31

## Question

What is the smallest deterministic extension to the R5b local JSON review that can identify genuine cross-artifact conflicts, cite Markdown by stable line range, and measure review quality without an LLM judge?

## Primary-source findings

- W3C Web Annotation separates a resource from the selector that addresses a segment. Its text-position selector uses an included start and excluded end, and warns that positions are brittle when a resource changes. Workbench therefore needs both a source hash and a selected-content hash, not a line number alone.
- CommonMark defines a line independently of whether the source uses LF, CR, or CRLF. GitHub exposes human-readable links to a single line or line range, including plain Markdown views. These support an explicit line-range locator, but neither source defines Workbench's hashing or one-based inclusive convention.
- W3C PROV treats provenance as information used to assess quality, reliability, and trustworthiness, and distinguishes alternate entities and versions. Two artifacts about a similarly named subject are not automatically comparable; provenance and applicability must first establish that they describe the same claim scope.
- FEVER separates `SUPPORTED`, `REFUTED`, and `NOT ENOUGH INFO`, and requires evidence for supported or refuted claims. This is a useful review-state analogy, but R5c retains `supported`, `unsupported`, `conflicted`, and `blocked` because an engineering review must distinguish source disagreement from lack of evidence.
- TREC test collections bind topics, a fixed document collection, and human relevance judgments. BEIR reports ranking measures such as nDCG and recall. For the initial Workbench dataset, exact gold evidence locators, citation precision/recall, and state accuracy are more diagnostic than an aggregate prose score.
- NIST has explicitly cautioned against using LLMs to create TREC-style relevance judgments. R5c therefore uses reviewed local gold labels and no LLM-as-judge.

Sources:

- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [CommonMark 0.31.2 specification](https://spec.commonmark.org/0.31.2/)
- [GitHub documentation: permanent links to code and Markdown lines](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet)
- [W3C PROV Data Model](https://www.w3.org/TR/prov-dm/)
- [FEVER dataset and evidence contract](https://fever.ai/dataset/fever.html)
- [NIST TREC relevance judgments](https://trec.nist.gov/data/reljudge_eng.html)
- [BEIR benchmark paper](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html)
- [NIST: Don't Use LLMs to Make Relevance Judgments](https://www.nist.gov/publications/dont-use-llms-make-relevance-judgments)

## R5c decision 1: conflict requires an explicit comparable claim

Lexical overlap only selects candidates. It cannot decide whether evidence supports or contradicts a proposition. R5c must not classify different wording, different timestamps, different configurations, or different test runs as a conflict.

A check may add a deterministic assertion:

```json
{
  "check_id": "repair-outcome-agrees",
  "statement": "The repair report and release note agree that repair committed.",
  "terms": ["repair", "committed"],
  "assertion": {
    "claim_key": "window-obstruction.repair.outcome",
    "operator": "equals",
    "expected": "committed",
    "observations": [
      {
        "artifact_id": "repair-report",
        "locator": {"type": "json-pointer", "pointer": "/repair_summary/outcome"}
      },
      {
        "artifact_id": "release-note",
        "locator": {"type": "line-range", "start_line": 12, "end_line": 12}
      }
    ]
  }
}
```

The caller owns `claim_key`, applicability, locators, operator, and expected value. The review kernel owns scope checks, resolution, normalization, comparison, citation validation, and status calculation.

Initial operators stay deliberately small:

- `equals`: type-sensitive JSON scalar equality; Markdown compares the exact normalized selected text.
- `all-equal`: all resolved observations must have the same normalized value; no preferred value is asserted.

Arrays, objects, numeric tolerance, temporal precedence, units conversion, and semantic entailment are out of scope until an adapter defines their domain rules.

### Check classification

- `blocked`: at least one required observation cannot be resolved because its artifact is missing, denied, stale, invalid, outside scope, or its locator is invalid.
- `conflicted`: comparable required observations for the same `claim_key` disagree under `all-equal`, or an `equals` check has at least one value equal to `expected` and at least one unequal value.
- `supported`: at least one required observation satisfies `equals`, or all required `all-equal` observations agree, with no blocked or conflicting observation.
- `unsupported`: no observation supports the assertion and the evidence is neither blocked nor internally conflicting. For `equals`, this includes the case where every resolved value consistently differs from `expected`.

Status precedence is `blocked > conflicted > supported > unsupported`. A conflicted required check forces the ReviewResult to `refused` with `REVIEW-EVIDENCE-CONFLICT`; it is never averaged away by high coverage. Conflict output must cite both sides and record each citation relation as `supports` or `contradicts`. Existing deterministic Findings remain unchanged and cannot be used as an implicit source-priority override.

## R5c decision 2: Markdown line-range locator

The locator is:

```json
{
  "type": "line-range",
  "start_line": 12,
  "end_line": 15
}
```

Resolution rules:

1. Read only an explicitly registered local `.md` artifact as UTF-8 with an optional BOM.
2. Hash the original bytes as `source_sha256` before normalization.
3. Recognize LF, CRLF, and CR as line endings; preserve every other character, including indentation, trailing spaces, and tabs.
4. Treat `start_line` and `end_line` as one-based and inclusive. Require `1 <= start_line <= end_line <= line_count`.
5. Join the selected logical lines with LF to form citation `content`; do not append a final LF. Hash that exact UTF-8 string as `content_sha256`.
6. Revalidation repeats the same resolution and rejects any source, locator, displayed content, content hash, evidence ID, or citation ID mismatch.

R5d may normalize each non-empty Markdown line as a retrieval EvidenceUnit and merge adjacent selected lines only when the caller supplies an explicit range. It will not implement a full CommonMark AST, heading inference, rendered-HTML positions, or fuzzy relocation. A source edit invalidates citations even if the selected text happens to remain at the same lines; this is intentional fail-closed behavior for the first version.

## R5c decision 3: minimal deterministic evaluation dataset

The dataset is a versioned local manifest plus immutable JSON/Markdown fixtures. Each case records:

- `case_id`, question, request path, and fixture IDs/hashes;
- expected ReviewResult status and per-check status;
- one or more acceptable gold evidence sets, expressed as artifact ID plus locator;
- expected refusal reason codes and preserved Findings;
- fields excluded from repeatability comparison, initially only `run_id` and `started_at`.

The first dataset should contain at least these ten cases:

1. single JSON artifact, fully supported;
2. single Markdown artifact with a valid line-range citation;
3. two artifacts that agree on one explicit claim;
4. two comparable artifacts that conflict;
5. two similarly worded artifacts with different applicability that must not be compared;
6. mixed supported and unsupported checks producing `partial`;
7. missing required artifact producing `refused`;
8. confidentiality denial or expected-hash mismatch producing `refused`;
9. invalid Markdown range or post-review source mutation invalidating citation;
10. repeated identical runs producing identical normalized result and citation ordering.

### Metrics and gates

- Review status accuracy: exact match per case; gate `100%`.
- Check-state accuracy: exact match over all checks; gate `100%`.
- Conflict recall and false-conflict count: all gold conflicts found and zero false conflicts; gate `100% / 0`.
- Citation validity: independently resolved valid citations divided by all emitted citations; gate `100%`.
- Citation precision: emitted gold-relevant locators divided by all emitted locators; gate `100%`.
- Citation evidence-set recall: cases where at least one complete acceptable gold evidence set is emitted divided by answerable cases; gate `100%`.
- Refusal-code accuracy and Finding preservation: exact structural match; gate `100%`.
- Repeatability: normalized JSON equality and stable citation order across three runs; gate `100%`.

Ranking measures such as nDCG and Recall@k may be added when the corpus and ranked candidate list are large enough to make them meaningful. They are not substitutes for citation validity or correct refusal.

## R5d minimal implementation acceptance

1. Extend artifact loading to explicit local Markdown while keeping JSON behavior backward compatible.
2. Add and independently validate one-based inclusive `line-range` locators.
3. Add explicit comparable assertions and deterministic `equals`/`all-equal` rules.
4. Refuse a real cross-artifact conflict and cite both sides without changing either source Finding.
5. Prove that similar but non-comparable evidence does not create a false conflict.
6. Add the versioned ten-case evaluation manifest and a dependency-free evaluator.
7. Meet every R5c metric gate and emit JSON/Markdown evaluation evidence.
8. Keep external LLMs, embeddings, vector databases, Web UI, fuzzy citation repair, and source-priority policy out of scope.

## Boundary

R5c defines a deterministic comparison and evaluation contract, not general fact checking. It does not infer that two artifacts describe the same ECU, variant, software version, calibration, test environment, or time window. It does not decide which conflicting source is authoritative. Those decisions require explicit request metadata or a domain adapter; absent that information, the safe result is unsupported, blocked, or refused.

## R5d implementation result

R5d implements the contract in `review.py` and `review_eval.py`:

- `review-request-0.1` remains backward compatible; `review-request-0.2` adds explicit assertions and emits `review-result-0.2`.
- Registered `.md` artifacts are normalized as non-empty physical-line EvidenceUnits. Explicit one-based inclusive ranges may span lines and are independently re-resolved during citation validation.
- `equals` and `all-equal` compare only explicit observations. Conflict citations preserve both `supports` and `contradicts` relations, and relation metadata is independently checked against current source content.
- The checked-in ten-case manifest pins fixture SHA-256 values, runs every case three times, and measures exact status/check/refusal/Finding results, citation validity/precision/evidence-set recall, conflict recall/false conflicts, and normalized repeatability.
- The public evaluation passes all ten cases: every proportional metric is `1.0`, false conflicts are `0`, and all citation validation passes.

The implementation remains local, deterministic, retrieval-only, and dependency-free. The ten synthetic and repair-oriented cases are a regression gate, not evidence of general semantic understanding or production review accuracy.
