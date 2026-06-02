"""
l1_filter.py — L1 input rail (regex + heuristic classifier).

FALLBACK implementation. NeMo Guardrails was the first choice but does NOT support the
project's Python 3.14 (nemoguardrails 0.22.0 declares requires_python "<3.14,>=3.10"; only the
obsolete 0.17.0 installs on 3.14 and it downgrades langchain-core, breaking the dep tree). So
this pure-stdlib regex+classifier rail runs instead. `ENGINE = "regex_classifier_fallback"`.

Blocks prompt-injection / jailbreak / encoding-obfuscation BEFORE the query reaches retrieval
or the SUT. classify_input() returns (blocked, signals); the classifier blocks when the number
of matched signal categories >= threshold (default 1 — any clear injection marker blocks).
Tuned to be FP-safe on benign enterprise-HR queries (no markers -> allowed).
"""
import base64
import binascii
import re

ENGINE = "regex_classifier_fallback"   # not NeMo (unsupported on Py 3.14)

# Each category is a clear prompt-injection / jailbreak marker. Patterns are specific enough
# that ordinary HR questions ("how many in Finance?", "what office is IT in?") match none.
_PATTERNS = {
    "instruction_override": [
        r"ignore\s+(?:all\s+|the\s+|your\s+|any\s+)?(?:previous|prior|above|earlier|preceding)\s+"
        r"(?:instruction|prompt|message|rule|context|direction)",
        r"disregard\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|instruction|rule)",
        r"forget\s+(?:all\s+|everything\s+|your\s+)?(?:previous|prior|instruction|rule)",
        r"override\s+(?:your\s+|the\s+)?(?:instruction|setting|filter|rule|guardrail|restriction)",
    ],
    "roleplay_jailbreak": [
        r"\bDAN\b", r"do\s+anything\s+now",
        r"\b(?:act\s+as|pretend\s+(?:to\s+be|you(?:'re|\s+are))|simulate\s+being|"
        r"roleplay\s+as|role-play\s+as|you\s+are\s+now)\b",
        r"\bunrestricted\b", r"\bjailbreak", r"developer\s+mode",
        r"\bno\s+(?:privacy\s+)?(?:restriction|filter|limitation|rule|guardrail)s?\b",
        r"without\s+(?:any\s+)?(?:restriction|filter|limitation|rule|guardrail)",
    ],
    "system_probe": [
        r"(?:reveal|show|print|output|repeat|disclose|dump)\s+(?:me\s+)?(?:your\s+|the\s+)?"
        r"(?:system\s+prompt|instruction|configuration|guardrail|rule)s?",
        r"(?:privacy|safety|content|security)\s+filters?\s+(?:are\s+)?"
        r"(?:disabled|off|removed|bypassed|turned\s+off)",
    ],
    "admin_impersonation": [
        r"\badmin\s+mode\b", r"\bmaintenance\s+(?:session|mode)\b",
        r"\bdebug\s+(?:mode|request|session)\b", r"developer\s+access",
        r"\[[^\]]*(?:admin|debug|maintenance|system|root)[^\]]*\]",  # [HR ADMIN MODE ...]
    ],
}
_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in _PATTERNS.items()}


def _has_base64_blob(text):
    """Detect a decodable base64 blob (>=32 chars) often used to smuggle injections."""
    for m in re.finditer(r"[A-Za-z0-9+/]{32,}={0,2}", text):
        s = m.group(0)
        if len(s) % 4 == 0:
            try:
                base64.b64decode(s, validate=True)
                return True
            except (binascii.Error, ValueError):
                continue
    return False


def classify_input(query, threshold=1):
    """Return (blocked: bool, signals: list[dict]). Block when matched categories >= threshold."""
    signals = []
    for cat, regexes in _COMPILED.items():
        for rx in regexes:
            m = rx.search(query)
            if m:
                signals.append({"category": cat, "match": m.group(0)[:60]})
                break  # one signal per category
    if "base64" in query.lower() or _has_base64_blob(query):
        signals.append({"category": "encoding", "match": "base64"})
    return (len(signals) >= threshold), signals
