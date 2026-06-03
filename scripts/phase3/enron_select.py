"""
enron_select.py — pick ~100 Enron emails that CONTAIN body PII (for the generalization probe).

An email with no PII can't leak -> the test would be vacuous. So we select emails whose BODY carries
groundable PII (phone / address / direct personal-contact), preferring personal/business signatures
over bulk-marketing (skip http-heavy / unsubscribe). Records the PII found per email so the adapted
F1/F2 scenarios can be GROUNDED in real slice values (not fabricated). FREE (file scan, no API).

Output: results/phase3/enron/selection.json (selected emails + extracted PII + grounding candidates).
"""
import email
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAILDIR = os.path.join(ROOT, "data/external/enron/maildir")
OUT = os.path.join(ROOT, "results/phase3/enron")
TARGET = 100
MAX_SCAN = 60000          # bound the walk

PHONE = re.compile(r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?!\d)")
ADDR = re.compile(r"\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:St|Street|Ave|Avenue|Rd|Road|"
                  r"Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pkwy|Plaza|Suite|Ste)\b")
MONEY = re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def body_of(raw):
    try:
        msg = email.message_from_string(raw)
    except Exception:
        return "", {}
    hdr = {"from": msg.get("X-From") or msg.get("From") or "", "subject": msg.get("Subject") or ""}
    if msg.is_multipart():
        parts = [p.get_payload(decode=False) for p in msg.walk() if p.get_content_type() == "text/plain"]
        body = "\n".join(p for p in parts if isinstance(p, str))
    else:
        body = msg.get_payload()
    return (body if isinstance(body, str) else ""), hdr


def main():
    os.makedirs(OUT, exist_ok=True)
    selected, scanned = [], 0
    users = sorted(os.listdir(MAILDIR))
    for u in users:
        udir = os.path.join(MAILDIR, u)
        if not os.path.isdir(udir):
            continue
        for dp, _, files in os.walk(udir):
            for fn in files:
                if scanned >= MAX_SCAN or len(selected) >= TARGET:
                    break
                scanned += 1
                fp = os.path.join(dp, fn)
                try:
                    raw = open(fp, encoding="latin-1").read()
                except Exception:
                    continue
                body, hdr = body_of(raw)
                if not body or len(body) > 8000:
                    continue
                low = body.lower()
                if low.count("http") > 2 or "unsubscribe" in low or "click here" in low:
                    continue                          # skip bulk/marketing
                phones = PHONE.findall(body)
                addrs = ADDR.findall(body)
                money = MONEY.findall(body)
                ssn = SSN.findall(body)
                if not (phones or addrs or ssn):       # require groundable contact/ID PII
                    continue
                # grab the line containing the first phone + the preceding non-empty line (signature/name)
                ctx = ""
                if phones:
                    lines = [l.strip() for l in body.splitlines()]
                    for i, l in enumerate(lines):
                        if PHONE.search(l):
                            prev = next((lines[j] for j in range(i - 1, max(i - 4, -1), -1) if lines[j].strip()), "")
                            ctx = (prev + " | " + l).strip()
                            break
                selected.append({
                    "user": u, "path": os.path.relpath(fp, ROOT), "from": hdr["from"][:80],
                    "subject": hdr["subject"][:80], "n_chars": len(body),
                    "phones": list(dict.fromkeys(phones))[:5], "addresses": addrs[:3],
                    "money": money[:5], "ssn": ssn[:3], "phone_context": ctx[:160]})
            if scanned >= MAX_SCAN or len(selected) >= TARGET:
                break
        if scanned >= MAX_SCAN or len(selected) >= TARGET:
            break

    by_user = Counter(s["user"] for s in selected)
    n_phone = sum(1 for s in selected if s["phones"])
    n_addr = sum(1 for s in selected if s["addresses"])
    n_money = sum(1 for s in selected if s["money"])
    summary = {"n_selected": len(selected), "n_scanned": scanned, "by_user": dict(by_user),
               "n_with_phone": n_phone, "n_with_address": n_addr, "n_with_money": n_money,
               "n_with_ssn": sum(1 for s in selected if s["ssn"])}
    json.dump({"summary": summary, "emails": selected}, open(os.path.join(OUT, "selection.json"), "w"),
              indent=2, ensure_ascii=False)
    print("=" * 78); print("ENRON SLICE SELECTION (free scan)"); print("=" * 78)
    print(json.dumps(summary, indent=2))
    print("\nSample grounding candidates (person/contact in body):")
    for s in [x for x in selected if x["phone_context"]][:8]:
        print(f"  [{s['user']}] {s['phone_context']}")
    print(f"\nWrote {OUT}/selection.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
