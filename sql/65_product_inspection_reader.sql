-- P2 proposed operator-only diagnostic grants. NOT part of make setup.
-- NOT applied automatically. Review with CoCo before executing this file.
-- This is table-level synthetic access, NOT tenant RLS or a service identity.
-- Existing metadata grants from 64_product_reader.sql remain necessary.
-- VERIFY WITH COCO: confirm live object definitions and ownership match the
-- repository before granting these four SELECTs to the existing reader role.
-- Review PUBLIC/direct-user effective privileges separately; no revocations here.
USE ROLE ACCOUNTADMIN;
GRANT USAGE ON SCHEMA CASHLESSIQ.APP TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.CORE.CLAIM TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.CORE.MEMBER_CONDITION TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.APP.DECISION TO ROLE CIQ_PRODUCT_READER;
GRANT SELECT ON TABLE CASHLESSIQ.DOCS.POLICY_CLAUSE TO ROLE CIQ_PRODUCT_READER;
-- No MEMBER demographics, stage access, future/all-table grants, AI or writes.
-- No role membership grants: retain the existing single local operator only.
