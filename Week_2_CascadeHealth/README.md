# Week 2 — Cascade Health Claims Adjudication

An agentic claims-adjudication system for Cascade Health Partners, the
fictional health-insurance subsidiary of Meridian Financial Group.
Inbound CMS-1500 PDFs are received by email, extracted by Document
Understanding, adjudicated by an LLM agent operating under explicit
policy rules — with an optional second-opinion consultation to
Anthropic's Claude for ambiguous medical-necessity calls — and routed
to one of three dispositions, with high-dollar reviews suspending the
flow for human approval in UiPath Action Center.

## Place in the three-build arc

This is **Build 2 of 3**. Where Week 1 proved deterministic discipline,
this build introduces agentic capability under enterprise constraints:
auditable agent decisions, human-in-the-loop on amounts that warrant it,
and a Maestro flow that can stay alive for days waiting on a reviewer
without losing context.

- **Build 1 ([Week_1_LoanIntake](../Week_1_LoanIntake/)):** Deterministic RPA — REFramework, Orchestrator queues, rule-based routing
- **Build 2 (this project):** Agentic LLM workflows under human review — two-agent pipeline with DU + Claude integration
- **Build 3 ([Week_3_RDD](../Week_3_RDD/)):** Synthesis — full agentic decisioning with regulator-grade governance, audit, and disclosure

## What it does

A member emails a CMS-1500 PDF to a designated inbox. Within roughly a
minute the system:

1. **Saves the PDF** to an Orchestrator Storage Bucket using the Gmail attachment ID as the transport key.
2. **Extracts** the structured claim data — member ID, policy number, provider NPI, service lines, total charges, narrative — via a Document Understanding project trained on the form's positional schema.
3. **Adjudicates** the claim using an LLM agent that applies five hard rules: extraction-quality thresholds, medical-necessity reasoning, policy-based decisioning, escalation thresholds, and a no-invention discipline that forbids the agent from inventing facts not present in the extracted record.
4. **Consults Claude** as an MCP-style second-opinion tool when the agent encounters ambiguous CPT/ICD-10 pairings — judgment-bearing edge cases where the policy alone doesn't resolve.
5. **Routes** to APPROVE, DENY, or REVIEW. REVIEW claims above $10K suspend the Maestro flow and surface in Action Center for a human reviewer with an SLA timer.
6. **Logs** every disposition to a Google Sheet audit log, with `escalation_required` carried as a metadata column rather than a separate routing branch.

The build is functional, deployed, and processing inbound claims
autonomously.

## How it works

```
                       Gmail trigger
                             │
                             ▼
            ┌────────────────────────────────┐
            │ UploadAttachmentToBucket (RPA) │   transport: Gmail attachment ID → bucket key
            └────────────────┬───────────────┘
                             │
                             ▼
                  Orchestrator Storage Bucket
                             │
                             ▼
       ┌────────────────────────────────────────────┐
       │ ClaimIntakeAgent  (LLM agent)              │
       │   calls Document Understanding as a Tool ──┼──→ ClaimsIntake_DU (DU project)
       │   returns: 12-field structured record      │
       │            + per-field confidence          │
       └────────────────────┬───────────────────────┘
                            │
                ┌───────────┴───────────┐
                │ confidence below      │
                │ threshold?            │
                └───────┬─────────┬─────┘
                        │ Yes     │ No
                        ▼         ▼
              RPA fallback   ┌──────────────────────────────────────┐
              (triage queue) │ AdjudicationAgent  (LLM agent)       │
                             │   five hard rules                    │
                             │   may invoke Tool ──→ Anthropic Claude │
                             │   "Medical Necessity Second Opinion" │
                             │   returns: disposition + escalation  │
                             └─────────────────┬────────────────────┘
                                               │
                                  Gateway on disposition
                       ┌───────────────────────┼───────────────────────┐
                       │                       │                       │
                       ▼                       ▼                       ▼
                    APPROVE                  DENY                   REVIEW
                       │                       │                       │
                       │                       │             ┌─────────┴─────────┐
                       │                       │             │ amount > $10K?    │
                       │                       │             └────┬──────────┬───┘
                       │                       │              Yes │       No │
                       │                       │                  ▼          ▼
                       │                       │           SimpleApprovalApp │
                       │                       │           (Action Center,   │
                       │                       │            suspend-and-wait)│
                       │                       │                  │          │
                       │                       │           reviewer responds │
                       │                       │                  │          │
                       └───────────────────────┴──────────────────┴──────────┘
                                               │
                                               ▼
                                Google Sheet audit log
                              (disposition + escalation flag
                               + reasoning + provenance)
```

The orchestration layer is **UiPath Maestro** (BPMN). It keeps each flow
instance alive across the entire pipeline including human-review
windows that may take days — a meaningfully different runtime model
from traditional run-to-completion RPA.

## Component breakdown

The deployed solution is **six projects**:

| Component | Type | Role |
|---|---|---|
| **ClaimIntakeAgent** | LLM Agent (Agent Builder) | Reads PDF from bucket, invokes DU as a tool, returns a structured 12-field record with per-field confidence |
| **AdjudicationAgent** | LLM Agent (Agent Builder) | Applies five hard rules, optionally invokes Claude as a tool for ambiguous medical-necessity calls, emits `{disposition, escalation_required, reasoning}` |
| **ClaimsIntake_DU document processing automation** | Document Understanding project | The actual DU extraction logic. Trained on the CMS-1500 form. Called by ClaimIntakeAgent as a Tool |
| **ClaimAdjudicationFlow** | Maestro BPMN process | Orchestrates the whole pipeline from Gmail trigger through final logging. The XML is in `source/ClaimAdjudicationFlow/Process.bpmn` and is reviewable on GitHub |
| **UploadAttachmentToBucket** | RPA workflow (Studio Web) | Wraps the Orchestrator Storage Bucket upload primitive so Maestro can call it (Maestro doesn't expose buckets natively) |
| **SimpleApprovalApp** | UiPath Action Center / Apps | Human reviewer interface for REVIEW claims above the $10K SLA threshold. Built from a template, not a custom form |

External services consumed (all defined in `source/resources/solution_folder/connection/`):

- **Anthropic Claude** — for the Medical Necessity Second Opinion tool
- **Google Gmail** — inbox trigger + audit-log destination
- **Google Sheets** — audit log

All three use `AuthenticateAfterDeployment` — no credentials in the
repo.

## The three dispositions (and what isn't one)

The AdjudicationAgent's contract specifies exactly three disposition
values:

| Disposition | When | Where it routes |
|---|---|---|
| `APPROVE` | Routine in-network claim, clean documentation, clear medical necessity | Audit log → terminal |
| `DENY` | Excluded service, expired coverage, out-of-network without referral, hard-fail rule | Audit log → terminal |
| `REVIEW` | Ambiguous medical necessity, off-label use, edge cases where the agent invokes Claude and still wants human eyes | Audit log; if `amount > $10K`, suspend in Action Center for human review |

**`escalation_required` is not a fourth disposition.** It's a boolean
metadata flag, carried in the audit log column. The instinct when
designing the gateway was to make escalation a branch — that would have
produced 3 × 2 = 6 combinations or required collapsing information.
Keeping the three-branch routing and carrying escalation as
observational metadata is the cleaner pattern. Not every flag deserves
a branch.

## Confidence-driven branching

The flow has a **second decision point** that isn't about adjudication —
it's about whether to adjudicate at all.

When ClaimIntakeAgent returns DU's structured record, it also carries
per-field confidence scores. If those scores fall below a configured
threshold (corrupted PDF, missing fields, illegible scan), Maestro
routes to an **RPA fallback** that creates a triage task in an
Orchestrator queue — *the agent never sees the claim*.

This is the heart of the agentic-plus-deterministic hybrid pattern:
agents handle the cases their inputs are trustworthy for; deterministic
fallbacks handle the cases that don't meet the agent's preconditions.
Test scenario family `CHC-5xxxxx` (LOW_CONFIDENCE) exercises this path
end-to-end with deliberately corrupted PDFs.

## Repository layout

```
Week_2_CascadeHealth/
├── README.md                                       (this file)
│
├── docs/
│   ├── ClaimAdjudication_SDD.docx                  Solution Design Document
│   ├── week2_governance_packet.md                  Governance findings — read this for the architectural lessons
│   ├── claims_data_scheme.md                       Test-data scheme: claim-ID prefix encodes expected outcome
│   └── phase-findings/                             Six sequential build-phase notes (phase 1 through 6)
│       ├── phase1_findings.md
│       ├── phase2_findings.md
│       ├── phase3_findings.md
│       ├── phase4_findings.md
│       ├── phase5_findings.md
│       └── phase6_findings.md
│
├── source/                                         flattened solution export
│   ├── ClaimIntakeAgent/                           LLM agent + .agent-builder/ definition + evals
│   ├── AdjudicationAgent/                          LLM agent + Medical Necessity Second Opinion tool
│   ├── ClaimsIntake_DU document processing automation/   DU project source
│   ├── ClaimAdjudicationFlow/                      Maestro BPMN — Process.bpmn is the canonical flow XML
│   ├── UploadAttachmentToBucket/                   RPA workflow (Storage Bucket bridge)
│   ├── SimpleApprovalApp/                          Action Center / Apps — Main.xaml + button handlers
│   ├── resources/solution_folder/                  package, process, connection, bucket manifests
│   ├── SolutionStorage.json                        solution-level config
│   ├── CascadeClaimsAdjudication.uipx              one-click re-import bundle (main solution)
│   └── ClaimsIntake_DU....uipx                     one-click re-import bundle (DU project)
│
└── test-data/
    ├── generate_claims.py                          deterministic per-seed CMS-1500 PDF generator
    └── sample_claims/                              40 PDFs + _manifest.csv (see scheme below)
```

## Test data — claim ID prefix encodes expected outcome

Forty pre-generated PDFs in `test-data/sample_claims/`. The scheme,
documented in full in `docs/claims_data_scheme.md`:

| ID prefix | Scenario | Expected disposition | DU confidence | Action Center? |
|---|---|---|---|---|
| `CHC-1xxxxx` | APPROVE — routine, in-network, clean | AUTO_APPROVE | High | No |
| `CHC-2xxxxx` | DENY — excluded, expired, out-of-network | AUTO_DENY | High | No |
| `CHC-3xxxxx` | REVIEW (under $10K) — ambiguous necessity | REVIEW | High | No, but flagged |
| `CHC-4xxxxx` | ESCALATE (over $10K REVIEW) — high-dollar + ambiguous | REVIEW | High | Yes, with SLA timer |
| `CHC-5xxxxx` | LOW_CONFIDENCE — corrupted fields | RPA fallback | Below threshold | No |

Distribution: 14 APPROVE, 10 DENY, 7 REVIEW, 5 ESCALATE, 4 LOW_CONFIDENCE
— roughly mirrors a production mix and clears DU Modern's 30-doc
extraction-training minimum with held-out test cases.

Filenames are self-labeling — `CHC-400003.pdf` is unambiguously a high-
dollar review test, no manifest lookup needed during a demo. The 4
LOW_CONFIDENCE PDFs are deliberately held out of DU training so the
model can't learn to compensate for the corruption patterns.

### Regenerating

```bash
cd test-data
python3 generate_claims.py .
# deterministic per seed (default 20260429) — same seed produces identical batch
```

## Tech stack

| Layer | Choice |
|---|---|
| Agent runtime | UiPath Agent Builder (two agents — intake, adjudication) |
| LLM | UiPath-provisioned models for both agents |
| External LLM as Tool | Anthropic Claude via UiPath Integration Service connector |
| Document extraction | UiPath Document Understanding (Modern, trained on the CMS-1500 schema) |
| Orchestration | UiPath Maestro (BPMN) — `Process.bpmn` is the canonical XML, reviewable on GitHub |
| Human-in-the-loop | UiPath Action Center (Apps + Forms) — suspend-and-wait runtime |
| Storage | Orchestrator Storage Bucket, bridged via Studio Web RPA workflow |
| Audit | Google Sheets via UiPath Integration Service |
| Test-data generation | Python (`generate_claims.py`) |

## Documentation

Worth reading, in order of priority for a reviewer:

- **[`docs/week2_governance_packet.md`](docs/week2_governance_packet.md)** — Architectural and governance findings from the build. The honest version of what's hard about agentic systems: hidden contract redundancy, distributed value-domain mismatches, transport vs. business identifiers, suspend-and-wait runtime, connection lifecycle risk. Read this first.
- **[`docs/ClaimAdjudication_SDD.docx`](docs/ClaimAdjudication_SDD.docx)** — Solution Design Document. The definitive spec.
- **[`docs/claims_data_scheme.md`](docs/claims_data_scheme.md)** — Why claim IDs encode outcomes, what's in each scenario family, and the CMS-1500 field schema DU was trained against.
- **[`docs/phase-findings/`](docs/phase-findings/)** — Six sequential build-phase notes. Useful if you want to see *how* the architecture arrived at its final shape, not just what it is.
