# Subtask 4 — Presidio recall vs answer key (recognizer set: ids_only)

- Real Presidio call: **True** (presidio-analyzer 2.2.362, spaCy 3.8.14 / en_core_web_lg 3.8.0)
- Default IBAN_CODE catches the synthetic DZ IBAN `DZ23-86758-8963334018-54`: **False**
- Precision (lower bound): **0.9217** (2308/2504 detections overlap a GT entity)

## Overall recall on severity>=3 types (gate >= 0.9) — FAILS on every variant
- sev>=3 answer-key entities: **1490** (100 not locatable verbatim in corpus -> locatable **1390**)
- recall CORRECT-label (honest floor): all=**0.6208**, locatable=**0.6655**
- recall ANY-label (upper bound; partial overlaps inflate it): all=**0.7141**, locatable=**0.7655**

## Types flagged (recall_any < 0.9): 20

| type | sev | n | det_any | recall_any | recall_correct | not_locatable | labels |
|---|--:|--:|--:|--:|--:|--:|---|
| PERSON | 4 | 130 | 130 | 1.0 | 1.0 | 0 | PERSON |
| HEALTH_RECORD_ID | 4 | 130 | 130 | 1.0 | 1.0 | 0 | HEALTH_RECORD_ID |
| NATIONAL_ID | 5 | 100 | 100 | 1.0 | 1.0 | 0 | NNI_DZ |
| EMAIL | 4 | 100 | 100 | 1.0 | 1.0 | 0 | EMAIL_ADDRESS |
| PHONE | 4 | 100 | 100 | 1.0 | 0.51 | 0 | PHONE_DZ,PHONE_NUMBER |
| ADDRESS | 4 | 100 | 89 | 0.89 | 0.6 | 0 | LOCATION |
| DOB | 4 | 100 | 100 | 1.0 | 1.0 | 0 | DATE_TIME |
| IBAN | 4 | 100 | 100 | 1.0 | 1.0 | 0 | IBAN_CODE,IBAN_DZ |
| SURNAME_TITLE | 4 | 100 | 51 | 0.51 | 0.49 | 0 | PERSON |
| SALARY | 3 | 100 | 48 | 0.48 | 0.0 | 0 | SALARY |
| EMPLOYEE_ID | 3 | 100 | 100 | 1.0 | 1.0 | 0 | EMPLOYEE_ID |
| AGE_GENDER | 3 | 100 | 0 | 0.0 | 0.0 | 100 | — |
| PERFORMANCE | 2 | 100 | 0 | 0.0 | 0.0 | 0 | — |
| DEPARTMENT | 2 | 100 | 0 | 0.0 | 0.0 | 0 | — |
| JOB_TITLE | 2 | 100 | 0 | 0.0 | 0.0 | 0 | — |
| WORK_SCHEDULE | 2 | 100 | 76 | 0.76 | 0.0 | 0 | — |
| OFFICE_LOCATION | 2 | 100 | 0 | 0.0 | 0.0 | 0 | LOCATION |
| PROJECT | 2 | 100 | 30 | 0.3 | 0.0 | 0 | — |
| TRAINING | 2 | 100 | 0 | 0.0 | 0.0 | 0 | — |
| MEDICAL | 3 | 93 | 0 | 0.0 | 0.0 | 0 | MEDICAL_LICENSE |
| CROSS_REFERENCE | 3 | 41 | 0 | 0.0 | 0.0 | 0 | CROSS_REFERENCE |
| IMMIGRATION | 3 | 36 | 0 | 0.0 | 0.0 | 0 | — |
| FILE_PATH | 3 | 15 | 0 | 0.0 | 0.0 | 0 | FILE_PATH |
| API_KEY | 5 | 10 | 0 | 0.0 | 0.0 | 0 | API_KEY |
| JWT_TOKEN | 5 | 5 | 0 | 0.0 | 0.0 | 0 | JWT_TOKEN |
| PASSWORD_HASH | 5 | 5 | 1 | 0.2 | 0.0 | 0 | PASSWORD_HASH |
| DB_CONN_STRING | 5 | 5 | 5 | 1.0 | 0.0 | 0 | DB_CONN_STRING |
| SYSTEM_PROMPT | 5 | 5 | 0 | 0.0 | 0.0 | 0 | — |
| PRIVATE_KEY | 5 | 5 | 0 | 0.0 | 0.0 | 0 | PRIVATE_KEY |
| INTERNAL_IP | 4 | 5 | 5 | 1.0 | 1.0 | 0 | IP_ADDRESS |
| ARCHITECTURE | 3 | 5 | 5 | 1.0 | 0.0 | 0 | — |
