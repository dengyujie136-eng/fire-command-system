# 智慧消防指挥系统 - 后端接口配置文档

## 概述
本文档描述前端预留的所有后端接口，包含接口名称、请求方法、URL、参数说明、返回值说明及调用示例。
基础URL: `http://localhost:8080`

---

## 一、公共数据接口

### 1.1 火情列表
- **接口名称**: `GET /api/fire/list`
- **描述**: 获取所有火情点位信息
- **参数**: 无
- **返回**:
```json
[
  {
    "id": "fire-001",
    "lat": 39.91,
    "lng": 116.40,
    "level": "high",
    "risk_hint": "火势向东北方向蔓延"
  }
]
```

### 1.2 火情统计
- **接口名称**: `GET /api/fire/stat`
- **描述**: 获取火情统计数据、环境参数
- **参数**: 无
- **返回**:
```json
{
  "summary_cards": [{ "label": "活跃火源", "value": 5 }],
  "chart_data": {},
  "wind_params": {
    "temperature": "26°C",
    "humidity": "45%",
    "wind_speed": "3.2m/s",
    "pm25": 85
  },
  "level_distribution": [
    { "value": 5, "name": "高危" },
    { "value": 10, "name": "中危" }
  ],
  "temperature": "26°C",
  "weather": "sunny"
}
```

### 1.3 火情历史
- **接口名称**: `GET /api/fire/history`
- **参数**: 无
- **返回**: 火情历史数据列表

### 1.4 气象数据
- **接口名称**: `GET /api/weather`
- **参数**: 无
- **返回**: 气象信息

### 1.5 场景状态
- **接口名称**: `GET /api/b/scene/{scene_id}/status`
- **描述**: 获取指定场景状态
- **参数**: `scene_id` (路径参数)
- **返回**: 场景状态信息

### 1.6 场景火线
- **接口名称**: `GET /api/b/scene/{scene_id}/fire-line`
- **描述**: 获取指定场景的火线数据
- **参数**: `scene_id` (路径参数)
- **返回**: GeoJSON火线数据

---

## 二、资源与人员接口

### 2.1 资源列表
- **接口名称**: `GET /api/resource/list`
- **描述**: 获取所有资源点信息
- **参数**: 无
- **返回**:
```json
[
  { "name": "消防水管", "total": 500, "available": 380, "unit": "m" }
]
```

### 2.2 资源统计
- **接口名称**: `GET /api/resource/stat`
- **参数**: 无
- **返回**: 资源统计数据

### 2.3 人员列表
- **接口名称**: `GET /api/personnel/list`
- **参数**: 无
- **返回**:
```json
[
  { "name": "张三", "role": "指挥员", "status": "deployed" }
]
```

### 2.4 调度列表
- **接口名称**: `GET /api/dispatch/list`
- **参数**: 无
- **返回**: 调度任务列表

### 2.5 创建调度
- **接口名称**: `POST /api/dispatch/create`
- **参数**:
```json
{ "type": "equipment", "target": "A区", "quantity": 10 }
```
- **返回**: 创建结果

### 2.6 发送调度
- **接口名称**: `POST /api/dispatch/send`
- **参数**: 调度发送数据
- **返回**: 发送结果

### 2.7 资源调度方案
- **接口名称**: `GET /api/b/decision/resource-dispatch/{scene_id}`
- **参数**: `scene_id` (路径参数)
- **返回**: 资源调度方案

---

## 三、无人机接口

### 3.1 无人机列表
- **接口名称**: `GET /api/uav/list`
- **参数**: 无
- **返回**:
```json
[
  { "id": "UAV-01", "name": "侦察机 1", "status": "online", "battery": 85, "lat": 39.91, "lng": 116.40 }
]
```

### 3.2 任务列表
- **接口名称**: `GET /api/uav/mission/list`
- **参数**: 无
- **返回**: 任务列表

### 3.3 任务详情
- **接口名称**: `GET /api/uav/mission/{id}`
- **参数**: `id` (路径参数)
- **返回**: 任务详情

### 3.4 无人机控制
- **接口名称**: `POST /api/uav/control`
- **参数**:
```json
{ "uav_id": "UAV-01", "command": "return" }
```
- **返回**: 控制结果

### 3.5 无人机调度
- **接口名称**: `POST /api/b/decision/uav/schedule`
- **参数**: 调度方案数据
- **返回**: 调度结果

---

## 四、传感器与融合接口

### 4.1 传感器列表
- **接口名称**: `GET /api/sensor/list`
- **参数**: 无
- **返回**: 传感器列表

### 4.2 融合结果
- **接口名称**: `GET /api/fusion/result`
- **参数**: 无
- **返回**:
```json
{
  "confidence": 85,
  "sources": ["卫星", "传感器", "无人机"],
  "fire_estimation": 1250
}
```

### 4.3 融合预览
- **接口名称**: `GET /api/fusion/preview`
- **参数**: 无
- **返回**: 融合预览数据

---

## 五、地图接口

### 5.1 地图全量数据
- **接口名称**: `GET /api/map/all`
- **参数**: 无
- **返回**: 地图所有图层数据

### 5.2 高程数据
- **接口名称**: `GET /api/map/elevation`
- **参数**: 无
- **返回**: 高程数据

---

## 六、路径规划接口

### 6.1 逃生路线规划
- **接口名称**: `POST /api/b/decision/escape-route`
- **参数**:
```json
{ "start": "起点坐标", "end": "终点坐标" }
```
- **返回**:
```json
{
  "routes": [
    { "name": "A", "distance": "3.2km", "time": "12min", "risk": "低", "cost": "低" }
  ]
}
```

### 6.2 消防员路线规划
- **接口名称**: `POST /api/b/decision/firefighter-route`
- **参数**: 同逃生路线
- **返回**: 同逃生路线

### 6.3 保存路线
- **接口名称**: `POST /api/route/save`
- **参数**: 路线数据
- **返回**: 保存结果

---

## 七、模拟与预测接口

### 7.1 启动模拟
- **接口名称**: `POST /api/simulate`
- **参数**:
```json
{
  "model": "static",
  "time": "2024-01-01T00:00:00Z",
  "duration": 6,
  "scene_id": "scene-001"
}
```
- **返回**:
```json
{
  "task_id": "task-001",
  "area": "12.5",
  "radius": "3.2",
  "eta": "2h 15min",
  "direction": "东北",
  "risk": "高",
  "speed": "2.5"
}
```

### 7.2 模拟结果
- **接口名称**: `GET /api/simulate/result/{task_id}`
- **参数**: `task_id` (路径参数)
- **返回**: 模拟结果数据

### 7.3 模拟历史
- **接口名称**: `GET /api/simulate/history`
- **参数**: 无
- **返回**: 模拟历史记录

---

## 八、AI Agent接口

### 8.1 智能分析
- **接口名称**: `POST /api/agent/analyze`
- **参数**:
```json
{ "type": "disaster_assessment" }
```
- **返回**:
```json
{
  "summary": "综合评估结果文本",
  "suggestions": ["建议1", "建议2"]
}
```

### 8.2 智能模拟
- **接口名称**: `POST /api/agent/simulate`
- **参数**: 模拟参数
- **返回**: 模拟分析结果

---

## 九、视频接口

### 9.1 视频列表
- **接口名称**: `GET /api/video/list`
- **参数**: 无
- **返回**: 视频源列表

### 9.2 视频流
- **接口名称**: `GET /api/video/stream?camera_id=xxx`
- **参数**: `camera_id` (查询参数)
- **返回**: 视频流数据

---

## 十、指挥与系统接口

### 10.1 指挥概览
- **接口名称**: `GET /api/command/overview`
- **参数**: 无
- **返回**:
```json
{
  "fires": 5,
  "suavs": 12,
  "resources": 45,
  "personnel": 320
}
```

### 10.2 系统状态
- **接口名称**: `GET /api/system/status`
- **参数**: 无
- **返回**:
```json
{
  "cpu": 45,
  "memory": 62
}
```

---

## 十一、WebSocket实时接口

### 11.1 告警推送
- **连接地址**: `ws://localhost:8080/ws/alert`
- **数据格式**:
```json
{
  "id": "alert-001",
  "level": "high",
  "time": "14:30",
  "message": "火情告警信息"
}
```

### 11.2 无人机位置推送
- **连接地址**: `ws://localhost:8080/ws/uav`
- **数据格式**: 无人机位置数据数组

---

## 错误处理

所有接口统一错误响应格式:
```json
{
  "code": 500,
  "message": "错误描述",
  "detail": "详细信息"
}
```

常见错误码:
| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

## 环境配置

前端通过环境变量配置后端地址:

```env
VITE_API_BASE_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080
```
