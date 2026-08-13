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

# 5. Judge 结构化输出的维度必须与 rubric 完全一致。
#    rubric 是唯一事实来源；若两处漂移，评分会静默丢维度或报错，且历史分数不可比。
JUDGE_OUTPUT_TO_RUBRIC = {"TopicJudgeOutput": "rubrics/topic.v1.yaml"}
for out_def, rubric_path in JUDGE_OUTPUT_TO_RUBRIC.items():
    rubric = yaml.safe_load((ROOT / rubric_path).read_text())
    rubric_keys = {d["key"] for d in rubric["dimensions"]}
    scores = DEFS[out_def]["properties"]["dimensionScores"]
    schema_keys = set(scores["properties"])
    check(
        f"{out_def} dimensions == {rubric_path}",
        schema_keys == rubric_keys,
        f"schema-only={sorted(schema_keys - rubric_keys)} rubric-only={sorted(rubric_keys - schema_keys)}",
    )
    check(
        f"{out_def} requires every dimension",
        set(scores.get("required", [])) == rubric_keys,
        f"required={sorted(scores.get('required', []))}",
    )
    check(
        f"{out_def} forbids extra dimensions",
        scores.get("additionalProperties") is False,
        "additionalProperties 必须为 false，否则模型可臆造维度",
    )

# 6. 调度设置：默认值必须自身合法（core 首次 seed 会用它）
sched_defaults = {
    "sourceFetch": {"enabled": True, "defaultIntervalMinutes": 60},
    "topicScout": {
        "enabled": True,
        "times": ["08:00", "20:00"],
        "timezone": "Asia/Shanghai",
        "minNewItems": 5,
    },
    "topicEvaluate": {"enabled": True, "maxConcurrency": 2},
}
errs = list(validator_for("SchedulerSettings").iter_errors(sched_defaults))
check("default SchedulerSettings is valid", not errs, "; ".join(e.message for e in errs[:3]))

if failures:
    print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
    sys.exit(1)
print("\nall contract checks passed")
