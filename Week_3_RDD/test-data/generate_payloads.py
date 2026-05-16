"""
Generate 25 loan + 25 claim sample email-body payloads for the RDD flow.

Each file contains JSON intended to be pasted into the body of the trigger
email. The Maestro 'Extract Payload' Script Task parses vars.response.Body
as JSON, so these files match that schema exactly.

Run from this folder:
    python3 generate_payloads.py

Outputs are written to sample_payloads/loan/ and sample_payloads/claim/.
Filenames encode the intended pipeline outcome so a demo operator can pick
a scenario by name without consulting a separate manifest.
"""

import json
from pathlib import Path

EMAIL = "c.williams101198@gmail.com"
OUT = Path(__file__).parent / "sample_payloads"
LOAN_DIR = OUT / "loan"
CLAIM_DIR = OUT / "claim"


def loan(name, dob, ssn, employment, income, debt, score, amount, purpose):
    return {
        "ApplicantName": name,
        "Email": EMAIL,
        "DateOfBirth": dob,
        "SSN": ssn,
        "EmploymentStatus": employment,
        "AnnualIncome": income,
        "MonthlyDebtPayments": debt,
        "CreditScore": score,
        "RequestedAmount": amount,
        "LoanPurpose": purpose,
    }


def claim(mid, mname, policy, doi, amount, coverage, provider, ctype, desc):
    return {
        "MemberID": mid,
        "MemberName": mname,
        "Email": EMAIL,
        "PolicyNumber": policy,
        "DateOfIncident": doi,
        "ClaimAmount": amount,
        "CoverageType": coverage,
        "ProviderName": provider,
        "ClaimType": ctype,
        "ClaimDescription": desc,
    }


LOAN_CASES = [
    # --- Auto-decline: credit floor (< 580) ---
    ("auto-decline-credit-540", loan(
        "Marcus Aldridge", "1988-03-12", "412-55-9821", "Employed",
        62000, 950, 540, 25000, "Debt Consolidation")),
    ("auto-decline-credit-560", loan(
        "Yvonne Castellanos", "1979-11-03", "318-66-2204", "Self-employed",
        48000, 720, 560, 8000, "Vehicle")),
    ("auto-decline-credit-520", loan(
        "Devon Mitchell", "1992-07-25", "604-77-1133", "Employed",
        55000, 1100, 520, 50000, "Home Improvement")),
    ("auto-decline-credit-575", loan(
        "Patricia Nguyen", "1985-02-14", "519-44-8866", "Employed",
        82000, 1500, 575, 100000, "Business")),
    ("auto-decline-credit-510", loan(
        "Howard Petrov", "1956-09-08", "227-33-5571", "Retired",
        34000, 600, 510, 5000, "Medical")),

    # --- Auto-decline: extreme LTI knockout ---
    ("auto-decline-lti-extreme", loan(
        "Janelle Brooks", "1996-05-19", "771-22-4408", "Employed",
        20000, 250, 690, 60000, "Debt Consolidation")),

    # --- Senior review: large amount, qualified credit ---
    ("escalate-senior-750k-clean", loan(
        "Theodore Whitman", "1972-08-30", "401-99-7754", "Employed",
        285000, 2400, 760, 750000, "Home Improvement")),
    ("escalate-senior-600k-business", loan(
        "Camille Okafor", "1968-12-04", "330-88-5519", "Self-employed",
        420000, 3100, 740, 600000, "Business")),
    ("escalate-senior-1200k-clean", loan(
        "Reginald Sato", "1965-04-22", "508-77-3328", "Employed",
        510000, 4200, 785, 1200000, "Home Improvement")),
    ("escalate-senior-550k-borderline", loan(
        "Maria Vasquez", "1981-10-17", "619-55-7790", "Employed",
        180000, 1800, 710, 550000, "Business")),

    # --- Manual review: middle band 580-719 ---
    ("manual-review-620-mid", loan(
        "Tyrell Andersson", "1989-06-11", "445-33-9120", "Employed",
        72000, 1300, 620, 35000, "Vehicle")),
    ("manual-review-660-selfemp", loan(
        "Selena Park", "1983-01-28", "201-66-4471", "Self-employed",
        95000, 1700, 660, 75000, "Business")),
    ("manual-review-685-large", loan(
        "Aaron Belmonte", "1976-09-15", "550-44-2289", "Employed",
        140000, 2600, 685, 150000, "Home Improvement")),
    ("manual-review-600-small", loan(
        "Renata Holloway", "1990-12-21", "118-77-9943", "Employed",
        58000, 1100, 600, 25000, "Debt Consolidation")),
    ("manual-review-650-moderate", loan(
        "Joaquin Reyes", "1978-04-09", "722-22-1166", "Employed",
        125000, 2200, 650, 200000, "Home Improvement")),

    # --- Auto-approve: clean (>= 720 + manageable amount) ---
    ("auto-approve-760-debt-consol", loan(
        "Naomi Fitzgerald", "1986-07-03", "311-88-4477", "Employed",
        88000, 950, 760, 8000, "Debt Consolidation")),
    ("auto-approve-790-vehicle", loan(
        "Ezekiel Tan", "1991-03-18", "624-55-7733", "Employed",
        76000, 700, 790, 5000, "Vehicle")),
    ("auto-approve-820-home-imp", loan(
        "Margot Diallo", "1982-11-26", "508-99-3344", "Employed",
        112000, 1100, 820, 10000, "Home Improvement")),
    ("auto-approve-750-education", loan(
        "Quinton Ramirez", "1993-08-14", "417-22-6680", "Employed",
        65000, 550, 750, 7500, "Education")),
    ("auto-approve-740-medical", loan(
        "Lillian Osei", "1980-05-07", "229-33-8851", "Employed",
        94000, 1200, 740, 9000, "Medical")),

    # --- Business exceptions: malformed / missing data ---
    ("business-exception-missing-credit", {
        "ApplicantName": "Hugo Marchetti",
        "Email": EMAIL,
        "DateOfBirth": "1987-02-19",
        "SSN": "302-44-7715",
        "EmploymentStatus": "Employed",
        "AnnualIncome": 70000,
        "MonthlyDebtPayments": 1100,
        # CreditScore intentionally omitted
        "RequestedAmount": 20000,
        "LoanPurpose": "Vehicle",
    }),
    ("business-exception-impossible-income", loan(
        "Sienna Whittaker", "1985-10-30", "806-11-2240", "Employed",
        -5000, 800, 700, 15000, "Debt Consolidation")),
    ("business-exception-malformed-ssn", loan(
        "Conrad Lindberg", "1979-06-23", "INVALID-SSN", "Employed",
        80000, 1200, 715, 25000, "Vehicle")),

    # --- Edge: high-income low-ask (clean auto-approve) ---
    ("auto-approve-high-income-low-ask", loan(
        "Beatrix Sterling", "1974-09-12", "611-77-4485", "Employed",
        340000, 1800, 800, 5000, "Vehicle")),

    # --- Edge: low-income low-ask (still passes LTI) ---
    ("auto-approve-low-income-low-ask", loan(
        "Felipe Andrade", "1995-01-08", "519-88-3367", "Employed",
        28000, 350, 730, 3000, "Vehicle")),
]


CLAIM_CASES = [
    # --- APPROVE: small, clean, in-coverage ---
    ("approve-outpatient-routine", claim(
        "M-1042-088", "Sarah Lindholm", "POL-MA-3320-B", "2026-04-02",
        350.00, "Outpatient", "Brookline Family Practice", "Medical",
        "Annual physical exam and routine bloodwork")),
    ("approve-prescription-generic", claim(
        "M-2208-441", "Darius Henley", "POL-PA-5519-A", "2026-04-18",
        120.00, "Prescription", "CVS Pharmacy #4421", "Medical",
        "90-day supply of generic lisinopril")),
    ("approve-dental-cleaning", claim(
        "M-3071-720", "Olivia Marchand", "POL-NY-7740-C", "2026-04-10",
        180.00, "Dental", "Midtown Dental Associates", "Dental",
        "Routine cleaning and exam, no cavities")),
    ("approve-vision-exam", claim(
        "M-4117-902", "Anand Subramaniam", "POL-CA-2233-A", "2026-04-25",
        85.00, "Vision", "ClearSight Optometry", "Vision",
        "Annual eye exam and prescription update")),
    ("approve-emergency-medical-necessity", claim(
        "M-5009-115", "Gabriella Romano", "POL-IL-8881-B", "2026-04-07",
        4500.00, "Emergency", "St. Anne's Memorial ER", "Medical",
        "ER visit for acute appendicitis, surgical consult")),

    # --- DENY: excluded, out-of-network, expired, missing docs ---
    ("deny-cosmetic-excluded", claim(
        "M-6233-440", "Vincent Caruso", "POL-FL-4419-A", "2026-03-30",
        8200.00, "Outpatient", "Coastal Aesthetics Clinic", "Medical",
        "Elective rhinoplasty for cosmetic enhancement")),
    ("deny-out-of-network", claim(
        "M-7188-205", "Adaeze Nwosu", "POL-TX-9907-C", "2026-04-12",
        12500.00, "Inpatient", "Pinnacle Orthopedic (out-of-network)",
        "Medical", "Knee replacement by non-network surgeon, no prior authorization")),
    ("deny-policy-expired", claim(
        "M-8240-377", "Bernard Olstad", "POL-OR-2218-A", "2026-04-20",
        2400.00, "Outpatient", "Willamette Internal Medicine", "Medical",
        "Office visit and labs; policy lapsed 2026-03-15")),
    ("deny-pre-existing-excluded", claim(
        "M-9302-661", "Imani Foster", "POL-GA-5503-B", "2026-04-05",
        6800.00, "Outpatient", "Atlanta Endocrinology Group", "Medical",
        "Type-1 diabetes management; condition pre-dates policy, exclusion applies")),
    ("deny-missing-documentation", claim(
        "M-1455-882", "Lukas Vandenberg", "POL-WA-7716-A", "2026-04-22",
        3200.00, "Outpatient", "Provider name not legible", "Medical",
        "Procedure unspecified; insufficient documentation submitted")),

    # --- REVIEW: large, complex, ambiguous medical necessity ---
    ("review-large-outpatient-25k", claim(
        "M-2566-103", "Priya Venkatesan", "POL-NJ-3340-A", "2026-04-08",
        25000.00, "Outpatient", "Princeton Imaging Center", "Medical",
        "Series of advanced PET/CT scans for oncology workup")),
    ("review-complex-inpatient-45k", claim(
        "M-3617-224", "Wesley Cartwright", "POL-OH-6628-B", "2026-04-15",
        45000.00, "Inpatient", "Cleveland Regional Medical", "Medical",
        "Multi-day admission, cardiac catheterization plus stent placement")),
    ("review-mental-health-intensive", claim(
        "M-4778-905", "Talia Brennan", "POL-MN-1109-A", "2026-04-03",
        15000.00, "Mental Health", "North Star Behavioral Health",
        "Mental Health", "Two-week intensive outpatient program for major depressive episode")),
    ("review-experimental-treatment", claim(
        "M-5889-516", "Renaldo Quintero", "POL-AZ-4427-C", "2026-04-19",
        30000.00, "Outpatient", "Desert Cancer Research Institute", "Medical",
        "Experimental immunotherapy infusion, off-label use of approved agent")),
    ("review-recurring-aggregate", claim(
        "M-6990-627", "Hannah Yablonski", "POL-CO-8814-A", "2026-04-14",
        20000.00, "Outpatient", "Rocky Mountain Pain Management", "Medical",
        "Sixth claim this quarter for chronic pain infusion series, utilization review flagged")),

    # --- Coverage variety: ensure all coverage types appear ---
    ("approve-inpatient-surgery", claim(
        "M-7011-738", "Cassius Mbeki", "POL-NC-2240-B", "2026-04-06",
        35000.00, "Inpatient", "Charlotte General Surgical", "Medical",
        "Elective gallbladder removal, 2-day inpatient stay")),
    ("approve-mental-health-therapy", claim(
        "M-8122-849", "Esperanza Aldama", "POL-NM-7728-A", "2026-04-11",
        2400.00, "Mental Health", "High Desert Counseling", "Mental Health",
        "12 weekly therapy sessions, anxiety disorder")),
    ("review-specialty-drug", claim(
        "M-9233-950", "Bartholomew Kinsey", "POL-MI-5519-C", "2026-04-13",
        8000.00, "Prescription", "Specialty Pharmacy Direct", "Medical",
        "Monthly Humira injection, prior authorization pending review")),
    ("approve-dental-implant", claim(
        "M-1344-061", "Jocelyn Mercier", "POL-LA-3306-A", "2026-04-09",
        4500.00, "Dental", "Bayou Implant Dentistry", "Dental",
        "Single posterior implant including crown")),
    ("approve-vision-corrective-surgery", claim(
        "M-2455-172", "Sebastien Halvorsen", "POL-WI-9923-B", "2026-04-17",
        3500.00, "Vision", "Lakeshore LASIK Center", "Vision",
        "Bilateral LASIK procedure")),
    ("approve-emergency-er", claim(
        "M-3566-283", "Anika Petrov", "POL-VA-4471-A", "2026-04-21",
        7800.00, "Emergency", "Tidewater Emergency Hospital", "Medical",
        "ER visit for severe allergic reaction with epinephrine administration")),
    ("approve-outpatient-pt", claim(
        "M-4677-394", "Magnus Olafsson", "POL-IA-6638-A", "2026-04-24",
        1200.00, "Outpatient", "Heartland Physical Therapy", "Medical",
        "8-session post-surgical knee rehabilitation series")),

    # --- Edge cases ---
    ("review-very-high-amount-250k", claim(
        "M-5788-405", "Constance Wright-Hamilton", "POL-NV-7706-A", "2026-04-16",
        250000.00, "Inpatient", "Las Vegas University Medical", "Medical",
        "Extended ICU stay for severe trauma, multiple surgeries and rehabilitation")),
    ("review-erisa-appeal", claim(
        "M-6899-516", "Demetrius Vasquez", "POL-OH-5512-B", "2026-04-04",
        18000.00, "Outpatient", "Buckeye Specialty Care", "Medical",
        "Formal ERISA Section 503 appeal of prior denial; claim resubmitted with additional supporting documentation")),
    ("review-dependent-different-name", claim(
        "M-7900-627", "Margaret Chen (dependent: Lucas Chen, age 12)",
        "POL-WA-2247-A", "2026-04-23", 5800.00, "Outpatient",
        "Seattle Children's Specialty Clinic", "Medical",
        "Pediatric specialist consultation for dependent child covered under member's plan")),
]


def main():
    LOAN_DIR.mkdir(parents=True, exist_ok=True)
    CLAIM_DIR.mkdir(parents=True, exist_ok=True)

    for i, (label, payload) in enumerate(LOAN_CASES, start=1):
        (LOAN_DIR / f"loan-{i:03d}-{label}.json").write_text(
            json.dumps(payload, indent=2) + "\n"
        )

    for i, (label, payload) in enumerate(CLAIM_CASES, start=1):
        (CLAIM_DIR / f"claim-{i:03d}-{label}.json").write_text(
            json.dumps(payload, indent=2) + "\n"
        )

    print(f"Wrote {len(LOAN_CASES)} loan + {len(CLAIM_CASES)} claim payloads to {OUT}")


if __name__ == "__main__":
    main()
