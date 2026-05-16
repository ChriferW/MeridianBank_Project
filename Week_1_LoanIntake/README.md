# Week 1 — LoanIntake

Production-grade deterministic automation for Meridian Financial Group's
loan-application intake. Ingests applications from a shared mailbox,
validates them, looks up the applicant in core banking, scores against
business rules, and routes each application to one of five outcomes —
without an AI agent anywhere in the loop.

## Place in the three-build arc

This is **Build 1 of 3**. The brief: prove mastery of deterministic
automation before introducing AI. Every routing decision is rule-based,
every exception is named and handled, and every transaction is logged
to Orchestrator queues with full provenance.

- **Build 1 (this project):** Deterministic RPA — REFramework, Orchestrator queues, rule-based routing
- **Build 2 ([Week_2_CascadeHealth](../Week_2_CascadeHealth/)):** Agentic LLM workflows under human review — Cascade Health claims adjudication
- **Build 3 ([Week_3_RDD](../Week_3_RDD/)):** Synthesis — agentic decisioning with regulator-grade governance, audit, and disclosure

## What it does

A bank operations team receives loan applications by email. Each email
contains an application PDF and structured fields. This automation:

1. **Watches the shared inbox** for unread applications.
2. **Validates the PDF** is readable, contains the required fields, and the SSN/ID format is well-formed.
3. **Extracts** the applicant data into structured form.
4. **Looks up the applicant** in the core-banking system (via stubbed VBO) and pulls their credit score.
5. **Scores** the application against the business rule set.
6. **Routes** to one of five outcomes — auto-decision, manual queue, senior-approval queue, or business-exception queue.
7. **Records** every step on the Orchestrator queue item for downstream audit.

At demo scale: **~500 applications processed in 3–4 minutes** end-to-end.

## How it works — dispatcher / performer + REFramework

```
                Shared inbox
                     │
                     ▼
     ┌───────────────────────────────┐
     │  LoanIntake.Loader            │     dispatcher
     │  (attended / scheduled)       │
     │  - read unread emails         │
     │  - extract fields             │
     │  - one queue item per email   │
     └───────────────┬───────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │ Orchestrator queue:         │
       │ Loan_Applications_Intake    │
       └──────────────┬──────────────┘
                      │
                      ▼
     ┌───────────────────────────────┐
     │  LoanIntake.Worker            │     performer (REFramework)
     │  (unattended)                 │
     │  - dequeue 1 item             │
     │  - validate → lookup → score  │
     │  - route to outcome           │
     │  - SetTransactionStatus       │
     │  - loop                       │
     └───────────────┬───────────────┘
                     │
                     ▼
           One of five outcomes
```

Both the Loader and the Worker consume **LoanIntake.Library** — a single
reusable activity library so the "extract email fields", "validate PDF",
and "lookup customer" logic exists in exactly one place.

The Worker is built on UiPath's **REFramework** (`Framework/` directory).
That gives us a state-machine driven runtime with:

- `InitAllSettings.xaml` — load Config.xlsx + Orchestrator assets
- `InitAllApplications.xaml` — open required apps (none in this project)
- `GetTransactionData.xaml` — dequeue one item from the queue
- `Process.xaml` — the per-transaction business logic
- `SetTransactionStatus.xaml` — mark Successful / BusinessException / SystemException
- `RetryCurrentTransaction.xaml` — retry path for transient failures
- `CloseAllApplications.xaml` / `KillAllProcesses.xaml` — graceful + forced shutdown
- `TakeScreenshot.xaml` — exception evidence capture

Why REFramework? Because regulators want to see exception architecture,
not heroic try/catch blocks. The state machine makes the recovery model
**inspectable as a diagram** — you can point at it and say "this is the
SystemException path; this is what happens on retry."

## The five outcomes

| Outcome | Trigger | Where it routes |
|---|---|---|
| `AUTO_APPROVE` | ≤ $10,000 **and** credit score ≥ 720 | Decision queue, status `Successful` |
| `AUTO_DECLINE` | Credit score < 580 (knockout) | Decision queue, status `Successful` |
| `MANUAL_REVIEW` | Middle band (580–719 or amount $10k–$500k) | Manual-review queue, status `Successful` |
| `ESCALATE_PENDING_APPROVAL` | Requested amount > $500,000 | Senior-approval queue + Action Center form (`HighValueLoanApproval.json`), status `Successful` |
| `BUSINESS_EXCEPTION` | Customer not found, PDF unreadable, required field missing | Exception queue, status `BusinessException` |

Knockouts (low credit) fire **before** amount checks so a low-credit
borrower requesting $750k auto-declines instead of wasting senior
reviewer time on a request that can't qualify.

## Worker exception handling

The Worker distinguishes three exception classes — every one of them
mapped to a distinct REFramework status so post-hoc reporting can split
them cleanly:

| Class | Caught where | Status set | Effect |
|---|---|---|---|
| **Business exception** | `Process.xaml` (data invalid, customer unknown) | `BusinessException` | Item is **not** retried; routed to exception queue for human follow-up |
| **System exception (transient)** | `Process.xaml` (network blip, locked file) | `ApplicationException` → retry | REFramework retries up to the limit set in Config; on final failure, abandoned and logged |
| **System exception (terminal)** | Init/Cleanup states | `SystemException` | Worker exits, alerts ops; whole batch is paused |

This three-class split is the unsexy heart of why Blue Prism's
contemporaries point to REFramework as the production-credible RPA
pattern: not every error is the same kind of error.

## Repository layout

```
Week_1_LoanIntake/
├── README.md                                       (this file)
│
├── docs/
│   ├── LoanIntake_SDD.pdf                          Solution Design Document — definitive spec
│   └── LoanIntake_Architecture_UIPath_Week_1.png   one-page architecture diagram
│
├── source/
│   ├── LoanIntake.Loader/                          dispatcher project
│   │   ├── Main.xaml                               read inbox → enqueue
│   │   └── project.json                            depends on LoanIntake.Library
│   │
│   ├── LoanIntake.Worker/                          performer project (REFramework)
│   │   ├── Main.xaml                               state-machine entry point
│   │   ├── Framework/                              9 REFramework state .xaml files
│   │   ├── Data/
│   │   │   ├── Config.xlsx                         assets, retries, queue name, log fields
│   │   │   └── Input | Output | Temp/              per-run scratch (gitkept)
│   │   ├── Forms/
│   │   │   └── HighValueLoanApproval.json          Action Center form for >$500k reviews
│   │   ├── Tests/                                  7 REFramework test cases (xaml + Tests.xlsx)
│   │   └── Exceptions_Screenshots/                 evidence captures on SystemException
│   │
│   └── LoanIntake.Library/                         14 reusable activities, three namespaces
│       ├── CoreBanking/                            (4) credit + customer lookup
│       ├── Documents/                              (4) PDF validation + field extraction
│       └── Email/                                  (6) inbox lifecycle
│
└── test-data/
    ├── loan_applications_sample.xlsx               canonical sample applications
    └── bulk_send_test_emails.py                    load harness — sends 500 emails in ~3–4 min
```

## The Library — 14 reusable activities

The "boring" surface that ends up doing the heavy lifting. Used by both
the Loader and the Worker, versioned independently (`LoanIntake.Library
v1.0.4`).

### `CoreBanking/` — wraps the core-banking system VBO

| Activity | Purpose |
|---|---|
| `Connect.xaml` | Open a session to the core-banking endpoint (stubbed for demo) |
| `Disconnect.xaml` | Close the session — pairs with Connect via try/finally in callers |
| `LookupCustomerBySSN.xaml` | Returns customer record or `BusinessException` if not found |
| `GetCreditScore.xaml` | Returns numeric credit score (300–850); raises on missing record |

### `Documents/` — PDF intake validation

| Activity | Purpose |
|---|---|
| `ValidatePdfIsReadable.xaml` | Can OCR open it? If not → BusinessException |
| `CheckRequiredFieldsPresent.xaml` | Are SSN, amount, purpose, name all present? |
| `ValidateIdFormat.xaml` | SSN matches `XXX-XX-XXXX`; ID format well-formed |
| `ExtractTextFromPdf.xaml` | Pulls text body for downstream field extraction |

### `Email/` — inbox lifecycle

| Activity | Purpose |
|---|---|
| `Initialize.xaml` | Open mailbox connection (uses Mail Activities) |
| `Cleanup.xaml` | Close mailbox connection cleanly |
| `GetUnreadLoanApplications.xaml` | Returns the unread set (filtered by subject convention) |
| `GetAttachments.xaml` | Saves the PDF attachment to a known path |
| `ExtractApplicationFields.xaml` | Parses subject + body for the structured fields |
| `MarkProcessed.xaml` | Moves the email to the `Processed/` label so it never re-runs |

Wrapping all I/O in a Library — rather than scattering Read/Write
activities across workflows — is what makes this thing maintainable when
the core-banking team changes their auth or the inbox convention shifts.
You patch the Library, publish v1.0.5, and every consumer picks it up.

## Running it

### Prerequisites

- UiPath Studio 26.0.191.0 (Windows)
- Orchestrator tenant with:
  - Queue `Loan_Applications_Intake` provisioned
  - Mail connection for the shared inbox
  - Action Center license (for the high-value approval form)

### Generating test load

```bash
cd test-data
python3 bulk_send_test_emails.py
# sends ~500 emails from loan_applications_sample.xlsx into the configured inbox
```

The harness reads the sample workbook, picks rows, and emits one email
per row. End-to-end on a single Worker robot, ~500 emails clear in 3–4
minutes including queue dispatch, PDF validation, core-banking lookup,
and outcome routing.

### Running the automation

1. Publish `LoanIntake.Library` to your tenant feed first (Loader and Worker depend on it)
2. Publish `LoanIntake.Loader` and `LoanIntake.Worker`
3. Start the Loader on a schedule (or attended trigger) — enqueues items
4. Run the Worker unattended — drains the queue, routes outcomes
5. High-value items requiring senior approval surface in Action Center
   via the `HighValueLoanApproval` form

## Tech stack

| Layer | Choice |
|---|---|
| IDE | UiPath Studio 26.0.191.0 |
| Pattern | Dispatcher / Performer with REFramework |
| Runtime | UiPath Robot, Windows target framework |
| Orchestration | UiPath Orchestrator (queues, assets, schedules) |
| Human-in-the-loop | UiPath Action Center (Forms) |
| Library deps | `UiPath.Mail.Activities`, `UiPath.PDF.Activities`, `UiPath.WebAPI.Activities`, `UiPath.System.Activities` |
| Worker deps | adds `UiPath.Persistence.Activities` (job-level persistence), `UiPath.Form.Activities`, `UiPath.Excel.Activities`, `UiPath.Testing.Activities` |
| Load harness | Python (`bulk_send_test_emails.py`) |

## Documentation

- **[`docs/LoanIntake_SDD.pdf`](docs/LoanIntake_SDD.pdf)** — the Solution Design Document. The definitive spec: queue config, exception decision tree, robot allocation, threshold rationale.
- **[`docs/LoanIntake_Architecture_UIPath_Week_1.png`](docs/LoanIntake_Architecture_UIPath_Week_1.png)** — one-page architecture diagram.
