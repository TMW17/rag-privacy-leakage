"""
recognizers.py — single source of truth for the Phase-3 Presidio custom recognizers.

SIDE-EFFECT-FREE: defines build_custom_recognizers() only (no I/O, no analysis, no
module-level execution). This is the canonical recognizer definition for L2 redaction;
imported by scripts/phase3/presidio_worker.py.

The function body is a VERBATIM copy of the bin_a recognizers validated in Task 0.1
(scripts/phase3/presidio_recall.py, which retains its own inline copy and is left frozen
so its canonical presidio_recall.json output is untouched — and so the worker never
triggers presidio_recall.py's module-level analysis on import). Keep the two identical;
any future recognizer change goes here (the worker's source of truth).

Runs ONLY under .venv-presidio (Python 3.11) — imports presidio_analyzer, which cannot
import under the project's Python 3.14.
"""
from presidio_analyzer import PatternRecognizer, Pattern


# -------------------------------------------------- subtask 3: recognizers
def build_custom_recognizers(set_name="bin_a"):
    # 4 Algerian-ID recognizers (always on) — verified 1.0 recall
    recs = [
        PatternRecognizer(
            supported_entity="NNI_DZ",
            patterns=[Pattern("nni_9digit", r"\b\d{9}\b", 0.4)],
            context=["national", "national id", "nni", "nin", "id national"],
        ),
        PatternRecognizer(
            supported_entity="EMPLOYEE_ID",
            patterns=[Pattern("emp_id", r"\bEMP-\d{5}\b", 0.85)],
            context=["employee", "employee id", "staff", "emp"],
        ),
        PatternRecognizer(
            supported_entity="HEALTH_RECORD_ID",
            patterns=[Pattern("mrn", r"\bMRN-\d{5}\b", 0.85)],
            context=["health", "medical", "patient", "record", "mrn"],
        ),
        PatternRecognizer(
            supported_entity="IBAN_DZ",
            patterns=[Pattern("iban_dz", r"\bDZ\d{2}-\d{5}-\d{10}-\d{2}\b", 0.9)],
            context=["iban", "bank", "account"],
        ),
    ]
    if set_name != "bin_a":
        return recs
    # bin-(a): legitimate, generalizable structured detectors (NOT corpus-value gazetteers)
    recs += [
        PatternRecognizer(
            supported_entity="API_KEY",
            patterns=[Pattern("api_key_sk", r"\bsk-(?:ant-)?[A-Za-z0-9]{20,}\b", 0.9)],
            context=["api", "key", "secret", "openai", "anthropic"],
        ),
        PatternRecognizer(
            supported_entity="JWT_TOKEN",
            patterns=[Pattern("jwt", r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", 0.9)],
            context=["jwt", "token", "bearer"],
        ),
        PatternRecognizer(
            supported_entity="PASSWORD_HASH",
            patterns=[Pattern("bcrypt", r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", 0.9)],
            context=["password", "hash", "bcrypt"],
        ),
        PatternRecognizer(
            supported_entity="PRIVATE_KEY",
            patterns=[Pattern("pem", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", 0.95)],
            context=["private", "key", "rsa", "pem"],
        ),
        PatternRecognizer(
            supported_entity="DB_CONN_STRING",
            patterns=[Pattern("db_uri", r"\b[a-zA-Z][\w+]*://[^\s:@/]+:[^\s:@/]+@[\w.-]+", 0.85)],
            context=["db", "database", "connection", "postgres", "dsn"],
        ),
        PatternRecognizer(
            supported_entity="FILE_PATH",
            patterns=[Pattern("unix_path", r"(?:/[\w.-]+){2,}", 0.6)],
            context=["path", "file", "directory", "paths"],
        ),
        PatternRecognizer(
            supported_entity="CROSS_REFERENCE",
            patterns=[Pattern("hr_ref", r"\bhr_file_\d{3}\b", 0.85)],
            context=["employee", "reference", "ref", "referenced"],
        ),
        PatternRecognizer(
            supported_entity="PHONE_DZ",
            patterns=[Pattern("dz_phone", r"\+213-\d{3}-\d{6}", 0.8)],
            context=["phone", "tel", "mobile"],
        ),
        PatternRecognizer(
            supported_entity="SALARY",
            patterns=[Pattern("salary_ctx",
                              r"(?:[Ss]alary|[Cc]ompensation)\s*[:\-]?\s*\$?\d{3,7}", 0.7)],
            context=["salary", "compensation", "pay"],
        ),
    ]
    return recs
