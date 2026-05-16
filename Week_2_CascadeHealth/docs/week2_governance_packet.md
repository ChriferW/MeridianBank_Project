# Week 2 Governance Packet: Cascade Claims Adjudication

**Author:** Christopher Williams
**Project:** Cascade Health Claims Adjudication, an agentic insurance-claims processing system built on UiPath
**Scope:** Findings from Week 2 of a multi-week build, covering Phases 5-7 (Maestro orchestration, disposition routing, human-in-the-loop, deployment activation)

## Project framing

Cascade Health is a fictional health insurance subsidiary of Meridian Bank. The challenge: build an end-to-end agentic system that ingests inbound claims via email, extracts structured data, applies medical-necessity and policy-based reasoning, routes outcomes appropriately, and surfaces edge cases to human reviewers — all on the UiPath platform.

By the end of Week 2, the system runs autonomously: a member emails a PDF claim to a designated inbox, and within roughly a minute the claim is extracted, adjudicated by an LLM agent operating under explicit policy rules (with optional second-opinion consultation to Anthropic's Claude), routed to one of three dispositions (APPROVE, DENY, REVIEW), logged to an audit sheet, and either terminated or suspended pending human review in UiPath Action Center. The orchestration layer (UiPath Maestro) keeps the flow alive across days if needed while a human reviewer responds.

The build works. This document is not a victory lap on that. It's a synthesis of the architectural and governance findings that surfaced while building it — the kinds of things that don't show up in a demo but matter for anyone operating an agentic system in production.

## Architecture summary

The deployed system is a single UiPath solution containing five components:

- **ClaimIntakeAgent** (autonomous LLM agent): reads PDFs from a Storage Bucket using UiPath's Document Understanding (DU) tool, extracts a 12-field structured record, validates internal consistency, and emits a confidence-scored JSON payload.
- **AdjudicationAgent** (autonomous LLM agent): consumes the structured record, applies five hard rules (extraction-quality thresholds, medical-necessity reasoning, policy-based decisioning, escalation thresholds, no-invention discipline), and outputs a disposition with reasoning. Has access to a "Medical Necessity Second Opinion" tool that calls Anthropic's Claude for an independent perspective on ambiguous CPT/ICD-10 pairings.
- **UploadAttachmentToBucket** (RPA workflow): wraps the Orchestrator-native Storage Bucket upload activity, exposing it as something Maestro can call.
- **ClaimAdjudicationFlow** (Maestro BPMN process): orchestrates the entire pipeline from Gmail trigger through final logging.
- **SimpleApprovalApp** (UiPath Action Center app): the human-reviewer interface for REVIEW dispositions, built from a template rather than a custom form.

The flow is triggered by inbound email matching a subject filter and attachment requirement. Outputs land in a Google Sheet audit log and (for REVIEW cases) in Action Center reviewer queues.

## Governance findings

The findings below are organized into themes. They are presented as observations, not recommendations. The implicit recommendation, where it exists, is that anyone building similar systems should be aware of these dynamics.

### 1. Hidden contract redundancy in agent input/output schemas

The original ClaimIntakeAgent contract listed `claim_id` as both a required input and a returned output. The intuitive read: the caller knows the claim ID, passes it in, and the agent echoes it back as part of the structured record. The reality: DU was extracting `claim_id` from the PDF content directly, and the input was being silently overwritten by the extraction.

The redundancy was discovered only by removing the input and observing that nothing broke. There was no static analysis or platform tooling that surfaced the conflict, because the conflict only existed at runtime, when the input value would arrive (whatever it was) and DU's extraction would produce its own value (whatever it was), and the agent's output schema would emit DU's value, and the caller would never know the input had been ignored.

This generalizes: any agent input that the agent's tools also produce is suspect. The platform offers no way to detect this category of redundancy. It's a class of contract drift specific to agentic systems, where the agent's internal tools can shadow the contract the orchestrator believes it's negotiating with.

### 2. Distributed contracts that schema validation does not cover

Agent prompts define value domains for output fields. The AdjudicationAgent's prompt specifies that `disposition` will be one of three string values: APPROVE, DENY, or REVIEW. The orchestration layer routes on those values via gateway conditions.

If the agent's prompt is updated to add a fourth disposition, the orchestrator silently breaks: the new value won't match any gateway condition, and the claim falls through. There is no contract validation between prompt-defined output domains and orchestrator-defined routing conditions. The prompt is documentation that the orchestrator depends on but cannot verify against. A typo in the prompt or a refactor that adds a value produces silent routing failures.

This is a subtle distributed-contract problem. It is not a schema mismatch in the traditional sense (the field is still typed as a string). It is a value-domain mismatch, and standard schema validation tools do not catch it. For agentic systems where prompts encode contracts, this is a gap in tooling that is worth thinking about explicitly.

### 3. Bucket filenames as transport identifiers, not business identifiers

An early instinct was to use the claim ID as the filename for the PDF stored in Orchestrator's bucket. This broke down on closer inspection: the claim ID lives inside the PDF, not in the email metadata. Subject-line parsing would work only if senders followed a strict naming convention, which is theatrical compliance rather than real automation.

The fix was to use the Gmail attachment ID as the bucket key. It's guaranteed unique per email, available at trigger time, and meaningless to the business logic. The agent extracts the actual claim ID from the PDF content and that becomes the business identifier downstream.

The principle: business identifiers live in the work product, not in the metadata. Asking the orchestration layer to know them before processing is asking it to do work that belongs to the agent. Transport identifiers (attachment IDs, GUIDs, timestamps) are the correct level of identifier at the orchestration boundary. The bucket key is plumbing, not data.

### 4. Routing branches versus observational metadata

The AdjudicationAgent emits both a `disposition` (APPROVE/DENY/REVIEW) and a separate `escalation_required` boolean flag, the latter triggered by claim value thresholds. The instinct when designing the disposition routing was to model escalation as a fourth branch in the gateway.

This was wrong. Escalation crosses cuts across all three dispositions. Modeling it as a branch would have produced six combinations (3 dispositions × 2 escalation states) or required collapsing information. The cleaner solution: keep the three-branch routing and carry `escalation_required` as a column in the audit log. Anyone reviewing the log can filter on the flag.

Not every flag deserves a branch. Some flags are observational metadata that travels with the record and gets surfaced through query rather than routing. Conflating "track this" with "branch on this" produces flows with combinatorial branching where simple metadata would suffice. The skill is recognizing which is which before building.

### 5. Suspend-and-wait as a different runtime model

UiPath Maestro supports flows that suspend on human action and resume when the human responds. The Action Center task in this build keeps the Maestro instance alive indefinitely, waiting for a reviewer. This is a meaningfully different runtime model from typical RPA, where workflows run to completion in seconds and release.

Designing around suspend-and-wait means thinking about timeouts, fallback routing, reviewer assignment, queue accumulation, and the operational reality that some flow instances will live for days. Standard RPA mental models do not include "this workflow lives for 96 hours waiting on a person." Most enterprise automation tooling assumes run-to-completion semantics. This is a capability that changes the design space, not a feature added to an existing one.

### 6. Connection lifecycles as silent operational risk

Between the end of Phase 6 and the deployment activation in Phase 7, three external connections expired silently: both Gmail OAuth tokens and the Anthropic Claude API connection. The only signal was deployment activation refusing to proceed, with errors surfaced in the activation panel.

This is an operational reality of agentic systems with multiple external dependencies. Each external connection has its own credential lifecycle, governed by the third-party provider, and the orchestration platform depends on all of them being valid simultaneously. There is no pre-emptive warning system, no dashboard surfacing "credentials expiring in N days," and no automated rotation. A system that worked perfectly on Friday can fail silently on Monday because a token expired over the weekend.

For production deployment, this implies a need for connection-monitoring infrastructure that the platform does not provide out of the box.

### 7. Naming inconsistencies and transformation rules that are not surfaced

Several findings in this category accumulated across the build:

- Agent input/output contracts use snake_case; Maestro normalizes to camelCase as flow variables. This caused an actual debugging session when `vars.claim_id` returned undefined and `vars.claimId` worked. No documentation surfaces the transformation.
- The "Execute connector activity" action name in Maestro suggests it can call any connector, but it is restricted to UiPath's Integration Service partner list. Native Orchestrator primitives (Storage Buckets, Queues, Assets) require different action types entirely. The label is misleading and cost real time to discover.
- The Action Center task's outputs use TitleCase (`Action`, `Comment`), inconsistent with the snake_case-to-camelCase normalization applied elsewhere. Different connectors normalize variables differently and there is no way to inspect the rules.

These are minor individually but accumulate into a pattern: the platform makes consequential transformations that are not documented, not visible in the UI, and discoverable only by failure.

## Reflection: what this build taught

Three observations worth surfacing for an interviewer rather than burying in findings:

**The hardest problems were not technical.** Wiring activities together, parsing JSON, building gateways — those are straightforward once you understand the platform's vocabulary. The hard problems were architectural: deciding what counts as a business identifier vs. a transport identifier, recognizing when a flag should drive routing vs. travel as metadata, noticing when an agent contract was redundant in ways the platform could not detect.

**Agentic systems require contract discipline that traditional tooling does not enforce.** Schema validation catches type mismatches. It does not catch value-domain drift between prompts and routing logic. It does not catch redundancy between explicit inputs and tool-generated outputs. It does not catch silent variable name normalization between layers. Building reliably on agentic platforms means developing a discipline of contract awareness that the tooling will not give you for free.

**Production deployment is a discrete capability, not the natural conclusion of building.** The build worked end-to-end in debug mode for days before the actual deployment surfaced credential expiration, folder placement decisions, and trigger registration as separate concerns. Treating deployment as a first-class engineering activity, with its own checklist and its own failure modes, would have saved time. This is true of most enterprise systems and especially true of ones with as many external dependencies as agentic platforms have.

## Closing

The Cascade Health build is functional, deployed, and processing inbound claims autonomously. The findings above are not critiques of UiPath specifically — many would apply to any agentic platform — but observations about the kinds of governance work that responsible deployment of these systems requires. Most of the failure modes here are silent ones. They do not produce errors at the time the mistake is made; they produce wrong behavior at runtime, often well after the original decision is forgotten.

For a bank evaluating production deployment of agentic systems, the recurring theme worth taking seriously is this: the platform handles a lot, but contract discipline, credential lifecycle management, and architectural judgment about what to model as routing vs. metadata remain the responsibility of the people building the system. Tooling will not catch these for you. They have to be built into the team's practice.
