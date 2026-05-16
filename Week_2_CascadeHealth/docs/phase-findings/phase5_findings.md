# Phase 5 Findings: Maestro Orchestration

## What Was Built

End-to-end claims adjudication flow orchestrated by Maestro (`ClaimAdjudicationFlow`) inside the `CascadeClaimsAdjudication` solution. Email-triggered, agent-executed, label-managed.

```
[Claim Email Received]   Gmail trigger, Inbox + subject contains [CASCADE-CLAIM] + has attachment
       ↓
[Extract Attachment]     Gmail connector, Download Email Attachment By Attachment ID
       ↓
[Save Attachment]        RPA workflow UploadAttachmentToBucket
                         Bucket key: InputFiles/<gmail_attachment_id>.pdf
       ↓
[Process Document]       ClaimIntakeAgent (Start and wait for agent)
                         Inputs: document_reference (bucket path)
                         Outputs: 12 fields including extracted claim_id
       ↓
[Adjudicate Claim]       AdjudicationAgent (Start and wait for agent)
                         Inputs: 12 fields auto-mapped from prior task
                         Outputs: disposition, escalation_required, reasoning, service_line_assessments
       ↓
[Mark Email Processed]   Gmail connector, Move Email (apply Processed Claims label, remove Inbox)
       ↓
[End Flow]
```

Validated working end-to-end via debug runs. Final test produced REVIEW disposition with per-service-line medical necessity assessments, including correct flagging of CPT 90471 + ICD-10 E78.5 as suspect (immunization administration paired with hyperlipidemia diagnosis).

## Phase 5 Completion Criteria

| Criterion | Status |
|---|---|
| Maestro flow validates green | Done |
| Solution republished as 1.1.0 | Not done (debug-tested only) |
| Solution redeployed | Not done |
| End-to-end test with real email | Done |
| Findings doc | This document |

Republish and redeploy intentionally deferred. Debug runs were sufficient to validate the architecture. Promotion to deployed artifact is a separate operational step.

## Architectural Decisions Worth Naming

### Solution placement of the Maestro process

Initial assistant suggestion was to create the Maestro process in a separate solution. Chris pushed back and was correct: the Maestro process belongs in the same solution as the agents it orchestrates. The orchestration and the components it composes are one deployable unit, not three.

This was settled by user instinct, not platform guidance. Studio Web's "create new agentic process" flow defaults to creating a new solution, repeating the same trap as agent creation in Phase 4 (Thread 19). See Thread 21.

### Bucket filename as transport ID, not business ID

Original assumption: bucket filename = `<claim_id>.pdf`, with claim_id parsed from email subject. Broke under inspection: claim_id lives inside the PDF, not in the email metadata. Subject-based parsing would only work if senders followed a strict convention, which is theater rather than real automation.

Resolution: bucket filename = `InputFiles/<gmail_attachment_id>.pdf`. The Gmail attachment ID is guaranteed-unique per email, available at trigger time, and meaningless to the business logic. ClaimIntakeAgent extracts the real claim_id from PDF content via DU. The bucket key becomes a pure transport handle.

This forced a related discovery, see "Hidden agent contract redundancy" below.

### Sequential rather than parallel for Mark Processed

Considered: run Mark Email Processed in parallel with Process Document/Adjudicate Claim to save wall-clock time.

Decided against. Parallelism would save ~2 seconds. Cost: if downstream processing fails, the email is already marked processed and won't be retried by the next polling cycle. Sequential ordering gives clean retry semantics for free.

Worth noting BPMN doesn't infer parallelism from canvas layout. Two outgoing arrows from a task is ambiguous routing, not parallel split. A parallel gateway (`+` diamond) is required for actual concurrent execution. The visual cue and the runtime semantics are decoupled.

### Label-and-archive vs labels alone vs Move Email

Gmail's "label vs folder" abstraction is leaky. Folders in the UI are labels under the hood. Moving an email = applying a new label and removing the Inbox label. Two operations.

The Gmail connector exposes both atomic operations (Apply Gmail Labels, Remove Gmail Labels) and the bundled one (Move Email). Move Email is the right call when the intent is "out of Inbox, into category X" because it's atomic and the rollback semantics are clean.

This matters for trigger filter integrity. The trigger filters on `Email folder or label = Inbox`. Apply-only would leave the email in Inbox and matching the trigger forever (subject filter and attachment filter still pass). Move-from-Inbox is what actually breaks the loop.

## Hidden Agent Contract Redundancy (Discovered, Not Predicted)

ClaimIntakeAgent's original input contract included `claim_id` (Text) as a required input. The system prompt and user prompt both referenced it. The output schema also included `claim_id` as one of the 12 returned fields, sourced from DU extraction.

In Phase 5, removing `claim_id` from the input contract caused zero functional impact. The agent ran successfully, output the correct claim_id (extracted from the PDF), and downstream wiring continued to work.

The input was decorative. DU was the source of truth all along. The redundancy was hidden by silent agreement: whatever was passed in matched whatever DU extracted, so nothing ever surfaced the conflict.

This is a category of agent design failure mode worth naming. Input contracts written under the assumption that the orchestrating layer knows business identifiers, when in reality those identifiers live in the documents being processed. The result is contracts that look like they require information the caller has, but actually require information the caller is asking the agent to produce.

The only way to discover this is to remove the input and observe nothing breaks. There's no static analysis or platform tooling that surfaces it.

## Governance Threads (21-26)

Threads 21-24 from the Phase 5 handoff played out as predicted. Two new threads emerged:

### 21. Maestro process creation defaults to new Solution
Predicted in handoff. Confirmed. Same trap as Thread 19 (agent creation flow). Studio Web's "current solution context" is not sticky in creation flows. User instinct ("this should go in the existing solution") was correct against assistant suggestion.

### 22. "Agentic process" terminology overload
Confirmed. Maestro BPMN container = "Agentic process." Individual autonomous agents = "Agent." Linguistically inverted from intuition: the Agentic process is the orchestrator, the Agents are the workers it orchestrates.

### 23. Defined resources vs Platform resources in Maestro task wiring
Confirmed. Platform resources (deployed) is the correct choice for runtime binding. Defined resources (local) is only valid if the same solution is also deployed. No in-product guidance on which to pick. The choice has runtime consequences but the UI presents them as equivalent.

### 24. Start event Action options are connector-only
Confirmed. Native primitives (file watcher, scheduled trigger) are not Start event options. All triggers route through the connector marketplace. Trigger architecture and connector authentication architecture are the same architecture, by construction.

### 25. "Execute connector activity" is Integration Service only
New thread. The action label "Execute connector activity" suggests "any connector," but the dropdown contains only Integration Service connectors (external SaaS). UiPath's own primitives (Storage Buckets, Queues, Assets) are not in the list. Native Orchestrator primitives require a different action type (`Start and wait for RPA workflow` wrapping the relevant activity, or API workflow with the Orchestrator REST API).

This is a naming failure with architectural consequences. A user expecting to call Storage Buckets directly from Maestro will spend real time discovering this only by failing to find the option, then needing to scaffold an entire RPA project to wrap a single activity.

### 26. Hidden agent contract redundancy
New thread, see "Hidden Agent Contract Redundancy" section above. Inputs that look authoritative but are actually overwritten by tool extraction. Discoverable only by removing the input and observing nothing breaks.

## Reflection Seeds for Week 3 Memo

Carry forward from prior phases (1-9 from earlier findings docs).

### 10. Orchestration as part of the deployed artifact
Settled in Phase 5 setup. The Maestro process belongs in the same solution as the agents it orchestrates. They are one deployable unit. Tooling that defaults to the opposite (new solution per process) is fighting the architecture. User instinct outweighed assistant suggestion. The disagreement is itself the lesson: when the platform's defaults contradict architectural sense, defaults should not win by inertia.

### 11. Trigger architecture is connector architecture
Confirmed strongly. The decision of where work originates (email arrival, file drop, scheduled run) is the same decision as which external system holds the credentials and exposes the event. There is no neutral "system trigger" primitive. Every trigger has an owner, and that owner is a connector. This collapses two architectural concerns into one and means trigger choice is downstream of credential management rather than a separate question.

### 12. Bucket filename design as a discipline
The "use claim_id as the filename" instinct was wrong, and the wrongness was instructive. Business identifiers live in the work product, not in the metadata. Asking the orchestration layer to know them before processing is asking it to do work that belongs to the agent. Transport identifiers (attachment IDs, GUIDs, timestamps) are the right level of identifier at the orchestration boundary. The bucket key is plumbing, not data.

### 13. Hidden contract redundancy as a category
Agent input contracts can encode redundancy that's invisible until tested. The only signal is removing the input and observing nothing breaks. This generalizes: any input that the agent's tools also produce is suspect. The platform offers no way to detect this statically.

## Files Touched

- `CascadeClaimsAdjudication/ClaimAdjudicationFlow/Process.bpmn` (built out from skeleton to full 6-task flow)
- `CascadeClaimsAdjudication/UploadAttachmentToBucket/Main.xaml` (new RPA workflow, single Upload Storage File activity)
- `CascadeClaimsAdjudication/UploadAttachmentToBucket/` Data Manager (3 arguments: in_Attachment File, in_ClaimId Text, out_BucketPath Text)
- `CascadeClaimsAdjudication/ClaimIntakeAgent` Data Manager (removed `claim_id` input)
- `CascadeClaimsAdjudication/ClaimIntakeAgent` user prompt (removed `Claim ID: {{claim_id}}` line)
- Gmail account `chrisbankingapp@gmail.com`: created `Processed Claims` label
- Orchestrator: linked `du_ClaimsIntake_DU_resources` bucket into ClaimsAdjudication folder

## Open Items for Phase 6

- Disposition routing (REVIEW → Action Center, ESCALATE → RPA fallback, APPROVE/DENY → terminal)
- The `in_ClaimId` argument on UploadAttachmentToBucket is misnamed (it's now a transport key, not a business ID). Cosmetic, can be renamed when convenient.
- Republish and redeploy as 1.1.0 when ready to promote out of debug.
