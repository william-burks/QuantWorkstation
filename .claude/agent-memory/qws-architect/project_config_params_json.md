---
name: Config node params_json property confirmed
description: Config.params_json is a documented property in data_dictionary.yaml — verified 2026-04-10
type: project
---

Config node has `params_json` (str, not nullable) documented in `qws_graph/docs/data_dictionary.yaml`. Contains JSON text blob of all config parameters. Also has `risk_params` as a separate JSON blob.

**Why:** QWS-0602 (Parameter Stability) reads params_json from Config nodes. Needed to confirm the property exists and is queryable.

**How to apply:** When reviewing stories that read Config parameters, params_json is the correct property name. First-class properties are also unpacked onto Config nodes for direct Cypher filtering.
