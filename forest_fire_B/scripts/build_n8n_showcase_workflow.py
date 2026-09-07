from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "n8n_backups" / "aCEy4kc1oQgz8ehx_original.json"
OUTPUT = ROOT / "n8n_backups" / "aCEy4kc1oQgz8ehx_showcase.json"


def code_node(nodes: dict[str, dict], name: str, new_name: str, position: list[int], js_code: str) -> None:
    node = nodes[name]
    node["name"] = new_name
    node["type"] = "n8n-nodes-base.code"
    node["typeVersion"] = 2
    node["position"] = position
    node["parameters"] = {"jsCode": js_code}
    node.pop("credentials", None)


def make_code_node(node_id: str, name: str, position: list[int], js_code: str) -> dict:
    return {
        "parameters": {"jsCode": js_code},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "id": node_id,
        "name": name,
    }


def make_webhook_node(
    node_id: str,
    name: str,
    position: list[int],
    *,
    method: str,
    path: str,
    webhook_id: str,
) -> dict:
    return {
        "parameters": {
            "httpMethod": method,
            "path": path,
            "responseMode": "lastNode",
            "options": {},
        },
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2.1,
        "position": position,
        "id": node_id,
        "name": name,
        "webhookId": webhook_id,
    }


def make_sticky_note(
    node_id: str,
    name: str,
    position: list[int],
    content: str,
    *,
    width: int,
    height: int,
    color: int,
) -> dict:
    return {
        "parameters": {
            "content": content,
            "height": height,
            "width": width,
            "color": color,
        },
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": position,
        "id": node_id,
        "name": name,
    }


def main() -> None:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    workflow = copy.deepcopy(raw[0] if isinstance(raw, list) else raw)
    by_name = {node["name"]: node for node in workflow["nodes"]}

    workflow["name"] = "星火智援-多因子耦合多智能体闭环展示"
    workflow["description"] = (
        "展示型 n8n 工作流：以态势包、风险包、方案包、任务包、反馈包串联"
        "环境评估、火势推演、决策指挥、资源调度和反馈学习智能体。"
    )
    workflow["active"] = True
    workflow["settings"] = {
        **workflow.get("settings", {}),
        "executionOrder": "v1",
        "binaryMode": "separate",
    }
    workflow["pinData"] = {}

    by_name["When clicking ‘Execute workflow’"]["name"] = "手动演示触发"
    by_name["When clicking ‘Execute workflow’"]["position"] = [-760, -120]

    by_name["Webhook1"]["name"] = "Webhook 主流程入口"
    by_name["Webhook1"]["position"] = [-760, 80]
    by_name["Webhook1"]["parameters"] = {
        "httpMethod": "POST",
        "path": "main-process",
        "responseMode": "lastNode",
        "options": {},
    }

    by_name["Webhook"]["name"] = "Webhook 外部执行反馈入口"
    by_name["Webhook"]["position"] = [1480, 300]
    by_name["Webhook"]["parameters"] = {
        "httpMethod": "POST",
        "path": "fire-feedback",
        "responseMode": "lastNode",
        "options": {},
    }

    code_node(
        by_name,
        "数据源路由器",
        "00 数据源路由器",
        [-520, 80],
        r"""
const body = $json.body || $json.query || $json.params || $json;
return [{
  json: {
    trigger_source: body.trigger_source || 'webhook',
    scene_id: body.scene_id || 'forest-fire-demo-001',
    commander_instruction: body.commander_instruction || '东侧风速增大，优先保护村庄和输电通道，调度无人机复核火线。',
    overrides: body.overrides || {},
    received_at: new Date().toISOString()
  }
}];
""".strip(),
    )

    code_node(
        by_name,
        "DataGenerator",
        "01 多源感知与样例数据源",
        [-300, -40],
        r"""
const inbound = $json || {};
const overrides = inbound.overrides || {};
const sceneId = inbound.scene_id || 'forest-fire-demo-001';

const firePoint = overrides.firePoint || { lat: 28.530278, lon: 101.269444, confidence: 0.91 };
const weather = {
  windSpeed: overrides.windSpeed ?? 12.6,
  windDirection: overrides.windDirection ?? 82,
  temp: overrides.temp ?? 31.4,
  humidity: overrides.humidity ?? 28,
  rainfall24h: overrides.rainfall24h ?? 0.8
};
const terrain = {
  slope: overrides.slope ?? 23.5,
  aspect: overrides.aspect ?? 96,
  elevation: overrides.elevation ?? 1840,
  roadAccessibility: overrides.roadAccessibility ?? 0.64
};
const vegetation = {
  fuelMoisture: overrides.fuelMoisture ?? 11.5,
  fuelLoad: overrides.fuelLoad ?? 0.72,
  crownDryness: overrides.crownDryness ?? 0.68,
  vegetationIndex: overrides.vegetationIndex ?? 0.58
};

const sensing = {
  satellite: {
    thermal_anomaly: true,
    confidence: 0.86,
    products: ['wide_area_screening', 'fireline_boundary', 'temporal_verification']
  },
  uav: {
    available: true,
    thermal_confirmed: true,
    confidence: 0.92,
    eta_minutes: 12
  },
  tower: {
    smoke_detected: true,
    confidence: 0.78,
    camera_quality: 0.82
  },
  canopy: {
    crown_temp_anomaly: true,
    confidence: 0.69,
    device_status: 'sample_plot_enhancement'
  },
  ground: {
    temperature_rise: 4.8,
    smoke_ppm: 31,
    soil_moisture: 13,
    confidence: 0.74
  }
};

const resources = [
  { id: 'R-FIRE-01', type: 'fire_crew', name: '北侧消防组', location: { lat: 28.534, lon: 101.242 }, count: 18, status: 'available', eta: 20 },
  { id: 'R-FIRE-02', type: 'fire_crew', name: '南侧消防组', location: { lat: 28.515, lon: 101.292 }, count: 12, status: 'available', eta: 28 },
  { id: 'R-UAV-01', type: 'uav', name: '侦查无人机', location: { lat: 28.526, lon: 101.263 }, count: 1, status: 'available', eta: 10 },
  { id: 'R-UAV-02', type: 'uav', name: '通信中继无人机', location: { lat: 28.524, lon: 101.266 }, count: 1, status: 'available', eta: 14 },
  { id: 'R-WATER-01', type: 'water_tanker', name: '水罐车组', location: { lat: 28.518, lon: 101.255 }, count: 4, status: 'available', eta: 25 },
  { id: 'R-MED-01', type: 'medical', name: '县医院应急点', location: { lat: 28.506, lon: 101.279 }, count: 8, status: 'available', eta: 35 }
];

const targets = [
  { id: 'T-VILLAGE-E', name: '东侧村庄', type: 'village', direction: 'east', exposure: 0.88, priority: 'critical' },
  { id: 'T-POWER-01', name: '输电通道', type: 'power_line', direction: 'north-east', exposure: 0.74, priority: 'high' },
  { id: 'T-SCENIC-01', name: '景区入口', type: 'scenic_spot', direction: 'south-east', exposure: 0.56, priority: 'medium' }
];

return [{
  json: {
    execution_id: `${sceneId}-${Date.now()}`,
    scene_id: sceneId,
    timestamp: new Date().toISOString(),
    commander_instruction: inbound.commander_instruction || '东侧风速增大，优先保护村庄和输电通道，调度无人机复核火线。',
    scene: { firePoint, weather, terrain, vegetation, sensing, targets },
    resources,
    product_chain: ['可信感知', '火势推演', '协同决策', '任务调度', '反馈学习'],
    display_note: '展示数据：用于说明多源感知、多因子耦合、多智能体闭环，不等同于真实火场指挥命令。'
  }
}];
""".strip(),
    )

    code_node(
        by_name,
        "EnvAgent",
        "02 环境评估Agent（态势包）",
        [-20, -160],
        r"""
const source = $('01 多源感知与样例数据源').first().json;
const { weather, terrain, vegetation, sensing, targets, firePoint } = source.scene;

const evidenceWeights = {
  satellite: 0.28,
  uav: 0.26,
  tower: 0.18,
  canopy: 0.13,
  ground: 0.15
};
const evidence = {
  satellite: sensing.satellite.confidence,
  uav: sensing.uav.confidence,
  tower: sensing.tower.confidence,
  canopy: sensing.canopy.confidence,
  ground: sensing.ground.confidence
};
const fireConfidence = Object.entries(evidenceWeights)
  .reduce((sum, [key, weight]) => sum + evidence[key] * weight, 0);

const windFactor = Math.min(1, weather.windSpeed / 18);
const humidityFactor = Math.max(0, 1 - weather.humidity / 70);
const slopeFactor = Math.min(1, terrain.slope / 35);
const fuelDryness = Math.max(0, 1 - vegetation.fuelMoisture / 35);
const crownFactor = vegetation.crownDryness;
const roadPenalty = Math.max(0, 1 - terrain.roadAccessibility);
const targetExposure = Math.max(...targets.map(t => t.exposure));

const fireDangerIndex = (
  windFactor * 0.22 +
  humidityFactor * 0.13 +
  slopeFactor * 0.18 +
  fuelDryness * 0.18 +
  crownFactor * 0.10 +
  targetExposure * 0.12 +
  fireConfidence * 0.07
);
const level = fireDangerIndex >= 0.72 ? 'extreme' : fireDangerIndex >= 0.55 ? 'high' : fireDangerIndex >= 0.35 ? 'moderate' : 'low';

return [{
  json: {
    package_type: 'situation_package',
    agent: 'EnvironmentAssessmentAgent',
    scene_id: source.scene_id,
    fire_point: { lat: firePoint.lat, lon: firePoint.lon, confidence: fireConfidence },
    weather_summary: {
      wind_speed: weather.windSpeed,
      wind_direction: weather.windDirection,
      humidity: weather.humidity,
      temperature: weather.temp,
      danger_level: level
    },
    terrain_impact: {
      slope: terrain.slope,
      aspect: terrain.aspect,
      road_accessibility: terrain.roadAccessibility,
      slope_risk: slopeFactor >= 0.65 ? 'high' : slopeFactor >= 0.4 ? 'moderate' : 'low',
      aspect_effect: '坡向与主导风向接近，东向/东北向蔓延敏感。'
    },
    fuel_status: {
      moisture: vegetation.fuelMoisture,
      fuel_load: vegetation.fuelLoad,
      crown_dryness: vegetation.crownDryness,
      combustibility: fuelDryness >= 0.65 ? 'high' : fuelDryness >= 0.4 ? 'moderate' : 'low'
    },
    evidence_chain: Object.entries(evidence).map(([sourceName, confidence]) => ({
      source: sourceName,
      confidence,
      weight: evidenceWeights[sourceName],
      contribution: Number((confidence * evidenceWeights[sourceName]).toFixed(3))
    })),
    fire_confidence: Number(fireConfidence.toFixed(3)),
    factor_scores: {
      wind_factor: Number(windFactor.toFixed(3)),
      humidity_factor: Number(humidityFactor.toFixed(3)),
      slope_factor: Number(slopeFactor.toFixed(3)),
      fuel_dryness: Number(fuelDryness.toFixed(3)),
      crown_factor: Number(crownFactor.toFixed(3)),
      road_penalty: Number(roadPenalty.toFixed(3)),
      target_exposure: Number(targetExposure.toFixed(3))
    },
    surrounding_risks: targets.map(t => `${t.name}:${t.priority}:${t.direction}`),
    required_actions: ['无人机热成像复核', '下风向重点目标保护', '道路可达性复核', '持续刷新火线边界'],
    risk_hint: `态势风险为 ${level}，主要受风速、坡度、可燃物干燥度和东侧重点目标暴露共同驱动。`
  }
}];
""".strip(),
    )

    code_node(
        by_name,
        "ParseEnvOutput",
        "02b 态势包结构校验",
        [240, -160],
        r"""
const situation = $input.first().json;
const required = ['package_type', 'agent', 'fire_point', 'factor_scores', 'evidence_chain'];
const missing = required.filter(key => situation[key] === undefined);
if (missing.length) throw new Error(`态势包缺少字段: ${missing.join(', ')}`);
return [{ json: situation }];
""".strip(),
    )

    code_node(
        by_name,
        "FireSpread",
        "03 火势推演Agent（机理推演包）",
        [-20, 80],
        r"""
const source = $('01 多源感知与样例数据源').first().json;
const { weather, terrain, vegetation, firePoint } = source.scene;

const baseSpreadRate = 4.2; // m/min, demonstration baseline
const windMultiplier = 1 + Math.min(1.8, weather.windSpeed / 10);
const slopeMultiplier = 1 + Math.min(1.2, terrain.slope / 28);
const fuelMultiplier = 0.65 + Math.max(0, 1 - vegetation.fuelMoisture / 32);
const crownMultiplier = 1 + vegetation.crownDryness * 0.35;
const spreadRate = baseSpreadRate * windMultiplier * slopeMultiplier * fuelMultiplier * crownMultiplier;

const dir = weather.windDirection;
const rad = (90 - dir) * Math.PI / 180;
const stepMinutes = [30, 60, 120, 180, 240];
const areaCurve = stepMinutes.map((minute, index) => {
  const hours = minute / 60;
  const area = 0.42 + Math.pow(spreadRate * hours / 35, 1.22) * (1 + index * 0.09);
  const centerShiftKm = spreadRate * minute / 1000;
  return {
    elapsed_minutes: minute,
    area_km2: Number(area.toFixed(3)),
    center: {
      lat: Number((firePoint.lat + Math.sin(rad) * centerShiftKm / 110.576).toFixed(6)),
      lon: Number((firePoint.lon + Math.cos(rad) * centerShiftKm / 98.0).toFixed(6))
    }
  };
});
const latest = areaCurve[areaCurve.length - 1];
const previous = areaCurve[areaCurve.length - 2];
const latestGrowth = (latest.area_km2 - previous.area_km2) / ((latest.elapsed_minutes - previous.elapsed_minutes) / 60);
const intensity = latestGrowth >= 2.5 ? 'extreme' : latestGrowth >= 1.3 ? 'high' : latestGrowth >= 0.6 ? 'moderate' : 'low';

const directionText = dir >= 45 && dir <= 135 ? 'east' : dir > 135 && dir <= 225 ? 'south' : dir > 225 && dir <= 315 ? 'west' : 'north';

return [{
  json: {
    package_type: 'spread_package',
    agent: 'FireSpreadAgent',
    mechanism: 'Rothermel simplified + ForeFire output adapter display',
    input_coupling_from_environment: ['wind_speed', 'wind_direction', 'slope', 'fuel_moisture', 'crown_dryness'],
    spread_rate_m_per_min: Number(spreadRate.toFixed(3)),
    latest_growth_km2_per_hour: Number(latestGrowth.toFixed(3)),
    latest_spread_intensity: intensity,
    main_spread_direction: directionText,
    area_growth_curve: areaCurve,
    high_risk_periods: areaCurve.filter(p => p.elapsed_minutes >= 120),
    final_bbox: [
      Number((latest.center.lon - 0.016).toFixed(6)),
      Number((latest.center.lat - 0.012).toFixed(6)),
      Number((latest.center.lon + 0.019).toFixed(6)),
      Number((latest.center.lat + 0.014).toFixed(6))
    ],
    priority_protection_directions: directionText === 'east' ? ['east', 'north-east'] : [directionText],
    coupling_notes: [
      '风速提高使火头推进速度增大。',
      '坡度与坡向影响热对流和可达性。',
      '可燃物含水率降低会放大蔓延强度。',
      '树冠干燥度用于补强冠层火风险。'
    ]
  }
}];
""".strip(),
    )

    by_name["Merge"]["name"] = "04 智能体输出汇聚"
    by_name["Merge"]["position"] = [520, -40]
    by_name["Merge"]["parameters"] = {"mode": "append"}

    code_node(
        by_name,
        "RiskFusion",
        "05 多因子耦合Agent（风险包）",
        [760, -40],
        r"""
const items = $input.all().map(item => item.json);
const situation = items.find(item => item.package_type === 'situation_package');
const spread = items.find(item => item.package_type === 'spread_package');
if (!situation || !spread) throw new Error('需要同时输入态势包和火势推演包。');

const factors = situation.factor_scores;
const spreadIntensity = Math.min(1, spread.spread_rate_m_per_min / 22);
const growthPressure = Math.min(1, spread.latest_growth_km2_per_hour / 3.5);
const targetExposure = factors.target_exposure;
const resourcePressure = Math.min(1, (spread.area_growth_curve.at(-1).area_km2 / 8) * (1 + factors.road_penalty * 0.5));

const mainEffects = {
  wind: factors.wind_factor * 0.17,
  humidity_drought: factors.humidity_factor * 0.09,
  slope: factors.slope_factor * 0.11,
  fuel: factors.fuel_dryness * 0.14,
  crown: factors.crown_factor * 0.07,
  evidence_confidence: situation.fire_confidence * 0.08,
  spread_intensity: spreadIntensity * 0.14,
  target_exposure: targetExposure * 0.11
};

const couplingTerms = {
  wind_slope: factors.wind_factor * factors.slope_factor * 0.09,
  weather_fuel: factors.wind_factor * factors.fuel_dryness * factors.humidity_factor * 0.08,
  terrain_fuel_crown: factors.slope_factor * factors.fuel_dryness * factors.crown_factor * 0.07,
  spread_target: spreadIntensity * targetExposure * 0.08,
  resource_access: resourcePressure * factors.road_penalty * 0.04
};

const riskScore = Object.values(mainEffects).reduce((a, b) => a + b, 0)
  + Object.values(couplingTerms).reduce((a, b) => a + b, 0);
const riskLevel = riskScore >= 0.78 ? 'extreme' : riskScore >= 0.58 ? 'high' : riskScore >= 0.38 ? 'moderate' : 'low';

const couplingMatrix = [
  { from: '气象风场', to: '地形坡度', term: 'wind_slope', mechanism: '风坡同向时加速火头推进', weight: 0.09 },
  { from: '风速/湿度', to: '可燃物含水率', term: 'weather_fuel', mechanism: '干热大风降低细小可燃物含水率', weight: 0.08 },
  { from: '坡度', to: '树冠干燥度', term: 'terrain_fuel_crown', mechanism: '坡面热对流和冠层干燥共同提高冠火风险', weight: 0.07 },
  { from: '蔓延强度', to: '重点目标暴露', term: 'spread_target', mechanism: '火线推进方向与村庄/输电通道暴露叠加', weight: 0.08 },
  { from: '资源可达性', to: '道路通行', term: 'resource_access', mechanism: '道路受阻会放大调度时间风险', weight: 0.04 }
];

return [{
  json: {
    package_type: 'risk_package',
    agent: 'RiskFusionAgent',
    risk_score: Number(riskScore.toFixed(3)),
    risk_level: riskLevel,
    main_effects: Object.fromEntries(Object.entries(mainEffects).map(([k, v]) => [k, Number(v.toFixed(3))])),
    coupling_terms: Object.fromEntries(Object.entries(couplingTerms).map(([k, v]) => [k, Number(v.toFixed(3))])),
    coupling_matrix: couplingMatrix,
    situation_package: situation,
    spread_package: spread,
    predicted_affected_zones: situation.surrounding_risks,
    recommended_priority: riskLevel === 'extreme' ? 'immediate_response' : riskLevel === 'high' ? 'high_priority' : 'routine',
    agent_coupling_edges: [
      { from: 'EnvironmentAssessmentAgent', to: 'FireSpreadAgent', data: '气象/地形/可燃物约束' },
      { from: 'FireSpreadAgent', to: 'CommandDecisionAgent', data: '蔓延方向/强度/风险时段' },
      { from: 'RiskFusionAgent', to: 'CommandDecisionAgent', data: '多因子耦合风险分数' }
    ]
  }
}];
""".strip(),
    )

    code_node(
        by_name,
        "DecisionAgent",
        "06 决策指挥Agent（方案包）",
        [1020, -40],
        r"""
const riskPackage = $input.first().json;
const situation = riskPackage.situation_package;
const spread = riskPackage.spread_package;
const source = $('01 多源感知与样例数据源').first().json;
const resources = source.resources;

function resourceCount(type) {
  return resources.filter(r => r.type === type).reduce((sum, r) => sum + (r.count || 1), 0);
}
function scorePlan(plan) {
  return Number((
    0.30 * plan.safety_margin +
    0.25 * plan.response_efficiency +
    0.20 * plan.resource_match +
    0.20 * plan.expected_control_effect -
    0.15 * plan.execution_difficulty
  ).toFixed(2));
}
function safetyRules(plan) {
  const flags = [];
  const reasons = [];
  let status = 'available';
  if (riskPackage.risk_level === 'high' || riskPackage.risk_level === 'extreme') {
    if (!plan.tasks.some(t => t.type === 'evacuation' || t.type === 'protect_key_targets')) {
      status = 'downgraded';
      flags.push('missing_evacuation_or_key_target_protection');
      reasons.push('高风险方案必须包含疏散或重点目标保护。');
    }
  }
  if (situation.weather_summary.wind_speed >= 12 && plan.tasks.some(t => t.type === 'low_altitude_uav_recon')) {
    status = 'downgraded';
    flags.push('uav_low_altitude_limited_by_wind');
    reasons.push('风速超过 12 m/s，低空无人机任务降级为中高空复核。');
  }
  if (resourceCount('fire_crew') < 24 && plan.plan_id !== 'PLAN-C') {
    status = 'downgraded';
    flags.push('crew_capacity_tight');
    reasons.push('消防员可用数量偏紧，激进/均衡方案需增加安全冗余。');
  }
  return { status_adjustment: status, flags, reasons };
}

const direction = spread.main_spread_direction;
const priority = spread.priority_protection_directions.join(', ');
const plans = [
  {
    plan_id: 'PLAN-A',
    name: '火头压制与重点目标前置保护',
    plan_type: 'aggressive',
    strategy: `沿 ${direction} 火头方向快速建立压制线，同时保护 ${priority} 方向重点目标。`,
    target_area: `${priority} sector near bbox ${JSON.stringify(spread.final_bbox)}`,
    required_resources: ['R-FIRE-01', 'R-UAV-01', 'R-WATER-01'],
    safety_margin: 76,
    response_efficiency: 84,
    resource_match: 72,
    expected_control_effect: 82,
    execution_difficulty: 66,
    tasks: [
      { type: 'protect_key_targets', action: 'deploy crews to village and power-line buffer' },
      { type: 'uav_recon', action: 'map active perimeter at medium altitude' },
      { type: 'water_supply', action: 'stage water tankers near safe access point' }
    ]
  },
  {
    plan_id: 'PLAN-B',
    name: '隔离带构建与分段围控',
    plan_type: 'balanced',
    strategy: '先建立安全隔离带，再按火线分段推进，兼顾控制效率与人员安全。',
    target_area: `outer perimeter around bbox ${JSON.stringify(spread.final_bbox)}`,
    required_resources: ['R-FIRE-01', 'R-FIRE-02', 'R-UAV-02', 'R-WATER-01'],
    safety_margin: 84,
    response_efficiency: 76,
    resource_match: 80,
    expected_control_effect: 78,
    execution_difficulty: 52,
    tasks: [
      { type: 'evacuation', action: 'prepare evacuation corridor outside final bbox' },
      { type: 'perimeter_suppression', action: 'split fireline into crew sectors' },
      { type: 'communication_relay', action: 'deploy aerial relay for command links' },
      { type: 'water_supply', action: 'secure tanker shuttle route' }
    ]
  },
  {
    plan_id: 'PLAN-C',
    name: '保守疏散与持续监测',
    plan_type: 'conservative',
    strategy: '优先人员疏散、交通管制和外围监测，等待下一轮火线边界更新后再压制。',
    target_area: `${direction} spread corridor and evacuation exits`,
    required_resources: ['R-FIRE-02', 'R-UAV-01', 'R-MED-01'],
    safety_margin: 90,
    response_efficiency: 62,
    resource_match: 74,
    expected_control_effect: 62,
    execution_difficulty: 38,
    tasks: [
      { type: 'evacuation', action: 'move exposed personnel away from spread corridor' },
      { type: 'uav_recon', action: 'refresh perimeter intelligence' },
      { type: 'medical_standby', action: 'stage medical team near safe camp' }
    ]
  }
].map(plan => {
  const safety = safetyRules(plan);
  const scored = { ...plan, risk_level: riskPackage.risk_level, score: scorePlan(plan), safety_rules: safety, status: safety.status_adjustment };
  scored.reasons = [
    `耦合风险 ${riskPackage.risk_score} / ${riskPackage.risk_level}`,
    ...safety.reasons
  ];
  return scored;
});

const available = plans.filter(p => p.status === 'available');
const recommended = (available.length ? available : plans).sort((a, b) => b.score - a.score)[0];
recommended.status = available.includes(recommended) ? 'recommended' : 'recommended_with_warnings';
recommended.reasons.push('综合安全裕度、响应效率、资源匹配和控制效果后评分最高。');

return [{
  json: {
    package_type: 'plan_package',
    agent: 'CommandDecisionAgent',
    scoring_formula: 'score = 0.30*safety_margin + 0.25*response_efficiency + 0.20*resource_match + 0.20*expected_control_effect - 0.15*execution_difficulty',
    risk_package: riskPackage,
    candidate_plans: plans,
    recommended_plan: recommended,
    blocked_or_downgraded_plans: plans.filter(p => p.status === 'downgraded' || p.status === 'blocked'),
    agent_coupling_edges: [
      ...riskPackage.agent_coupling_edges,
      { from: 'CommandDecisionAgent', to: 'ResourceDispatchAgent', data: '推荐方案/安全规则/资源需求' }
    ]
  }
}];
""".strip(),
    )

    code_node(
        by_name,
        "CleanDecisionJSON",
        "06b 方案包校验与排序",
        [1260, -40],
        r"""
const planPackage = $input.first().json;
if (!Array.isArray(planPackage.candidate_plans) || !planPackage.recommended_plan) {
  throw new Error('方案包缺少 candidate_plans 或 recommended_plan。');
}
planPackage.candidate_plans = planPackage.candidate_plans
  .slice()
  .sort((a, b) => b.score - a.score);
planPackage.plan_count = planPackage.candidate_plans.length;
planPackage.recommended_plan_id = planPackage.recommended_plan.plan_id;
return [{ json: planPackage }];
""".strip(),
    )

    by_name["Switch"]["name"] = "07 推荐方案路由"
    by_name["Switch"]["position"] = [1480, -60]
    by_name["Switch"]["parameters"] = {
        "rules": {
            "values": [
                {
                    "conditions": {
                        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                        "conditions": [
                            {
                                "leftValue": "={{ $json.recommended_plan.plan_id }}",
                                "rightValue": "PLAN-A",
                                "operator": {"type": "string", "operation": "equals"},
                                "id": "route-plan-a",
                            }
                        ],
                        "combinator": "and",
                    },
                    "renameOutput": True,
                    "outputKey": "PLAN-A 火头压制",
                },
                {
                    "conditions": {
                        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                        "conditions": [
                            {
                                "leftValue": "={{ $json.recommended_plan.plan_id }}",
                                "rightValue": "PLAN-B",
                                "operator": {"type": "string", "operation": "equals"},
                                "id": "route-plan-b",
                            }
                        ],
                        "combinator": "and",
                    },
                    "renameOutput": True,
                    "outputKey": "PLAN-B 分段围控",
                },
                {
                    "conditions": {
                        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3},
                        "conditions": [
                            {
                                "leftValue": "={{ $json.recommended_plan.plan_id }}",
                                "rightValue": "PLAN-C",
                                "operator": {"type": "string", "operation": "equals"},
                                "id": "route-plan-c",
                            }
                        ],
                        "combinator": "and",
                    },
                    "renameOutput": True,
                    "outputKey": "PLAN-C 保守疏散",
                },
            ]
        },
        "options": {},
    }

    dispatch_js = r"""
const planPackage = $input.first().json;
const source = $('01 多源感知与样例数据源').first().json;
const selectedPlan = planPackage.recommended_plan;
const firePoint = source.scene.firePoint;

function distanceKm(a, b) {
  const dx = (b.lon - a.lon) * 98.0;
  const dy = (b.lat - a.lat) * 110.576;
  return Math.sqrt(dx * dx + dy * dy);
}
function route(from, to, mode) {
  const d = distanceKm(from, to);
  const offset = mode === 'safe' ? 0.006 : mode === 'backup' ? -0.004 : 0;
  return {
    mode,
    waypoints: [
      from,
      { lat: Number(((from.lat + to.lat) / 2 + offset).toFixed(6)), lon: Number(((from.lon + to.lon) / 2 - offset).toFixed(6)) },
      to
    ],
    distance_km: Number((d * (mode === 'safe' ? 1.28 : mode === 'backup' ? 1.16 : 1)).toFixed(3)),
    estimated_time_min: Math.round(d * (mode === 'safe' ? 4.0 : 3.2) + 12)
  };
}

const matchedResources = source.resources.filter(r => selectedPlan.required_resources.includes(r.id));
const tasks = matchedResources.map((resource, index) => {
  const taskType = resource.type === 'uav' ? 'recon_or_relay'
    : resource.type === 'water_tanker' ? 'water_supply'
    : resource.type === 'medical' ? 'medical_standby'
    : selectedPlan.tasks[index % selectedPlan.tasks.length]?.type || 'field_support';
  return {
    task_id: `TASK-${selectedPlan.plan_id}-${index + 1}`,
    resource_id: resource.id,
    resource_name: resource.name,
    resource_type: resource.type,
    task_type: taskType,
    target: firePoint,
    main_route: route(resource.location, firePoint, 'safe'),
    backup_route: route(resource.location, firePoint, 'backup'),
    evacuation_route: {
      mode: 'evacuation',
      exit_points: [
        { lat: Number((firePoint.lat - 0.025).toFixed(6)), lon: Number((firePoint.lon - 0.035).toFixed(6)) },
        { lat: Number((firePoint.lat - 0.018).toFixed(6)), lon: Number((firePoint.lon + 0.028).toFixed(6)) }
      ]
    },
    estimated_eta_min: resource.eta,
    priority: selectedPlan.risk_level === 'extreme' ? 'critical' : taskType === 'medical_standby' ? 'high' : 'critical',
    status: 'planned',
    feedback_required: true
  };
});

const taskPackage = {
  package_type: 'task_package',
  agent: 'ResourceDispatchAgent',
  plan_id: selectedPlan.plan_id,
  plan_type: selectedPlan.plan_type,
  selected_strategy: selectedPlan.strategy,
  risk_level: selectedPlan.risk_level,
  timestamp: new Date().toISOString(),
  resources_used: matchedResources.map(r => r.id),
  tasks,
  safety_checks: selectedPlan.safety_rules,
  execution_instructions: [
    selectedPlan.strategy,
    '每个任务必须回传位置、阻断、资源消耗和火线变化。',
    '若风速继续升高或道路受阻，进入反馈学习节点触发重规划。'
  ],
  dispatch_coupling: {
    from_plan_package: selectedPlan.plan_id,
    to_feedback_package: 'task_status + resource_consumption + observed_fireline',
    front_end_panels: ['任务列表', '路线规划', '无人机调度', '物资人员调度']
  },
  status: 'dispatched'
};

return [{ json: taskPackage }];
""".strip()

    code_node(by_name, "plan_A", "07A 资源调度Agent（PLAN-A）", [1740, -260], dispatch_js)
    code_node(by_name, "plan_B", "07B 资源调度Agent（PLAN-B）", [1740, -60], dispatch_js)
    code_node(by_name, "plan_C", "07C 资源调度Agent（PLAN-C）", [1740, 140], dispatch_js)

    code_node(
        by_name,
        "构建反馈请求体",
        "08 执行反馈包（状态回传）",
        [2020, -60],
        r"""
const taskPackage = $input.first().json;
const source = $('01 多源感知与样例数据源').first().json;
const riskPackage = $('05 多因子耦合Agent（风险包）').first().json;

const feedbackPackage = {
  package_type: 'feedback_package',
  agent: 'FeedbackBuilder',
  execution_id: source.execution_id,
  scene_id: source.scene_id,
  plan_id: taskPackage.plan_id,
  task_package: taskPackage,
  generated_at: new Date().toISOString(),
  feedback_type: 'simulated_execution_feedback',
  task_status: taskPackage.tasks.map((task, index) => ({
    task_id: task.task_id,
    resource_id: task.resource_id,
    status: index === 0 && riskPackage.risk_level !== 'low' ? 'blocked_need_replan' : 'executing',
    progress: index === 0 ? 0.35 : 0.62,
    eta_delta_min: index === 0 ? 9 : 0,
    message: index === 0 ? '东侧道路受烟雾影响，建议切换备用路线并提高无人机复核频次。' : '按计划推进，持续回传。'
  })),
  observed_fireline_update: {
    direction: riskPackage.spread_package.main_spread_direction,
    latest_growth_km2_per_hour: Number((riskPackage.spread_package.latest_growth_km2_per_hour * 1.08).toFixed(3)),
    confidence: 0.82
  },
  resource_consumption: {
    water_tanker_rounds: 2,
    uav_battery_drop_percent: 18,
    fire_hose_rolls: 12,
    medical_standby: true
  },
  model_feedback: {
    coupling_terms_to_watch: Object.keys(riskPackage.coupling_terms).filter(k => riskPackage.coupling_terms[k] >= 0.03),
    suggested_weight_update: {
      resource_access: '+0.02 when blocked routes are reported',
      spread_target: '+0.01 when target exposure is confirmed by UAV'
    }
  },
  triggers: {
    need_replan: true,
    reasons: ['route_blocked', 'growth_rate_updated', 'resource_consumption_reported']
  }
};

return [{ json: feedbackPackage }];
""".strip(),
    )

    code_node(
        by_name,
        "HTTP Request",
        "09 反馈学习Agent（闭环校准）",
        [2280, -60],
        r"""
const feedback = $input.first().json;
const riskPackage = $('05 多因子耦合Agent（风险包）').first().json;

const routeBlocked = feedback.task_status?.some(t => t.status === 'blocked_need_replan');
const growthIncreased = feedback.observed_fireline_update?.latest_growth_km2_per_hour
  > riskPackage.spread_package.latest_growth_km2_per_hour;

const learningPackage = {
  package_type: 'learning_package',
  agent: 'FeedbackLearningAgent',
  scene_id: feedback.scene_id || 'external-feedback',
  plan_id: feedback.plan_id || feedback.payload?.plan_id || 'unknown',
  received_feedback_type: feedback.feedback_type || 'external_feedback',
  closed_loop_result: {
    need_replan: Boolean(routeBlocked || growthIncreased || feedback.triggers?.need_replan),
    update_risk_level: growthIncreased && riskPackage.risk_level === 'moderate' ? 'high' : riskPackage.risk_level,
    update_reason: [
      routeBlocked ? '执行路线受阻，反馈给资源调度与路径规划。' : null,
      growthIncreased ? '实测火线增长率高于推演，反馈给火势推演参数。' : null,
      '资源消耗回流到物资/人员调度面板。'
    ].filter(Boolean)
  },
  parameter_updates: {
    coupling_weight_resource_access_delta: routeBlocked ? 0.02 : 0,
    spread_growth_bias_delta: growthIncreased ? 0.08 : 0,
    evidence_confidence_note: '无人机/前线反馈作为下一轮态势包的高权重证据。'
  },
  feedback_edges: [
    { from: 'ResourceDispatchAgent', to: 'FeedbackLearningAgent', data: '任务状态/资源消耗/路线受阻' },
    { from: 'FeedbackLearningAgent', to: 'EnvironmentAssessmentAgent', data: '现场证据权重修正' },
    { from: 'FeedbackLearningAgent', to: 'FireSpreadAgent', data: '实测火线增长率校准' },
    { from: 'FeedbackLearningAgent', to: 'CommandDecisionAgent', data: '规则库与候选方案阈值修正' }
  ],
  raw_feedback: feedback,
  generated_at: new Date().toISOString()
};

return [{ json: learningPackage }];
""".strip(),
    )

    code_node(
        by_name,
        "构建反馈包",
        "08b 外部反馈包标准化",
        [1740, 300],
        r"""
const body = $json.body || $json;
return [{
  json: {
    package_type: 'feedback_package',
    agent: 'ExternalFeedbackAdapter',
    execution_id: body.execution_id || `external-${Date.now()}`,
    scene_id: body.scene_id || body.payload?.scene_id || 'forest-fire-demo-001',
    plan_id: body.plan_id || body.payload?.plan_id || 'external',
    generated_at: new Date().toISOString(),
    feedback_type: body.feedback_type || 'external_field_feedback',
    task_status: body.task_status || [],
    observed_fireline_update: body.observed_fireline_update || {},
    resource_consumption: body.resource_consumption || {},
    triggers: body.triggers || { need_replan: true, reasons: ['external_feedback_received'] },
    payload: body.payload || body
  }
}];
""".strip(),
    )

    final_node = make_code_node(
        "b3d3bca1-159a-4b6b-9276-frontend0001",
        "10 前端展示输出（五包闭环）",
        [2540, -60],
        r"""
const learning = $input.first().json;
const situation = $('02 环境评估Agent（态势包）').first().json;
const spread = $('03 火势推演Agent（机理推演包）').first().json;
const risk = $('05 多因子耦合Agent（风险包）').first().json;
const plan = $('06 决策指挥Agent（方案包）').first().json;
const feedback = learning.raw_feedback || {};
const task = feedback.task_package || null;

return [{
  json: {
    status: 'showcase_closed_loop_generated',
    generated_at: new Date().toISOString(),
    architecture: {
      title: '星火智援多因子耦合多智能体闭环',
      agents: ['EnvironmentAssessmentAgent', 'FireSpreadAgent', 'RiskFusionAgent', 'CommandDecisionAgent', 'ResourceDispatchAgent', 'FeedbackLearningAgent'],
      data_packages: ['situation_package', 'risk_package', 'plan_package', 'task_package', 'feedback_package', 'learning_package'],
      purpose: '展示火情发现、态势研判、火势推演、协同决策、资源调度与反馈复盘的闭环链路。'
    },
    packages: {
      situation_package: situation,
      risk_package: risk,
      plan_package: {
        recommended_plan_id: plan.recommended_plan_id,
        recommended_plan: plan.recommended_plan,
        candidate_plans: plan.candidate_plans,
        blocked_or_downgraded_plans: plan.blocked_or_downgraded_plans
      },
      task_package: task,
      feedback_package: feedback,
      learning_package: learning
    },
    front_end_payload: {
      scene_id: situation.scene_id,
      fire_point: situation.fire_point,
      risk_level: risk.risk_level,
      risk_score: risk.risk_score,
      spread_direction: spread.main_spread_direction,
      latest_growth_km2_per_hour: spread.latest_growth_km2_per_hour,
      recommended_plan_id: plan.recommended_plan_id || plan.recommended_plan.plan_id,
      recommended_plan_name: plan.recommended_plan.name,
      need_replan: learning.closed_loop_result.need_replan,
      map_layers: ['fireline', 'risk_heatmap', 'resources', 'routes', 'targets'],
      dashboard_cards: [
        { name: '态势包', value: situation.risk_hint },
        { name: '风险包', value: `${risk.risk_level} / ${risk.risk_score}` },
        { name: '方案包', value: plan.recommended_plan.name },
        { name: '反馈包', value: learning.closed_loop_result.update_reason.join('；') }
      ]
    }
  }
}];
""".strip(),
    )

    sticky_notes = [
        make_sticky_note(
            "1a8c6697-3330-4b24-b701-note000001",
            "说明：五包闭环",
            [-760, -520],
            (
                "### 五包闭环展示\n"
                "态势包 -> 风险包 -> 方案包 -> 任务包 -> 反馈包\n\n"
                "用于答辩展示：每个包都是前端可消费的结构化 JSON，"
                "反馈包会回流到态势、推演和决策节点，体现闭环优化。"
            ),
            width=560,
            height=260,
            color=4,
        ),
        make_sticky_note(
            "1a8c6697-3330-4b24-b701-note000002",
            "说明：多因子耦合",
            [680, -520],
            (
                "### 多因子耦合机制\n"
                "主效应：风速、湿度、坡度、可燃物、树冠干燥度、证据置信度、蔓延强度、目标暴露。\n\n"
                "耦合项：风-坡、气象-可燃物、地形-树冠、蔓延-目标、资源-道路。"
            ),
            width=640,
            height=280,
            color=5,
        ),
        make_sticky_note(
            "1a8c6697-3330-4b24-b701-note000003",
            "说明：智能体耦合",
            [1460, -520],
            (
                "### 智能体之间的耦合\n"
                "环境评估Agent提供气象/地形/可燃物约束；火势推演Agent提供火线方向和强度；"
                "决策指挥Agent基于风险包生成候选方案；资源调度Agent转成任务和路线；"
                "反馈学习Agent根据阻断、消耗和实测火线触发重规划。"
            ),
            width=780,
            height=280,
            color=6,
        ),
    ]

    browser_get_webhook = make_webhook_node(
        "b3d3bca1-159a-4b6b-9276-getwebhook01",
        "Webhook 浏览器GET入口",
        [-760, 260],
        method="GET",
        path="main-process",
        webhook_id="browser-get-main-process",
    )

    workflow["nodes"] = [
        node for node in workflow["nodes"]
        if node["name"] not in {"Ollama Chat Model", "Ollama Chat Model1"}
    ]
    workflow["nodes"].append(final_node)
    workflow["nodes"].extend(sticky_notes)
    workflow["nodes"].append(browser_get_webhook)

    workflow["connections"] = {
        "手动演示触发": {
            "main": [[{"node": "01 多源感知与样例数据源", "type": "main", "index": 0}]]
        },
        "Webhook 主流程入口": {
            "main": [[{"node": "00 数据源路由器", "type": "main", "index": 0}]]
        },
        "Webhook 浏览器GET入口": {
            "main": [[{"node": "00 数据源路由器", "type": "main", "index": 0}]]
        },
        "00 数据源路由器": {
            "main": [[{"node": "01 多源感知与样例数据源", "type": "main", "index": 0}]]
        },
        "01 多源感知与样例数据源": {
            "main": [[
                {"node": "02 环境评估Agent（态势包）", "type": "main", "index": 0},
                {"node": "03 火势推演Agent（机理推演包）", "type": "main", "index": 0},
            ]]
        },
        "02 环境评估Agent（态势包）": {
            "main": [[{"node": "02b 态势包结构校验", "type": "main", "index": 0}]]
        },
        "02b 态势包结构校验": {
            "main": [[{"node": "04 智能体输出汇聚", "type": "main", "index": 1}]]
        },
        "03 火势推演Agent（机理推演包）": {
            "main": [[{"node": "04 智能体输出汇聚", "type": "main", "index": 0}]]
        },
        "04 智能体输出汇聚": {
            "main": [[{"node": "05 多因子耦合Agent（风险包）", "type": "main", "index": 0}]]
        },
        "05 多因子耦合Agent（风险包）": {
            "main": [[{"node": "06 决策指挥Agent（方案包）", "type": "main", "index": 0}]]
        },
        "06 决策指挥Agent（方案包）": {
            "main": [[{"node": "06b 方案包校验与排序", "type": "main", "index": 0}]]
        },
        "06b 方案包校验与排序": {
            "main": [[{"node": "07 推荐方案路由", "type": "main", "index": 0}]]
        },
        "07 推荐方案路由": {
            "main": [
                [{"node": "07A 资源调度Agent（PLAN-A）", "type": "main", "index": 0}],
                [{"node": "07B 资源调度Agent（PLAN-B）", "type": "main", "index": 0}],
                [{"node": "07C 资源调度Agent（PLAN-C）", "type": "main", "index": 0}],
            ]
        },
        "07A 资源调度Agent（PLAN-A）": {
            "main": [[{"node": "08 执行反馈包（状态回传）", "type": "main", "index": 0}]]
        },
        "07B 资源调度Agent（PLAN-B）": {
            "main": [[{"node": "08 执行反馈包（状态回传）", "type": "main", "index": 0}]]
        },
        "07C 资源调度Agent（PLAN-C）": {
            "main": [[{"node": "08 执行反馈包（状态回传）", "type": "main", "index": 0}]]
        },
        "08 执行反馈包（状态回传）": {
            "main": [[{"node": "09 反馈学习Agent（闭环校准）", "type": "main", "index": 0}]]
        },
        "Webhook 外部执行反馈入口": {
            "main": [[{"node": "08b 外部反馈包标准化", "type": "main", "index": 0}]]
        },
        "08b 外部反馈包标准化": {
            "main": [[{"node": "09 反馈学习Agent（闭环校准）", "type": "main", "index": 0}]]
        },
        "09 反馈学习Agent（闭环校准）": {
            "main": [[{"node": "10 前端展示输出（五包闭环）", "type": "main", "index": 0}]]
        },
    }

    OUTPUT.write_text(json.dumps([workflow], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"nodes={len(workflow['nodes'])} connections={len(workflow['connections'])}")


if __name__ == "__main__":
    main()
