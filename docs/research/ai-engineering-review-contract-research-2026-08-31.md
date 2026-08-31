# AI engineering review contract research

Date: 2026-08-31

## Question

What is the smallest review contract that can answer engineering questions from Workbench artifacts with verifiable citations, measurable coverage, and deterministic refusal before any external LLM or user interface is introduced?

## Existing foundation

The repository already has the right separation of concerns:

- `Artifact` identifies a source, type, hash, confidentiality and producer.
- `Finding` carries a deterministic code, severity, source artifact and location.
- `Trace` records cross-layer nodes and unknowns.
- Lab reports preserve raw or derived evidence and identify their source artifacts.
- The architecture requires deterministic rules to remain authoritative and keeps the core independent of GUI, vector database and LLM choices.

The current objects are not yet sufficient for citation-backed review:

1. Most runtime reports expose `artifact_type` and path lists but are not wrapped in the `artifact.schema.json` identity/confidentiality contract.
2. `Finding.location` is a free-form string, so a reviewer cannot always resolve it back to an exact JSON value or source range.
3. `test-result.schema.json` models `findings` as strings, while current reports commonly embed Finding objects.
4. No shared object records a citation, validates a locator, measures required-question coverage, or explains a refusal.
5. A source hash is present in some CAN evidence but is not mandatory across review inputs, so stale citations cannot yet be rejected consistently.

## R5a decision

Start with a local deterministic review kernel. It normalizes JSON and Markdown artifacts into addressable evidence units, performs lexical retrieval, validates citations, computes coverage against caller-provided review checks, and refuses unsupported conclusions. It does not generate prose with an LLM.

```text
ReviewRequest
  -> Artifact registry and policy filter
  -> EvidenceUnit normalization
  -> deterministic lexical retrieval
  -> Citation validation
  -> claim/check coverage
  -> answered | partial | refused ReviewResult
```

## Minimal objects

### ReviewRequest

- `request_id`: stable caller identifier.
- `question`: human-readable engineering question.
- `checks`: non-empty list of required, caller-defined claims or questions. Each check provides a stable ID, statement and explicit lexical terms. Coverage is calculated against these checks, never against model-generated claims.
- `artifact_ids`: explicit review scope; no implicit workspace-wide ingestion.
- `minimum_coverage`: value in `0..1`, default `1.0` for deterministic review.
- `allowed_confidentiality`: explicit policy set.

### EvidenceUnit

- `evidence_id`: deterministic identifier derived from artifact identity, source hash and locator.
- `artifact_id`, `artifact_type`, `source`, `source_sha256`, `confidentiality`.
- `locator`: structured locator with one supported type: `json-pointer`, `line-range`, or `finding`.
- `content`: the exact normalized value used for retrieval and support checks.
- `content_sha256`: detects mutation after normalization.
- `finding_codes`: deterministic Findings directly associated with the unit.

JSON Pointer is the preferred locator for generated reports and intents. Line ranges are allowed for Markdown or text sources and use one-based inclusive line numbers. A Finding locator contains its code plus source location, but must still resolve to an ingested artifact.

### Citation

- `citation_id`, `evidence_id`, `artifact_id`.
- A copy of `source_sha256`, locator and `content_sha256` from the cited EvidenceUnit.
- `supports_checks`: one or more ReviewRequest check identifiers.

A citation is valid only when the artifact is in request scope, confidentiality policy allows access, source hash matches, locator resolves, content hash matches, and every referenced check exists. Display text is derived from the resolved unit and is not trusted as citation identity.

### ReviewResult

- `status`: `answered`, `partial`, or `refused`.
- `mode`: fixed to `retrieval-only` in the first implementation.
- `checks`: each check is `supported`, `unsupported`, `conflicted`, or `blocked`, with zero or more citation IDs.
- `coverage`: supported required checks divided by total required checks.
- `citations`: validated Citation objects only.
- `findings`: deterministic Findings copied without severity reduction or semantic override.
- `refusal_reasons`: stable reason codes and messages.

## Coverage and status rules

Coverage is deterministic:

```text
coverage = supported required checks / all required checks
```

- `answered`: coverage meets `minimum_coverage`, no required check is conflicted or blocked, and every supported check has at least one valid citation.
- `partial`: at least one check is supported, but coverage is below the threshold or another check is unsupported. Supported and unsupported checks remain explicit.
- `refused`: no check is supported, a required artifact is unavailable or disallowed, citation validation fails globally, or evidence conflict prevents a safe answer.

An `ERROR` Finding is not automatically a refusal: it may be the exact evidence requested. However, a review conclusion may never contradict, downgrade or close a deterministic Finding. Unknown Trace nodes and unresolved conflicts must be surfaced as unsupported or conflicted checks.

## Stable refusal reasons

- `REVIEW-ARTIFACT-MISSING`
- `REVIEW-ARTIFACT-HASH-MISMATCH`
- `REVIEW-ARTIFACT-INVALID`
- `REVIEW-CONFIDENTIALITY-DENIED`
- `REVIEW-NO-EVIDENCE`
- `REVIEW-CITATION-INVALID`
- `REVIEW-EVIDENCE-CONFLICT`
- `REVIEW-COVERAGE-BELOW-THRESHOLD`

Refusal is a normal result, not an exception or transport failure.

## R5b minimal implementation acceptance

1. Add schemas or equivalent strict loaders for ReviewRequest, EvidenceUnit, Citation and ReviewResult.
2. Register only explicitly supplied local JSON artifacts; calculate SHA-256 before normalization.
3. Normalize JSON leaf values to JSON Pointer EvidenceUnits. Markdown line-range support can follow after the JSON vertical slice.
4. Implement dependency-free case-folded lexical retrieval with deterministic tie-breaking; do not add embeddings or a vector database.
5. Produce a fully cited answer for a known Finding query.
6. Produce `partial` when only some caller checks have evidence.
7. Produce `refused` for missing artifacts, denied confidentiality, stale hashes and zero evidence.
8. Prove that citations fail validation after the source artifact changes.
9. Prove that deterministic Finding severity and content are preserved in ReviewResult.
10. Emit JSON and Markdown evidence plus unit tests; no external network, account or LLM is required.

## Boundary

R5a does not define natural-language generation quality, embeddings, reranking, agent autonomy, prompt templates, web search, a vector database, a browser UI, access-control infrastructure, or production secrets handling. The first review result states only what local deterministic evidence supports and explicitly refuses the rest.

## R5b implementation result

R5b implements the local JSON vertical slice in `review.py` and exposes it through `run-review`:

- Four schemas define ReviewRequest, EvidenceUnit, Citation and ReviewResult.
- Explicit registry scope and confidentiality policy are enforced before artifact content is read.
- JSON scalar leaves become deterministic JSON Pointer EvidenceUnits bound to source and content SHA-256 values and are persisted in `evidence-units.json`.
- Caller-provided lexical terms are covered across a deterministic, greedily selected citation set.
- The public sample is `answered` at coverage `1.0` with four validated citations.
- Tests cover `partial`, missing/denied/stale/no-evidence refusal, citation invalidation after source or citation-metadata mutation, invalid requests and exact Finding preservation.

The implementation remains retrieval-only and dependency-free. It does not infer semantic equivalence beyond caller-provided lexical terms.
