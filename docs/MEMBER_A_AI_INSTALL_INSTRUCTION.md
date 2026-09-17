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

## Shared FIRMS Key handoff

The shared FIRMS key is provided in `<handoff root>\\FINAL\\FIRMS_MAP_KEY.txt`. Configure that value in the local repository `.env` as `FIRMS_MAP_KEY`. Do not copy the member A `.env`. Do not print, commit, put the key in code, SQL, ZIP files, logs, or public documents. Do not push this key to GitHub.

## 必须额外提醒

- 不要把甲分支直接合并到自己的开发分支，除非用户明确要求；需要集成时交给汇总成员在 integration 分支处理。
- 不要把当前分支切换成 `member/qingzhe_ivory`，也不要用甲分支覆盖自己的分支。
- 不要执行 `docker compose down -v`，这会删除本机 Docker PostgreSQL 数据卷。
- 不要删除现有 `data` 目录，不要把两个 ZIP 直接解压到仓库根目录或 `data` 目录造成错误嵌套。
- 不要复制、打印、提交或传播甲的 `.env`、FIRMS MAP KEY、Cesium Token、LLM Key 或任何密码。
- 每台电脑的 Docker PostgreSQL 数据库都是独立的，必须分别导入 SQL 种子；复制仓库代码不会自动同步数据库。
- Sentinel-2 影像已单独交给乙、丙，不属于本通用交接包的必需文件。
- 甲的代码可通过 `git fetch origin member/qingzhe_ivory` 查看；最终由汇总成员在集成分支合并，不要直接修改 `main`。

## 交接目录的具体约定

用户会把甲发送的文件放到任意位置。先要求用户提供交接目录，记为 `<交接根目录>`；不要假定是 E 盘。文件应直接位于 `<交接根目录>\FINAL`：

```text
<交接根目录>\FINAL\qingzhe_ivory_dixie_fire_2021_data_bundle.zip
<交接根目录>\FINAL\dixie_fire_2021_database_seed.sql
<交接根目录>\FINAL\member_a_realtime_demo_data_20260917.zip
<交接根目录>\FINAL\member_a_realtime_database_seed_20260917.sql
<交接根目录>\FINAL\SHA256SUMS_20260917.txt
```

`<仓库根目录>` 是当前 Git 仓库实际位置，也不要假定为 E 盘。先校验 Hash，再将两个 ZIP 解压到 `<仓库根目录>\handoff_temp`。确认包内是 `data` 目录后，把其中的内容合并到 `<仓库根目录>\data`，不能形成 `data\data`，不能清空或全部覆盖已有数据。

在 `<仓库根目录>` 启动 Docker：

```powershell
docker compose up -d postgis fire-agent-api
```

然后恢复数据库：

```powershell
./scripts/restore-dixie-data-docker.ps1 -SeedPath '<交接根目录>\FINAL\dixie_fire_2021_database_seed.sql'
./scripts/restore-member-a-realtime-docker.ps1 -SeedPath '<交接根目录>\FINAL\member_a_realtime_database_seed_20260917.sql'
```

最后运行校验和接口检查。遇到工作区未提交修改、同名文件、Hash 不一致或数据库恢复错误时，停止操作并报告，不能使用强制覆盖命令。整个过程不得读取、复制或提交甲的 `.env`；FIRMS NRT 需要由本机用户自己配置个人 `FIRMS_MAP_KEY`。
