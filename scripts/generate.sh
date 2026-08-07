#!/usr/bin/env bash
# 从 schemas/ + openapi/ 生成三端代码到 gen/。
# 生成物提交入库；CI 会重跑本脚本并校验无 diff（防手改漂移）。
# 工具全部固定版本 —— 升级工具 = 显式改本文件。
set -euo pipefail
cd "$(dirname "$0")/.."

SCHEMA=schemas/scholars.schema.json
OPENAPI=openapi/core.yaml

DATAMODEL_CODEGEN_VERSION=0.72.2   # koxudaxi/datamodel-code-generator
GO_JSONSCHEMA_VERSION=v0.24.1      # omissis/go-jsonschema
JSON2TS_VERSION=15.0.4             # json-schema-to-typescript
OPENAPI_TS_VERSION=7.13.0          # openapi-typescript

echo "==> python (pydantic v2)"
uvx --from "datamodel-code-generator==${DATAMODEL_CODEGEN_VERSION}" datamodel-codegen \
  --input "$SCHEMA" --input-file-type jsonschema \
  --output gen/python/scholar_contracts/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --use-schema-description --use-field-description \
  --disable-timestamp

echo "==> go structs"
go run "github.com/atombender/go-jsonschema@${GO_JSONSCHEMA_VERSION}" \
  -p contracts \
  --output gen/go/contracts/contracts.go \
  "$SCHEMA"

echo "==> typescript (entities + api)"
npx -y "json-schema-to-typescript@${JSON2TS_VERSION}" \
  -i "$SCHEMA" -o gen/ts/contracts.d.ts --bannerComment "" --unreachableDefinitions
npx -y "openapi-typescript@${OPENAPI_TS_VERSION}" "$OPENAPI" -o gen/ts/core-api.d.ts

echo "==> done. regenerate check: git diff --stat gen/"
