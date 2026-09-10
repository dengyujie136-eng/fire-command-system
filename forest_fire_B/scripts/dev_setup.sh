#!/usr/bin/env bash
# [Frontend-Contract] 联调一键启动包
set -euo pipefail

PORT_OFFSET=0
SKIP_SEED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-seed)
      SKIP_SEED=1
      shift
      ;;
    --port-offset)
      PORT_OFFSET="${2:-0}"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

C_PORT=$((8888 + PORT_OFFSET))
B_PORT=$((8100 + PORT_OFFSET))
REPORT_FILE="scripts/verify_report.md"

mkdir -p scripts

check_dep() {
  local name="$1"
  local cmd="$2"
  if ! eval "$cmd" >/dev/null 2>&1; then
    echo "❌ 步骤1失败，请检查：缺少 ${name}，请先安装"
    exit 1
  fi
}

# 步骤1：检查依赖
check_dep "Python 3.10+" "python3 --version || python --version"
check_dep "uvicorn" "python -c \"import uvicorn\""
check_dep "httpx" "python -c \"import httpx\""
check_dep "SQLite" "python -c \"import sqlite3\""

# 步骤2：启动 C 端
C_ROOT="../wildfire_nqz"
if [[ ! -d "$C_ROOT" ]]; then
  echo "❌ C 端项目未找到，请确认目录结构"
  exit 1
fi

activate_c_venv() {
  # 激活 C 端虚拟环境（若存在）
  if [[ -f "$C_ROOT/venv/Scripts/activate" ]]; then
    # Windows venv
    # shellcheck disable=SC1091
    source "$C_ROOT/venv/Scripts/activate"
  elif [[ -f "$C_ROOT/venv/bin/activate" ]]; then
    # Unix venv
    # shellcheck disable=SC1091
    source "$C_ROOT/venv/bin/activate"
  elif [[ -f "$C_ROOT/.venv/Scripts/activate" ]]; then
    # shellcheck disable=SC1091
    source "$C_ROOT/.venv/Scripts/activate"
  elif [[ -f "$C_ROOT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$C_ROOT/.venv/bin/activate"
  fi
}

launch_c_service() {
  cd "$C_ROOT"
  activate_c_venv
  # 优先使用 uvicorn，fallback 到 python -m
  if [[ -f "simulation/app/main.py" ]]; then
    if command -v uvicorn >/dev/null 2>&1; then
      uvicorn simulation.app.main:app --host 0.0.0.0 --port "$C_PORT" --reload >/tmp/wildfire_c.log 2>&1 &
    else
      python -m uvicorn simulation.app.main:app --host 0.0.0.0 --port "$C_PORT" --reload >/tmp/wildfire_c.log 2>&1 &
    fi
  elif [[ -f "simulation/app/main.py" ]] || [[ -f "simulation/app/__init__.py" ]]; then
    python -m simulation.app.main --port "$C_PORT" >/tmp/wildfire_c.log 2>&1 &
  else
    python -m simulation.app.main --port "$C_PORT" >/tmp/wildfire_c.log 2>&1 &
  fi
  C_PID=$!
  cd - >/dev/null
}

if ! curl -fsS "http://127.0.0.1:${C_PORT}/health" >/dev/null 2>&1; then
  echo "启动 C 端中..."
  launch_c_service
  sleep 3
fi

if ! curl -fsS "http://127.0.0.1:${C_PORT}/health" >/dev/null 2>&1; then
  echo "❌ 步骤2失败，请检查：C端启动失败，建议查看 /tmp/wildfire_c.log"
  exit 1
fi

# 步骤3：启动 B 端
if ! curl -fsS "http://127.0.0.1:${B_PORT}/health" >/dev/null 2>&1; then
  echo "⚠️ B端未启动，建议执行：uvicorn main:app --host 0.0.0.0 --port ${B_PORT}"
fi

# 步骤4：等待健康检查
sleep 2

if ! curl -fsS "http://127.0.0.1:${B_PORT}/health" >/dev/null 2>&1; then
  echo "❌ 步骤4失败，请检查：B端健康检查未通过，确认主程序是否正常启动"
  exit 1
fi

if [[ "$SKIP_SEED" -eq 0 ]]; then
  # 步骤5：注入种子数据
  python scripts/seed_data.py --scene-id=dev --demo-safe || {
    echo "❌ 步骤5失败，请检查：seed 脚本、数据库或 WebSocket 服务是否可用"
    exit 1
  }
else
  echo "⚠️ 已跳过种子注入"
fi

# 步骤6：生成就绪报告
cat > "$REPORT_FILE" <<EOF
# 联调就绪报告

## 服务健康状态
- ✅/❌ C端：待检查
- ✅/❌ B端：待检查
- ✅/❌ DB：待检查

## P0 接口响应结构验证
- ✅/❌ /api/fire/list
- ✅/❌ /api/fire/stat
- ✅/❌ /api/uav/list
- ✅/❌ /api/resource/list
- ✅/❌ /api/personnel/list

## WebSocket 连通性测试
- ✅/❌ ws://localhost:${B_PORT}/ws/alert

## 前端测试账号
- 如启用 auth，请填写：

## 直接可点击的测试URL
- Swagger: http://127.0.0.1:${B_PORT}/docs
- Fire Stat: http://127.0.0.1:${B_PORT}/api/fire/stat?scene_id=dev
- Fire List: http://127.0.0.1:${B_PORT}/api/fire/list?scene_id=dev

EOF

# 步骤7：打印前端可访问 URL
cat <<EOF
联调已就绪，前端可直接访问：
- Swagger: http://127.0.0.1:${B_PORT}/docs
- /api/fire/stat?scene_id=dev
- /api/fire/list?scene_id=dev
- /api/resource/list
- /api/uav/list
- /api/personnel/list
EOF

# 联调自检清单
# [ ] C 端健康
# [ ] B 端健康
# [ ] DB 可访问
# [ ] 5 个 P0 接口可返回 data
# [ ] ws://localhost:${B_PORT}/ws/alert 可连接
# [ ] 前端页面可按 scene_id 直接渲染
# [ ] 资源页表格可直接消费 table_data
# [ ] 地图页可直接消费 GeoJSON
