#!/usr/bin/env python3
"""契约自检：rubric YAML 符合 schema、权重归一、队列注册表指向存在的 definition。
运行：uv run --no-project --with jsonschema --with pyyaml scripts/validate.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/scholars.schema.json").read_text())
DEFS = SCHEMA["definitions"]

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        failures.append(f"{name}: {detail}")
    print(("✓" if ok else "✗"), name, detail if not ok else "")


def validator_for(def_name: str) -> Draft7Validator:
    return Draft7Validator({"definitions": DEFS, "$ref": f"#/definitions/{def_name}"})


# 1. schema 本身合法
check("schema is valid draft-07", Draft7Validator.check_schema(SCHEMA) is None)

# 2. rubric 文件符合 RubricDefinition，且初始权重和为 1
for f in sorted((ROOT / "rubrics").glob("*.yaml")):
    if f.name.startswith("performance-weights"):
        continue
    data = yaml.safe_load(f.read_text())
    errs = list(validator_for("RubricDefinition").iter_errors(data))
    check(f"{f.name} matches RubricDefinition", not errs, "; ".join(e.message for e in errs[:3]))
    total = sum(d["initialWeight"] for d in data["dimensions"])
    check(f"{f.name} initialWeight sums to 1", math.isclose(total, 1.0, abs_tol=1e-6), f"sum={total}")
    keys = [d["key"] for d in data["dimensions"]]
    check(f"{f.name} dimension keys unique", len(keys) == len(set(keys)))

# 3. 表现分权重文件：每项符合 PerformanceWeights，且权重和为 1
pw_file = ROOT / "rubrics/performance-weights.v1.yaml"
pw = yaml.safe_load(pw_file.read_text())
for item in pw:
    errs = list(validator_for("PerformanceWeights").iter_errors(item))
    check(f"performance-weights[{item.get('platform')}] matches schema", not errs,
          "; ".join(e.message for e in errs[:3]))
    total = sum(item["weights"].values())
    check(f"performance-weights[{item.get('platform')}] sums to 1",
          math.isclose(total, 1.0, abs_tol=1e-6), f"sum={total}")
platforms = [i["platform"] for i in pw]
check("performance-weights covers all platforms",
      set(platforms) == set(DEFS["Platform"]["enum"]),
      f"got {platforms}")

# 4. 队列注册表指向存在的 definition
queues = json.loads((ROOT / "schemas/queues.json").read_text())["queues"]
for q, def_name in queues.items():
    check(f"queue {q} -> {def_name} exists", def_name in DEFS)

if failures:
    print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
    sys.exit(1)
print("\nall contract checks passed")
