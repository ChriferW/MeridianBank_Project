# Phase 4 Findings — AdjudicationAgent with Claude Second-Opinion Integration

**Project:** Cascade Health Claims Adjudication
**Phase:** 4 of 8 (Week 2)
**Author:** Chris Williams
**Date:** April 30, 2026
**Status:** Complete

---

## Objective

Build a second autonomous agent (`AdjudicationAgent`) that consumes the structured claim payload produced by `ClaimIntakeAgent` (Phase 3) and renders a disposition decision with reasoning. The agent must apply policy-based rules deterministically while reserving the ability to escalate diagnostically ambiguous cases to a specialized model. The architectural goal: demonstrate a multi-LLM agent pattern where a primary model (gpt-4o) handles routine adjudication and a secondary model (Claude Sonnet 4.6) is consulted as a tool on edge cases.

---

## What Was Built

### 1. AdjudicationAgent shell

Created in the same Solution as ClaimIntakeAgent. Autonomous agent type. Primary model gpt-4o-2024-11-20 (the only OpenAI model UiPath's native dropdown exposes).

Twelve input variables matching ClaimIntakeAgent's twelve outputs structurally: `claim_id`, `member_id`, `date_of_birth`, `policy_number`, `provider_npi`, `provider_name`, `total_charges`, `provider_narrative`, `service_lines` (Array of objects), `confidence_score`, `needs_fallback`, `consistency_error`. The downstream-upstream shape match is intentional and lets Maestro pipe one agent's output into the next without translation logic.

Four output variables capturing the adjudication decision: `disposition` (Text, one of APPROVE/DENY/REVIEW/ESCALATE), `escalation_required` (Yes/No), `reasoning` (Text, free-form rationale), and `service_line_assessments` (Array of objects with cpt_code, icd10_code, medically_necessary three-state Text, and justification).

### 2. System prompt with five hard rules

The prompt establishes role (claims adjudicator for Cascade Health) and enforces:

1. **Extraction quality gates.** If `needs_fallback=true` or `consistency_error=true` from upstream, disposition must be ESCALATE regardless of medical content. The agent does not adjudicate on data the intake layer flagged as unreliable.
2. **Medical necessity reasoning.** Each service line must be evaluated for CPT/ICD-10 alignment. The agent reasons through whether the procedure is medically necessary given the diagnosis.
3. **Policy-based decisioning.** The agent applies a small set of inline policy rules (cosmetic exclusions, pre-authorization requirements, emergency exceptions). No invented policies.
4. **Escalation thresholds.** Any claim over $50,000 escalates regardless of disposition. REVIEW disposition over $10,000 escalates. Both populate `escalation_required=true`.
5. **No policy invention.** If a situation isn't covered by stated rules, disposition is REVIEW with reasoning that names the gap.

A sixth instruction was added after Step 4.6 to govern when the agent should invoke the Claude second-opinion tool (see below).

### 3. Claude integration via Integration Service connector

This was the most architecturally interesting decision in Phase 4 and warrants explanation.

**The handoff document anticipated MCP-based integration.** UiPath publishes "MCP Servers" in its Orchestrator UI and the assumption was that an external MCP endpoint (Anthropic's Claude API exposed via MCP) could be registered and consumed by the agent.

**That is not how UiPath's MCP architecture works.** UiPath publishes its own automations and agents *as* MCP servers for external consumption. It is the producer side of the MCP protocol, not the consumer side. There is no native "register an external MCP endpoint" flow in the product as of this date.

**The actual integration path is the Integration Service connector marketplace.** Anthropic ships an official UiPath connector ("Anthropic Claude") which exposes two activities: Generate Message and HTTP Request. These are added to the agent's Tools socket as Activity-typed tools, with the connector handling auth, retries, and request shaping.

**Configuration steps:**

- Procured API key from Anthropic Console, named `health-adjucation-key` (typo preserved as artifact)
- Created Anthropic Claude connection in UiPath Orchestrator → Connections, scoped to both My Workspace and Autopilot folder (the latter via a separate connection creation rather than cross-folder linking, which the connector does not expose)
- Added Generate Message activity as a tool on AdjudicationAgent's Tools socket
- Renamed the tool to "Medical Necessity Second Opinion" with a detailed description specifying *when* the agent should invoke it (CPT/ICD-10 misalignment, complex multi-procedure scenarios, REVIEW disposition validation)
- Configured model `claude-sonnet-4-6`, temperature 0.3 (deterministic medical reasoning), max tokens 2048
- Authored a parameterized prompt template injecting claim details and the primary adjudicator's initial assessment, asking Claude for an independent medical-necessity perspective and disposition recommendation

The Generate Message activity exhibited a default-fill bug: System prompt, Temperature, Top P, and Top K fields were pre-populated with the literal placeholder string `{{prompt}}`. The Health Analyzer flagged these as type errors before runtime. Cleared the unwanted fields and set Temperature to a real value.

### 4. Agent system prompt updated for tool usage

Added a paragraph instructing the agent to invoke the Medical Necessity Second Opinion tool only on edge cases, with explicit don't-call-this-tool criteria (routine claims with clear CPT/ICD-10 alignment, obvious policy exclusions, claims that fail rule 1). The intent: keep Claude calls focused on the cases where its specialized reasoning materially changes the outcome, not as a default consultation on every claim.

---

## Testing

Three test cases were run against the configured agent.

### Test 1: CHC-100001 (routine APPROVE)

Standard preventive care visit, single service line with aligned CPT/ICD-10, charges under $1,000.

**Expected behavior:** APPROVE, no escalation, no Claude consultation (clearly routine).

**Result:** disposition=APPROVE, escalation_required=false. Execution Trail showed two LLM calls and zero tool calls. Agent correctly identified this as routine and did not invoke Claude. Tool description criteria worked.

### Test 2: CHC-200001 (cosmetic DENY)

Cosmetic procedure (rhinoplasty for non-functional reasons), explicit policy exclusion.

**Expected behavior:** DENY, no escalation, no Claude consultation (clear exclusion).

**Result:** disposition=DENY, escalation_required=false. Execution Trail again showed no tool call. Agent applied the cosmetic exclusion policy directly and did not waste a Claude call on an unambiguous case.

### Test 3: CHC-400002 (high-cost ambiguous)

Two service lines totaling $108,430. The CPT codes are major surgical procedures (33533 = coronary artery bypass; 27447 = total knee arthroplasty). The ICD-10 codes (M17.0 = bilateral knee osteoarthritis; K80.20 = gallstones) are *cross-matched* with the procedures: the bypass is paired with the knee diagnosis, and the knee replacement is paired with the gallstone diagnosis. Each procedure is paired with the *other* procedure's plausible diagnosis.

**Expected behavior:** Agent invokes Claude due to CPT/ICD-10 misalignment AND high-cost trigger. Claude provides specialized assessment. Final disposition reflects both perspectives.

**Result:**

Execution Trail showed the expected three-step sequence:

```
Agent run - AdjudicationAgent (19.29s)
  ├── LLM call - gpt-4o-2024-11-20 (5.80s)
  ├── Tool call - Medical_Necessity_Second_Opinion (10.26s)
  │     └── Generate Message - claude-sonnet-4-6 (10.14s)
  ├── LLM call - gpt-4o-2024-11-20 (2.73s)
  └── Agent output
```

The agent autonomously decided to invoke Claude based on the tool description criteria. It did not need explicit instruction to call the tool on this specific claim.

Claude's response materially changed the disposition. The primary adjudicator (gpt-4o) had assessed the case as REVIEW: "the medical necessity is unclear based on the provided diagnosis codes, requires further medical officer judgment." Claude's independent assessment went further. It identified the cross-matched pattern explicitly, classified both pairings as NOT MEDICALLY NECESSARY with one-sentence justifications, and recommended DENY with a fraud/integrity flag. The systematic nature of the mismatch (every procedure paired with the wrong diagnosis) was, in Claude's words, "diagnostically incoherent and suggests a coding error or claim integrity issue."

The final agent output incorporated this:

```json
{
  "disposition": "DENY",
  "escalation_required": true,
  "reasoning": "The claim involves high-cost procedures with diagnosis-procedure pairings that are diagnostically incoherent and suggest a coding error. A second opinion confirmed that the pairings are not medically necessary and recommended denial due to lack of clinical justification. The claim should be returned to the provider for corrected coding and documentation.",
  "service_line_assessments": [
    {"cpt_code": "33533", "icd10_code": "M17.0", "medically_necessary": "false",
     "justification": "Coronary artery bypass grafting has no established clinical relationship to bilateral knee osteoarthritis; this pairing is diagnostically incoherent."},
    {"cpt_code": "27447", "icd10_code": "K80.20", "medically_necessary": "false",
     "justification": "Total knee replacement is not indicated for cholelithiasis; this pairing is diagnostically incoherent."}
  ]
}
```

The disposition shifted from REVIEW to DENY because Claude reframed the case from "ambiguous medical necessity" to "billing/coding error." This is exactly the value-add the multi-LLM architecture was designed to capture.

---

## Governance Threads (Phase 4 additions)

The following threads extend the catalog established in Phases 1-3 and will feed the Phase 7 governance packet.

### Thread 17: UiPath MCP architecture is inverted from common assumption

Practitioners coming from MCP-aware contexts assume MCP-based integration means consuming external MCP endpoints. UiPath's MCP support is the inverse: it publishes UiPath automations and agents as MCP servers for consumption by external clients (including Claude Desktop, Claude Code, etc.). There is no native flow for registering an external MCP endpoint as an agent tool. Anthropic integration runs through the Integration Service connector marketplace instead. This is not documented prominently and surfaced only when attempting to wire Claude as a tool. Implication for governance: the integration choice (connector vs MCP vs direct API) should be a documented architectural decision, not a default; and the MCP terminology in product naming is a source of practitioner confusion that should be flagged in onboarding.

### Thread 18: Generate Message activity has a default-fill bug

The Anthropic Claude connector's Generate Message activity pre-populates the System prompt, Temperature, Top P, and Top K fields with the literal string `{{prompt}}`, which is the placeholder syntax for variable interpolation. At runtime these would either error (Temperature is a number field) or silently corrupt the request (System prompt would send "{{prompt}}" as a literal string to Claude). The Health Analyzer caught these before debug, but a less-defensive practitioner could push to Production with broken defaults. Implication for governance: connector activities have edge-case defaults that the governance review should explicitly inspect, and the Health Analyzer is a critical pre-deploy gate that should be required green before any publish.

### Thread 19: Agent creation flow does not surface solution association

When creating a new agent, the UI defaults to creating a fresh empty Solution rather than attaching to the current one. The first AdjudicationAgent attempt landed in a separate Solution, requiring deletion and recreation through the in-Solution path (right-click on Solution explorer → New Agent). This is a workflow trap: practitioners creating multiple agents intended to compose into a single Solution must explicitly navigate the Solution context, and the default behavior runs counter to that intent. Implication for governance: Solution membership is a deployment unit, and the creation-flow ambiguity should be addressed by documentation or, ideally, by changing the default to associate-with-current-solution when the user is already inside one.

### Thread 20: Claude Sonnet 4.6 materially outperforms gpt-4o on diagnostically incoherent claims

The CHC-400002 test case is the empirical anchor. gpt-4o alone classified the cross-matched procedure-diagnosis pairings as "ambiguous" and routed to REVIEW. Claude Sonnet 4.6, given the same input plus the primary adjudicator's reasoning, identified the systematic nature of the mismatch (each procedure paired with the *other* procedure's plausible diagnosis), classified the pattern as a billing/coding error, and recommended DENY with a fraud/integrity flag. The pattern recognition is qualitatively different. gpt-4o saw "two pairings that don't quite fit." Claude saw "two pairings that are systematically swapped, which is a signature of a specific failure mode." This is the case for the multi-LLM second-opinion architecture: not because Claude is universally better, but because specialized reasoning on edge cases catches patterns the primary model misses, and the cost (one extra Claude call on ~10% of claims) is small relative to the downstream cost of misrouting a fraud-flagged claim to manual REVIEW.

---

## Reflection seeds (for Week 3 memo)

1. **Multi-LLM agent architecture is a real pattern, not a buzzword.** A primary model handles the bulk of routine work cheaply, and a specialized model is invoked on edge cases via tool-calling. This produces materially better outcomes than single-LLM and is cheaper than running every case through the more capable model. The Phase 4 evidence is concrete: gpt-4o said REVIEW, gpt-4o + Claude said DENY with fraud flag.

2. **Tool descriptions are governance surface.** The instruction to the agent about *when* to call Claude is a governance artifact. It encodes business policy ("when do we want a second opinion?"). It is editable text, version-controllable, and review-friendly. This is a healthier place for that policy than buried logic in a script.

3. **Vendor-neutral integration matters.** The connector-based path to Claude works the same way the connector-based path to Salesforce or Slack works. The agent doesn't know it's calling a different vendor's LLM than its primary. This is exactly the architectural property that makes vendor lock-in less acute than the marketing-level rhetoric of any single platform suggests, but it's only true because the practitioner went through the connector marketplace rather than building a bespoke API integration.

4. **Tooling that misleads vs tooling that lies.** The Generate Message default-fill bug (Thread 18) is in the "tooling that misleads" category: the field appears configured (it has a value!) but the value is wrong. Compare to the Studio Web Number type label ambiguity from Phase 3 (Thread 15), which was tooling that lies (the type label "Number" claimed Int32 at compile time but accepted decimals at runtime). Both produce silent failures. Governance review needs to be calibrated to catch both.

---

## Status

Phase 4 complete. Both agents built and tested. ClaimIntakeAgent extracts and validates; AdjudicationAgent decides with optional Claude consultation on edge cases. The two-agent pipeline has been validated end-to-end with shared input shape.

Neither agent has been published yet. Publishing happens at the end of Phase 4 (now) or the start of Phase 5, in which Maestro will orchestrate them into a single inbound-claim → final-disposition pipeline.

---

## Next: Phase 5 — Maestro orchestration

Compose ClaimIntakeAgent and AdjudicationAgent into a single Maestro process triggered by an inbound claim (file drop or email), with routing logic for the four disposition outcomes (APPROVE → payment queue, DENY → notification, REVIEW → Action Center, ESCALATE → fallback bot).
