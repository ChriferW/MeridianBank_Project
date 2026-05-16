# Meridian Financial Group — Automation Portfolio

A three-build progression on the UiPath platform that traces an
enterprise automation strategy from foundations to synthesis: from
deterministic loan intake, through agentic claims adjudication with
human-in-the-loop review, to a unified regulator-grade decisioning
platform with full audit and disclosure.

## The scenario

**Meridian Financial Group** is a fictional $40B-AUM regional bank that
has just acquired **Cascade Health Partners**, a specialty insurance
subsidiary. The merger forces three immediate questions onto the
automation team:

- **Operational** — how do you consolidate 2,000+ back-office processes across loan origination, claims adjudication, and compliance reporting without doubling headcount?
- **Regulatory** — how do you make every customer-facing decision defensible to an auditor inside a 90-day post-merger window?
- **Strategic** — how do you become "agentic-first" inside twelve months and still hold the line on governance?

The three builds in this repository are a study in answering those
questions progressively — not with hype, and not by replacing existing
work with new work, but by **layering capability** so each build keeps
the discipline of the one before it.

## The three builds

### [Week 1 — LoanIntake](Week_1_LoanIntake/)

**Deterministic RPA. No agents.** A production-grade dispatcher/performer
pair on classic UiPath Studio + Orchestrator, built on REFramework, that
ingests loan applications from a shared inbox, validates them, scores
them against business rules, and routes to one of five outcomes. The
foundational discipline: object-oriented design, named exception
classes, full audit on Orchestrator queue items.

> *Before anyone trusts you with agents, you have to prove you can still
> do the boring stuff brilliantly.*

→ [Read the Week 1 README](Week_1_LoanIntake/README.md)

### [Week 2 — Cascade Health Claims Adjudication](Week_2_CascadeHealth/)

**Agentic capability under enterprise constraints.** Two LLM agents
orchestrated by a Maestro BPMN flow. The first uses Document
Understanding as a Tool to extract structured data from CMS-1500 PDFs.
The second adjudicates under five hard rules, with Anthropic's Claude
available as a second-opinion Tool for ambiguous medical-necessity
calls. High-dollar reviews suspend the Maestro instance in Action Center
for human review — a runtime model meaningfully different from
run-to-completion RPA.

> *Agents handle the cases their inputs are trustworthy for;
> deterministic fallbacks handle the cases that don't meet the agent's
> preconditions.*

→ [Read the Week 2 README](Week_2_CascadeHealth/README.md)

### [Week 3 — Regulated Document Decisioning (RDD)](Week_3_RDD/)

**The synthesis.** A single agentic pipeline that serves both lines of
business — loan applications and insurance claims — through a unified
classify → intake → risk → compliance → disclosure flow. Risk
decisioning is a **hybrid**: deterministic for loans (a real-bank credit
ladder), agentic for claims (Week 2's pattern, reused). Every stage
appends to an immutable `decisionEvent` record that, by end of flow,
contains the complete ordered trace of how the disposition was reached
— so an examiner can reconstruct any decision in a single record
without log archeology.

> *Governance is the product of doing automation well, not the
> constraint on it.*

→ [Read the Week 3 README](Week_3_RDD/README.md)

## The arc

| Property | Week 1 | Week 2 | Week 3 |
|---|---|---|---|
| Decision-making layer | Rule-based scripts | LLM agents | LLM agents + deterministic |
| Orchestration | Orchestrator queues | Maestro BPMN | Maestro BPMN |
| Human-in-the-loop | Action Center form (>$500K) | Action Center, suspend-and-wait (>$10K REVIEW) | Action Center, suspend-and-wait (escalation_required) |
| External integrations | Gmail, core-banking VBO (stub) | Gmail, Sheets, Claude, DU | Gmail, Claude, DU, PDFMonkey, Storage Bucket |
| Output | Routing decision on queue | Audit log row in Google Sheets | PDF disclosure letter + email + bucket archive |
| Governance posture | Exception classes + Orchestrator audit | Per-agent contract discipline | Formal Model Card + Decision Logging Spec + Audit Retention Matrix + Override Audit Trail Standard |
| Lines of business | Loans only | Claims only | Loans + claims, unified |

Each build adds capability *without abandoning* the prior build's
discipline. Week 1's exception classes survive into Week 3's
business-exception path. Week 2's confidence-driven branching pattern
survives into Week 3's classifier-confidence gate. Week 3's
`decisionEvent` record is the production-grade evolution of Week 2's
Google Sheet audit log.

## Repository navigation

```
MeridianBank_Project/
├── README.md                          ← you are here
├── .gitignore                         macOS / Windows / UiPath build cache
│
├── Week_1_LoanIntake/                 Build 1 — deterministic RPA
│   ├── README.md
│   ├── docs/                          SDD + architecture diagram
│   ├── source/                        LoanIntake.Loader / .Worker / .Library
│   └── test-data/                     sample applications + 500-email load harness
│
├── Week_2_CascadeHealth/              Build 2 — agentic with HITL
│   ├── README.md
│   ├── docs/                          SDD, governance packet, data scheme, phase findings
│   ├── source/                        6-project solution (intake + adjudication agents,
│   │                                  DU project, Maestro BPMN, bucket RPA, Action Center app)
│   └── test-data/                     40 CMS-1500 PDFs + deterministic generator
│
└── Week_3_RDD/                        Build 3 — synthesis with full governance
    ├── README.md
    ├── docs/                          board memo, governance packet, architecture diagram
    ├── source/                        8-project solution (4 LLM agents + Maestro BPMN +
    │                                  Action Center app + 2 RPA bucket bridges)
    └── test-data/                     50 self-labeling JSON payloads + generator
```

## Platform

Built entirely on the UiPath platform across:

- **UiPath Studio** (classic, Windows) — Week 1 dispatcher/performer/library
- **UiPath Studio Web** — Weeks 2 and 3 solution composition
- **UiPath Maestro** — BPMN orchestration in Weeks 2 and 3
- **UiPath Agent Builder** — LLM agent definition for Weeks 2 and 3
- **UiPath Document Understanding** (Modern) — Week 2 CMS-1500 extraction
- **UiPath Action Center** — human-in-the-loop in all three builds
- **UiPath Orchestrator** — queues, assets, storage buckets, schedules across all three
- **UiPath Integration Service** — connectors for Gmail, Sheets, Claude, PDFMonkey

## Reading order

If you have ten minutes and want the shortest path to evaluating this
work, read in this order:

1. **[Week 3 README](Week_3_RDD/README.md)** — the synthesis and the most fully-realized build
2. **[Week 3 board memo](Week_3_RDD/docs/RDD%20Project%20Summary.docx)** — the strategic case the build defends
3. **[Week 2 governance packet](Week_2_CascadeHealth/docs/week2_governance_packet.md)** — the honest version of what's hard about agentic systems
4. **[Week 1 README](Week_1_LoanIntake/README.md)** — for the foundational discipline that underpins the rest

If you have an hour and want regulator-grade detail, add the **[Week 3
Governance Packet](Week_3_RDD/docs/RDD%20Governance%20Packet.docx)** —
Model Card + Decision Logging Specification + Audit Retention Matrix +
Human Override Audit Trail Standard.

## Author

Christopher Williams · c.williams101198@gmail.com

This is a portfolio build. All companies, customers, claims, and
applicants are fictional. Connection definitions in the repo use
`AuthenticateAfterDeployment` — no credentials are committed.
