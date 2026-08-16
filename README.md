# scholar-shared

scholars-ai 军团的**语言中立契约层**：JSON Schema + OpenAPI + rubric YAML 为单一事实来源，codegen 出 Go / Python / TS 三端代码。架构见 [spec/SPEC-001 §3](https://github.com/scholars-ai/spec/blob/main/specs/SPEC-001-architecture.md)。

## 结构

```
schemas/scholars.schema.json   实体/枚举/job payload/rubric 结构（draft-07，单一事实来源）
schemas/queues.json            队列注册表：queue 名 → payload definition
openapi/core.yaml              scholar-core 的 REST API 契约
rubrics/*.yaml                 评分 rubric 数据（版本化，SPEC-004）
profiles/*.yaml                平台专家档案：语气、结构、硬约束和 rubric 引用（SPEC-005）
gen/go/                        生成物 → scholar-core 以 go module 引用
gen/python/                    生成物（Pydantic v2）→ scholar-agents 引用
gen/ts/                        生成物 → scholar-client 引用
scripts/generate.sh            codegen 管线（工具版本全固定）
scripts/validate.py            契约自检（schema 合法/权重归一/队列指向存在）
```

## 修改契约的流程

1. 改 `schemas/` / `openapi/` / `rubrics/` / `profiles/`（重大变更先改 [spec](https://github.com/scholars-ai/spec)）
2. `./scripts/generate.sh` 重新生成三端代码
3. `uv run --no-project --with jsonschema --with pyyaml scripts/validate.py` 自检
4. 生成物一并提交。CI 会重跑 codegen 并校验 `gen/` 无 diff（防手改漂移）

## 消费方式

- **Go（core）**：`require github.com/scholars-ai/scholar-shared/gen/go`
- **Python（agents）**：以 git 子路径依赖引入 `gen/python/scholar_contracts`
- **TS（client）**：`@scholars-ai/contracts` 随 `contracts-vX.Y.Z` tag 打包为公开 GitHub Release asset；client 依赖固定版本的 tarball，无需 GitHub Packages token

## 发布 TypeScript 契约

1. 修改契约并重新生成代码
2. 更新 `gen/ts/package.json` 的 `version`
3. 合并并推送 `main`
4. 创建并推送与版本一致的 tag，例如 `contracts-v0.2.0`

`release-ts-contracts.yml` 会校验 tag 与 package version 一致，执行 `npm pack`，并把 tarball 发布到同名的公开 GitHub Release。Client 应固定依赖该 Release URL；新版本发布后再显式升级，避免 `main` 的变化无意间破坏构建。

## 约定

- rubric 的 `initialWeight` 仅是初始值；**生效权重存 DB（WeightSet）**，由校准环节人工确认后调整（SPEC-004 §4）
- 队列名禁止手写字符串，一律从 `queues.json` 读取
- breaking change 先修订 spec，再改 schema
