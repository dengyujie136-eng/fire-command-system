# 鏅烘収娑堥槻鎸囨尌绯荤粺 API 鏂囨。

鏇存柊鏃堕棿锛?026-06-03

## 1. 姒傝

鏈枃妗ｈ褰曞綋鍓嶅墠绔」鐩凡灏佽鎴栨鍦ㄤ娇鐢ㄧ殑鍚庣 API銆傚綋鍓嶉噸鐐瑰凡鎺ュ叆鐪熷疄 ForeFire 鐏娍钄撳欢棰勬祴鏈嶅姟锛屽墠绔€氳繃 `src/api/index.ts` 缁熶竴閰嶇疆 API 鍦板潃銆?
榛樿鍚庣鍦板潃锛?
```txt
http://localhost:5000
```

鍓嶇鐜鍙橀噺锛?
```env
VITE_API_BASE_URL=http://localhost:5000
```

Axios 灏佽浣嶇疆锛?
```txt
src/api/index.ts
src/api/modules.ts
```

璇存槑锛?
- 褰撳墠 ForeFire API 鏄湡瀹炲彲鐢ㄦ帴鍙ｃ€?- 鍏跺畠涓氬姟鎺ュ彛涓哄墠绔鐣欐帴鍙ｏ紝鑻ュ悗绔皻鏈疄鐜帮紝鍓嶇椤甸潰浼氶€氳繃闄嶇骇鏁版嵁鎴栫┖鏁版嵁缁х画灞曠ず銆?- Cesium 鍦板浘缁熶竴浣跨敤缁忕含搴﹀潗鏍?`[longitude, latitude]`銆?
---

## 2. ForeFire 鐏娍钄撳欢棰勬祴 API

### 2.1 鍋ュ悍妫€鏌?
```http
GET /health
```

鐢ㄩ€旓細

妫€鏌?ForeFire API銆佽緭鍏ユ暟鎹拰 ForeFire 鍛戒护鏄惁鍙敤銆?
杩斿洖绀轰緥锛?
```json
{
  "ok": true,
  "final_input_exists": true,
  "ignition_exists": true,
  "environment_dir": "/app/environment",
  "forefire_cmd_configured": true,
  "forefire_executable_available": true,
  "real_result_mode": true
}
```

瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| `ok` | boolean | API 鏈嶅姟鏄惁杩愯 |
| `final_input_exists` | boolean | `environment/final_input.nc` 鏄惁瀛樺湪 |
| `ignition_exists` | boolean | `environment/ignition.txt` 鏄惁瀛樺湪 |
| `environment_dir` | string | 瀹瑰櫒鍐呯幆澧冩暟鎹洰褰?|
| `forefire_cmd_configured` | boolean | 鏄惁閰嶇疆 ForeFire 鎵ц鍛戒护 |
| `forefire_executable_available` | boolean | ForeFire 鍙墽琛岀▼搴忔槸鍚﹀彲鐢?|
| `real_result_mode` | boolean | 鏄惁涓虹湡瀹?ForeFire 缁撴灉妯″紡 |

---

### 2.2 鑾峰彇棰勮楂樺嵄鐏偣

```http
GET /hotspot
GET /api/hotspot
```

鐢ㄩ€旓細

杩斿洖褰撳墠棰勮鐩戞祴鐏偣锛岀敤浜庡疄鏃剁伀鎯呯洃娴嬮〉闈㈠拰鐏伨钄撳欢棰勬祴椤甸潰鐨?Cesium 楂樺嵄鐏偣鍥惧眰銆?
褰撳墠鐏偣锛?
```txt
缁忓害锛?01.269444
绾害锛?8.530278
```

杩斿洖绀轰緥锛?
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "kind": "high_risk_hotspot",
        "name": "High-risk fire hotspot",
        "level": "high",
        "source": "backend_monitoring_preset"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [101.269444, 28.530278]
      }
    }
  ]
}
```

---

### 2.3 鍚姩鐪熷疄 ForeFire 钄撳欢棰勬祴

```http
POST /api/simulate
POST /simulate
```

鐢ㄩ€旓細

鍚姩涓€娆＄湡瀹?ForeFire 鐏娍钄撳欢棰勬祴銆傚悗绔細璇诲彇 `environment/final_input.nc` 鍜?`environment/ignition.txt`锛岃皟鐢?ForeFire 寮曟搸锛岀敓鎴愬悇鏃堕棿姝ョ伀绾?GeoJSON銆?
鍓嶇璋冪敤浣嶇疆锛?
```txt
src/api/modules.ts -> simulateAPI.start()
src/views/FirePredict.vue -> startSimulation()
```

璇锋眰浣擄細

```json
{
  "model": "standard",
  "time": "2026-06-03T13:52:29.000Z",
  "duration": 6,
  "scene_id": "scene-001",
  "longitude": 101.269444,
  "latitude": 28.530278
}
```

璇锋眰瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 蹇呭～ | 榛樿鍊?| 璇存槑 |
|---|---|---:|---|---|
| `model` | string | 鍚?| `standard` | 棰勬祴妯″瀷鏍囪瘑锛屽綋鍓嶄繚鐣欏瓧娈?|
| `time` | string/null | 鍚?| `null` | 鍓嶇閫夋嫨鐨勫紑濮嬫椂闂达紝ISO 鏍煎紡 |
| `duration` | number | 鍚?| `6` | 妯℃嫙鎬绘椂闀匡紝鍗曚綅灏忔椂锛屾渶灏?`0.1` |
| `scene_id` | string | 鍚?| `scene-001` | 鍦烘櫙 ID |
| `longitude` | number | 鍚?| `101.269444` | 鐐圭伀鐐圭粡搴?|
| `latitude` | number | 鍚?| `28.530278` | 鐐圭伀鐐圭含搴?|

杩斿洖绀轰緥锛?
```json
{
  "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
  "status": "done",
  "source": "forefire",
  "area": null,
  "radius": null,
  "speed": null,
  "direction": null,
  "risk": null,
  "output_nc": "/app/output/13357085-ae9c-4acf-bd6e-730abf35c7f3/output.nc",
  "run_dir": "/app/output/13357085-ae9c-4acf-bd6e-730abf35c7f3",
  "geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

杩斿洖瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| `task_id` | string | 鏈妯℃嫙浠诲姟 ID |
| `status` | string | 褰撳墠鍥哄畾涓?`done`锛岃〃绀哄悓姝ヨ绠楀畬鎴?|
| `source` | string | 褰撳墠涓?`forefire` |
| `area` | number/string/null | 棰勭暀瀛楁锛屽綋鍓嶉潰绉敱鍓嶇鎴栨暟鎹垎鏋愯剼鏈粠 GeoJSON 璁＄畻 |
| `radius` | number/string/null | 棰勭暀瀛楁 |
| `speed` | number/string/null | 棰勭暀瀛楁 |
| `direction` | string/null | 棰勭暀瀛楁 |
| `risk` | string/null | 棰勭暀瀛楁 |
| `output_nc` | string/null | ForeFire 杈撳嚭鐨?NetCDF 鏂囦欢璺緞 |
| `run_dir` | string | 鏈妯℃嫙杈撳嚭鐩綍 |
| `geojson` | object | 鍙洿鎺ョ敤浜?Cesium 灞曠ず鐨勬椂搴忕伀绾?GeoJSON |

GeoJSON Feature 瀛楁绀轰緥锛?
```json
{
  "type": "Feature",
  "properties": {
    "kind": "fire_front",
    "step": 1,
    "elapsed_seconds": 4320,
    "elapsed_minutes": 72,
    "source": "forefire",
    "output_file": "front_t4320.geojson"
  },
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": []
  }
}
```

GeoJSON 瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| `properties.kind` | string | 鍥哄畾涓?`fire_front` |
| `properties.step` | number | 鏃堕棿姝ュ簭鍙?|
| `properties.elapsed_seconds` | number | 浠庣偣鐏紑濮嬬粡杩囩殑绉掓暟 |
| `properties.elapsed_minutes` | number | 浠庣偣鐏紑濮嬬粡杩囩殑鍒嗛挓鏁?|
| `properties.source` | string | 鍥哄畾涓?`forefire` |
| `properties.output_file` | string | 瀵瑰簲鐨?ForeFire 鍘熷 GeoJSON 鏂囦欢鍚?|
| `geometry.type` | string | 閫氬父涓?`MultiPolygon` |
| `geometry.coordinates` | array | 鐏嚎澶氳竟褰㈠潗鏍囷紝鏍煎紡涓?`[longitude, latitude]` |

褰撳墠 6 灏忔椂妯℃嫙榛樿杈撳嚭 5 涓椂闂存锛?
| step | elapsed_seconds | elapsed_minutes | 鏂囦欢 |
|---:|---:|---:|---|
| 1 | 4320 | 72 | `front_t4320.geojson` |
| 2 | 8640 | 144 | `front_t8640.geojson` |
| 3 | 12960 | 216 | `front_t12960.geojson` |
| 4 | 17280 | 288 | `front_t17280.geojson` |
| 5 | 21600 | 360 | `front_t21600.geojson` |

閲嶈绾﹀畾锛?
- 鍚庣鎸?`elapsed_seconds` 鏁板€间粠灏忓埌澶ц繑鍥炵伀绾裤€?- 鍓嶇 Cesium 鍔ㄧ敾浼氶澶栨彃鍏?`0鍒嗛挓` 鍒濆甯э紝鍥犳鍒氬紑濮嬪彧鏄剧ず鐏偣锛?2 鍒嗛挓鍚庢墠鍑虹幇绗竴鏉＄伀绾裤€?- 姣忎釜鏃堕棿姝ョ殑鍘嗗彶鐏嚎浼氬湪鍒拌揪瀵瑰簲鏃堕棿鍚庢樉绀猴紝骞跺湪鍚庣画鏃堕棿姝ヤ繚鐣欍€?- 鏈€缁堢姸鎬佸仠鐣欏湪鏈€澶ц繃鐏寖鍥达紝涓嶅惊鐜挱鏀俱€?
---

### 2.4 鑾峰彇鎸囧畾妯℃嫙缁撴灉

```http
GET /api/simulate/result/{task_id}
```

鐢ㄩ€旓細

璇诲彇鎸囧畾浠诲姟鐩綍涓嬬殑 ForeFire 妯℃嫙缁撴灉銆?
璺緞鍙傛暟锛?
| 鍙傛暟 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| `task_id` | string | 妯℃嫙浠诲姟 ID |

杩斿洖绀轰緥锛?
```json
{
  "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
  "status": "done",
  "source": "forefire",
  "output_nc": "/app/output/13357085-ae9c-4acf-bd6e-730abf35c7f3/output.nc",
  "geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

閿欒锛?
- `404`: 鎸囧畾 `task_id` 鐨勬ā鎷熺粨鏋滀笉瀛樺湪銆?
---

### 2.5 鑾峰彇妯℃嫙鍘嗗彶

```http
GET /api/simulate/history
```

鐢ㄩ€旓細

杩斿洖杈撳嚭鐩綍涓殑鍘嗗彶妯℃嫙浠诲姟鍒楄〃銆?
杩斿洖绀轰緥锛?
```json
[
  {
    "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
    "output_nc": "/app/output/13357085-ae9c-4acf-bd6e-730abf35c7f3/output.nc",
    "geojson_count": 5
  }
]
```

瀛楁璇存槑锛?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| `task_id` | string | 鍘嗗彶浠诲姟鐩綍鍚?|
| `output_nc` | string/null | 鏄惁瀛樺湪 `output.nc` |
| `geojson_count` | number | 褰撳墠浠诲姟杈撳嚭鐨?`front_t*.geojson` 鏁伴噺 |

---


### 2.6 Fire Event Archive API

```http
POST /api/fire/archive
GET /api/fire/archive
GET /api/fire/archive/{event_id}
DELETE /api/fire/archive/{event_id}
```

用途：保存本次木里县森林火灾演示事件。前端顶部“归档”按钮会提交火点、ForeFire 结果、Agent 决策、实时消息和前端派生状态到本地 ForeFire API。

数据库：

```txt
backend/forefire_api/data/fire_events.db
```

请求示例：

```json
{
  "event_id": "muli-fire-demo-2026-06-03",
  "event_name": "木里县森林火灾演示事件",
  "ignition_point": {
    "longitude": 101.269444,
    "latitude": 28.530278
  },
  "forefire_result": {},
  "agent_result": {},
  "agent_messages": [],
  "derived_state": {
    "dispatch_tasks": [],
    "uav_tasks": [],
    "evacuation_tasks": []
  }
}
```

---## 3. ForeFire Agent 鍐崇瓥閫氫俊 API

褰撳墠鍓嶇宸插湪鐏伨钄撳欢棰勬祴椤甸潰鎺ュ叆 Agent 杈撳嚭鍙鍖栥€傛祦绋嬩负锛?
1. 鍓嶇璋冪敤鏈満 ForeFire API锛歚POST /api/simulate`銆?2. 寰楀埌鐪熷疄 ForeFire JSON/GeoJSON 鍚庯紝鍓嶇閫氳繃 WebSocket 灏嗗畬鏁寸粨鏋滃彂閫佺粰 Agent 鍚庣銆?3. Agent 鍚庣瀹炴椂杩斿洖鎺ㄧ悊鐘舵€併€侀闄╂憳瑕併€佹帹鑽愭柟妗堝拰璋冨害浠诲姟銆?4. 濡傛灉 WebSocket 鏃犳硶杩炴帴锛屽墠绔細鑷姩鍏滃簳璋冪敤 REST锛歚POST /api/agent/forefire/decision`銆?
Agent 鍚庣榛樿鍦板潃鏉ヨ嚜鍚庣寮€鍙戣€?ZeroTier IP锛?
```env
VITE_AGENT_API_BASE_URL=http://10.62.223.117:8000
VITE_AGENT_WS_URL=ws://10.62.223.117:8000/ws/agent/forefire/decision
```

鍓嶇灏佽浣嶇疆锛?
```txt
src/services/forefireAgentSocket.ts
```

椤甸潰鎺ュ叆浣嶇疆锛?
```txt
src/views/FirePredict.vue
```

### 3.1 WebSocket 鍙屽悜閫氫俊

```txt
ws://10.62.223.117:8000/ws/agent/forefire/decision
```

璇存槑锛?
- `FOREFIRE_AGENT_API.md` 褰撳墠鍙槑纭啓浜?REST 璺緞锛屾湭鏄庣‘ WebSocket 璺緞銆?- 鍓嶇宸插皢 WebSocket 璺緞鍋氭垚 `.env` 鍙厤缃」銆?- 濡傛灉鍚庣瀹為檯璺緞涓嶅悓锛屽彧闇€淇敼 `VITE_AGENT_WS_URL`銆?
鍓嶇鍙戦€佹秷鎭細

```json
{
  "type": "forefire_decision_request",
  "payload": {
    "forefire_json": {
      "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
      "status": "done",
      "source": "forefire",
      "geojson": {
        "type": "FeatureCollection",
        "features": []
      }
    },
    "weather": {
      "temperature": "24掳",
      "humidity": "40%",
      "wind_speed": "3.2m/s",
      "weather": "sunny"
    },
    "resources": {
      "fire_crews": 6,
      "uavs": 3,
      "water_tankers": 4,
      "evacuation_buses": 3
    },
    "include_coordinates": false
  }
}
```

寤鸿鍚庣杩斿洖鐨勫疄鏃舵秷鎭被鍨嬶細

```json
{
  "type": "progress",
  "status": "streaming",
  "message": "EnvironmentAssessmentAgent completed.",
  "payload": {}
}
```

鏈€缁堢粨鏋滄秷鎭細

```json
{
  "type": "result",
  "status": "decision_generated",
  "payload": {
    "task_id": "13357085-ae9c-4acf-bd6e-730abf35c7f3",
    "source": "forefire",
    "status": "decision_generated",
    "input_summary": {},
    "agent_outputs": {},
    "packages": {},
    "candidate_plans": [],
    "recommended_plan": {},
    "blocked_or_downgraded_plans": [],
    "warnings": []
  }
}
```

鍓嶇鍏煎浠ヤ笅杩斿洖褰㈡€侊細

- 椤跺眰灏辨槸瀹屾暣鍐崇瓥缁撴灉銆?- `{ "type": "result", "payload": 瀹屾暣鍐崇瓥缁撴灉 }`
- `{ "type": "completed", "data": 瀹屾暣鍐崇瓥缁撴灉 }`
- 浠绘剰杩涘害娑堟伅閮戒細杩涘叆瀹炴椂閫氫俊鍒楄〃銆?
褰撳墠鍓嶇灞曠ず瀛楁锛?
| 鍓嶇鍖哄煙 | 瀛楁 |
|---|---|
| AI 鏍囩鎽樿 | `agent_outputs.environment_assessment.environment_risk_summary` 鎴?`agent_outputs.fire_spread_analysis.future_6h_summary` |
| KPI | `input_summary.final_area_km2`銆乣input_summary.risk_level`銆乣input_summary.avg_growth_km2_per_hour` |
| 鎺ㄨ崘鏂规 | `recommended_plan.name`銆乣recommended_plan.score`銆乣recommended_plan.strategy`銆乣recommended_plan.reasons` |
| 璋冨害浠诲姟 | `packages.task_package.tasks` 鎴?`agent_outputs.resource_dispatch.tasks` |
| 瀹炴椂鏃ュ織 | WebSocket 姣忔潯娑堟伅鐨?`type/status/message/content` |

### 3.2 REST 鍏滃簳鎺ュ彛

```http
POST /api/agent/forefire/decision
```

Base URL锛?
```txt
http://10.62.223.117:8000
```

璇锋眰浣撲笌 WebSocket 鐨?`payload` 涓€鑷淬€?
### 3.3 褰撳墠缃戠粶鐘舵€?
鎴嚦 2026-06-03 褰撳墠娴嬭瘯锛?
```txt
10.62.223.117:8000 TCP connect succeeded
http://10.62.223.117:8000/openapi.json -> 200
POST http://10.62.223.117:8000/api/agent/forefire/decision -> decision_generated
ws://10.62.223.117:8000/ws/agent/forefire/decision -> WebSocket close 1006
raw WebSocket Upgrade /ws/agent/forefire/decision -> HTTP/1.1 404 Not Found
ws://10.62.223.117:8000/ws/forefire -> WebSocket close 1006
```

2026-06-03 鍚庣閲嶆柊璋冩暣鍚庡娴嬶細

```txt
10.62.223.117:8000 TCP connect succeeded
/ws/agent/forefire/decision -> HTTP/1.1 101 Switching Protocols
/ws/forefire -> HTTP/1.1 101 Switching Protocols
WebSocket request -> progress x7 -> result decision_generated PLAN-A
```

杩欒〃绀哄綋鍓?Agent REST 涓?WebSocket 鍧囧彲鐢ㄣ€傚墠绔綋鍓嶇瓥鐣ヤ繚鎸佷笉鍙橈細

- 浼樺厛灏濊瘯 `VITE_AGENT_WS_URL`銆?- WebSocket 2 绉掑唴鏈墦寮€鎴栨彙鎵嬪け璐ユ椂锛岃嚜鍔ㄨ皟鐢?REST 鍏滃簳鎺ュ彛銆?- WebSocket 鎴?REST 杩斿洖 `decision_generated` 鍚庢甯告覆鏌?AI 鎽樿銆佹帹鑽愭柟妗堝拰璋冨害浠诲姟銆?
---

## 4. 鐏儏涓庡満鏅帴鍙?
杩欎簺鎺ュ彛鐢?`fireAPI` 灏佽锛屼富瑕佺敤浜庡疄鏃剁伀鎯呯洃娴嬨€佹寚鎸ヤ腑蹇冦€佺伨鎯呰瘎浼般€佽矾寰勮鍒掔瓑椤甸潰銆?
### 3.1 鐏儏鍒楄〃

```http
GET /api/fire/list
```

杩斿洖绀轰緥锛?
```json
[
  {
    "id": "fire-001",
    "lat": 28.530278,
    "lng": 101.269444,
    "level": "high",
    "risk_hint": "鐏娍鍙兘鍚戜笢鍖楁柟鍚戣敁寤?
  }
]
```

### 3.2 鐏儏缁熻

```http
GET /api/fire/stat
```

杩斿洖绀轰緥锛?
```json
{
  "summary_cards": [
    { "label": "娲昏穬鐏簮", "value": 5 }
  ],
  "chart_data": {},
  "wind_params": {
    "temperature": "26掳C",
    "humidity": "45%",
    "wind_speed": "3.2m/s",
    "pm25": 85
  },
  "level_distribution": [
    { "value": 5, "name": "楂樺嵄" },
    { "value": 10, "name": "涓嵄" }
  ],
  "temperature": "26掳C",
  "weather": "sunny"
}
```

### 3.3 鐏儏鍘嗗彶

```http
GET /api/fire/history
```

### 3.4 鍦烘櫙鐘舵€?
```http
GET /api/b/scene/{scene_id}/status
```

### 3.5 鍦烘櫙鐏嚎

```http
GET /api/b/scene/{scene_id}/fire-line
```

杩斿洖锛?
GeoJSON 鐏嚎鏁版嵁銆?
---

## 4. 璧勬簮銆佷汉鍛樹笌璋冨害鎺ュ彛

### 4.1 璧勬簮鍒楄〃

```http
GET /api/resource/list
```

杩斿洖绀轰緥锛?
```json
[
  {
    "name": "娑堥槻姘寸",
    "total": 500,
    "available": 380,
    "unit": "m"
  }
]
```

### 4.2 璧勬簮缁熻

```http
GET /api/resource/stat
```

### 4.3 浜哄憳鍒楄〃

```http
GET /api/personnel/list
```

杩斿洖绀轰緥锛?
```json
[
  {
    "name": "寮犱笁",
    "role": "鎸囨尌鍛?,
    "status": "deployed"
  }
]
```

### 4.4 璋冨害鍒楄〃

```http
GET /api/dispatch/list
```

### 4.5 鍒涘缓璋冨害

```http
POST /api/dispatch/create
```

璇锋眰绀轰緥锛?
```json
{
  "type": "equipment",
  "target": "A鍖?,
  "quantity": 10
}
```

### 4.6 鍙戦€佽皟搴?
```http
POST /api/dispatch/send
```

### 4.7 璧勬簮璋冨害鏂规

```http
GET /api/b/decision/resource-dispatch/{scene_id}
```

---

## 5. 鏃犱汉鏈烘帴鍙?
### 5.1 鏃犱汉鏈哄垪琛?
```http
GET /api/uav/list
```

杩斿洖绀轰緥锛?
```json
[
  {
    "id": "UAV-01",
    "name": "渚﹀療鏃犱汉鏈?1",
    "status": "online",
    "battery": 85,
    "lat": 28.530278,
    "lng": 101.269444
  }
]
```

### 5.2 浠诲姟鍒楄〃

```http
GET /api/uav/mission/list
```

### 5.3 浠诲姟璇︽儏

```http
GET /api/uav/mission/{id}
```

### 5.4 鏃犱汉鏈烘帶鍒?
```http
POST /api/uav/control
```

璇锋眰绀轰緥锛?
```json
{
  "uav_id": "UAV-01",
  "command": "return"
}
```

### 5.5 鏃犱汉鏈鸿皟搴?
```http
POST /api/b/decision/uav/schedule
```

---

## 6. 澶氭簮铻嶅悎涓庣幆澧冩帴鍙?
### 6.1 浼犳劅鍣ㄥ垪琛?
```http
GET /api/sensor/list
```

### 6.2 姘旇薄鏁版嵁

```http
GET /api/weather
```

### 6.3 铻嶅悎缁撴灉

```http
GET /api/fusion/result
```

杩斿洖绀轰緥锛?
```json
{
  "confidence": 85,
  "sources": ["鍗槦", "浼犳劅鍣?, "鏃犱汉鏈?],
  "fire_estimation": 1250,
  "unit": "骞虫柟绫?
}
```

### 6.4 铻嶅悎棰勮

```http
GET /api/fusion/preview
```

---

## 7. 鍦板浘涓庤矾寰勮鍒掓帴鍙?
### 7.1 鍦板浘鍏ㄩ噺鏁版嵁

```http
GET /api/map/all
```

### 7.2 楂樼▼鏁版嵁

```http
GET /api/map/elevation
```

### 7.3 閫冪敓璺嚎瑙勫垝

```http
POST /api/b/decision/escape-route
```

璇锋眰绀轰緥锛?
```json
{
  "start": [101.269444, 28.530278],
  "end": [101.280000, 28.540000]
}
```

杩斿洖绀轰緥锛?
```json
{
  "routes": [
    {
      "name": "A",
      "distance": "3.2km",
      "time": "12min",
      "risk": "浣?,
      "cost": "浣?
    }
  ]
}
```

### 7.4 娑堥槻鍛樿矾绾胯鍒?
```http
POST /api/b/decision/firefighter-route
```

### 7.5 淇濆瓨璺嚎

```http
POST /api/route/save
```

---

## 8. AI Agent 鎺ュ彛

### 8.1 鏅鸿兘鍒嗘瀽

```http
POST /api/agent/analyze
```

璇锋眰绀轰緥锛?
```json
{
  "type": "disaster_assessment"
}
```

杩斿洖绀轰緥锛?
```json
{
  "summary": "缁煎悎璇勪及缁撴灉鏂囨湰",
  "suggestions": ["寤鸿1", "寤鸿2"]
}
```

### 8.2 鏅鸿兘妯℃嫙

```http
POST /api/agent/simulate
```

---

## 9. 瑙嗛銆佹寚鎸ヤ笌绯荤粺鎺ュ彛

### 9.1 瑙嗛鍒楄〃

```http
GET /api/video/list
```

### 9.2 瑙嗛娴?
```http
GET /api/video/stream?camera_id={camera_id}
```

### 9.3 鎸囨尌姒傝

```http
GET /api/command/overview
```

杩斿洖绀轰緥锛?
```json
{
  "fires": 5,
  "uavs": 12,
  "resources": 45,
  "personnel": 320
}
```

### 9.4 绯荤粺鐘舵€?
```http
GET /api/system/status
```

杩斿洖绀轰緥锛?
```json
{
  "cpu": 45,
  "memory": 62
}
```

---

## 10. WebSocket 棰勭暀鎺ュ彛

### 10.1 鍛婅鎺ㄩ€?
```txt
ws://localhost:5000/ws/alert
```

娑堟伅绀轰緥锛?
```json
{
  "id": "alert-001",
  "level": "high",
  "time": "14:30",
  "message": "鐏儏鍛婅淇℃伅"
}
```

### 10.2 鏃犱汉鏈轰綅缃帹閫?
```txt
ws://localhost:5000/ws/uav
```

璇存槑锛?
褰撳墠浠呬负棰勭暀鍦板潃锛屽疄闄呮槸鍚﹀彲鐢ㄥ彇鍐充簬鍚庣瀹炵幇銆?
---

## 11. 閿欒澶勭悊

FastAPI 榛樿閿欒鍝嶅簲鏍煎紡锛?
```json
{
  "detail": "閿欒鎻忚堪"
}
```

ForeFire 鍛戒护鎵ц澶辫触鏃讹細

```json
{
  "detail": {
    "message": "ForeFire command failed.",
    "command": "forefire -i case.ff",
    "stdout": "...",
    "stderr": "..."
  }
}
```

ForeFire 瓒呮椂鏃讹細

```json
{
  "detail": {
    "message": "ForeFire command timed out.",
    "command": "forefire -i case.ff",
    "stdout": "...",
    "stderr": "..."
  }
}
```

甯歌鐘舵€佺爜锛?
| 鐘舵€佺爜 | 璇存槑 |
|---:|---|
| 200 | 鎴愬姛 |
| 400 | 璇锋眰鍙傛暟閿欒 |
| 404 | 璧勬簮涓嶅瓨鍦?|
| 422 | 璇锋眰浣撳瓧娈电被鍨嬫垨绾︽潫涓嶇鍚堣姹?|
| 500 | 鏈嶅姟绔唴閮ㄩ敊璇垨 ForeFire 杩愯澶辫触 |
| 503 | ForeFire 寮曟搸涓嶅彲鐢?|
| 504 | ForeFire 杩愯瓒呮椂 |

---

## 12. 鏈湴璋冭瘯鍛戒护

鍋ュ悍妫€鏌ワ細

```powershell
Invoke-RestMethod http://localhost:5000/health
```

鑾峰彇鐏偣锛?
```powershell
Invoke-RestMethod http://localhost:5000/hotspot
```

鍚姩 6 灏忔椂棰勬祴锛?
```powershell
Invoke-RestMethod `
  -Uri http://localhost:5000/api/simulate `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"duration":6,"longitude":101.269444,"latitude":28.530278}'
```

鏌ョ湅鍘嗗彶锛?
```powershell
Invoke-RestMethod http://localhost:5000/api/simulate/history
```

Docker 閲嶅缓 ForeFire API锛?
```powershell
docker compose -f docker-compose.forefire.yml up -d --build forefire-api
```

