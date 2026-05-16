# RDD sample email-body payloads

50 JSON payloads designed to exercise every branch of the RDD pipeline.
Each file matches the shape that `Extract Payload` (Maestro Script Task)
parses out of the trigger email body.

To run a scenario: paste the file's contents as the body of an email sent
to the inbox the RDD flow listens on. The Document Classification Agent
classifies it as a loan or claim and routes accordingly.

All payloads use `c.williams101198@gmail.com` as the recipient address per
the P13 fallback decision — sample applicants/members are fictional and
their emails are not used.

## Loan (`loan/` — 25 files)

Filenames encode the intended ladder outcome. Distribution maps to the
real-bank deterministic ladder (knockouts first, escalation last):

| Count | Outcome / pattern | Files |
|------:|---|---|
| 5 | Auto-decline — credit floor (< 580) | `loan-001` through `loan-005` |
| 1 | Auto-decline — extreme LTI knockout | `loan-006` |
| 4 | Escalate senior review — large amount, qualified credit | `loan-007` through `loan-010` |
| 5 | Manual review — middle band 580–719 | `loan-011` through `loan-015` |
| 5 | Auto-approve — clean (≥ 720, manageable amount) | `loan-016` through `loan-020` |
| 3 | Business exception — missing / malformed input | `loan-021` through `loan-023` |
| 2 | Auto-approve edge cases (high-income/low-ask, low-income/low-ask) | `loan-024`, `loan-025` |

## Claim (`claim/` — 25 files)

| Count | Outcome / pattern | Files |
|------:|---|---|
| 5 | APPROVE — small amount, in-coverage, clean | `claim-001` through `claim-005` |
| 5 | DENY — excluded, out-of-network, expired, missing docs | `claim-006` through `claim-010` |
| 5 | REVIEW — large, complex, ambiguous medical necessity | `claim-011` through `claim-015` |
| 7 | Coverage variety (Inpatient / MH / Rx / Dental / Vision / ER / Outpatient PT) | `claim-016` through `claim-022` |
| 3 | Edge cases — very large amount, ERISA appeal, dependent | `claim-023` through `claim-025` |

## Schemas

**Loan body:**
```json
{
  "ApplicantName": "string",
  "Email": "string",
  "DateOfBirth": "YYYY-MM-DD",
  "SSN": "XXX-XX-XXXX",
  "EmploymentStatus": "Employed | Self-employed | Retired | Unemployed",
  "AnnualIncome": "number",
  "MonthlyDebtPayments": "number",
  "CreditScore": "integer",
  "RequestedAmount": "number",
  "LoanPurpose": "Home Improvement | Debt Consolidation | Vehicle | Education | Business | Medical"
}
```

**Claim body:**
```json
{
  "MemberID": "M-XXXX-XXX",
  "MemberName": "string",
  "Email": "string",
  "PolicyNumber": "POL-XX-XXXX-X",
  "DateOfIncident": "YYYY-MM-DD",
  "ClaimAmount": "number",
  "CoverageType": "Inpatient | Outpatient | Emergency | Mental Health | Prescription | Dental | Vision",
  "ProviderName": "string",
  "ClaimType": "Medical | Dental | Vision | Mental Health",
  "ClaimDescription": "string"
}
```

## Regenerating

```bash
cd Week_3_RDD/test-data
python3 generate_payloads.py
```

Edit `generate_payloads.py` to add or modify cases — the source of truth
for what each file contains lives in that script's `LOAN_CASES` and
`CLAIM_CASES` lists.
