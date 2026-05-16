# Phase 3 Findings: Agent 1 (Claim Intake) Build

**Project:** Cascade Health Claims Adjudication, Week 2 of 12-day Enterprise RPA Challenge
**Phase:** 3 of 8 (Agent 1 — Intake build)
**Status:** Complete. Successful end-to-end debug run validated.
**Test claim:** CHC-400002, single-document plumbing validation.

---

## Build summary

Built the ClaimIntakeAgent in Studio Web (autonomous agent type, gpt-4o-2024-11-20). Agent receives a `claim_id` and a `document_reference` (path inside an Orchestrator storage bucket), invokes a registered RPA workflow tool that wraps the CascadeClaim Document Understanding model, and returns a structured claim record with derived confidence and validation fields.

Wrapper workflow (`ClaimsIntake_DU document processing automation`) was scaffolded by Autopilot via the "Open Studio Web" button on the DU Publish page. Original scaffold was a batch-loop demo pattern (Manual Trigger → Retrieve sample files → For each → Download → Extract → Validate → Write extracted data). Restructured into a single-document agent-tool pattern: Manual Trigger → Download sample file → Extract Document Data → 9 Set Variable Value activities mapping DU extraction fields to typed output arguments. Republished as v1.0.3, deployed as a Process in Orchestrator under the Autopilot folder, and registered as a Tool on the agent.

Agent contract has 2 input args (claim_id, document_reference) and 12 output args. Of those 12, 9 are extracted by the workflow (claim_id, member_id, date_of_birth, policy_number, provider_npi, provider_name, total_charges, provider_narrative, service_lines) and 3 are derived by the agent itself per system prompt rules (confidence_score, needs_fallback, consistency_error).

System prompt encodes three hard rules: never invent data, lower confidence by 0.1 per missing field and trigger needs_fallback below 0.85, and validate that line-item charges sum to total_charges within $1.00 tolerance.

---

## End-to-end test result

Single debug run with claim_id=CHC-400002, document_reference=InputFiles/CHC-400002.pdf. Job completed Successful in roughly 50 seconds (35s suspended waiting on robot, 4s active LLM and tool execution).

Output round-trip validated. All 8 scalar DU fields extracted correctly. service_lines came back as a typed array of 2 objects with all 4 nested fields populated. Agent computed confidence_score=1.0 (no missing fields), needs_fallback=false, and consistency_error=false correctly (line items sum 66167.57 + 42262.52 = 108430.09 exactly matches total_charges).

Note: CHC-400002 is in the ESCALATE tier (>$100K, set aside for Phase 5 failure-scenario testing). Agent 1 correctly extracted without flagging escalation; escalation routing is Agent 2's responsibility, not Agent 1's. This confirms the architectural separation between extraction and adjudication.

---

## Governance-packet threads accumulated this phase

This phase surfaced an unusually large number of platform-quirk findings, all real and worth capturing for Phase 7. They cluster around three themes: scaffolding versus engineering, type system disclosure, and the agent-tool data contract.

### 1. API workflow vs RPA workflow architectural distinction

When wrapping the DU project as an agent tool, the agent's tool registration UI presents both API workflows and RPA workflows as valid choices. The product surface offers no in-line guidance on which to pick for which integration. The naming is also actively misleading: "API workflow" sounds like it consumes an external API, but it actually exposes one. RPA workflows are the consumers. The first attempt went down the API workflow path before the mistake became evident, requiring the workflow to be deleted and re-scaffolded. An enterprise-grade build experience needs explicit guidance at the tool picker.

### 2. Autopilot scaffolding is opinionated, not generic

Autopilot's "Open Studio Web" button on the DU Publish page produces a working integration, but the pattern it scaffolds assumes a batch-demo loop (iterate over a bucket directory). Single-document agent-tool flows require restructuring: lifting activities out of the For Each, deleting the manual trigger and bucket-listing activities, replacing the file-write step with output assignments. Autopilot helped at the field-level (DU activity wired correctly with project, version, and document type), but the orchestration topology had to be hand-rebuilt. Engineers need to be aware that Autopilot scaffolds patterns, not minimum viable wrappers.

### 3. Robot account folder permission gap surfaces only at first agent invocation

The Default Robot account is created at tenant level and added to the Automation Users group. When the agent first attempted a tool call, execution failed with `Couldn't find any user with unattended robot permissions in the current folder`. The fix required explicitly assigning the Default Robot account to the Autopilot folder via the folder's Manage Access surface and giving it the Automation User role. Group membership at tenant level does not propagate to folder-level execution permissions, despite the inheritance language in the documentation. This is a real production-readiness gap: engineers won't know they need this until they try to run.

### 4. DU buckets land in the user's personal workspace, not the solution folder

DU automatically creates a storage bucket named `du_<project>_resources` in the user's personal workspace folder when a project is published. Agent tool calls run under a robot account assigned to the solution folder (Autopilot in this case). The cross-folder access fails with error 1100, "could not be accessed". Resolution required using the "Link from other folders" option to make the bucket visible to the Autopilot folder. Lossless, but it's another silent integration gap that only appears at runtime.

### 5. Agent input File-vs-Text type defaults are silently wrong for path references

The agent input arg `document_reference` was created via the agent UI. The default type rendered as a File upload (paperclip icon, drag-and-drop area) at debug time, even though the architecture intent is a string path reference. Inspecting the agent's Data Manager confirmed the type was File. Changing it to Text (= String) restored the expected path-string behavior. The agent UI defaults to File when the field name suggests a document, regardless of whether the architecture passes a reference or a payload.

### 6. Studio Web workflow Array[] cannot hold Object element types

When attempting to define `out_service_lines` as a typed Array of Object (matching the agent's nested array output), the `of` dropdown on the Array[] type only offers scalar element types (Text, Number, True or false, Number with decimal, Date, File). Selecting "Advanced types..." for the element type does work, and the Newtonsoft.Json.Linq `JArray` type from `Newtonsoft.Json.Linq` can be used as the entire argument type to hold a typed JSON array. This is the workable path, but the discoverability is poor: the basic type picker actively suggests the platform doesn't support what it actually does support behind one more click.

### 7. Agent-tool data contract requires manual field-by-field plumbing

Each DU-extracted field must be individually declared as a workflow output argument and assigned via a Set Variable Value activity. There is no schema-driven binding between DU output and agent structured outputs. A claims schema with N fields produces N output args and N assigns, regardless of whether DU and the agent could (in principle) share a schema definition. Refactoring schemas means updating both sides by hand. This is a real engineering cost at enterprise scale and a strong argument for a future schema-binding feature.

### 8. ExtractedField wrapper requires .Data.<Field>.Value access pattern

DU returns extracted fields wrapped in an `ExtractedField(Of T)` envelope that includes confidence metadata. Field values are accessed as `cascadeClaimDocumentData.Data.<FieldName>.Value` (not `cascadeClaimDocumentData.<FieldName>`). The intermediate `.Data` property is undocumented in the agent-tool integration guide; it was discovered via IntelliSense on the variable. Engineers building DU-backed tools need to know this pattern before they start. PascalCase naming convention applies to `<FieldName>`, not the snake_case used in the source schema.

### 9. Studio Web "Number" type label is ambiguous between Int32 and decimal

In the workflow's Data Manager Type dropdown, "Number" maps to Int32 (the Decimal icon `1.2` shown in the Variables list is misleading). Decimal-precision values require either "Number with decimal" (which exists in the workflow Type dropdown) or "Advanced types..." selecting `Decimal (System)`. In the agent's Data Manager Type dropdown, "Number with decimal" is not present, and "Number" appears to map to Int32 at compile time but works fine for decimal values at runtime. The compile-time error is misleading. This caused multiple debug cycles before the right type combination was discovered. Type discoverability across these surfaces is inconsistent; the same word means different things in different places, and the runtime behavior doesn't always match the compile-time complaint.

### 10. Separation of extraction vs inference between RPA tool and agent

Initial design attempted to have the workflow return all 12 fields including derived ones (confidence_score, needs_fallback, consistency_error). DU's `IDocumentData<V1CascadeClaimV1>` type does not contain these fields because they aren't extraction outputs; they're agent reasoning outputs. The compile error (`'ConfidenceScore' is not a member of 'V1CascadeClaimV1'`) was the right answer to the wrong design. Cleaner architecture: the tool returns only extracted facts, the agent computes derived/inferred fields per its system prompt. This is a useful design discipline worth codifying as a pattern guideline for agent-tool boundaries: tools deal in facts, agents deal in inferences.

---

## Autopilot observations

Two Autopilot moments occurred in this phase. Both worth capturing.

**First moment: workflow scaffolding from DU Publish page.** The "Open Studio Web" button generated a working DU integration workflow with the Extract Document Data activity correctly bound to the CascadeClaim project, version, and document type. Autopilot saved real time on this integration step. Where it produced a rejected pattern was the orchestration topology: a batch-demo For Each loop wrapped around the extraction, instead of a single-document call-and-return pattern. Net: helpful, but engineers must restructure the scaffold rather than use it as-is for agent-tool flows.

**Second moment: not used.** The agent's prompt iteration was authored manually rather than via Autopilot. Autopilot is available for prompt rewriting in the agent UI but was not exercised in this phase. May be useful for Phase 4 prompt tuning when adjudication logic is more complex.

---

## Reflection seeds added this phase

For the Week 3 1500-word strategic memo:

- **Tooling that lies vs tooling that misleads.** A compile error that says one thing while runtime does another is worse than no error at all. Engineers calibrate their mental model on the error messages they see, and inconsistent type-system disclosure across surfaces (workflow Data Manager vs agent Data Manager vs runtime) means even careful engineers will form wrong models.
- **Scaffolding is a contract, not a starting point.** When Autopilot generates a pattern, that pattern becomes the de facto architecture unless the engineer actively restructures. Pre-opinionated scaffolding has hidden cost: it shapes downstream design decisions in ways that aren't visible at scaffold-time.
- **The agent-tool boundary as a design discipline.** Tools deal in facts, agents deal in inferences. This separation emerged as a corrective during Phase 3 and is a useful axiom for any future agent-tool architecture: confidence scores, validation flags, and reasoning outputs belong to the agent. Extraction outputs belong to the tool. Crossing these boundaries causes compile errors and conceptual confusion equally.
