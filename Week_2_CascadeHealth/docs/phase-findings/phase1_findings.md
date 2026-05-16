# Phase 1 Findings — ClaimsIntake (Cascade Health)

**Date:** 2026-04-29
**Phase:** 1 (Foundations)
**Status:** Complete
**Author:** Chris Williams

This note captures what was verified, what was discovered, and what those discoveries mean for Phases 2 through 8. It is the source of record for the Phase 7 governance packet and the Week 3 reflection.

## Tooling verified

Document Understanding Modern is provisioned. A project named `ClaimsIntake_DU` was created in the Modern flavor. The Build, Measure, Publish, and Monitor lifecycle surfaces are present. AI Center is not enabled on this tenant; Modern DU does not require it for the semi-structured claim form scenario we have planned, so this is not a blocker.

UiPath Agents is provisioned. The Agents service opens directly into a registry view (Overview, Deployed agents, Draft agents, Templates, Guardrails, Context grounding indexes, Feedback) and the "Build your agent now" entry point launches Studio Web with a scaffolded autonomous agent project. Three agent types are offered at scaffolding time: Autonomous, Conversational, and Coded (Preview). Autonomous is the correct fit for both Agent 1 (Claim Intake) and Agent 2 (Adjudication) since both act independently on a structured task and emit a disposition.

The agent Definition canvas exposes three sockets on the Agent block: Escalations (top), Context (bottom-left), Tools (bottom-right). This shape maps cleanly to the locked architecture: Tools will hold DU extraction and policy lookup, Context will hold patient and policy grounding, Escalations will hold the Action Center handoff for high-dollar REVIEW dispositions. No architecture changes required.

Studio Web version observed in this session is consistent with the Week 1 Studio (26.x line). Available agent units on this tenant: 250 of 250.

The AI Trust Layer page exists at the org admin level. It contains Autopilot for Everyone configuration and Context Grounding configuration. Tenant scope: DefaultTenant. Version 26.3.1.

## Findings that change the build

### Finding 1: Claude is reached via Custom Model, not the native dropdown

The native model dropdown on the Agent Definition lists only `gpt-4o-2024-11-20 (OpenAI)` under "UiPath models" plus a "Use custom model" option. No Anthropic model is offered as a first-class entry in this tenant.

This is on-brief, not a workaround. The Week 2 brief explicitly requires connecting at least one agent to a non-UiPath model via an open standard. The MCP path is the open standard. Agent 2 (Adjudication) will register Claude as a custom model and reach it through MCP. This becomes a clean talking point in the reflection and the demo.

Action for Phase 4: configure Claude as a custom model on Agent 2. Anthropic API credentials will be stored as a UiPath Connection (Connections is a first-class node in the Solution Explorer) rather than hard-coded.

### Finding 2: Guardrails are not entitled on this tenant

The Definition right-rail shows: "You are not entitled to use guardrails. Click here to learn more." The Guardrails left-nav item exists in the Agents service registry view but is gated by license.

Implication for the Trust Layer story: the governance packet cannot lean on a turnkey Guardrails toggle. It has to be assembled from primitives. This is actually a stronger story than "we enabled the feature flag." The reflection can speak credibly to the realities of enterprise rollout, where governance is composed rather than purchased.

The composed Trust Layer for this project consists of: Evaluators and Evaluation Sets configured on each agent project, Studio's per-agent Execution Trail capturing prompts and tool calls and decisions, Orchestrator job and queue logs for the RPA fallback path, the Autopilot for Everyone admin controls (this is policy-level, not run-level), Context Grounding configuration at the tenant level, and four hand-authored governance documents living in this Docs folder: Prompt Register, Model Inventory, Escalation Matrix, and Audit Trail Sample.

### Finding 3: AI Trust Layer admin page is policy, not audit

The page reachable from the waffle menu under "AI Trust Layer" is an admin surface for Autopilot for Everyone. It controls what data Autopilots use, what tools they can call, and tenant-level Context Grounding behavior. It is not a prompt log viewer, not a model call audit dashboard, not a single-pane governance console. Advanced settings on the page expose roughly 20 toggles for Autopilot UX behavior (idle exit, file upload, system prompt hints, suggested prompts, chat history, max pre-response actions, feedback routing, color theme, maintenance mode, and so on). None of those toggles produce audit artifacts.

Implication: the actual audit trail for the governance packet must be assembled from Execution Trail captures and Orchestrator logs. Phase 7 will export representative traces from a successful run, a failure run, and an Action Center escalation run, then redact and format them as the Audit Trail Sample.

## Architecture deltas locked in

Architecture remains as designed at Phase 0. The findings above did not require structural changes; they specified how some pieces are realized:

Two autonomous agents in UiPath Agent Builder: Claim Intake and Adjudication.

Maestro orchestrates: claim arrives, Agent 1 extracts and validates, branch on confidence to either Agent 2 or RPA fallback, Agent 2 renders APPROVE or DENY or REVIEW, branch on disposition and dollar amount to either auto-action or Action Center.

Document Understanding Modern is the extraction engine for Agent 1, exposed to the agent as a Tool.

Claude is reached by Agent 2 via MCP, registered as a custom model. The MCP server is configured on the Connections node of the agent project.

Action Center handles human-in-the-loop for any claim above $10,000 with a REVIEW disposition. The form is authored in Studio's Form Designer (carrying the Week 1 lesson that hand-written form JSON parses but fails activity validation).

The RPA fallback bot from Phase 6 reuses Week 1 patterns: REFramework shell, queue-driven, the same Library NuGet pattern.

The Trust Layer is composed: Evaluators plus Eval Sets plus Execution Trail plus Orchestrator logs plus four hand-authored governance documents.

## What is deferred

Sample claim PDFs do not exist yet. Phase 2 will generate them as part of DU document type training.

The custom-model registration for Claude is not configured. Phase 4 work.

The MCP server endpoint for Claude is not configured. Phase 4 work.

The Anthropic API credentials are not stored as a UiPath Connection. Phase 4 work, gated on having an Anthropic API key available in the workspace.

No agents have been published. The "_scratch_verify" project from Step 1.3 is a draft and will be deleted once Phase 3 begins, to keep the Draft agents pane clean.

## Reflection seeds

Three threads from Phase 1 worth carrying into the 1500-word reflection.

First, the gap between marketing surface and operational surface. The brief says "AI Trust Layer" as if it is a product. What you actually find when you click the menu is a policy admin page for a different product (Autopilot for Everyone). The Trust Layer in practice is a posture you assemble from primitives, not a console you log into. That is worth naming.

Second, the open-standard requirement is satisfied by a constraint, not a choice. Claude is not in the native dropdown, which forces the MCP integration path. That happens to be the right answer; the brief asks for it. But the architecture is shaped by what the platform offers natively as much as by the brief.

Third, license entitlements meaningfully shape what governance looks like. Guardrails being gated means the governance packet is heavier on hand-authored documents and lighter on platform-native artifacts. A real CRO conversation about adopting this stack would have to weigh those entitlements explicitly.

## Phase 1 exit checklist

DU Modern project created and accessible: yes.
Agents service accessible and autonomous agent scaffolds correctly: yes.
Studio Web Definition canvas surfaces Model, User Prompt, Tools, Context, Escalations, Evaluators, Eval Sets, I/O Schema: yes.
AI Trust Layer admin page reachable: yes.
Native Anthropic model option present: no. Custom Model path confirmed available.
Guardrails entitlement: no. Compensating Trust Layer composition documented above.
Phase 2 prerequisites understood and unblocked: yes.

Phase 2 begins with sample claim PDF generation, then DU document type definition, then extraction training.
