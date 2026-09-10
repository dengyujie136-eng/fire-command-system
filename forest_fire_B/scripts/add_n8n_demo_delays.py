from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "n8n_backups" / "aCEy4kc1oQgz8ehx_final_get_enabled.json"
OUTPUT = ROOT / "n8n_backups" / "aCEy4kc1oQgz8ehx_slow_demo.json"

DEFAULT_DELAY_MS = 1800
MAX_DELAY_MS = 10000
DELAY_MARKER = "// __CODEx_DEMO_DELAY__"


def clamp_js_default() -> str:
    return f"""
{DELAY_MARKER}
const __readDemoDelayMs = () => {{
  let value = $json.demo_delay_ms ?? $json.delayMs ?? $json.query?.delayMs ?? $json.body?.delayMs;
  try {{
    if (value === undefined) value = $('__DATA_NODE_NAME__').first().json.demo_delay_ms;
  }} catch (e) {{}}
  const parsed = Number(value ?? {DEFAULT_DELAY_MS});
  if (!Number.isFinite(parsed)) return {DEFAULT_DELAY_MS};
  return Math.max(0, Math.min(parsed, {MAX_DELAY_MS}));
}};
const __demoDelayMs = __readDemoDelayMs();
if (__demoDelayMs > 0) {{
  await new Promise(resolve => setTimeout(resolve, __demoDelayMs));
}}
""".strip()


def main() -> None:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    workflows = raw if isinstance(raw, list) else [raw]
    workflow = workflows[0]

    data_node = next(
        node for node in workflow["nodes"]
        if node["id"] == "249664d1-891f-4836-bb9e-26aadaa5bc2c"
    )
    router_node = next(
        node for node in workflow["nodes"]
        if node["id"] == "c89ecf88-0564-4754-af5b-0d7ae78395c4"
    )

    router_node["parameters"]["jsCode"] = f"""
const body = $json.body || $json.query || $json.params || $json;
const toNumber = (value, fallback) => {{
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}};
const overrides = {{ ...(body.overrides || {{}}) }};
for (const key of ['windSpeed', 'windDirection', 'temp', 'humidity', 'rainfall24h', 'slope', 'aspect', 'fuelMoisture', 'fuelLoad', 'crownDryness']) {{
  if (body[key] !== undefined && overrides[key] === undefined) overrides[key] = toNumber(body[key], body[key]);
}}
const rawDelay = body.delayMs ?? body.demo_delay_ms ?? overrides.delayMs;
const demoDelayMs = Math.max(0, Math.min(toNumber(rawDelay, {DEFAULT_DELAY_MS}), {MAX_DELAY_MS}));
return [{{
  json: {{
    trigger_source: body.trigger_source || 'webhook',
    scene_id: body.scene_id || 'forest-fire-demo-001',
    commander_instruction: body.commander_instruction || '东侧风速增大，优先保护村庄和输电通道，调度无人机复核火线。',
    overrides,
    demo_delay_ms: demoDelayMs,
    received_at: new Date().toISOString()
  }}
}}];
""".strip()

    data_code = data_node["parameters"]["jsCode"]
    if "const demoDelayMs =" not in data_code:
        data_code = data_code.replace(
            "const sceneId = inbound.scene_id || 'forest-fire-demo-001';",
            f"""
const sceneId = inbound.scene_id || 'forest-fire-demo-001';
const rawDelay = inbound.demo_delay_ms ?? inbound.delayMs ?? inbound.overrides?.delayMs;
const parsedDelay = Number(rawDelay ?? {DEFAULT_DELAY_MS});
const demoDelayMs = Number.isFinite(parsedDelay) ? Math.max(0, Math.min(parsedDelay, {MAX_DELAY_MS})) : {DEFAULT_DELAY_MS};
""".strip(),
        )
        data_code = data_code.replace(
            "scene_id: sceneId,",
            "scene_id: sceneId,\n    demo_delay_ms: demoDelayMs,",
            1,
        )
        data_node["parameters"]["jsCode"] = data_code

    delay_prefix = clamp_js_default().replace("__DATA_NODE_NAME__", data_node["name"].replace("\\", "\\\\").replace("'", "\\'"))
    delayed = 0
    for node in workflow["nodes"]:
        if node.get("type") != "n8n-nodes-base.code":
            continue
        code = node.get("parameters", {}).get("jsCode", "")
        if DELAY_MARKER in code:
            continue
        node["parameters"]["jsCode"] = f"{delay_prefix}\n\n{code}"
        delayed += 1

    note = {
        "parameters": {
            "content": (
                "### 录屏演示模式\n"
                f"每个关键 Code 节点默认停顿 {DEFAULT_DELAY_MS / 1000:.1f} 秒。\n\n"
                "浏览器测试可加参数：`delayMs=3000`，表示每步停 3 秒。"
            ),
            "height": 220,
            "width": 520,
            "color": 3,
        },
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [-180, -520],
        "id": "1a8c6697-3330-4b24-b701-note-delay",
        "name": "说明：录屏慢速模式",
    }
    workflow["nodes"] = [node for node in workflow["nodes"] if node.get("id") != note["id"]]
    workflow["nodes"].append(note)

    OUTPUT.write_text(json.dumps(workflows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Added delay prefix to {delayed} code nodes")
    print(f"Default delay: {DEFAULT_DELAY_MS} ms, max delay: {MAX_DELAY_MS} ms")


if __name__ == "__main__":
    main()
