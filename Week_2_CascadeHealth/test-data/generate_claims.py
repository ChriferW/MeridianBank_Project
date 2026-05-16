"""
Cascade Health claim PDF generator.

Generates semi-structured claim form PDFs with consistent field layout for
UiPath Document Understanding Modern training. Field VALUES vary across PDFs;
field LABELS and POSITIONS stay constant so DU can learn the schema.

Test data scheme uses claim ID prefix to encode expected outcome:
  CHC-1xxxxx  AUTO_APPROVE  routine, in-network, low-dollar
  CHC-2xxxxx  DENY          policy exclusion, expired coverage, cosmetic
  CHC-3xxxxx  REVIEW        ambiguous medical necessity, mid-dollar
  CHC-4xxxxx  ESCALATE      high-dollar (>$10K) with REVIEW disposition
  CHC-5xxxxx  LOW_CONFIDENCE deliberately scrambled fields, triggers RPA fallback
  CHC-9xxxxx  BUSINESS_EXCEPTION missing required fields entirely

Run: python generate_claims.py [output_dir]
"""

import os
import sys
import random
from datetime import date, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Page geometry
PAGE_W, PAGE_H = letter  # 612 x 792 points
MARGIN_L = 0.6 * inch
MARGIN_R = PAGE_W - 0.6 * inch
MARGIN_T = PAGE_H - 0.6 * inch
USABLE_W = MARGIN_R - MARGIN_L

# ---------------------------------------------------------------------------
# Reference data pools
# ---------------------------------------------------------------------------

PATIENTS = [
    ("Mitchell", "Sarah", "1978-03-15", "F", "142 Elm Street, Apt 3B", "Providence", "RI", "02906", "(401) 555-0142"),
    ("Chen", "James", "1985-11-22", "M", "88 Hope Street", "Providence", "RI", "02906", "(401) 555-0188"),
    ("Rodriguez", "Michael", "1990-07-04", "M", "215 Wickenden Street", "Providence", "RI", "02903", "(401) 555-0215"),
    ("Williams", "Patricia", "1962-09-30", "F", "47 Benefit Street", "Providence", "RI", "02904", "(401) 555-0047"),
    ("Hayes", "Robert", "1955-01-18", "M", "1200 Smith Street", "Providence", "RI", "02908", "(401) 555-1200"),
    ("Park", "Jennifer", "1992-05-12", "F", "67 Atwells Avenue", "Providence", "RI", "02903", "(401) 555-0067"),
    ("Davis", "Thomas", "1971-12-08", "M", "334 Broadway", "Providence", "RI", "02909", "(401) 555-0334"),
    ("Garcia", "Maria", "1988-04-25", "F", "522 Westminster Street", "Providence", "RI", "02903", "(401) 555-0522"),
    ("Singh", "Rajesh", "1980-08-14", "M", "19 Power Street", "Providence", "RI", "02906", "(401) 555-0019"),
    ("Anderson", "Linda", "1965-02-28", "F", "780 Cranston Street", "Providence", "RI", "02907", "(401) 555-0780"),
    ("O'Brien", "Patrick", "1973-10-17", "M", "245 Thayer Street", "Providence", "RI", "02906", "(401) 555-0245"),
    ("Nakamura", "Yuki", "1994-06-21", "F", "112 Federal Hill Avenue", "Providence", "RI", "02903", "(401) 555-0112"),
    ("Brown", "Marcus", "1959-11-09", "M", "456 Pawtucket Avenue", "Pawtucket", "RI", "02860", "(401) 555-0456"),
    ("Foster", "Emily", "1983-03-30", "F", "78 Angell Street", "Providence", "RI", "02906", "(401) 555-0078"),
    ("Kowalski", "Adam", "1968-07-13", "M", "910 Reservoir Avenue", "Cranston", "RI", "02910", "(401) 555-0910"),
    ("Martinez", "Sofia", "1991-09-04", "F", "33 Hope Street", "Providence", "RI", "02906", "(401) 555-0033"),
    ("Wright", "Daniel", "1976-12-19", "M", "609 Smith Street", "Providence", "RI", "02908", "(401) 555-0609"),
    ("Thompson", "Karen", "1960-04-08", "F", "21 Cooke Street", "Providence", "RI", "02906", "(401) 555-0021"),
    ("Patel", "Anjali", "1987-08-26", "F", "155 Brook Street", "Providence", "RI", "02906", "(401) 555-0155"),
    ("Murphy", "Sean", "1982-01-11", "M", "344 Olney Street", "Providence", "RI", "02906", "(401) 555-0344"),
]

PROVIDERS = [
    ("1487293042", "Brown Family Medicine", "22-5849371", "300 Wickenden Street, Providence, RI 02903", "(401) 555-7700", "primary"),
    ("1592847163", "Rhode Island Cardiology Associates", "22-4738291", "120 Dudley Street, Providence, RI 02905", "(401) 555-3120", "cardiology"),
    ("1734829562", "Newport Orthopedic Specialists", "22-9182736", "55 Memorial Boulevard, Newport, RI 02840", "(401) 555-5500", "orthopedic"),
    ("1283746591", "Coastal Dermatology", "22-3849217", "789 Reservoir Avenue, Cranston, RI 02910", "(401) 555-7890", "dermatology"),
    ("1948372615", "Providence Diagnostic Imaging", "22-6172839", "180 Plain Street, Providence, RI 02905", "(401) 555-1800", "radiology"),
    ("1659384720", "Wayland Square Internal Medicine", "22-7263849", "240 Wayland Avenue, Providence, RI 02906", "(401) 555-2400", "internal"),
    ("1837465920", "Hope Mental Health Associates", "22-8374615", "67 Hope Street, Providence, RI 02906", "(401) 555-0670", "behavioral"),
    ("1726384951", "East Side Pediatrics", "22-1928374", "412 Wickenden Street, Providence, RI 02903", "(401) 555-4120", "pediatric"),
    ("1573829461", "Bay State Surgical Center", "22-5638294", "850 Reservoir Avenue, Cranston, RI 02910", "(401) 555-8500", "surgical"),
    ("1462738591", "Ocean State Oncology", "22-4729183", "445 Plainfield Street, Providence, RI 02909", "(401) 555-4450", "oncology"),
]

# CPT pools by claim profile
CPT_LOW = [
    ("99213", "Office visit established patient low complexity", 145.00),
    ("99214", "Office visit established patient moderate complexity", 215.00),
    ("99203", "Office visit new patient low complexity", 195.00),
    ("87880", "Strep A test immunoassay", 42.00),
    ("85025", "Complete blood count with differential", 38.00),
    ("80053", "Comprehensive metabolic panel", 52.00),
    ("90471", "Immunization administration", 28.00),
    ("99396", "Preventive visit established patient adult", 285.00),
    ("36415", "Routine venipuncture", 18.00),
]

CPT_MID = [
    ("73721", "MRI lower extremity joint without contrast", 1850.00),
    ("70553", "MRI brain with and without contrast", 2400.00),
    ("93306", "Echocardiography complete with Doppler", 950.00),
    ("45378", "Diagnostic colonoscopy", 1650.00),
    ("29881", "Arthroscopy knee with meniscectomy", 4200.00),
    ("90837", "Psychotherapy 60 minutes", 235.00),
    ("99285", "Emergency department visit high complexity", 1875.00),
    ("11042", "Debridement subcutaneous tissue", 320.00),
]

CPT_HIGH = [
    ("27447", "Total knee arthroplasty", 38500.00),
    ("33533", "Coronary artery bypass single arterial graft", 62000.00),
    ("47562", "Laparoscopic cholecystectomy", 14800.00),
    ("63030", "Lumbar laminectomy single interspace", 22500.00),
    ("J9035", "Bevacizumab injection 10 mg oncology", 12400.00),
    ("19303", "Mastectomy simple complete", 18200.00),
]

CPT_DENIED = [
    ("15823", "Blepharoplasty upper eyelid", 3200.00),
    ("17380", "Electrolysis hair removal", 450.00),
    ("15876", "Suction-assisted lipectomy", 4800.00),
    ("S9999", "Non-covered service", 1200.00),
]

ICD_LOW = [
    ("J06.9", "Acute upper respiratory infection unspecified"),
    ("Z00.00", "General adult medical exam no abnormal findings"),
    ("I10", "Essential hypertension"),
    ("E78.5", "Hyperlipidemia unspecified"),
    ("M54.5", "Low back pain"),
    ("J45.909", "Asthma unspecified uncomplicated"),
    ("E11.9", "Type 2 diabetes without complications"),
]

ICD_MID = [
    ("M17.11", "Osteoarthritis right knee"),
    ("S83.241A", "Bucket-handle tear right meniscus initial"),
    ("R07.9", "Chest pain unspecified"),
    ("F33.1", "Major depressive disorder recurrent moderate"),
    ("R10.9", "Abdominal pain unspecified"),
    ("G43.909", "Migraine unspecified not intractable"),
]

ICD_HIGH = [
    ("M17.0", "Bilateral primary osteoarthritis of knee"),
    ("I25.10", "Atherosclerotic heart disease native coronary"),
    ("C50.911", "Malignant neoplasm right female breast"),
    ("M48.06", "Spinal stenosis lumbar region"),
    ("K80.20", "Calculus of gallbladder without obstruction"),
]

ICD_DENIED = [
    ("H02.401", "Unspecified ptosis right eyelid"),
    ("L65.9", "Nonscarring hair loss unspecified"),
    ("Z41.1", "Encounter for cosmetic surgery"),
]

# Narratives shape Agent 1's judgment surface. Each scenario family ships with
# 3-5 narrative templates that an Adjudication Agent could plausibly disagree on.
NARRATIVES = {
    "APPROVE": [
        "Patient presented with documented symptoms consistent with diagnosis. Standard evaluation and management performed within established care plan. No prior authorization required for these services per policy schedule. Patient is established with this practice.",
        "Routine follow-up visit for chronic condition under active management. Vitals reviewed, medication regimen confirmed, no changes recommended at this time. All services within standard preventive care guidelines.",
        "Acute presentation managed appropriately in office setting. Diagnostic testing ordered to confirm clinical impression. Patient counseled on findings and treatment plan. In-network provider, in-policy service.",
        "Annual preventive examination performed in accordance with USPSTF guidelines. Age-appropriate screening completed. No abnormal findings requiring further workup. Service is covered preventive care.",
    ],
    "DENY": [
        "Patient requested procedure for cosmetic improvement. No functional impairment documented. Service is excluded per Section 4.2 of policy schedule (cosmetic exclusion).",
        "Service rendered outside network without referral or prior authorization. Member is enrolled in HMO plan requiring PCP referral for specialist services. No authorization on file.",
        "Procedure billed under CPT code that is on the policy non-covered services list. Member acknowledged financial responsibility at point of service per signed waiver.",
        "Date of service falls after policy termination effective date. Coverage was terminated due to non-payment of premium. No grace period extension applies.",
    ],
    "REVIEW": [
        "Patient presents with complex symptoms suggesting need for advanced imaging. Clinical guidelines support imaging in select cases but criteria for this patient are borderline. Provider believes imaging is medically necessary; recommend medical director review.",
        "Procedure is on formulary but requires documentation of failed conservative therapy. Patient records indicate two prior conservative interventions but documentation is incomplete. Medical necessity unclear without additional records.",
        "Off-label use of medication for indication with limited published evidence. Provider cites recent peer-reviewed literature supporting efficacy. Coverage determination depends on clinical evidence interpretation.",
        "Step therapy protocol typically requires trial of two preferred agents before this medication. Patient has trial of one preferred agent with documented intolerance. Whether single trial satisfies protocol is open to interpretation.",
        "Diagnosis code combination is unusual and may indicate either complex comorbidity or coding error. Provider narrative supports clinical complexity but coding precision is questionable.",
    ],
    "ESCALATE": [
        "Major surgical procedure with prior authorization on file but auth was issued for different facility than service was rendered at. Facility transfer was last-minute due to surgeon availability. Authorization technically does not match site of service. Total billed exceeds high-cost threshold.",
        "Specialty drug therapy initiated for advanced-stage diagnosis. Drug is on formulary with prior auth. Auth documentation references different ICD code than what was billed. Medical necessity is clear but administrative discrepancy requires medical director sign-off given dollar amount.",
        "Emergency surgical intervention performed without pre-authorization due to acute clinical presentation. Hospital documentation supports emergency exception per policy. High-cost claim requires escalation regardless of disposition per policy threshold.",
    ],
    "LOW_CONFIDENCE": [
        "Pat ient pres ent ed wit h sym pt oms. Ev a lu at ion was per for med. Tre at ment plan dis cussed.",  # spaced
        "Service was provided to the patient on the date listed. The provider performed the necessary care.",  # vague
        "**SCANNED COPY -- ORIGINAL HANDWRITTEN NARRATIVE -- LEGIBILITY POOR**",  # signal poor scan
    ],
    "EXCEPTION": [
        "[NARRATIVE SECTION INCOMPLETE]",
    ],
}

# ---------------------------------------------------------------------------
# Scenario configuration
# ---------------------------------------------------------------------------

SCENARIO_PROFILES = {
    "APPROVE": {
        "prefix": "1",
        "cpt_pool": CPT_LOW,
        "icd_pool": ICD_LOW,
        "lines_min": 1, "lines_max": 3,
        "narratives": NARRATIVES["APPROVE"],
    },
    "DENY": {
        "prefix": "2",
        "cpt_pool": CPT_DENIED,
        "icd_pool": ICD_DENIED + ICD_LOW,
        "lines_min": 1, "lines_max": 2,
        "narratives": NARRATIVES["DENY"],
    },
    "REVIEW": {
        "prefix": "3",
        "cpt_pool": CPT_MID,
        "icd_pool": ICD_MID,
        "lines_min": 1, "lines_max": 3,
        "narratives": NARRATIVES["REVIEW"],
    },
    "ESCALATE": {
        "prefix": "4",
        "cpt_pool": CPT_HIGH,
        "icd_pool": ICD_HIGH,
        "lines_min": 1, "lines_max": 2,
        "narratives": NARRATIVES["ESCALATE"],
    },
    "LOW_CONFIDENCE": {
        "prefix": "5",
        "cpt_pool": CPT_MID + CPT_LOW,
        "icd_pool": ICD_MID + ICD_LOW,
        "lines_min": 1, "lines_max": 2,
        "narratives": NARRATIVES["LOW_CONFIDENCE"],
        "scramble": True,  # deliberately corrupt some fields
    },
}

# ---------------------------------------------------------------------------
# PDF rendering primitives
# ---------------------------------------------------------------------------

def label(c, x, y, text, size=8):
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text)

def value(c, x, y, text, size=10, mono=False):
    font = "Courier" if mono else "Helvetica"
    c.setFont(font, size)
    c.drawString(x, y, str(text))

def hr(c, y, dashed=False):
    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.5)
    if dashed:
        c.setDash(2, 2)
    c.line(MARGIN_L, y, MARGIN_R, y)
    c.setDash()

def section_heading(c, y, text):
    c.setFillColorRGB(0.12, 0.20, 0.36)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN_L, y, text)
    c.setFillColorRGB(0, 0, 0)

def header_block(c, claim_id, submission_date):
    # Brand bar
    c.setFillColorRGB(0.12, 0.20, 0.36)
    c.rect(MARGIN_L, MARGIN_T - 36, USABLE_W, 36, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN_L + 12, MARGIN_T - 20, "CASCADE HEALTH")
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN_L + 12, MARGIN_T - 32, "Health Insurance Claim Form")

    c.setFont("Helvetica", 8)
    c.drawRightString(MARGIN_R - 12, MARGIN_T - 14, "Form CHC-1500   Rev 2025-09")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(MARGIN_R - 12, MARGIN_T - 26, f"Claim ID: {claim_id}")
    c.setFillColorRGB(0, 0, 0)

    # Submission line
    y = MARGIN_T - 52
    label(c, MARGIN_L, y, "Submission date:")
    value(c, MARGIN_L + 95, y, submission_date)
    label(c, MARGIN_L + 280, y, "Claim status:")
    value(c, MARGIN_L + 350, y, "Initial submission")

    return y - 14  # next y

def patient_block(c, y, patient):
    last, first, dob, sex, addr, city, state, zipc, phone = patient
    member_id = f"CH-{random.randint(10000, 99999)}-{random.randint(10, 99)}"

    section_heading(c, y, "SECTION 1   PATIENT INFORMATION")
    hr(c, y - 4)
    y -= 18

    label(c, MARGIN_L, y, "Member ID:")
    value(c, MARGIN_L + 80, y, member_id, mono=True)
    label(c, MARGIN_L + 280, y, "Date of birth:")
    value(c, MARGIN_L + 355, y, dob)
    y -= 14

    label(c, MARGIN_L, y, "Last name:")
    value(c, MARGIN_L + 80, y, last)
    label(c, MARGIN_L + 280, y, "First name:")
    value(c, MARGIN_L + 355, y, first)
    y -= 14

    label(c, MARGIN_L, y, "Sex:")
    value(c, MARGIN_L + 80, y, sex)
    label(c, MARGIN_L + 280, y, "Phone:")
    value(c, MARGIN_L + 355, y, phone)
    y -= 14

    label(c, MARGIN_L, y, "Address:")
    value(c, MARGIN_L + 80, y, addr)
    y -= 14

    label(c, MARGIN_L, y, "City:")
    value(c, MARGIN_L + 80, y, city)
    label(c, MARGIN_L + 200, y, "State:")
    value(c, MARGIN_L + 240, y, state)
    label(c, MARGIN_L + 280, y, "ZIP:")
    value(c, MARGIN_L + 310, y, zipc)
    y -= 14
    return y - 6, member_id

def policy_block(c, y, member_id, scenario):
    section_heading(c, y, "SECTION 2   POLICY INFORMATION")
    hr(c, y - 4)
    y -= 18

    plan_type = random.choice(["PPO", "HMO", "EPO"])
    policy = f"CH-{plan_type}-2026-{member_id.split('-')[1]}"
    group = f"CASCH-EMP-{random.randint(1, 99):03d}"

    label(c, MARGIN_L, y, "Policy number:")
    value(c, MARGIN_L + 95, y, policy, mono=True)
    label(c, MARGIN_L + 280, y, "Group number:")
    value(c, MARGIN_L + 360, y, group, mono=True)
    y -= 14

    label(c, MARGIN_L, y, "Relationship:")
    value(c, MARGIN_L + 95, y, "Self")
    label(c, MARGIN_L + 280, y, "Plan type:")
    value(c, MARGIN_L + 360, y, plan_type)
    y -= 14
    return y - 6

def provider_block(c, y, provider):
    npi, name, tax_id, addr, phone, _ = provider
    section_heading(c, y, "SECTION 3   PROVIDER INFORMATION")
    hr(c, y - 4)
    y -= 18

    label(c, MARGIN_L, y, "Provider NPI:")
    value(c, MARGIN_L + 95, y, npi, mono=True)
    label(c, MARGIN_L + 280, y, "Tax ID / EIN:")
    value(c, MARGIN_L + 360, y, tax_id, mono=True)
    y -= 14

    label(c, MARGIN_L, y, "Provider name:")
    value(c, MARGIN_L + 95, y, name)
    y -= 14

    label(c, MARGIN_L, y, "Address:")
    value(c, MARGIN_L + 95, y, addr)
    y -= 14

    label(c, MARGIN_L, y, "Phone:")
    value(c, MARGIN_L + 95, y, phone)
    y -= 14
    return y - 6

def service_lines_block(c, y, lines, scramble=False):
    """lines: list of dicts with date, pos, cpt, desc, icd, units, charge"""
    section_heading(c, y, "SECTION 4   SERVICE DETAILS")
    hr(c, y - 4)
    y -= 18

    # Column header row. Geometry is sized so Description gets the largest slot.
    cols_x = [MARGIN_L, MARGIN_L + 28, MARGIN_L + 95, MARGIN_L + 125,
              MARGIN_L + 165, MARGIN_L + 332, MARGIN_L + 385, MARGIN_L + 440]
    headers = ["Line", "Date of service", "POS", "CPT", "Description", "ICD-10", "Units", "Charges"]
    c.setFont("Helvetica-Bold", 7)
    for x, h in zip(cols_x, headers):
        c.drawString(x, y, h)
    y -= 4
    hr(c, y, dashed=True)
    y -= 10

    # Description column is 165pt wide. At 8pt Helvetica that fits ~32 chars
    # comfortably with a small safety margin.
    DESC_MAX = 30

    total = 0.0
    c.setFont("Helvetica", 8)
    for i, line in enumerate(lines, 1):
        c.drawString(cols_x[0], y, str(i))
        c.drawString(cols_x[1], y, line["date"])
        c.drawString(cols_x[2], y, line["pos"])
        c.drawString(cols_x[3], y, line["cpt"])
        desc = line["desc"]
        if len(desc) > DESC_MAX:
            desc = desc[:DESC_MAX - 1].rstrip() + "."
        c.drawString(cols_x[4], y, desc)
        c.drawString(cols_x[5], y, line["icd"])
        c.drawString(cols_x[6], y, str(line["units"]))
        c.drawRightString(cols_x[7] + 60, y, f"${line['charge']:,.2f}")
        total += line["charge"]
        y -= 12

    y -= 4
    return y - 6, total

def totals_block(c, y, total):
    section_heading(c, y, "SECTION 5   TOTALS")
    hr(c, y - 4)
    y -= 18

    label(c, MARGIN_L, y, "Total charges:")
    value(c, MARGIN_L + 95, y, f"${total:,.2f}", mono=True)
    y -= 14
    label(c, MARGIN_L, y, "Amount paid:")
    value(c, MARGIN_L + 95, y, "$0.00", mono=True)
    y -= 14
    label(c, MARGIN_L, y, "Balance due:")
    value(c, MARGIN_L + 95, y, f"${total:,.2f}", mono=True)
    y -= 14
    return y - 6

def narrative_block(c, y, narrative):
    section_heading(c, y, "SECTION 6   PROVIDER NARRATIVE / ADJUSTER NOTES")
    hr(c, y - 4)
    y -= 18

    # wrap narrative to ~95 chars per line
    c.setFont("Helvetica", 9)
    words = narrative.split()
    cur = ""
    lines = []
    for w in words:
        if len(cur) + len(w) + 1 > 95:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    for ln in lines[:6]:
        c.drawString(MARGIN_L, y, ln)
        y -= 12
    return y - 6

def auth_block(c, y, provider_name, sub_date):
    section_heading(c, y, "SECTION 7   AUTHORIZATION")
    hr(c, y - 4)
    y -= 18
    label(c, MARGIN_L, y, "Provider signature:")
    c.line(MARGIN_L + 110, y - 1, MARGIN_L + 320, y - 1)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(MARGIN_L + 115, y + 1, provider_name)
    label(c, MARGIN_L + 360, y, "Date:")
    value(c, MARGIN_L + 395, y, sub_date)
    y -= 22
    return y

# ---------------------------------------------------------------------------
# Scenario synthesis
# ---------------------------------------------------------------------------

def random_recent_date(days_back=30):
    today = date(2026, 4, 28)
    delta = random.randint(2, days_back)
    return (today - timedelta(days=delta)).isoformat()

def build_service_lines(profile):
    n = random.randint(profile["lines_min"], profile["lines_max"])
    pool = profile["cpt_pool"]
    icd_pool = profile["icd_pool"]
    dos = random_recent_date()
    pos_options = ["11", "21", "22", "23"]  # office, inpatient, outpatient, ER
    pos = random.choice(pos_options)
    lines = []
    for _ in range(n):
        cpt, desc, base = random.choice(pool)
        icd, _ = random.choice(icd_pool)
        units = 1
        # Add slight variance to charge
        charge = base * random.uniform(0.95, 1.10)
        lines.append({
            "date": dos, "pos": pos, "cpt": cpt, "desc": desc,
            "icd": icd, "units": units, "charge": round(charge, 2),
        })
    return lines

def scramble_fields(patient, provider, lines):
    """Deliberately corrupt fields for LOW_CONFIDENCE scenario."""
    last, first, dob, sex, addr, city, state, zipc, phone = patient
    # Random scramble: corrupt one of dob, npi, or cpt
    choice = random.randint(0, 2)
    if choice == 0:
        # Mangled DOB
        dob = dob.replace("-", "/")[:6] + "??"
    elif choice == 1:
        # Mangled NPI
        npi = provider[0]
        npi_bad = npi[:4] + "X" + npi[5:]
        provider = (npi_bad,) + provider[1:]
    else:
        # Mangled CPT
        if lines:
            lines[0]["cpt"] = lines[0]["cpt"][:3] + "?"
    patient = (last, first, dob, sex, addr, city, state, zipc, phone)
    return patient, provider, lines

# ---------------------------------------------------------------------------
# Main rendering
# ---------------------------------------------------------------------------

def generate_one(claim_id, scenario, output_path):
    profile = SCENARIO_PROFILES[scenario]
    patient = random.choice(PATIENTS)
    provider = random.choice(PROVIDERS)
    lines = build_service_lines(profile)
    narrative = random.choice(profile["narratives"])
    sub_date = random_recent_date(days_back=14)

    if profile.get("scramble"):
        patient, provider, lines = scramble_fields(patient, provider, lines)

    c = canvas.Canvas(output_path, pagesize=letter)
    c.setTitle(f"Cascade Health Claim {claim_id}")
    c.setAuthor("Cascade Health")
    c.setSubject("Health insurance claim form")

    next_y = header_block(c, claim_id, sub_date)
    next_y, _member_id = patient_block(c, next_y, patient)
    next_y = policy_block(c, next_y, _member_id, scenario)
    next_y = provider_block(c, next_y, provider)
    next_y, total = service_lines_block(c, next_y, lines)
    next_y = totals_block(c, next_y, total)
    next_y = narrative_block(c, next_y, narrative)
    auth_block(c, next_y, provider[1], sub_date)

    # Footer
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(MARGIN_L, 0.4 * inch, "Cascade Health is a wholly-owned subsidiary of Meridian Bank Holdings.")
    c.drawRightString(MARGIN_R, 0.4 * inch, f"Page 1 of 1   {claim_id}")

    c.showPage()
    c.save()
    return total, scenario

# ---------------------------------------------------------------------------
# Batch driver
# ---------------------------------------------------------------------------

# Initial training batch composition. Sized to clear DU Modern's 30-document
# minimum for extraction training while leaving comfortable headroom for a
# held-out test set and 4 LOW_CONFIDENCE docs that are never used for training.
INITIAL_BATCH = [
    ("APPROVE", 14),
    ("DENY", 10),
    ("REVIEW", 7),
    ("ESCALATE", 5),
    ("LOW_CONFIDENCE", 4),
]

def generate_batch(output_dir, batch=INITIAL_BATCH, seed=20260429):
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)
    manifest = []
    counter = {"APPROVE": 100001, "DENY": 200001, "REVIEW": 300001,
               "ESCALATE": 400001, "LOW_CONFIDENCE": 500001, "EXCEPTION": 900001}
    for scenario, count in batch:
        for _ in range(count):
            cid = f"CHC-{counter[scenario]}"
            counter[scenario] += 1
            fn = os.path.join(output_dir, f"{cid}.pdf")
            total, _ = generate_one(cid, scenario, fn)
            manifest.append((cid, scenario, total, fn))
    return manifest

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/claims_pdfs"
    manifest = generate_batch(out)
    print(f"Generated {len(manifest)} claim PDFs in {out}")
    print()
    print(f"{'Claim ID':<14} {'Scenario':<16} {'Total':>12}")
    print("-" * 46)
    for cid, scenario, total, _ in manifest:
        print(f"{cid:<14} {scenario:<16} ${total:>10,.2f}")
