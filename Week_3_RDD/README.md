# Week 3 — Regulated Document Decisioning (RDD)

A unified agentic decisioning platform for Meridian Financial Group that
ingests inbound regulated requests (loan applications and insurance
claims), classifies and routes them, scores risk through a hybrid of
deterministic logic and LLM judgment, runs every machine-issued
disposition through a regulatory-compliance check, drafts a customer-
facing disclosure letter, archives the rendered PDF to an audit-grade
storage bucket, and emails the customer — with full provenance retained
on an immutable `decisionEvent` record at every step.

## Place in the three-build arc

This is **Build 3 of 3** — the synthesis. Where Week 1 proved
deterministic discipline and Week 2 proved agentic capability under
human review, this build combines both into a single pipeline that
serves both lines of business (banking + insurance, post-merger) and
treats governance not as an external checkpoint but as a property of
the system's design.

- **Build 1 ([Week_1_LoanIntake](../Week_1_LoanIntake/)):** Deterministic RPA — REFramework, Orchestrator queues, rule-based routing
- **Build 2 ([Week_2_CascadeHealth](../Week_2_CascadeHealth/)):** Agentic LLM workflows under human review — Cascade Health claims adjudication
- **Build 3 (this project):** Synthesis — unified agentic decisioning across both lines of business with regulator-grade governance, audit, and disclosure

## What it does

A customer emails Meridian Bank with a loan application or an insurance
claim. The system:

1. **Classifies** the inbound request via an LLM agent that decides loan vs. claim.
2. **Routes** to the appropriate intake — loan intake (structured-field extraction) or claim intake (Cascade Health pipeline) — each emitting a normalized intake record.
3. **Scores risk** through the branch-appropriate engine:
   - **Loans:** a deterministic Credit Decisioning script that walks a real-bank ladder (credit knockouts → large-amount escalation → manual review band → clean auto-approve)
   - **Claims:** the Claims Adjudication Agent (LLM) from Week 2's pattern, with the Claude second-opinion tool
4. **Holds for human review** in Action Center if the risk decision sets `escalation_required` — the flow suspends and resumes after a human reviewer acts.
5. **Checks regulatory compliance** on every machine-issued disposition (Reg B, ERISA Section 503, FCRA, TILA, state insurance code, OFAC) via an LLM agent grounded in citation-required reasoning.
6. **Drafts a customer disclosure letter** through a second LLM agent operating under a strict no-invention discipline and a brand-style guard.
7. **Renders to PDF** via PDFMonkey using Meridian's branded letter template.
8. **Archives** the PDF to an Orchestrator Storage Bucket (path: `adverse-actions/<reference_number>.pdf`) — the audit-grade record of what was sent.
9. **Emails** the customer with the PDF attached.

Every stage **writes to a single immutable `decisionEvent` record** that
travels with the flow instance and constitutes the complete audit
provenance for the decision — extraction inputs, risk reasoning, human
touchpoints, compliance citations, the rendered disclosure, and the
disposition.

## How it works

```
                       Inbound email (loan or claim)
                                    │
                                    ▼
                ┌─────────────────────────────────────┐
                │ Extract Payload (Script Task)       │
                │   parse JSON body from email        │
                │   mint decision_event_id            │
                │     RDD-<YYYYMMDD>-<6 base36>       │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ DocumentClassificationAgent (LLM)   │  decides loan vs claim
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                  ┌───────── Gateway ─────────┐
                  │                           │
                  ▼ loan                      ▼ claim
        ┌─────────────────────┐    ┌─────────────────────┐
        │ Loan Intake Agent   │    │ Claim Intake Agent  │
        │  (Script Task — JS) │    │  (Script Task — JS) │
        └──────────┬──────────┘    └──────────┬──────────┘
                   │                          │
                   ▼                          ▼
        ┌─────────────────────┐    ┌─────────────────────┐
        │ Credit Decisioning  │    │ ClaimsAdjudication  │
        │ (Script — knockouts │    │ Agent (LLM, with    │
        │  → escalation       │    │ Claude as Tool)     │
        │  → manual           │    │                     │
        │  → auto-approve)    │    │                     │
        └──────────┬──────────┘    └──────────┬──────────┘
                   │                          │
                   └────────────┬─────────────┘
                                ▼
                  ┌─────── Gateway ──────┐
                  │ escalation_required? │
                  └─────┬────────────┬───┘
                        │ Yes        │ No
                        ▼            │
              ┌─────────────────┐    │
              │ RDDApprovalApp  │    │
              │ (Action Center, │    │
              │  suspend-and-   │    │
              │  wait)          │    │
              └─────────┬───────┘    │
                        │            │
                        ▼            │
              ┌─────────────────┐    │
              │ Set Auto Final  │    │
              │ Disposition     │◄───┘ (auto path)
              │ (Script Task)   │
              └─────────┬───────┘
                        │
                        ▼
                ┌─────────────────────────────────────┐
                │ RegulatoryComplianceAgent (LLM)     │  Reg B / ERISA / FCRA / TILA / state ins
                │   reviews disposition + intake      │  emits citations + clearance
                │   under no-invention discipline     │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ CustomerDisclosureAgent (LLM)       │  drafts customer-facing letter text
                │   no-invention + Meridian-brand     │  enforces required disclosure language
                │   sub-brand guard                   │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ Generate PDF Letter                 │  PDFMonkey (Meridian template)
                │   reference_number =                │
                │     decision_event_id               │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ UploadPDFtoBucket (RPA workflow)    │  → rdd-decision-letters-archive
                │   path:                             │     /adverse-actions/<ref>.pdf
                │     adverse-actions/<ref>.pdf       │
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ DownloadPDFfromBucket (RPA)         │  re-fetches the canonical archived PDF
                └─────────────────┬───────────────────┘
                                  │
                                  ▼
                ┌─────────────────────────────────────┐
                │ Send Customer Email with PDF        │  Gmail (To = intake email, fallback)
                └─────────────────────────────────────┘
                                  │
                                  ▼
                                 End
```

Throughout the flow, every stage **merges its output into the
`decisionEvent` record** via Script Tasks (`Merge Classification`,
`Merge Risk Response`, `Merge Compliance Response`, `Merge Disclosure
Response`). The record is append-only — no stage rewrites a prior
stage's fields. By the End event, `decisionEvent` is the complete,
ordered, queryable trace of how the disposition was reached.

## The eight components

| Component | Type | Role |
|---|---|---|
| **DocumentClassificationAgent** | LLM agent | Decides loan vs. claim from email body |
| **ClaimsAdjudicationAgent** | LLM agent | Claim-branch risk decisioning (REUSED from Week 2's pattern) with Claude second-opinion tool |
| **RegulatoryComplianceAgent** | LLM agent | Post-decision compliance check; emits regulatory citations and clearance/concerns under no-invention discipline |
| **CustomerDisclosureAgent** | LLM agent | Drafts the customer-facing disclosure letter; enforces required regulatory disclosure language and Meridian brand guard |
| **Orchestrator** | Maestro BPMN | The whole flow. `Process.bpmn` is the canonical XML and is reviewable directly on GitHub. Every Script Task (Extract Payload, Merge*, Set Auto Final Disposition, loan/claim intake JS, Credit Decisioning) lives inline in this file. |
| **RDDApprovalApp** | Action Center / Apps | Human reviewer interface — Approve / Reject / CommentBox. Surfaces the in-flight `decisionEvent` so the reviewer sees full provenance, not just a summary |
| **UploadPDFtoBucket** | RPA workflow (Studio Web) | Bridges Maestro to Orchestrator Storage Bucket (Maestro lacks native bucket support) |
| **DownloadPDFfromBucket** | RPA workflow (Studio Web) | Same bridge in the reverse direction — retrieves the canonical archived PDF for email attachment |

External services (all `AuthenticateAfterDeployment` — no credentials in
repo):

- **Anthropic Claude** — Medical Necessity Second Opinion tool for the Claims Adjudication Agent
- **Google Gmail** — inbound trigger + outbound customer email
- **PDFMonkey** — letter rendering against the `Meridian_Bank_Regulatory_Decision_Letter_v1` template (ID `ACD9F4AC-EF3E-40CD-98EC-D287292E8913`)

## The `decisionEvent` record

A single mutable variable that every stage appends to (via spread-merge
patterns like `{...vars.decisionEvent, ...new_fields}`). By End, it
contains:

| Section | Written by | Contents |
|---|---|---|
| `decision_event_id` | Extract Payload | Stable `RDD-<YYYYMMDD>-<6 base36>` ID used as the audit reference number end-to-end |
| `classification_output` | Merge Classification | `event_type`, classifier confidence, classifier reasoning |
| `intake_output` | Loan or Claim Intake | The structured intake record (applicant/member details, financials, etc.) |
| `risk_output` | Merge Risk Response | `decision_type`, `reasoning`, `escalation_required`, branch-specific rule trace |
| `human_touchpoints` | RDDApprovalApp resume | `reviewer_action`, comment, timestamp — present only if escalation path was taken |
| `final_disposition` | Set Auto Final Disposition or human review | Normalized `approved` / `declined` / `review` |
| `compliance_output` | Merge Compliance Response | Per-framework citations + clearance status |
| `disclosure_output` | Merge Disclosure Response | The drafted letter body, salutation, signatures, required disclosure block |
| `communication_output` | Update Communication Metadata | PDF reference, bucket key, send timestamp |

The record is append-only by convention enforced through the merge
script pattern — no stage rewrites a prior stage's fields. This is what
makes the system **defensible**: an examiner reconstructing why
decision `RDD-20260514-V1SN7X` was issued has every input, intermediate
reasoning, human touchpoint, and output in a single ordered record,
without log archeology.

## Loan vs. claim routing

The two intake branches diverge only between Classification and Risk
Decisioning, then **reconverge** for Compliance → Disclosure → PDF →
Email. This is intentional: regulatory disclosure obligations apply
uniformly to both lines of business once a disposition is reached, so
the compliance and disclosure stages should run once over a unified
record rather than being duplicated per branch.

| Stage | Loan branch | Claim branch |
|---|---|---|
| Intake | Loan Intake Agent (Script Task) extracts applicant + financials | Claim Intake Agent (Script Task) extracts member + policy + claim |
| Risk | Credit Decisioning (deterministic Script Task with knockout ladder) | ClaimsAdjudicationAgent (LLM with Claude tool) |
| Risk output enum | `auto_approve` / `auto_decline` / `manual_review` / `escalate_senior_review` | `APPROVE` / `DENY` / `REVIEW` |
| Post-risk | Set Auto Final Disposition (Script Task) normalizes enum | (same) |
| Compliance through Email | shared | shared |

## Repository layout

```
Week_3_RDD/
├── README.md                                       (this file)
│
├── docs/
│   ├── RDD Project Summary.docx                    Board-ready strategic memo (~2,500 words)
│   ├── RDD Governance Packet.docx                  Four-part formal governance packet
│   └── RDD Diagram Flow.png                        One-page architecture diagram
│
├── source/                                         flattened solution export
│   ├── DocumentClassificationAgent/                LLM — loan vs claim classifier
│   ├── ClaimsAdjudicationAgent/                    LLM — claim risk + Claude tool
│   ├── RegulatoryComplianceAgent/                  LLM — regulatory check
│   ├── CustomerDisclosureAgent/                    LLM — letter drafting
│   ├── Orchestrator/                               Maestro BPMN — Process.bpmn is the whole flow
│   ├── RDDApprovalApp/                             Action Center — Approve/Reject/CommentBox handlers
│   ├── UploadPDFtoBucket/                          RPA — bucket upload bridge
│   ├── DownloadPDFfromBucket/                      RPA — bucket download bridge
│   ├── resources/solution_folder/                  package, process, connection, bucket manifests
│   ├── SolutionStorage.json                        solution-level config
│   └── RegulatedDocumentDecisioning.uipx           one-click re-import bundle
│
└── test-data/
    ├── generate_payloads.py                        Python generator — source of truth for the 50 sample payloads
    └── sample_payloads/
        ├── README.md                               coverage matrix
        ├── loan/                                   25 JSON payloads
        └── claim/                                  25 JSON payloads
```

## Test data — 50 sample payloads, self-labeling filenames

`test-data/sample_payloads/` contains 50 JSON email-body payloads, 25
loan + 25 claim, covering every routing path. Filenames encode the
intended outcome so a demo operator can pick scenarios by name:

```
loan-001-auto-decline-credit-540.json
loan-007-escalate-senior-750k-clean.json
loan-016-auto-approve-760-debt-consol.json
loan-021-business-exception-missing-credit.json
claim-001-approve-outpatient-routine.json
claim-007-deny-out-of-network.json
claim-011-review-large-outpatient-25k.json
claim-024-review-erisa-appeal.json
```

Coverage breakdown is in [`test-data/sample_payloads/README.md`](test-data/sample_payloads/README.md).
The 25 loan files exercise all five ladder outcomes plus business
exceptions; the 25 claim files cover the three dispositions plus all
seven coverage types plus ERISA appeal and dependent-coverage edge
cases.

To run a scenario: paste a file's contents as the body of an email sent
to the inbox the RDD flow listens on. The Document Classification Agent
will classify and route from there.

## Tech stack

| Layer | Choice |
|---|---|
| Agent runtime | UiPath Agent Builder (four agents) |
| LLM | UiPath-provisioned models |
| External LLM as Tool | Anthropic Claude via Integration Service connector |
| Orchestration | UiPath Maestro (BPMN) — `Process.bpmn` is the canonical XML |
| Inline logic | JavaScript Script Tasks within the BPMN (Extract Payload, Merge*, intake parsers, Credit Decisioning, Set Auto Final Disposition) |
| Human-in-the-loop | UiPath Action Center (Apps) — `RDDApprovalApp` with Approve/Reject/CommentBox |
| PDF rendering | PDFMonkey (Integration Service connector, Meridian template) |
| Archive | Orchestrator Storage Bucket `rdd-decision-letters-archive`, bridged via Studio Web RPA workflows |
| Customer comms | Gmail via Integration Service |
| Test data | Python (`generate_payloads.py`) |

## Documentation

Read in this order for full context:

- **[`docs/RDD Project Summary.docx`](docs/RDD%20Project%20Summary.docx)** — Board-ready strategic memo. The thesis the build defends: "governance is the product of doing automation well, not the constraint on it." Read this first for the why.
- **[`docs/RDD Governance Packet.docx`](docs/RDD%20Governance%20Packet.docx)** — Formal four-part governance packet: Model Card (system identity, composition, limitations), Decision Logging Specification (`decisionEvent` structure), Audit Retention Matrix (6-year envelope, per-artifact retention drivers), Human Override Audit Trail Standard (SR 11-7 framing, override vs. abstention distinction, chain of custody). Read this second for the regulator-grade detail.
- **[`docs/RDD Diagram Flow.png`](docs/RDD%20Diagram%20Flow.png)** — One-page architecture diagram.

The packet is honest about what's implemented today vs. what's
roadmapped — the unconfigured bucket retention policy, the mocked
sanctions screening, the not-yet-implemented `pdf_hash` content
addressing — and frames them as the Phase 2 hardening backlog rather
than overclaiming. An examiner-literate reviewer will respect the
honesty.
