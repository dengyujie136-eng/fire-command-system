from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, tasks, simulate, agent, websocket, scene, decision, frontend_data, aggregation, chat_agent, forefire_agent

# 创建 FastAPI 应用实例
app = FastAPI(title="森林火灾应急决策后端", version="1.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 或 ["*"] 仅用于开发
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由模块
# include_router 会将子路由挂载到主应用上
app.include_router(auth.router)
app.include_router(tasks.router)
# 注意：simulate.py 中已经定义了 prefix="/simulate"
# 所以最终路径是 /simulate/ (POST) 和 /simulate/result/{id} (GET)
app.include_router(simulate.router)
app.include_router(agent.router)
app.include_router(websocket.router)
app.include_router(scene.router)
app.include_router(decision.router)
app.include_router(frontend_data.router)
app.include_router(aggregation.router, prefix="/api")
app.include_router(chat_agent.router)
app.include_router(forefire_agent.router)
app.include_router(forefire_agent.ws_router)

# 根路由
@app.get("/")
def root():
    return {"message": "森林火灾应急决策后端服务运行中"}

# 健康检查
@app.get("/health")
def health():
    return {"status": "ok"}

# 3. 建议加上这段，方便直接运行
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("FOREST_FIRE_B_PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)
