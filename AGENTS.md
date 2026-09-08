# 星火智援 AI Coding 协作规则

本文件适用于所有在本仓库中工作的 AI Coding 工具。开始任何开发任务前，必须先完整阅读本文件，并遵守当前用户给出的具体任务范围。

## 1. 协作模式

- `main` 保存已经检查并合并的稳定版本，只有项目负责人负责合并和更新。
- 每位成员使用自己的长期开发分支，推荐命名为 `member/<github-username>`。
- 普通成员的 AI 不得直接在 `main` 上开发、提交或推送。
- 成员完成一个相对完整、可以单独检查的功能后，再通知项目负责人申请合并；不要求每天合并。
- `main` 更新后，每位成员下一次开发前必须先把最新 `origin/main` 合并到自己的分支。
- 不允许通过复制整个项目目录、覆盖整个文件或重新初始化 Git 仓库的方式完成合并。

## 2. 开始任务前必须执行

AI 应先确认当前目录、分支和未提交修改：

```powershell
git status
git branch --show-current
git remote -v
```

必须保留成员已有的未提交修改，不得擅自运行 `git reset --hard`、`git checkout -- 文件`、`git clean -fd` 或其他可能丢失代码的命令。

如果当前处于 `main`，普通成员的 AI 应先询问成员的 GitHub 用户名或指定分支，然后创建或切换到成员分支：

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c member/<github-username>
```

如果成员分支已经存在：

```powershell
git fetch origin
git switch member/<github-username>
git merge origin/main
```

如果工作区已有未提交修改，必须先判断这些修改属于谁、是否需要提交。不得为了同步 `main` 而丢弃现有修改。

## 3. 开发范围与文件边界

成员的 AI 只修改当前任务需要的文件，不能顺手重构无关代码。

默认职责边界：

- GIS 与卫星成员：`data/`、数据处理脚本、卫星模拟和识别模块、数据入库脚本。
- 感知与 Agent 成员：观测、MQTT、Node-RED、无人机、Qwen-VL、证据融合、Agent和审批相关后端。
- 空间决策成员：`backend/forefire_api/`、ForeFire、影响分析、路径规划和资源推荐。
- 前端集成成员：`src/`、Cesium、页面交互、人工确认界面和报告展示。

以下是高冲突公共文件：

- `compose.yaml`
- `src/api/modules.ts`
- `src/stores/fireEventStore.ts`
- `fire_agent_backend/app/main.py`
- 公共数据库模型与公共 Schema
- `docs/API_CONTRACT.md`
- `.env.example`

普通成员确实需要修改公共文件时，可以修改，但必须在个人开发日志中单独列出修改原因、接口影响和需要集成人员检查的内容。`docs/API_CONTRACT.md` 的最终整理原则上由项目负责人或集成 AI 在功能合并时完成。

## 4. 开发过程中必须记录的内容

每位成员维护自己的日志文件：

```text
docs/dev-logs/<github-username>.md
```

不要让多人共同编辑同一个日志文件。每次开发至少记录：

1. 日期、分支和本次任务目标。
2. 已完成的功能。
3. 修改、新增和删除的主要文件。
4. 新增或修改的 API，包括请求和响应字段。
5. 数据库表、字段、空间参考或数据文件变化。
6. 环境变量、依赖和 Docker 配置变化。
7. 已运行的验证命令及结果。
8. 尚未解决的问题、临时模拟内容和降级逻辑。
9. 对其他成员模块的依赖或可能造成的影响。
10. 建议项目负责人合并时重点检查的冲突位置。

日志格式按照 `docs/dev-logs/README.md` 中的模板填写。

## 5. 接口与数据规则

- 前端只访问同源 `/api` 和 `/ws`，不直接访问 ForeFire 服务。
- 8200 端口的 `fire_agent_backend` 是唯一业务编排后端。
- 5000 端口的 `backend/forefire_api` 只负责 ForeFire 计算。
- 不再向冻结的 `forest_fire_B` 增加新功能；其中有用算法应迁移到当前后端。
- 新增接口前先明确请求、响应、错误和状态变化，并在个人日志中记录接口提案。
- 不得用硬编码结果冒充空间分析、路径计算、卫星识别或 ForeFire 输出。
- 演示用模拟数据必须标记为 simulated，真实数据和模拟数据必须能够区分。
- 不得将隐藏火点真值作为卫星识别算法输入。
- 不提交大型原始 GIS 数据，只提交下载说明、数据清单、处理脚本和必要的小样例。
- 不提交 `.env`、API Key、密码、数据库文件、日志、构建产物、虚拟环境或 `node_modules`。

## 6. 提交前验证

AI 应根据修改范围运行适当检查。仓库级基础检查为：

```powershell
npm run build
python -m compileall fire_agent_backend/app backend/forefire_api/app
docker compose config --quiet
```

如果只修改单一模块，也必须至少运行该模块的语法、单元或接口检查。无法运行 Docker、外部模型或真实数据测试时，要在日志和交付说明中明确写出“未验证”，不能写成已经通过。

提交前还要执行：

```powershell
git diff --check
git status
```

确认没有密钥、大型数据、无关文件和他人未完成修改被加入提交。

## 7. 提交与推送成员分支

只暂存本次任务涉及的明确文件，优先使用：

```powershell
git add 路径1 路径2 docs/dev-logs/<github-username>.md
```

不要习惯性使用 `git add .`，避免把 `.env`、下载数据或无关修改一起提交。

提交说明应简短明确，例如：

```powershell
git commit -m "Add satellite hotspot detection pipeline"
git push -u origin member/<github-username>
```

后续在同一分支推送时：

```powershell
git push origin member/<github-username>
```

禁止执行：

```powershell
git push --force
git push origin main
```

除非当前操作者明确是项目负责人并且正在执行已经确认的功能合并。

## 8. 推送完成后必须给成员的交付摘要

AI 完成推送后，应向成员明确报告：

- 当前分支名。
- 最新提交的短哈希和提交说明。
- 已完成内容。
- 主要修改文件。
- 接口、数据库或配置变化。
- 已通过和未执行的测试。
- 已知问题。
- 是否可以交给项目负责人合并。

不能只回复“已经完成”或“已经上传”。

## 9. main 更新后同步最新版本

项目负责人完成一次功能合并并推送 `main` 后，成员下一次开始开发前必须执行：

```powershell
git fetch origin
git switch member/<github-username>
git merge origin/main
git push origin member/<github-username>
```

建议直接让成员的 AI 执行，并对 AI 说：

> 请先阅读仓库根目录 AGENTS.md。项目负责人已经更新 main，请在保留我现有修改的前提下，把 origin/main 合并到我的成员分支，处理并说明冲突，完成必要测试后推送成员分支。不要向 main 推送。

## 10. 冲突处理规则

- Git 能自动合并时仍需运行测试。
- 出现冲突时，先查看双方提交、个人日志和接口约定，再决定如何组合逻辑。
- 不得直接采用“全部保留当前版本”或“全部保留对方版本”。
- 不得为了消除冲突删除另一成员已经完成的功能。
- 无法确定业务意图时，停止该冲突文件的处理并请项目负责人决定。
- 冲突解决后必须重新运行相关测试，并在日志中记录冲突文件和处理方式。

## 11. 项目负责人功能集成规则

项目负责人不需要每天固定合并。成员完成一个相对完整、可以独立验证的功能并推送成员分支后，再由项目负责人进行合并。建议一次只合并一个成员分支，并在每次合并后运行检查。

推荐顺序：

1. GIS 数据与卫星识别。
2. 传感器、融合与 Agent。
3. ForeFire、空间分析、路径与资源。
4. 前端与系统集成。

如果前一个合并改变了公共接口，后续准备合并的分支应先同步最新 `main`，再进入最终合并。合并并验证完成后，由项目负责人推送 `main`，并通知所有成员在下一次开发前同步。
