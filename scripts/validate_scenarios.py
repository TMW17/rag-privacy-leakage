"""
validate_scenarios.py
=====================
CI-style pre-flight gate for the Phase 2 adversarial scenario registry.

Exit codes
----------
0  no validation errors AND all per-profile floors met (or file empty)
1  any validation error, missing required family, or --strict with unmet floors
2  no errors but some per-profile floors unmet (and not --strict)
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scenario_schema import AttackFamily, ExecutionMode, Priority, ScenarioSpec
from scripts.evaluation_engine import AttackerProfile

# ── Non-negotiable families (Phase2_Roadmap.md §9.1 cut T3) ──────────────────
_REQUIRED_FAMILIES = {
    AttackFamily.F1_DIRECT_PII,
    AttackFamily.F3_DIRECT_INJECTION,
    AttackFamily.F8_CORPUS_POISONING,
}

# ── Per-profile floor counts (Phase2_Roadmap.md Table 6) ─────────────────────
_PROFILE_FLOORS = {
    AttackerProfile.INTERNAL:    16,
    AttackerProfile.EXTERNAL:    24,
    AttackerProfile.ADMIN:        6,
    AttackerProfile.THIRD_PARTY:  4,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CI pre-flight gate for Phase 2 scenario registry."
    )
    parser.add_argument(
        "--file",
        default="scenarios/registry/v0_skeletons.json",
        help="Path to the scenario JSON array (default: scenarios/registry/v0_skeletons.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unmet per-profile floors as exit 1 instead of exit 2.",
    )
    args = parser.parse_args()

    # ── Resolve file path relative to CWD ────────────────────────────────────
    file_path = os.path.abspath(args.file)

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        print(f"ERROR: file not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {file_path}: {exc}")
        sys.exit(1)

    if not isinstance(raw, list):
        print(f"ERROR: expected a JSON array, got {type(raw).__name__}")
        sys.exit(1)

    if not raw:
        print("no scenarios to validate")
        sys.exit(0)

    total = len(raw)

    # ── Per-scenario validation (collect ALL errors, don't stop early) ────────
    # Checks b (maps_to_threat_row format), e (THIRD_PARTY → OFFLINE_ANALYSIS),
    # and f (non-THIRD_PARTY → LIVE_CHAT) are enforced inside ScenarioSpec.__post_init__
    # and will surface here as ValueError if violated.
    validation_errors: list = []  # (idx_or_None, scenario_id, message)
    specs: list = []

    for idx, d in enumerate(raw):
        if isinstance(d, dict):
            sid = d.get("scenario_id", f"<index {idx}>")
        else:
            sid = f"<index {idx}>"
        try:
            specs.append(ScenarioSpec.from_dict(d))
        except (KeyError, ValueError, TypeError) as exc:
            validation_errors.append((idx, sid, str(exc)))

    # ── Cross-scenario checks ─────────────────────────────────────────────────

    # a. Unique scenario_ids
    seen_ids: dict = {}
    for i, spec in enumerate(specs):
        if spec.scenario_id in seen_ids:
            validation_errors.append((
                None,
                spec.scenario_id,
                f"Duplicate scenario_id {spec.scenario_id!r} "
                f"(first seen at valid-spec index {seen_ids[spec.scenario_id]})",
            ))
        else:
            seen_ids[spec.scenario_id] = i

    # c. Required attack families covered
    present_families = {spec.attack_family for spec in specs}
    missing_families = _REQUIRED_FAMILIES - present_families

    # d. Per-profile floor counts
    profile_counts: Counter = Counter(spec.attacker_profile for spec in specs)
    unmet_floors: dict = {
        profile: (profile_counts.get(profile, 0), floor)
        for profile, floor in _PROFILE_FLOORS.items()
        if profile_counts.get(profile, 0) < floor
    }

    # ── Print summary ─────────────────────────────────────────────────────────
    skipped = total - len(specs)
    print(f"Total scenarios : {total}")
    if skipped:
        print(f"Skipped (errors): {skipped}")
    print()

    family_counts: Counter = Counter(spec.attack_family for spec in specs)
    priority_counts: Counter = Counter(spec.priority for spec in specs)
    mode_counts: Counter = Counter(spec.execution_mode for spec in specs)

    print("By attacker profile:")
    for profile in AttackerProfile:
        print(f"  {profile.value:<14} {profile_counts.get(profile, 0)}")
    print()

    print("By attack family:")
    for family in AttackFamily:
        print(f"  {family.value:<25} {family_counts.get(family, 0)}")
    print()

    print("By priority:")
    for priority in Priority:
        print(f"  {priority.value:<4} {priority_counts.get(priority, 0)}")
    print()

    print("By execution mode:")
    for mode in ExecutionMode:
        print(f"  {mode.value:<20} {mode_counts.get(mode, 0)}")
    print()

    if validation_errors:
        print(f"Validation errors ({len(validation_errors)}):")
        for idx, sid, msg in validation_errors:
            loc = f"index {idx}" if idx is not None else "cross-check"
            print(f"  [{loc}] {sid}: {msg}")
        print()

    if missing_families:
        print("Missing required attack families (non-negotiable per Phase2_Roadmap §9.1):")
        for family in sorted(missing_families, key=lambda f: f.value):
            print(f"  {family.value}")
        print()

    if unmet_floors:
        print("Unmet per-profile floor counts (Phase2_Roadmap Table 6):")
        for profile, (count, floor) in sorted(
            unmet_floors.items(), key=lambda kv: kv[0].value
        ):
            print(f"  {profile.value:<14} have {count:>3}, need >= {floor}")
        print()

    # ── Exit codes ────────────────────────────────────────────────────────────
    has_errors = bool(validation_errors) or bool(missing_families)
    has_unmet_floors = bool(unmet_floors)

    if has_errors:
        sys.exit(1)
    if has_unmet_floors:
        sys.exit(1 if args.strict else 2)
    sys.exit(0)


if __name__ == "__main__":
    main()
