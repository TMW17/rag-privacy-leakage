# Subtask 2 — Answer-key inventory vs Presidio out-of-box coverage

- Source: `data/ground_truth/ground_truth_annotations.json`
- Total entities: **2190** across **31** types (metadata declares 35 specs; 31 types produced entities (4 specs generated 0))
- Answer-key offsets present: **False** → No char offsets in answer key -> reconstruct each document from ground_truth_index.json, locate each GT entity's text string, mark detected if a Presidio span overlaps an occurrence (any-label AND correct-label both reported).
- Presidio analyzer version (target): 2.2.359; coverage per https://microsoft.github.io/presidio/supported_entities/

## Summary by classification

| class | types | entities |
|---|--:|--:|
| out_of_box | 6 | 535 |
| out_of_box_partial | 4 | 393 |
| custom_needed | 3 | 330 |
| not_detectable_default | 18 | 932 |

## Per-type detail

| type | n | sev | presidio_label | class | note |
|---|--:|--:|---|---|---|
| PERSON | 130 | 4 | PERSON | out_of_box | NER-based; default spaCy model |
| HEALTH_RECORD_ID | 130 | 4 | (custom) HEALTH_RECORD_ID | custom_needed | No Presidio default; subtask-3 PatternRecognizer |
| NATIONAL_ID | 100 | 5 | (custom) NNI_DZ | custom_needed | Algerian NNI; no generic NATIONAL_ID (US_SSN etc. are country-specific, won't match DZ) |
| EMAIL | 100 | 4 | EMAIL_ADDRESS | out_of_box | Regex + RFC-822 validation |
| PHONE | 100 | 4 | PHONE_NUMBER | out_of_box | phonenumbers lib; may need DZ region config for full recall |
| ADDRESS | 100 | 4 | LOCATION | out_of_box_partial | NER LOCATION; full street addresses only partially covered |
| DOB | 100 | 4 | DATE_TIME | out_of_box | Broad: DATE_TIME flags all dates, not only DOB (precision caveat) |
| IBAN | 100 | 4 | IBAN_CODE | out_of_box | Presidio HAS IBAN_CODE (checksum); task listed IBAN as custom -> verify DZ IBAN passes mod-97 in step 4, build custom only if it misses |
| SURNAME_TITLE | 100 | 4 | PERSON | out_of_box_partial | PERSON NER may catch surname; honorific title not a PII label |
| SALARY | 100 | 3 | — | not_detectable_default | No MONEY/SALARY default recognizer |
| EMPLOYEE_ID | 100 | 3 | (custom) EMPLOYEE_ID | custom_needed | No Presidio default; subtask-3 PatternRecognizer |
| AGE_GENDER | 100 | 3 | — | not_detectable_default | AGE explicitly unsupported; gender ~ NRP only |
| PERFORMANCE | 100 | 2 | — | not_detectable_default | Semantic, not a PII entity |
| DEPARTMENT | 100 | 2 | — | not_detectable_default | Org metadata, no default |
| JOB_TITLE | 100 | 2 | — | not_detectable_default | No default |
| WORK_SCHEDULE | 100 | 2 | — | not_detectable_default | No default |
| OFFICE_LOCATION | 100 | 2 | LOCATION | out_of_box_partial | May surface via LOCATION NER |
| PROJECT | 100 | 2 | — | not_detectable_default | No default |
| TRAINING | 100 | 2 | — | not_detectable_default | No default |
| MEDICAL | 93 | 3 | MEDICAL_LICENSE | out_of_box_partial | Only licenses via default; clinical terms need transformers medical NER (not in default spaCy) |
| CROSS_REFERENCE | 41 | 3 | — | not_detectable_default | No default |
| IMMIGRATION | 36 | 3 | — | not_detectable_default | No default |
| FILE_PATH | 15 | 3 | — | not_detectable_default | No FILE_PATH entity (URL is distinct) |
| API_KEY | 10 | 5 | — | not_detectable_default | Secret; no default (would need custom regex, not in subtask-3 set) |
| JWT_TOKEN | 5 | 5 | — | not_detectable_default | Secret; no default |
| PASSWORD_HASH | 5 | 5 | — | not_detectable_default | Secret; no default |
| DB_CONN_STRING | 5 | 5 | — | not_detectable_default | Secret; no default |
| SYSTEM_PROMPT | 5 | 5 | — | not_detectable_default | Not PII |
| PRIVATE_KEY | 5 | 5 | — | not_detectable_default | Secret; CRYPTO is wallet-address, different |
| INTERNAL_IP | 5 | 4 | IP_ADDRESS | out_of_box | Regex + checksum |
| ARCHITECTURE | 5 | 3 | — | not_detectable_default | Not a PII entity |

## Custom recognizers required for subtask 3
- NATIONAL_ID (Algerian NNI)
- EMPLOYEE_ID
- HEALTH_RECORD_ID
- IBAN (verify default IBAN_CODE covers DZ in step 4; build custom only if it misses)
