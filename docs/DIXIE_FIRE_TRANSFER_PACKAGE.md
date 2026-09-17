# Dixie Fire transfer package

详细的 AI 自动配置步骤见 `docs/TEAM_DATA_HANDOFF_AI_GUIDE.md`。

U 盘交付物：

```text
qingzhe_ivory_dixie_fire_2021_data_bundle.zip
dixie_fire_2021_database_seed.sql
SHA256SUMS.txt
```

压缩包包含 `data/` 下的原始数据、处理数据、数据清单、SQL 模式和 ForeFire 输入清单。数据库种子是从当前 Docker PostGIS 生成的 Dixie 专用恢复脚本。

不交付 `.env`、API Key、Cesium Token、LLM Key、Docker named volume、OSM 超时错误响应作为数据、虚构的 ForeFire 结果或无人机影像。

每台电脑的 `postgis-data` volume 独立存在。复制 `data/` 不会自动同步数据库，必须运行：

```powershell
.\scripts\restore-dixie-data-docker.ps1 -SeedPath "<数据库种子文件路径>"
```

这个脚本只重建 `dixie_fire_2021`，不会删除其他事件。

基线记录数：FIRMS 70460，候选热点 60013，10 分钟聚合 11704，MTBS 边界 1，日气象 105，小时气象 2520。
