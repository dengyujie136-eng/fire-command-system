# 给乙、丙、丁 AI 助手的执行指令

请在当前 `fire-command-system` 仓库中完成成员甲数据恢复和接口验证。严格遵守以下要求：

1. 先执行 `git status --short --branch`，不得切换、覆盖或删除当前成员分支，不得修改或推送 `main`。
2. 如果工作区存在未提交改动，先报告冲突风险；不要执行 `git reset --hard`、`git checkout --` 或 `docker compose down -v`。
3. 执行 `git fetch origin member/qingzhe_ivory`，只读取该远程分支。除非用户明确要求合并，否则不要把甲分支直接合并进当前成员分支。
4. 在用户提供的交接目录中核对 `SHA256SUMS_20260917.txt`，确认所有压缩包和 SQL 文件校验通过。
5. 将两个 ZIP 解压到临时目录，把其中的 `data` 合并到当前仓库的 `data`；不得先删除现有 `data`，不得覆盖其他成员独有的数据成果。
6. 启动 Docker Desktop 后执行 `docker compose up -d fire-agent-api`。
7. 使用 `scripts/restore-dixie-data-docker.ps1` 恢复 Dixie Fire 数据；使用 `scripts/restore-member-a-realtime-docker.ps1` 恢复甲的实时观测数据。只允许操作脚本声明的甲模块表，不得删除其他成员业务数据。
8. 每台电脑使用自己的 `.env`。不得读取、打印、提交或传播甲的 API Key。需要 FIRMS NRT 联网同步时，由本机用户配置个人 `FIRMS_MAP_KEY`。
9. 执行 `docker compose up -d --build`、`python scripts/verify_member_a_data.py`，并验证以下地址返回成功：
   - `http://localhost:8200/health`
   - `http://localhost:8200/api/data-agent/catalog/dixie_fire_2021`
   - `http://localhost:8200/api/data-agent/realtime-catalog`
   - `http://localhost:8200/api/realtime-demo/manifest`
   - `http://localhost:8200/api/realtime-demo/firms-archive/manifest`
   - `http://localhost:5173/realtime-monitor`
10. 最后报告当前分支、恢复文件、数据库记录数、容器状态、接口状态和任何冲突。不要自动提交或推送当前成员分支。

完整规则与目录说明见 `docs/MEMBER_A_FINAL_HANDOFF.md`。
