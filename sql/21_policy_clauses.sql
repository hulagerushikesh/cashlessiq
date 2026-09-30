USE ROLE CIQ_ADMIN;
USE DATABASE CASHLESSIQ;
USE SCHEMA DOCS;
USE WAREHOUSE CIQ_WH;

CREATE TABLE IF NOT EXISTS POLICY_DOCUMENT_PARSE (
  PRODUCT_ID VARCHAR(40) NOT NULL PRIMARY KEY REFERENCES CASHLESSIQ.CORE.POLICY_PRODUCT(PRODUCT_ID),
  FILE_PATH VARCHAR(1000) NOT NULL,
  PARSED_DOCUMENT VARIANT,
  PARSED_TEXT VARCHAR,
  PARSE_ERROR VARCHAR,
  PARSED_AT TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

TRUNCATE TABLE POLICY_DOCUMENT_PARSE;

INSERT INTO POLICY_DOCUMENT_PARSE
SELECT
  'AS_NIA_V02_2425', D.RELATIVE_PATH,
  P:value, P:value:content::VARCHAR, P:error::VARCHAR, CURRENT_TIMESTAMP()
FROM (
  SELECT RELATIVE_PATH,
         AI_PARSE_DOCUMENT(
           TO_FILE('@CASHLESSIQ.DOCS.POLICY_STAGE', RELATIVE_PATH),
           {'mode': 'LAYOUT'}, TRUE
         ) P
  FROM DIRECTORY(@CASHLESSIQ.DOCS.POLICY_STAGE)
  WHERE RELATIVE_PATH = 'newindia_arogya_sanjeevani_NIAHLIP25044V022425.pdf'
) D;

-- Stable, human-reviewed clause boundaries. The full parsed wording is retained
-- above; these focused chunks make retrieval deterministic and auditable.
MERGE INTO POLICY_CLAUSE T USING (
  SELECT COLUMN1 CLAUSE_ID, 'AS_NIA_V02_2425' PRODUCT_ID, COLUMN2 SECTION,
         COLUMN3 HEADING, COLUMN4 TEXT, COLUMN5 PAGE
  FROM VALUES
    ('NIA-4.1-A','4.1(a)','Room rent cap','Room rent, boarding and nursing is covered up to 2% of sum insured, subject to INR 5,000 per day.',7),
    ('NIA-4.1-B','4.1(b)','ICU and ICCU cap','ICU or ICCU expenses are covered up to 5% of sum insured, subject to INR 10,000 per day.',7),
    ('NIA-4.1-NOTE-B','4.1 Note (b)','Proportionate deduction','When room or ICU rates exceed limits, other hospital expenses except medicines are paid in the ratio of admissible to actual room rate.',8),
    ('NIA-4.3','4.3','Cataract treatment','Cataract treatment is limited to 25% of sum insured or INR 40,000, whichever is lower, per eye in one policy year.',8),
    ('NIA-6.1','6.1','Pre-existing diseases','Pre-existing disease and direct complications are excluded until 36 months of continuous coverage have elapsed.',9),
    ('NIA-6.2-24','6.2(i)','24-month specific waiting period','Listed treatments including cataract, hernia, gallstones and non-infective arthritis have a 24-month waiting period, except accidents.',10),
    ('NIA-6.2-36','6.2(ii)','36-month specific waiting period','Joint replacement unless caused by accident, age-related osteoarthritis and osteoporosis have a 36-month waiting period.',10),
    ('NIA-6.3','6.3','First thirty days waiting period','Illness within 30 days of first policy commencement is excluded; covered claims arising from accidents are exempt.',10),
    ('NIA-7.12','7.12','Refractive error exclusion','Treatment to correct eyesight for refractive error below 7.5 dioptres is excluded.',12),
    ('NIA-9.5','9.5','Co-payment','Every claim is subject to a 5% co-payment on the admissible and payable claim amount.',15)
) S
ON T.CLAUSE_ID = S.CLAUSE_ID
WHEN MATCHED THEN UPDATE SET SECTION=S.SECTION, HEADING=S.HEADING, TEXT=S.TEXT, PAGE=S.PAGE
WHEN NOT MATCHED THEN INSERT (CLAUSE_ID,PRODUCT_ID,SECTION,HEADING,TEXT,PAGE)
VALUES (S.CLAUSE_ID,S.PRODUCT_ID,S.SECTION,S.HEADING,S.TEXT,S.PAGE);

SELECT PRODUCT_ID, LENGTH(PARSED_TEXT) AS PARSED_CHARACTERS, PARSE_ERROR
FROM POLICY_DOCUMENT_PARSE;
