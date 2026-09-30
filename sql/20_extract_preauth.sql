USE ROLE CIQ_ADMIN;
USE DATABASE CASHLESSIQ;
USE SCHEMA DOCS;
USE WAREHOUSE CIQ_WH;

CREATE TABLE IF NOT EXISTS PREAUTH_PARSE (
  REQUEST_ID VARCHAR(20) NOT NULL PRIMARY KEY REFERENCES PREAUTH_REQUEST(REQUEST_ID),
  PARSED_DOCUMENT VARIANT,
  PARSED_TEXT VARCHAR,
  PARSE_ERROR VARCHAR,
  PARSED_AT TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

TRUNCATE TABLE PREAUTH_FACTS;
TRUNCATE TABLE PREAUTH_PARSE;

CREATE OR REPLACE TEMP TABLE PREAUTH_PARSE_LOAD AS
SELECT
  R.REQUEST_ID,
  AI_PARSE_DOCUMENT(
    TO_FILE('@CASHLESSIQ.DOCS.PREAUTH_STAGE', D.RELATIVE_PATH),
    {'mode': 'LAYOUT'}, TRUE
  ) AS PARSE_RESULT
FROM DIRECTORY(@CASHLESSIQ.DOCS.PREAUTH_STAGE) D
JOIN PREAUTH_REQUEST R ON R.FILE_PATH = D.RELATIVE_PATH;

INSERT INTO PREAUTH_PARSE (REQUEST_ID, PARSED_DOCUMENT, PARSED_TEXT, PARSE_ERROR)
SELECT
  REQUEST_ID,
  PARSE_RESULT:value,
  PARSE_RESULT:value:content::VARCHAR,
  PARSE_RESULT:error::VARCHAR
FROM PREAUTH_PARSE_LOAD;

CREATE OR REPLACE TEMP TABLE PREAUTH_EXTRACT_LOAD AS
SELECT
  R.REQUEST_ID,
  AI_EXTRACT(
    file => TO_FILE('@CASHLESSIQ.DOCS.PREAUTH_STAGE', D.RELATIVE_PATH),
    responseFormat => PARSE_JSON($$
      {
        "schema": {
          "type": "object",
          "properties": {
            "diagnosis": {"description": "Primary diagnosis exactly as written", "type": "string"},
            "icd10_code": {"description": "ICD-10 code, or empty if absent", "type": "string"},
            "procedure": {"description": "Planned procedure exactly as written", "type": "string"},
            "is_emergency": {"description": "Whether Emergency is true or false", "type": "string"},
            "admission_date": {"description": "Admission date in YYYY-MM-DD", "type": "string"},
            "planned_los_days": {"description": "Planned stay as an integer number of days", "type": "string"},
            "room_category": {"description": "Room category", "type": "string"},
            "room_rent_per_day_inr": {"description": "Room rent per day as digits only", "type": "string"},
            "icu_days": {"description": "ICU days as digits, or 0 if absent", "type": "string"},
            "cost_breakup": {
              "description": "Estimated cost break-up table",
              "type": "object",
              "column_ordering": ["item", "claimed_inr"],
              "properties": {
                "item": {"description": "Item", "type": "array"},
                "claimed_inr": {"description": "Amount INR", "type": "array"}
              }
            },
            "estimated_total_inr": {"description": "Estimated total as digits only", "type": "string"},
            "clinical_note": {"description": "Clinical note on page two", "type": "string"}
          }
        }
      }
    $$),
    scores => TRUE
  ) AS EXTRACT_RESULT
FROM DIRECTORY(@CASHLESSIQ.DOCS.PREAUTH_STAGE) D
JOIN PREAUTH_REQUEST R ON R.FILE_PATH = D.RELATIVE_PATH;

INSERT INTO PREAUTH_FACTS (
  REQUEST_ID, DIAGNOSIS, ICD10_CODE, PROCEDURE, IS_EMERGENCY,
  ADMISSION_DATE, PLANNED_LOS_DAYS, ROOM_CATEGORY, ROOM_RENT_PER_DAY_INR,
  ICU_DAYS, COST_BREAKUP, ESTIMATED_TOTAL_INR, CLINICAL_NOTE,
  MISSING_FIELDS, RAW_EXTRACT
)
SELECT
  REQUEST_ID,
  NULLIF(
    REGEXP_REPLACE(
      TRIM(EXTRACT_RESULT:response:diagnosis::VARCHAR),
      '^(Not supplied|Not provided|N/?A)$',
      '',
      1,
      0,
      'i'
    ),
    ''
  ),
  NULLIF(TRIM(EXTRACT_RESULT:response:icd10_code::VARCHAR), ''),
  NULLIF(TRIM(EXTRACT_RESULT:response:procedure::VARCHAR), ''),
  TRY_TO_BOOLEAN(EXTRACT_RESULT:response:is_emergency::VARCHAR),
  TRY_TO_DATE(EXTRACT_RESULT:response:admission_date::VARCHAR),
  TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:planned_los_days::VARCHAR, '[^0-9]', '')),
  NULLIF(TRIM(EXTRACT_RESULT:response:room_category::VARCHAR), ''),
  TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:room_rent_per_day_inr::VARCHAR, '[^0-9]', '')),
  COALESCE(TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:icu_days::VARCHAR, '[^0-9]', '')), 0),
  IFF(
    LOWER(GET(
      EXTRACT_RESULT:response:cost_breakup:item,
      ARRAY_SIZE(EXTRACT_RESULT:response:cost_breakup:item) - 1
    )::VARCHAR) = 'estimated total',
    OBJECT_CONSTRUCT(
      'item', ARRAY_SLICE(
        EXTRACT_RESULT:response:cost_breakup:item,
        0,
        ARRAY_SIZE(EXTRACT_RESULT:response:cost_breakup:item) - 1
      ),
      'claimed_inr', ARRAY_SLICE(
        EXTRACT_RESULT:response:cost_breakup:claimed_inr,
        0,
        ARRAY_SIZE(EXTRACT_RESULT:response:cost_breakup:claimed_inr) - 1
      )
    ),
    EXTRACT_RESULT:response:cost_breakup
  ),
  TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:estimated_total_inr::VARCHAR, '[^0-9]', '')),
  NULLIF(TRIM(EXTRACT_RESULT:response:clinical_note::VARCHAR), ''),
  ARRAY_CONSTRUCT_COMPACT(
    IFF(
      NULLIF(
        REGEXP_REPLACE(
          TRIM(EXTRACT_RESULT:response:diagnosis::VARCHAR),
          '^(Not supplied|Not provided|N/?A)$',
          '',
          1,
          0,
          'i'
        ),
        ''
      ) IS NULL,
      'diagnosis',
      NULL
    ),
    IFF(NULLIF(TRIM(EXTRACT_RESULT:response:procedure::VARCHAR), '') IS NULL, 'procedure', NULL),
    IFF(TRY_TO_DATE(EXTRACT_RESULT:response:admission_date::VARCHAR) IS NULL, 'admission_date', NULL),
    IFF(NULLIF(TRIM(EXTRACT_RESULT:response:room_category::VARCHAR), '') IS NULL, 'room_category', NULL),
    IFF(TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:room_rent_per_day_inr::VARCHAR, '[^0-9]', '')) IS NULL, 'room_rent_per_day_inr', NULL),
    IFF(TRY_TO_NUMBER(REGEXP_REPLACE(EXTRACT_RESULT:response:estimated_total_inr::VARCHAR, '[^0-9]', '')) IS NULL, 'estimated_total_inr', NULL),
    IFF(
      EXTRACT_RESULT:response:cost_breakup IS NULL
        OR ARRAY_SIZE(EXTRACT_RESULT:response:cost_breakup:item)
          - IFF(
              LOWER(GET(
                EXTRACT_RESULT:response:cost_breakup:item,
                ARRAY_SIZE(EXTRACT_RESULT:response:cost_breakup:item) - 1
              )::VARCHAR) = 'estimated total',
              1,
              0
            ) = 0,
      'cost_breakup',
      NULL
    )
  ),
  EXTRACT_RESULT
FROM PREAUTH_EXTRACT_LOAD;

SELECT COUNT(*) AS EXTRACTED_REQUESTS,
       COUNT_IF(ARRAY_SIZE(MISSING_FIELDS) = 0) AS COMPLETE_REQUESTS
FROM PREAUTH_FACTS;
