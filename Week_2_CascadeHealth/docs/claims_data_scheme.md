# Claims Test Data Scheme

**Project:** ClaimsIntake (Cascade Health)
**Phase:** 2 (DU setup)
**Author:** Chris Williams
**Pattern:** Mirrors Week 1's SSN-prefix-encodes-outcome approach. Here the claim ID prefix encodes the expected adjudication outcome, so any test run is self-labeling.

## Claim ID format

`CHC-PNNNNN` where `P` is the scenario prefix digit and `NNNNN` is a zero-padded sequence number within the scenario.

| Prefix | Scenario | Expected disposition | DU confidence target | Action Center? |
| ------ | -------- | -------------------- | -------------------- | -------------- |
| `1` | APPROVE | AUTO_APPROVE | High | No |
| `2` | DENY | AUTO_DENY | High | No |
| `3` | REVIEW | REVIEW (under $10K) | High | No, but flagged |
| `4` | ESCALATE | REVIEW (over $10K) | High | Yes, with SLA timer |
| `5` | LOW_CONFIDENCE | RPA fallback | Below threshold | No |
| `9` | BUSINESS_EXCEPTION | Hard fail | N/A | No |

## Scenario profiles

### CHC-1xxxxx — APPROVE

Routine, in-network, low-dollar claims with clean documentation. Office visits, basic labs, preventive care. CPT pool is the routine set (`99213`, `99214`, `99203`, `87880`, `85025`, `80053`, `90471`, `99396`, `36415`). ICD pool is common ambulatory diagnoses. Narrative consistently supports medical necessity within standard care guidelines. Charges typically under $500.

Agent 1 should extract cleanly with high confidence. Agent 2 should render APPROVE without invoking the MCP-Claude path because no edge-case judgment is required. End-to-end happy path.

### CHC-2xxxxx — DENY

Claims that fail clear policy rules. Cosmetic procedures, expired coverage, out-of-network without referral, non-covered services. CPT pool includes the denied set (`15823` blepharoplasty, `17380` electrolysis, `15876` lipectomy, `S9999` non-covered) plus realistic billed-but-excluded services. Narrative explicitly references the exclusion category.

Agent 1 extracts cleanly. Agent 2 renders DENY by rule lookup, not by judgment. Tests the deterministic-denial path.

### CHC-3xxxxx — REVIEW (under $10K)

Mid-dollar claims with ambiguous medical necessity. MRI without clear failed conservative therapy, off-label medication use, step-therapy edge cases, unusual diagnosis-code combinations. CPT pool is the moderate set. Narrative is the engineered-ambiguity set: each template presents a defensible case for coverage with a defensible counter-case.

This is the scenario where Agent 2's MCP-Claude path is exercised. Agent 2 invokes Claude for medical-necessity reasoning, gets a recommended disposition with rationale, and emits REVIEW. Routes to a non-blocking review queue, not Action Center, because dollar amount is below the SLA threshold.

### CHC-4xxxxx — ESCALATE (over $10K REVIEW)

Same ambiguity profile as CHC-3 but on high-dollar surgical or specialty-drug claims. CPT pool is the high-dollar set (`27447` knee replacement, `33533` CABG, `47562` lap chole, `63030` lumbar laminectomy, `J9035` bevacizumab, `19303` mastectomy). Narrative references administrative discrepancies (auth-to-site mismatch, ICD-to-auth mismatch, post-hoc emergency exceptions) layered over genuine clinical complexity.

End-to-end test of the SLA-driven escalation path. Agent 2 emits REVIEW, Maestro routes to Action Center because the claim exceeds the $10K threshold, SLA timer starts, human approver completes the form. This is the demo's primary happy-path-with-human-in-the-loop.

### CHC-5xxxxx — LOW_CONFIDENCE

Same scenario distribution as CHC-3 in terms of CPT and ICD profile, but with deliberately scrambled fields. The generator corrupts one of: date of birth (changes format and inserts question marks), provider NPI (substitutes a digit with `X`), or CPT code (truncates and adds `?`). The narrative is also degraded into spaced-out characters or vague boilerplate.

This is the demo's failure scenario. Agent 1 invokes Document Understanding, DU extraction confidence drops below the configured threshold, Maestro routes to the RPA fallback bot rather than to Agent 2. The bot creates a triage task in Orchestrator queue for manual review. The reflection writeup uses this scenario to discuss confidence-driven branching as a concrete instance of agentic-plus-deterministic hybrid orchestration.

### CHC-9xxxxx — BUSINESS_EXCEPTION (not in initial batch)

Reserved for hard-fail testing. PDF is missing a required field entirely (no patient ID, no provider NPI, no service line, or no narrative). DU returns extractions with critical fields null. Both Agents refuse to proceed, RPA fallback also fails preconditions, claim lands in the `Claims_Exceptions` Orchestrator queue.

Generated on demand when needed for exception-path testing.

## Initial batch composition

Forty PDFs span the five scenario families with this distribution:

- 14 APPROVE (CHC-100001 through CHC-100014)
- 10 DENY (CHC-200001 through CHC-200010)
- 7 REVIEW (CHC-300001 through CHC-300007)
- 5 ESCALATE (CHC-400001 through CHC-400005)
- 4 LOW_CONFIDENCE (CHC-500001 through CHC-500004)

Sized to clear DU Modern's 30-document minimum for extraction training with comfortable headroom for a held-out test set. The distribution roughly mirrors a realistic production mix where most claims are clearly approve or deny, fewer require review, and only a small fraction are high-dollar escalations or low-quality submissions.

Of the 40, the 36 clean ones (APPROVE, DENY, REVIEW, ESCALATE) get uploaded to DU for extraction training. The 4 LOW_CONFIDENCE PDFs are deliberately held back from training so DU does not learn to compensate for the corruption patterns. They are reserved for end-to-end testing of the confidence-driven RPA fallback path in Phase 5 and Phase 6.

## Field schema

Every PDF carries the same labeled fields in the same positions across all twenty documents. The Modern DU document type definition will train against this schema:

**Header**: claim ID, submission date, claim status, form revision

**Section 1 (Patient)**: member ID, last name, first name, sex, date of birth, phone, address, city, state, ZIP

**Section 2 (Policy)**: policy number, group number, relationship to insured, plan type

**Section 3 (Provider)**: NPI, tax ID/EIN, provider name, address, phone

**Section 4 (Service lines, 1 to 3 per claim)**: line number, date of service, place-of-service code, CPT, description, ICD-10, units, charges

**Section 5 (Totals)**: total charges, amount paid, balance due

**Section 6 (Narrative)**: free-text provider narrative and adjuster notes (multi-line)

**Section 7 (Authorization)**: provider signature, date

The narrative field is deliberately the only unstructured surface. Sections 1 through 5 and 7 are positionally consistent so DU's extraction confidence is high for the structured fields. The narrative is what Agent 1 hands to Agent 2 as judgment-bearing context.

## Regenerating the batch

The generator is deterministic per seed. Default seed is `20260429`. To produce a different batch:

```cmd
cd C:\Users\cwilliams\Documents\UiPath\ClaimsIntake\TestData
python generate_claims.py .
```

To change the batch composition or add an exception scenario, edit `INITIAL_BATCH` at the bottom of `generate_claims.py`. To change the random seed, pass `seed=` to `generate_batch()` directly (or modify the `seed` arg in the call inside `__main__`).

## Realism caveat

The test data has known clinical implausibilities, since the generator picks providers and services independently. A dermatology practice may bill for laparoscopic cholecystectomy, for example. This is acceptable: DU trains on field positions and Agents reason on structured values, not on whether a procedure makes specialty sense. If a future phase wants specialty-aware data, restructure `build_service_lines()` to filter `CPT_*` pools by `provider[5]` (the specialty tag).

## Phase 2 next steps

With the initial batch generated, the remaining Phase 2 work is:

1. Upload representative PDFs to the `ClaimsIntake_DU` project in DU Modern.
2. Define the `CascadeClaim` document type with the field schema above.
3. Label the fields on a training subset (8 to 10 documents).
4. Run DU's classification and extraction training.
5. Hold out 4 to 5 documents as a test set.
6. Verify extraction accuracy against the ground truth (which is, by construction, captured in the generator's data pools).

Phase 3 will then attach the trained DU document type to Agent 1 as a Tool.
