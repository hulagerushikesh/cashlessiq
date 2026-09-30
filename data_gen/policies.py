"""Constants for the single Phase 1 policy product and its reviewed clauses."""

PRODUCT = {
    "product_id": "AS_NIA_V02_2425",
    "product_name": "Arogya Sanjeevani Policy, The New India Assurance Co. Ltd",
    "insurer": "The New India Assurance Co. Ltd",
    "uin": "NIAHLIP25044V022425",
    "version": "V02 2024-25",
    "effective_from": "2024-10-01",
    "source_url": (
        "https://www.newindia.co.in/assets/docs/know-more/health/"
        "arogya-sanjeevani/POLICY%20CLAUSES%20Arogya%20Sanjeevani.pdf"
    ),
}

VERIFIED_BY = "Rushikesh"
VERIFIED_AT = "2026-09-29T23:30:00+05:30"

CLAUSES = (
    ("NIA-4.1-A", "4.1", "Hospitalization - room rent", 7),
    ("NIA-4.1-B", "4.1", "Hospitalization - ICU/ICCU", 7),
    ("NIA-4.1-NOTE-B", "4.1 Note", "Proportionate deduction", 8),
    ("NIA-4.3", "4.3", "Cataract treatment", 8),
    ("NIA-6.1", "6.1", "Pre-existing diseases", 9),
    ("NIA-6.2-24", "6.2(i)", "24-month specific waiting period", 10),
    ("NIA-6.2-36", "6.2(ii)", "36-month specific waiting period", 10),
    ("NIA-6.3", "6.3", "First thirty days waiting period", 10),
    ("NIA-7.12", "7.12", "Refractive error exclusion", 12),
    ("NIA-9.5", "9.5", "Co-payment", 15),
)

RULES = (
    ("RULE_ROOM", "ROOM_RENT_CAP", '{"pct_of_si":2,"max_inr_per_day":5000}', "NIA-4.1-A"),
    ("RULE_ICU", "ICU_CAP", '{"pct_of_si":5,"max_inr_per_day":10000}', "NIA-4.1-B"),
    (
        "RULE_PROP",
        "PROPORTIONATE_DEDUCTION",
        '{"applies_to":["procedure and professional fees","surgery and implant",'
        '"hernia repair package","debridement and medical care","medical management"],'
        '"exempt_items":["medicines"]}',
        "NIA-4.1-NOTE-B",
    ),
    (
        "RULE_CATARACT",
        "PROCEDURE_SUBLIMIT",
        '{"procedure":"cataract","pct_of_si":25,"max_inr":40000,"basis":"per_eye_per_policy_year"}',
        "NIA-4.3",
    ),
    ("RULE_PED", "WAITING_PED", '{"months":36}', "NIA-6.1"),
    (
        "RULE_SPECIFIC_24",
        "WAITING_SPECIFIC",
        '{"months":24,"conditions":["cataract","hernia","gallstones",'
        '"non_infective_arthritis"],"accident_exempt":true}',
        "NIA-6.2-24",
    ),
    (
        "RULE_SPECIFIC_36",
        "WAITING_SPECIFIC",
        '{"months":36,"conditions":["joint_replacement","osteoarthritis",'
        '"osteoporosis"],"accident_exempt":true}',
        "NIA-6.2-36",
    ),
    ("RULE_INITIAL", "WAITING_INITIAL", '{"days":30,"accident_exempt":true}', "NIA-6.3"),
    (
        "RULE_EXCLUSION",
        "EXCLUSION",
        '{"condition":"refractive_error_below_7_5_dioptres"}',
        "NIA-7.12",
    ),
    ("RULE_COPAY", "COPAY", '{"pct":5}', "NIA-9.5"),
)
