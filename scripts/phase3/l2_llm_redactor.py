"""
l2_llm_redactor.py — L2-LLM: a GENERALIZABLE LLM-based retrieval-time PII redactor.

Replaces Presidio (regex/NER) at L2 with a Claude call that redacts PII BY CATEGORY using the
model's general PII understanding. This is the GENERALIZABLE fix for the Task-0.1 recall gap
(prose salary, open-vocabulary medical, surname that Presidio misses: MEDICAL recall 0.0,
SURNAME 0.51) — explicitly **NOT** the in-sample L6 gazetteer (`l6_linkage.py`): the instruction
defines PII by *category*, never by a corpus value list, so it generalizes to unseen data.

POLICY (locked, pre-registered): redact the **sev≥3 PII classes** — matching Presidio-L2's sev≥3
threshold for a fair head-to-head — i.e. direct identifiers + sensitive attributes (names,
national/employee/health IDs, IBAN, salary INCLUDING in prose, medical conditions, addresses,
emails, phones, DOB, immigration). **PRESERVE** non-sensitive structural fields (department, job
title, office location, work schedule, project, training, performance) so benign utility is not
cratered. Honest ceiling: it therefore does NOT redact sev2 quasi-identifiers and CANNOT close the
genuine attribute→group LINKAGE third of the F2 residual — only the detector-recall gap. (See
results/phase3/linkability_diagnosis/FINDING.md.)

FAIL-SAFE: on API error, empty/over-long output, or chatty scaffolding, fall back to Presidio L2
(`presidio_bridge.redact`) — never return an unredacted chunk. The `fallbacks` counter is reported;
a high rate means the cell is a Presidio/LLM hybrid (comparison contaminated) and must be caveated.
Content-addressed cache dedups identical chunks (cost saver for THIS experiment; per-turn latency is
still reported uncached — it is the headline downside of the approach).
"""
import hashlib
import os
import re

import anthropic

from scripts.phase3.presidio_bridge import redact as _presidio_redact

_MODEL = "claude-sonnet-4-6"

_SYS = """You are a PII redaction filter for a retrieval-augmented system. Redact ALL personally \
identifiable and sensitive personal information in the user's text, replacing each span with a TYPED \
placeholder in square brackets. Redact by MEANING, not just format — catch PII written in prose.

REDACT (replace with the bracketed placeholder):
- person names -> [NAME]
- national IDs, employee IDs, health-record/MRN numbers, IBANs, account numbers -> [ID]
- salary / compensation / pay, INCLUDING in prose (e.g. "earns 95,000", "compensation of $106,307", \
"120,000 DA per year") -> [SALARY]
- medical conditions, diagnoses, health status (e.g. "diagnosed with anxiety", "has hypertension") -> [MEDICAL]
- home / street addresses -> [ADDRESS]
- email addresses -> [EMAIL]
- phone numbers -> [PHONE]
- dates of birth -> [DOB]
- immigration / visa / work-permit status -> [IMMIGRATION]

DO NOT redact (these are NOT sensitive identifiers and are needed for legitimate use — leave them verbatim):
- department names, job titles, office locations / buildings / floors, work schedules / working hours, \
project names, training status, performance descriptors.

Output ONLY the redacted text — no preamble, no explanation, no quotes, nothing else. Preserve all \
non-PII text and structure exactly."""

_SCAFFOLD = re.compile(r"^\s*(here is|here'?s|sure|i['’]ve|i have|the redacted|redacted text|below is|certainly)",
                       re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\[[A-Z_]+\]")


class LLMRedactor:
    """Generalizable per-chunk LLM redactor with Presidio fail-safe + content-addressed cache."""

    def __init__(self, model: str = _MODEL, dry_run: bool = False):
        self.model = model
        self.dry_run = dry_run
        self._client = None if dry_run else anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip())
        self._cache: dict[str, tuple[str, dict]] = {}
        self.calls = 0          # real API calls (cache misses)
        self.cache_hits = 0
        self.fallbacks = 0
        self.in_tok = 0
        self.out_tok = 0

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}|{text}".encode()).hexdigest()

    def _fallback(self, chunk: str, why: str) -> tuple[str, dict]:
        self.fallbacks += 1
        red = _presidio_redact([chunk], sev_threshold=3)["redacted"][0]
        return red, {"src": "presidio_fallback", "why": why}

    def redact(self, chunk: str) -> tuple[str, dict]:
        k = self._key(chunk)
        if k in self._cache:
            self.cache_hits += 1
            return self._cache[k]

        if self.dry_run:                       # $0 stub: deterministic marker, no API, no fallback
            out = (re.sub(r"\$\s?\d[\d,]*", "[SALARY]", chunk), {"src": "dry_stub"})
            self._cache[k] = out
            return out

        try:
            self.calls += 1
            resp = self._client.messages.create(
                model=self.model, temperature=0, max_tokens=1024,
                system=_SYS, messages=[{"role": "user", "content": chunk}])
            self.in_tok += resp.usage.input_tokens
            self.out_tok += resp.usage.output_tokens
            red = "".join(b.text for b in resp.content if b.type == "text").strip()
            if not red:
                out = self._fallback(chunk, "empty")
            elif len(red) > len(chunk) * 2 + 120:
                out = self._fallback(chunk, "over-long")
            elif _SCAFFOLD.match(red):
                out = self._fallback(chunk, "scaffolded")
            else:
                out = (red, {"src": "llm", "n_placeholders": len(_PLACEHOLDER.findall(red))})
        except Exception as e:                  # API/transport error -> safe fallback
            out = self._fallback(chunk, f"error:{type(e).__name__}:{str(e)[:60]}")

        self._cache[k] = out
        return out

    def stats(self) -> dict:
        total = self.calls + self.cache_hits
        return {"real_calls": self.calls, "cache_hits": self.cache_hits, "fallbacks": self.fallbacks,
                "fallback_rate": round(self.fallbacks / self.calls, 4) if self.calls else 0.0,
                "in_tok": self.in_tok, "out_tok": self.out_tok,
                "est_usd": round(self.in_tok * 3 / 1e6 + self.out_tok * 15 / 1e6, 4)}
