#!/usr/bin/env python3
"""Validate the shared JSON Schema contracts.

Checks, in order:
  1. Every *.v1.json in packages/contracts is a valid JSON Schema (draft 2020-12 meta-validation).
  2. Every example in packages/contracts/examples validates against its schema.
     File naming: <schema-title>__<label>.json  (e.g. signal.generated.v1__buy.json)
  3. Negative cases: deliberately invalid instances are rejected. This proves the
     constraints bite, not just that the schemas parse.

Exit code 0 on success, 1 on any failure.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "packages" / "contracts"
EXAMPLES = CONTRACTS / "examples"

FORMAT_CHECKER = FormatChecker()


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def schema_files() -> dict[str, Path]:
    found = {}
    for path in sorted(CONTRACTS.glob("*.v1.json")):
        found[path.name[: -len(".json")]] = path
    return found


def check_meta(schemas: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    for name, path in schemas.items():
        try:
            Draft202012Validator.check_schema(load(path))
            print(f"  meta OK    {name}")
        except SchemaError as exc:
            errors.append(f"meta-validation failed for {name}: {exc.message}")
            print(f"  meta FAIL  {name}: {exc.message}")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {path.name}: {exc}")
            print(f"  meta FAIL  {name}: invalid JSON")
    return errors


def check_examples(schemas: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    for example in sorted(EXAMPLES.glob("*.json")):
        title = example.name.split("__", 1)[0]
        if title not in schemas:
            errors.append(f"example {example.name} has no matching schema '{title}'")
            print(f"  example FAIL {example.name}: no schema")
            continue
        validator = Draft202012Validator(load(schemas[title]), format_checker=FORMAT_CHECKER)
        instance = load(example)
        problems = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        if problems:
            for p in problems:
                errors.append(f"{example.name}: {p.message}")
            print(f"  example FAIL {example.name}: {problems[0].message}")
        else:
            print(f"  example OK   {example.name}")
    return errors


def _mutate(base: dict, fn) -> dict:
    clone = copy.deepcopy(base)
    fn(clone)
    return clone


def check_negative(schemas: dict[str, Path]) -> list[str]:
    """Each case must FAIL validation. A pass here is a test failure."""
    errors: list[str] = []
    buy = load(EXAMPLES / "signal.generated.v1__buy.json")
    no_trade = load(EXAMPLES / "signal.generated.v1__no_trade.json")
    candle = load(EXAMPLES / "candle.closed.v1__1m.json")
    tick = load(EXAMPLES / "tick.normalized.v1__replay.json")

    cases = [
        ("signal: calibrated=true with null probability",
         "signal.generated.v1",
         _mutate(buy, lambda d: d.update(calibrated=True, probability=None))),
        ("signal: uncalibrated probability leaked",
         "signal.generated.v1",
         _mutate(buy, lambda d: d.update(probability=0.61))),
        ("signal: BUY without stop_loss",
         "signal.generated.v1",
         _mutate(buy, lambda d: d.update(stop_loss=None))),
        ("signal: NO_TRADE without reason_code",
         "signal.generated.v1",
         _mutate(no_trade, lambda d: d.update(reason_code=None))),
        ("signal: unknown action",
         "signal.generated.v1",
         _mutate(buy, lambda d: d.update(action="HOLD"))),
        ("candle: non-final candle published",
         "candle.closed.v1",
         _mutate(candle, lambda d: d.update(is_final=False))),
        ("candle: missing-bar with non-zero volume",
         "candle.closed.v1",
         _mutate(candle, lambda d: d.update(is_missing=True))),
        ("tick: price as JSON float (must be decimal string)",
         "tick.normalized.v1",
         _mutate(tick, lambda d: d.update(price=1412.5))),
        ("tick: data_mode outside enum",
         "tick.normalized.v1",
         _mutate(tick, lambda d: d.update(data_mode="PAPER"))),
        ("tick: missing provider_ts",
         "tick.normalized.v1",
         _mutate(tick, lambda d: d.pop("provider_ts"))),
    ]

    for label, title, instance in cases:
        if title not in schemas:
            errors.append(f"negative case '{label}': schema {title} missing")
            continue
        validator = Draft202012Validator(load(schemas[title]), format_checker=FORMAT_CHECKER)
        if validator.is_valid(instance):
            errors.append(f"negative case should have FAILED but passed: {label}")
            print(f"  neg  FAIL  {label} (accepted)")
        else:
            print(f"  neg  OK    {label}")
    return errors


def main() -> int:
    schemas = schema_files()
    if not schemas:
        print("No schemas found in packages/contracts", file=sys.stderr)
        return 1
    print(f"Schemas found: {len(schemas)}")

    print("\n[1/3] Meta-validation (draft 2020-12)")
    errors = check_meta(schemas)

    print("\n[2/3] Valid examples")
    errors += check_examples(schemas)

    print("\n[3/3] Negative cases (must be rejected)")
    errors += check_negative(schemas)

    print()
    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASSED: all schemas meta-valid, all examples valid, all negative cases rejected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
