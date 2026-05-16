# Phase 6 Findings: Disposition Routing and Human-in-the-Loop

This document covers Phase 6 (disposition routing, Action Center, audit logging) and includes Phase 5 cleanup items that surfaced or got resolved during Phase 6 work.

## What Was Built

Disposition routing layer added after the agent chain. The Maestro flow now ends with a four-way exclusive gateway that routes each claim based on `disposition` from AdjudicationAgent, with one branch suspending for human review.

```
[... existing flow through Adjudicate Claim → Mark Email Processed ...]
       ↓
[Route by Disposition]   Exclusive gateway, JS conditions on vars.disposition
       ├── APPROVE  → [Log Approved]    Google Sheets Write Row to audit log
       ├── DENY     → [Log Denied]      Google Sheets Write Row to audit log
       └── REVIEW   → [Send to Action Center] Simple Approval app, suspends flow
                       ↓
                     [Log Reviewed]     Google Sheets Write Row with reviewer's
                                        action overriding agent disposition
       ↓
[End Flow]
```

Audit log: Google Sheet `Cascade Claims Audit Log`, single tab `Adjudicated`, columns:
```
timestamp | claim_id | member_id | total_charges | disposition | escalation_required | reasoning
```

Validated end-to-end on the REVIEW branch (the longest path). Action Center task created in queue, reviewer (Chris) opened it, hit Approve, flow resumed, row written to sheet with reviewer's action and comment captured in the reasoning column.

## Architectural Decisions Worth Naming

### Three-way disposition vs four-way

Initial plan was four branches: APPROVE, DENY, REVIEW, ESCALATE. Caught before building: the AdjudicationAgent's prompt only outputs three dispositions. ESCALATE doesn't exist as a disposition value, it's a separate boolean flag (`escalation_required`) that crosses cuts across all three dispositions per the agent's hard rule 4 (any claim above $50K, regardless of disposition).

Resolution: three-branch disposition routing with `escalation_required` carried as a column in the audit sheet rather than a separate routing path. Anyone reviewing the log can filter on the flag to surface escalated claims regardless of disposition.

This is a category of mistake worth naming. The natural instinct is to model every distinct concern as a branch in the flow. But not every flag needs a branch. Some flags are observational metadata that travels with the record and gets surfaced through query/filter rather than routing. Conflating "this needs to be tracked" with "this needs its own path" produces overengineered flows.

### Mark Email Processed before the gateway, not after

Considered placing Mark Email Processed at the end of each branch. Rejected: the email is processed (extracted, uploaded, adjudicated) regardless of disposition. Marking it processed in the inbox is about deduplication, not business outcome. Putting it after the gateway would either duplicate the task four times or require a converging gateway.

Cleaner: Adjudicate Claim → Mark Email Processed → Route by Disposition. Email is removed from Inbox once the agent has decided something, before the routing concerns kick in.

### Action Center "Simple Approval" template vs custom app

Action Center supports two paths: build a custom UiPath App with a tailored form, or use a built-in template. For tonight: Simple Approval template.

The template gives Approve/Reject buttons, a Content field showing whatever string we pass in, and a Comment field for the reviewer to fill. We constructed Content as a multi-line summary including claim ID, member, charges, and the agent's reasoning. Sufficient for a reviewer to make an informed decision.

Building a custom app would have meant pausing Phase 6 to build a separate Apps project. Worth the deferral. The interesting architectural lesson is the suspend-and-wait semantics, not the form layout.

### Single shared End event vs three terminal End events

Both branches converge into one End Flow. BPMN allows either pattern. Single End is visually cleaner and the branches don't need to signal different terminal states (no downstream system reads the End event itself). If we ever needed differentiated terminal handling (e.g., webhook on REVIEW completion), we'd split them then.

## Hidden Architectural Detail: Suspend-and-Wait

Action Center's `Create action app task` puts the Maestro instance in a Suspended state. The flow stays alive indefinitely (or until the configured task timer expires), waiting for the reviewer to respond. On respond, the flow resumes from where it suspended.

This is a meaningfully different runtime model from typical RPA workflows. RPA workflows run, finish, release. Maestro instances can be live for hours or days while waiting on human action. The suspended state doesn't cost compute, but it does mean Maestro instances accumulate over time if reviewers don't respond.

Optional safety valve: Task timer on the Send to Action Center task with end criteria. Lets timed-out reviews route differently (auto-escalate, auto-deny, ping a backup reviewer). Not configured for tonight, but worth considering for production.

## Phase 5 Cleanup Items Resolved Here

Several Phase 5 items got cleaned up during Phase 6 work:

- The misnamed `in_ClaimId` argument on UploadAttachmentToBucket is still misnamed (cosmetic, deferred again).
- The `claim_id` input to ClaimIntakeAgent was already removed in Phase 5 work session.
- Bucket linking into ClaimsAdjudication folder was already done.

## Phase 6 Completion Criteria

| Criterion | Status |
|---|---|
| Disposition routing wired with conditional gateway | Done |
| APPROVE/DENY paths log to audit sheet | Done |
| REVIEW path creates Action Center task | Done |
| Action Center task carries claim context to reviewer | Done |
| Reviewer decision captured back to audit sheet | Done |
| End-to-end test on REVIEW path | Done |

Republish to 1.1.0 + redeploy still deferred. Debug runs sufficient for validation. Promotion to deployed artifact remains a separate operational step.

## Governance Threads (27-31)

### 27. snake_case agent contracts vs camelCase Maestro variables
New thread. Agent input/output contracts are written in snake_case (`claim_id`, `total_charges`, `escalation_required`). Maestro normalizes these to camelCase as flow variables (`claimId`, `totalCharges`, `escalationRequired`). The agent's documented schema and the variables you actually bind against don't match.

This caught us when writing the Google Sheets row expression. The original `vars.claim_id` returned undefined; `vars.claimId` worked. No documentation surfaces this transformation.

The transformation is silent: no warning, no schema viewer that shows both names, no error if you reference the snake_case version. The expression just evaluates to undefined and you get blank cells in your sheet.

### 28. "Execute connector activity" listing for Google Sheets vs Storage Buckets
Reaffirms Thread 25 from Phase 5. Google Sheets is in the Integration Service connector list (it's a third-party SaaS), so it shows up in "Execute connector activity." Storage Buckets are not, because they're an Orchestrator primitive. Same action label, different rules for what's accessible. The naming continues to mislead.

### 29. Disposition routing as observable behavior of agent contracts
The agent's prompt defines what dispositions can come out (APPROVE, DENY, REVIEW). The orchestrator has to match. If the agent prompt is updated to add a fourth disposition, the orchestrator silently breaks: the new disposition won't match any gateway condition and the claim falls through (or hits a default branch).

There's no contract validation between the agent's prompt-defined output values and the orchestrator's routing conditions. The agent prompt is documentation that the orchestrator depends on but cannot verify against. A typo in the prompt or a refactor that adds a value produces silent routing failures.

This is a subtle category of distributed contract: not a schema mismatch (the field is still a string), but a value-domain mismatch (the string can take on values the consumer doesn't know to handle). Standard schema validation tools don't catch this.

### 30. Action Center task variable casing
The Action Center task's Outputs panel shows `Action` and `Comment` (TitleCase). Maestro variables for those outputs are `vars.Action` and `vars.Comment`, also TitleCase. This is inconsistent with the snake_case → camelCase transformation in Thread 27. Different connectors normalize variables differently and there's no way to see the rule.

### 31. Suspend-and-wait as architectural primitive
Maestro's ability to keep an instance alive across human review is a real capability that changes how you think about flows. Standard RPA mental models don't include "this workflow lives for 4 days waiting on a person." Designing around suspend-and-wait means thinking about timeouts, fallbacks, and accumulated state that traditional RPA doesn't require.

This is reflection seed material more than a thread. The capability isn't broken, it's just genuinely different from what's familiar.

## Reflection Seeds for Week 3 Memo (continued)

### 14. Flags vs branches as a design distinction
Not every distinct concern needs its own path through the flow. Some concerns are observational metadata that travels with the record and gets surfaced through query rather than routing. Conflating "track this" with "branch on this" produces flows with combinatorial branching where simple metadata would suffice. The skill is recognizing which is which.

### 15. Distributed contracts that schema validation doesn't cover
Agent prompts define value domains for output fields. Orchestrators route on those values. The contract is real but lives in two places (the prompt and the routing conditions) and can drift silently. Standard contract testing (schema validation, type checking) doesn't catch value-domain drift. This is a gap in tooling for agentic systems specifically, where prompts encode contracts that traditional tooling treats as unstructured text.

### 16. Suspend-and-wait changes the design space
Once a flow can suspend on human action, you're designing for time horizons measured in hours and days, not seconds. Timeouts, fallbacks, reviewer assignment, and queue management become first-class concerns. Most enterprise automation tooling assumes "run to completion" semantics; Maestro's suspend-and-wait is a different model that requires different architectural intuitions.

## Files Touched

- `CascadeClaimsAdjudication/ClaimAdjudicationFlow/Process.bpmn`: added gateway, three branches, Action Center task, three log tasks, all conditions and bindings
- Google Sheets: created `Cascade Claims Audit Log` with single Adjudicated tab and 7-column header row
- Gmail account `chrisbankingapp@gmail.com`: Google Sheets connection authorized through OAuth
- ClaimsAdjudication folder: Google Sheets connection added to folder

## Open Items for Phase 7

- Republish + redeploy as 1.1.0 (deferred from Phase 5).
- Cleanup pass on the audit log: timestamp formatting (`2026-05-02T20:52:00.199Z` → human-readable), column widths, possibly a derived column for "agent vs reviewer disposition" so override patterns are visible.
- Custom Action Center app (replacing Simple Approval template) if the demo benefits from a tailored form.
- Optional: Task timer on Send to Action Center for SLA enforcement.
- Phase 7 governance packet drawing on threads 1-31 across all phases.
