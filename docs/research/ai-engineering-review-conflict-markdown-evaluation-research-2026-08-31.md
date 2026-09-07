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

## R5e automotive-domain evaluation expansion

R5e retains the ten R5d core cases and adds nineteen explicit checks over four existing public Workbench artifacts:

- five DBC-derived contract checks over `canonical_contract.json`;
- five CAN/BSW mapping checks over `bsw_intent.json`;
- five transport, DID, and NRC checks over `uds_intent.json`;
- four lifecycle and persistence-policy checks over `dtc_intent.json`.

The resulting `review-evaluation-0.2` manifest contains fourteen cases and exactly thirty checks. Every referenced source carries `expected_sha256`; evaluation results expose per-domain check counts and accuracy. The loader keeps `0.1` compatibility by assigning legacy cases to `core`. All five domains achieve check-state accuracy `1.0`, all existing global metrics remain `1.0`, and false conflicts remain `0` across three runs per case.

These nineteen checks use caller-authored exact assertions and stable JSON Pointers. They prove deterministic resolution and regression coverage across current public artifacts, not retrieval of unknown questions, DBC parsing inside the review kernel, or semantic correctness beyond the gold contract.

## R5f runtime reports and held-out negatives

R5f adds a narrow producer contract to the evaluator rather than allowing manifests to execute commands. The only accepted producer kinds are the existing in-process CAN lab, UDS lab, and DTC lifecycle runner. Each producer runs once per evaluation case, writes into the case output directory, and must return a passed result plus its expected report filename. The evaluator then materializes exactly one `${producer_report}` source, pins the generated bytes with SHA-256, and runs the review three times against that immutable report.

Evaluation `0.3` records `development`, `runtime`, or `held-out` splits and reports check counts and accuracy for each split. The original 30 checks remain the development baseline. A separate runtime manifest checks one stable output from each generated CAN/UDS/DTC report and preserves all UDS Findings exactly. A separate held-out negative manifest checks consistent contradictions and an unknown JSON Pointer; it is not merged into the development manifest.

This closes the gap between static intent-only evaluation and runner-produced evidence, but it does not solve automatic locator discovery. Report timestamps, run IDs, durations, and virtual channel identifiers remain dynamic and are not treated as comparable claims. Cross-run applicability, stable-field drift, and intentionally conflicting runner outputs remain R5g work. External LLMs and LLM judges remain out of scope.

## R5g cross-run stability and drift

R5g extends the producer contract to exactly two independent runs. Both generated reports are retained and SHA-256 pinned before the review executes. Requests use explicit `all-equal` observations over one stable pointer in each report. The CAN, UDS, and DTC cases demonstrate that different whole-report hashes do not imply a conflict when the selected stable values agree.

Drift injection is deliberately narrower than a generic JSON patch facility. Each runner has a small stable-pointer allowlist, a mutation targets one of the two generated reports, and its replacement must be a scalar. The first R5g conflict case changes only the second CAN report's round-trip status. The review cites both values, classifies the check as conflicted, and refuses with `REVIEW-EVIDENCE-CONFLICT`.

Run IDs, timestamps, durations, and channel identifiers are classified as dynamic pointer tokens. A paired producer request that observes one of these fields is rejected before any runner executes. This is a manifest-contract failure rather than an engineering conflict: normal execution identity and timing variation must not contribute to conflict recall or false-conflict counts.

The `review-evaluation-0.4` cross-run set contains four checks across CAN, UDS, and DTC. All gates pass, including conflict recall and zero false conflicts. Applicability across variants, software or calibration versions, and backends remains caller knowledge; R5h must represent that metadata explicitly before expanding the drift catalog.

## R5l fixed external report cohort import

R5l separates evidence production from deterministic evaluation. A `review-evaluation-0.9` case may declare one to three existing local `external_reports`; each entry provides a path and an exact lowercase SHA-256. The request refers to those bytes with `${external_report_1..3}` placeholders. The evaluator resolves the files relative to the manifest, verifies the digest before parsing, requires valid UTF-8 JSON and the complete artifact-bound applicability profile, then materializes an immutable review request with absolute paths and verified hashes.

`external_reports` and `producer` are mutually exclusive. Import never invokes a runner, executes a command, downloads an artifact, or mutates report content. Result evidence records the declared source, verified digest, applicability profile, and verification state separately from producer evidence. A checked-in CAN CI-style baseline plus stable and drifted candidates proves that the same citation and drift-catalog gates work without a `producer/` directory; the candidate judgments are exactly one stable and one drifted.

This contract establishes byte identity and local deterministic replay only. A matching digest does not authenticate the CI system, repository, workflow, job, commit, or human who supplied the manifest. It is not a signature or attestation. UDS/DTC fixed-report coverage and explicit CI provenance remain follow-on work; remote artifact fetching and trust-policy enforcement remain out of scope.

## R5m cross-domain fixed reports and CI provenance

R5m upgrades the external cohort contract to `review-evaluation-1.0`. The checked-in cohort now contains CAN, UDS, and DTC cases, each with an explicit baseline, a stable candidate, and a drifted candidate. The selected stable fields are CAN round-trip status, decoded VIN, and DTC confirmed state. All three domains produce one stable and one drifted candidate judgment without invoking a producer.

Every 1.0 external report must contain a `ci_provenance` object with provider, repository, run ID, job ID, and a 40- or 64-character lowercase hexadecimal commit SHA. The evaluator validates this closed shape only after the report bytes match the manifest SHA-256, then archives the fields with `status=hash-bound`. Missing or malformed provenance fails before request materialization.

`hash-bound` is deliberately weaker than `verified` identity. It means the provenance declaration was inside the exact report bytes consumed by the evaluator. The sample values are synthetic, and the evaluator does not contact a CI provider, confirm repository ownership, inspect a workflow, validate a signature, or compare the declaration with an independently supplied expectation. R5n may add explicit local expectation matching; remote attestation and trust policy remain outside this deterministic baseline.

## R5n explicit provenance expectation

R5n upgrades the fixed-report contract to `review-evaluation-1.1`. Every external report entry now carries a caller-owned `provenance_expectation` containing repository, job ID, and a 40- or 64-character lowercase hexadecimal commit SHA. These fields are deliberately outside the report bytes and therefore provide an independent local statement of which checked-in report the caller intends to review.

The evaluator first checks the pinned report SHA-256 and parses its closed `ci_provenance` object, then compares the three expected fields exactly. A missing expectation, malformed commit, or repository/job/commit mismatch fails closed before `materialized-request.json` is written or any repeated review run begins. Successful result evidence keeps `ci_provenance.status=hash-bound` and separately records `provenance_expectation.status=matched`, so byte binding and caller-intent matching are not conflated.

The cross-domain CAN/UDS/DTC cohort declares expectations for all nine reports. Positive evaluation preserves the existing six stable/drifted candidate judgments; negative tests independently alter repository, job, and commit and verify that all three paths stop before request materialization. This still does not authenticate a CI provider, fetch an artifact, validate a signature or attestation, or prove repository ownership. It is deterministic local declaration matching only.

## R5o cohort provenance policy

R5o upgrades the evaluation contract to `review-evaluation-1.2` and adds a case-level `provenance_policy` for external cohorts. The deliberately small policy contains one required repository and a unique, non-empty `allowed_job_ids` list. Per-report expectations continue to bind exact repository/job/commit tuples; the policy adds a second layer that constrains which repository and jobs may participate in the cohort as a whole.

Policy enforcement occurs after the report digest, closed provenance shape, and per-report expectation match, but before artifact substitution or request materialization. A report from another repository or a job outside the allowlist fails closed. Successful evaluation evidence records the effective policy with `status=enforced`, while each report retains the separate `hash-bound` and `matched` states. Tests cover missing, empty, and duplicate policies plus repository and job violations, and preserve 1.0/1.1 manifest compatibility.

This is an exact local allowlist, not a general policy language. It does not interpret repository aliases, wildcard jobs, branches, workflow names, provider identities, commit ancestry, signatures, or attestations. Keeping those out avoids implying supply-chain guarantees that the evaluator cannot establish from local fixture bytes.

## R5p preflight rejection evidence

R5p upgrades the external-report evaluation contract to `review-evaluation-1.3`. A digest mismatch, malformed report provenance, caller expectation mismatch, or cohort repository/job policy violation still raises an error and keeps the CLI exit status non-zero, but now also writes `review-evaluation-rejection.json` at the evaluation output root. This gives CI a deterministic artifact even though review execution never begins.

The rejection artifact is deliberately smaller than an evaluation result. It records only evaluation and case identifiers, a timestamp, the fixed `external-report-preflight` phase, report index, stage, stable reason code, and—where useful—the mismatched field name. It does not contain a report path, expected or actual digest, provenance value, policy value, request body, report body, or materialized artifact registry. The schema is closed, and negative tests cover integrity, provenance shape, expectation, and policy rejection categories.

This evidence improves failure observability without weakening fail-closed behavior. It is not a partial review result, does not authenticate the rejected artifact, and does not convert invalid input into a scored evaluation case. Manifest-structure errors and failures outside external-report preflight continue to use the existing exception path without a rejection artifact.
## R5q CI rejection contract 演练补充（2026-09-07）

- CI 必须观察 evaluator CLI 的真实非零退出，不能只调用内部函数并把“抛异常”当作远端流程已经正确连接。
- `continue-on-error` 只负责保留后续校验和 artifact 上传机会；独立检查步骤要求 outcome 为 `failure`，因此 CLI 意外成功仍会令 job 失败。
- 演练输入从已固定 cohort manifest 派生，只注入确定的 SHA-256 mismatch；原 fixture、gold manifest 和报告字节保持不变。
- 正常 cohort 与拒绝证据使用不同输出目录和 artifact 名称，避免失败件被误认为正式 evaluation result。
- 拒绝验收同时检查最小字段、稳定 reason code、敏感字段不泄漏，以及 materialized request / evaluation result 不存在。
- 当前只验证 GitHub-hosted Windows/Ubuntu runner 上的工作流连接和 artifact 留存，不扩大到 provider API 下载、身份认证、签名或 attestation。
