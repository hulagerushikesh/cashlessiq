-- Phase 4 governed policy-onboarding rehearsal.
-- Human approval (Rushikesh, 2026-10-03):
-- "I approve the 25 clause-only additions and zero rule changes."
-- Unsupported benefits remain searchable clauses; POLICY_RULE is never changed here.

USE ROLE CIQ_ADMIN;
USE DATABASE CASHLESSIQ;
USE SCHEMA DOCS;

BEGIN;

MERGE INTO POLICY_CLAUSE AS target
USING (
    SELECT column1 AS CLAUSE_ID, 'AS_NIA_V02_2425' AS PRODUCT_ID,
           column2 AS SECTION, column3 AS HEADING, column4 AS TEXT, column5 AS PAGE
    FROM VALUES
      ('NIA-4.1.1-E','4.1.1(e)','Ambulance charges','Expenses incurred on road ambulance subject to a maximum of Rs 2,000 per hospitalisation.',7),
      ('NIA-4.2','4.2','AYUSH treatment','Expenses for inpatient care treatment under Ayurveda, Yoga and Naturopathy, Unani, Siddha and Homeopathy systems is covered up to 100% of sum insured during each policy year.',8),
      ('NIA-4.4','4.4','Pre-hospitalisation expenses','Pre-hospitalisation medical expenses incurred for a fixed period of 30 days prior to the date of admissible hospitalisation are covered.',8),
      ('NIA-4.5','4.5','Post-hospitalisation expenses','Post-hospitalisation medical expenses incurred for a fixed period of 60 days from the date of discharge following an admissible hospitalisation are covered.',8),
      ('NIA-4.6','4.6','Special procedures sublimit','Twelve listed procedures including uterine artery embolization, balloon sinuplasty, deep brain stimulation, oral chemotherapy, immunotherapy, intravitreal injections, robotic surgeries, stereotactic radiosurgeries, bronchial thermoplasty, vaporisation of the prostate, IONM and stem cell therapy are covered up to 50% of sum insured.',8),
      ('NIA-5','5','Cumulative bonus','Cumulative bonus increases by 5% for each claim-free policy year, subject to a maximum of 50% of sum insured. A claim reduces the bonus at the same accrual rate.',9),
      ('NIA-7.1','7.1','Investigation and evaluation exclusion','Expenses related to any admission primarily for diagnostics and evaluation purposes, or diagnostic expenses not related to the current diagnosis and treatment.',11),
      ('NIA-7.2','7.2','Rest cure rehabilitation and respite care exclusion','Expenses related to any admission primarily for enforced bed rest and not for receiving treatment, including custodial care and terminal care services.',11),
      ('NIA-7.3','7.3','Obesity and weight control exclusion','Expenses related to surgical treatment of obesity unless the surgery is doctor-advised, clinically supported, member is 18+ and BMI is 40+ or 35+ with specified severe comorbidities after failure of less invasive methods.',11),
      ('NIA-7.4','7.4','Change of gender exclusion','Expenses related to any treatment including surgical management to change characteristics of the body to those of the opposite sex.',11),
      ('NIA-7.5','7.5','Cosmetic or plastic surgery exclusion','Expenses for cosmetic or plastic surgery or any treatment to change appearance unless for reconstruction following an accident, burns or cancer or as part of medically necessary treatment.',11),
      ('NIA-7.6','7.6','Hazardous or adventure sports exclusion','Expenses related to any treatment necessitated due to participation as a professional in hazardous or adventure sports including para-jumping, rock climbing, mountaineering, rafting, motor racing, horse racing, scuba diving, hand gliding, sky diving, deep-sea diving.',12),
      ('NIA-7.7','7.7','Breach of law exclusion','Expenses for treatment directly arising from or consequent upon any insured person committing or attempting to commit a breach of law with criminal intent.',12),
      ('NIA-7.8','7.8','Excluded providers exclusion','Expenses incurred towards treatment in any hospital or by any medical practitioner specifically excluded by the insurer. In life-threatening situations or accidents, expenses up to stabilisation are payable.',12),
      ('NIA-7.9','7.9','Alcoholism drug or substance abuse exclusion','Treatment for alcoholism, drug or substance abuse or any addictive condition and consequences thereof.',12),
      ('NIA-7.10','7.10','Health hydros and spas exclusion','Treatments received in health hydros, nature cure clinics, spas or similar establishments or private beds registered as a nursing home attached to such establishments.',12),
      ('NIA-7.11','7.11','Dietary supplements exclusion','Dietary supplements and substances that can be purchased without prescription including vitamins, minerals and organic substances unless prescribed by a medical practitioner as part of hospitalisation claim or day care procedure.',12),
      ('NIA-7.13','7.13','Unproven treatments exclusion','Expenses related to any unproven treatment, services and supplies that lack significant medical documentation to support their effectiveness.',12),
      ('NIA-7.14','7.14','Sterility and infertility exclusion','Expenses related to sterility and infertility including contraception, sterilisation, assisted reproduction services (IVF, ZIFT, GIFT, ICSI), gestational surrogacy and reversal of sterilisation.',12),
      ('NIA-7.15','7.15','Maternity expenses exclusion','Medical treatment expenses traceable to childbirth including complicated deliveries and caesarean sections except ectopic pregnancy. Expenses towards miscarriage unless due to an accident and lawful medical termination of pregnancy.',12),
      ('NIA-7.16','7.16','War exclusion','War whether declared or not, war-like occurrences, invasion, acts of foreign enemies, hostilities, civil war, rebellion, revolutions, insurrections, mutiny, military or usurped power, seizure, capture, arrest, restraints and detainment.',12),
      ('NIA-7.17','7.17','Nuclear chemical or biological attack exclusion','Expenses arising from nuclear, chemical or biological attack or weapons including nuclear devices, radioactive material, chemical compounds and pathogenic micro-organisms or biologically produced toxins.',13),
      ('NIA-7.18','7.18','Domiciliary and OPD exclusion','Any expenses incurred on domiciliary hospitalisation and OPD treatment.',13),
      ('NIA-7.19','7.19','Treatment outside India exclusion','Treatment taken outside the geographical limits of India.',13),
      ('NIA-7.20','7.20','Disclosed existing disease ICD exclusion','In respect of existing diseases disclosed by the insured and mentioned in the policy schedule, policyholder is not entitled to get coverage for specified ICD codes.',13)
) AS source
ON target.CLAUSE_ID = source.CLAUSE_ID
WHEN NOT MATCHED THEN INSERT (CLAUSE_ID, PRODUCT_ID, SECTION, HEADING, TEXT, PAGE)
VALUES (source.CLAUSE_ID, source.PRODUCT_ID, source.SECTION, source.HEADING, source.TEXT, source.PAGE);

COMMIT;

-- Post-merge invariants: expected results are 35 clauses and 10 rules.
SELECT COUNT(*) AS CLAUSE_COUNT FROM POLICY_CLAUSE WHERE PRODUCT_ID = 'AS_NIA_V02_2425';
SELECT COUNT(*) AS RULE_COUNT FROM POLICY_RULE WHERE PRODUCT_ID = 'AS_NIA_V02_2425';

-- Search lifecycle used in the approved rehearsal.
ALTER CORTEX SEARCH SERVICE CASHLESSIQ.AI.CLAUSE_SEARCH RESUME;
ALTER CORTEX SEARCH SERVICE CASHLESSIQ.AI.CLAUSE_SEARCH REFRESH;

-- Standard probes: each expected clause appeared at rank 1 (10/10).
-- SEARCH_PREVIEW requires a constant JSON argument, so probes are kept explicit.
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"room rent daily limit","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"ICU daily limit","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"proportionate deduction room rate exceeds limit","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"cataract treatment sublimit","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"pre-existing disease waiting period 36 months","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"24 month specific disease waiting period","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"joint replacement waiting period","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"first thirty days illness exclusion","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"refractive error less than 7.5 dioptres exclusion","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CASHLESSIQ.AI.CLAUSE_SEARCH','{"query":"mandatory copayment percentage","columns":["CLAUSE_ID"],"filter":{"@eq":{"PRODUCT_ID":"AS_NIA_V02_2425"}},"limit":3}'))['results'] AS RESULTS;

-- Always leave the service suspended after validation to control spend.
ALTER CORTEX SEARCH SERVICE CASHLESSIQ.AI.CLAUSE_SEARCH SUSPEND;
