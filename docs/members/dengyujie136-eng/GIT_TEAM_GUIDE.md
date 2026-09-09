# 星火智援小组 Git 与 GitHub 使用指南

本指南面向第一次使用 Git 的小组成员。请先完整阅读“基本概念”和“首次准备”，日常开发时主要按照“推荐协作流程”操作。

项目仓库：<https://github.com/dengyujie136-eng/fire-command-system>

## 1. 先理解四个位置

Git 协作涉及四个不同位置：

1. **工作目录**：电脑上正在编辑的项目文件。
2. **暂存区**：本次准备提交的修改清单，由 `git add` 加入。
3. **本地仓库**：电脑上的提交历史，由 `git commit` 创建提交。
4. **GitHub 远程仓库**：所有组员共享的版本，由 `git push` 上传。

因此：

- 保存文件不等于提交 Git。
- `git commit` 只保存到本机。
- 执行 `git push` 后，GitHub 才能看到新提交。
- `git pull` 用于把 GitHub 上其他人的新提交同步到本机。

## 2. 小组协作规则

为减少代码冲突，请全组遵守以下规则：

1. `main` 始终保存经过检查、可以运行的版本。
2. 每个人开发新功能时创建自己的功能分支，不直接在 `main` 上长期开发。
3. 开始工作前先同步最新的 `main`。
4. 一次提交只完成一个明确任务，提交说明写清修改内容。
5. 功能完成后推送分支，并通过 Pull Request 合并到 `main`。
6. 禁止使用强制推送 `git push --force`。
7. 不提交密码、API Key、个人 `.env`、数据库、原始 GIS 数据、依赖目录和运行日志。
8. 遇到冲突时不要随意删除文件或覆盖别人的修改，先在小组内沟通。

## 3. 首次准备

### 3.1 安装 Git

从 Git 官方网站下载安装 Git：<https://git-scm.com/download/win>

安装完成后打开 PowerShell，执行：

```powershell
git --version
```

能够显示版本号即表示安装成功。

### 3.2 设置姓名和邮箱

每台电脑只需要设置一次。姓名建议使用真实姓名或小组内能识别的名字，邮箱建议与 GitHub 账号邮箱一致。

```powershell
git config --global user.name "你的姓名"
git config --global user.email "你的GitHub邮箱"
```

检查设置：

```powershell
git config --global user.name
git config --global user.email
```

### 3.3 接受仓库邀请

仓库管理员邀请成员后，成员需要：

1. 登录 GitHub。
2. 打开 GitHub 通知或邀请邮件。
3. 接受 `fire-command-system` 仓库邀请。
4. 确认可以打开项目仓库页面。

## 4. 第一次下载项目

先进入希望存放项目的父目录。例如：

```powershell
cd "C:\Users\你的用户名\Desktop"
```

克隆仓库：

```powershell
git clone https://github.com/dengyujie136-eng/fire-command-system.git
cd fire-command-system
```

检查仓库状态：

```powershell
git status
```

第一次推送时，GitHub 可能要求在浏览器中登录并授权。这是正常现象，但不要把密码、验证码或访问令牌发给其他组员。

## 5. 安装并检查前端

进入项目根目录后安装依赖：

```powershell
npm install
```

启动开发环境：

```powershell
npm run dev
```

生产构建检查：

```powershell
npm run build
```

`node_modules` 和 `dist` 不需要提交，它们已由 `.gitignore` 排除。

本机运行配置应从示例文件创建：

```powershell
Copy-Item .env.example .env
```

根据自己的环境填写 `.env`。不要把真实密钥提交到 GitHub。

## 6. 推荐协作流程：一个功能一个分支

下面以“实现火情分级预警”为例。

### 第一步：回到主分支

```powershell
git switch main
```

### 第二步：同步最新代码

```powershell
git pull --rebase origin main
```

如果这里出现未提交修改提示，先不要继续，参见“工作做到一半时需要同步”。

### 第三步：创建功能分支

```powershell
git switch -c feature/fire-warning
```

分支名建议使用英文小写和短横线：

- 新功能：`feature/fire-warning`
- 修复问题：`fix/map-display`
- 文档修改：`docs/update-readme`

每个人的分支名必须不同。

### 第四步：修改并测试

编辑代码后运行相应测试，前端至少执行：

```powershell
npm run build
```

### 第五步：检查修改

```powershell
git status
git diff
```

重点确认没有出现以下内容：

- `.env` 或密钥文件
- `node_modules`
- `.venv`
- 数据库文件
- 大体积原始数据
- 日志、缓存或临时截图

### 第六步：加入暂存区

确定所有改动都属于本次任务时：

```powershell
git add -A
```

再次检查：

```powershell
git status
```

如果只想提交指定文件，可以使用：

```powershell
git add src/views/RealtimeMonitor.vue
git add src/components/CesiumMap.vue
```

### 第七步：创建本地提交

```powershell
git commit -m "实现火情分级预警"
```

推荐的提交说明示例：

- `实现资源调度列表与地图联动`
- `修复火势推演时间轴显示错误`
- `补充后端启动说明`

避免只写 `update`、`修改`、`test` 等无法说明内容的文字。

### 第八步：推送功能分支

第一次推送该分支：

```powershell
git push -u origin feature/fire-warning
```

以后继续推送同一分支时，只需要：

```powershell
git push
```

### 第九步：创建 Pull Request

1. 打开 GitHub 仓库页面。
2. 点击 `Compare & pull request`，或进入 `Pull requests` 后点击 `New pull request`。
3. 确认目标分支是 `main`，来源分支是自己的功能分支。
4. 标题写明完成的功能。
5. 在说明中写清主要改动、测试方法和仍存在的问题。
6. 创建 Pull Request，请至少一名组员检查。
7. 检查通过后合并到 `main`。

Pull Request 说明可以使用以下格式：

```text
完成内容：
- 实现火情分级预警
- 增加证据来源展示

测试：
- npm run build 通过
- 已检查实时监测页面

注意事项：
- 需要在 .env 中配置后端地址
```

## 7. 合并完成后开始下一个任务

Pull Request 合并后，在本机执行：

```powershell
git switch main
git pull --rebase origin main
```

删除已经合并的本地功能分支：

```powershell
git branch -d feature/fire-warning
```

然后为下一个任务重新创建分支。

## 8. 只修改少量内容时的简化流程

如果组内约定由项目负责人直接更新 `main`，可以使用：

```powershell
git switch main
git pull --rebase origin main
git status
git add -A
git commit -m "说明本次修改内容"
git push origin main
```

多人同时开发时仍推荐使用功能分支和 Pull Request。

## 9. 工作做到一半时需要同步

如果你已经修改文件，但暂时不想提交，而 `git pull` 提示本地有修改，可以临时保存：

```powershell
git stash push -u -m "临时保存正在开发的内容"
git pull --rebase origin main
git stash pop
```

执行 `git stash pop` 后可能出现冲突。如果不熟悉冲突处理，应停止修改并联系组员共同处理。

查看临时保存列表：

```powershell
git stash list
```

## 10. 冲突是什么

当两个人修改了同一个文件的相同位置，Git 无法自动判断保留哪一份，就会产生冲突。

冲突文件中通常会出现：

```text
（开始标记）<<<<<<< HEAD
你当前分支的内容
（分隔标记）=======
另一个分支的内容
（结束标记）>>>>>>> 分支或提交名称
```

处理步骤：

1. 与相关组员确认正确内容。
2. 手动编辑文件，保留最终需要的代码。
3. 删除 `<<<<<<<`、`=======` 和 `>>>>>>>` 标记。
4. 重新测试程序。
5. 标记冲突已解决并继续：

```powershell
git add 冲突文件路径
git rebase --continue
```

如果只是 Pull Request 页面提示冲突，建议由项目负责人统一处理。

不要使用 `git reset --hard`、强制推送或直接删除冲突文件来处理不理解的问题，这些操作可能丢失代码或覆盖他人的提交。

## 11. 加错文件后怎么办

### 已执行 `git add`，但还没有提交

将文件移出暂存区，但保留本地修改：

```powershell
git restore --staged 文件路径
```

例如：

```powershell
git restore --staged src/views/RealtimeMonitor.vue
```

### 已提交但还没有推送

不要急着执行网上找到的重置命令。先联系项目负责人，根据具体情况选择新增修正提交或安全地调整提交。

### 已经推送到 GitHub

通常应通过一个新的提交修正：

```powershell
git add -A
git commit -m "修正上一次提交中的配置问题"
git push
```

不要删除公开历史或强制推送。

## 12. 常用查看命令

查看当前状态：

```powershell
git status
```

查看当前分支：

```powershell
git branch --show-current
```

查看本地分支：

```powershell
git branch
```

查看最近提交：

```powershell
git log --oneline -10
```

查看尚未暂存的修改：

```powershell
git diff
```

查看已经暂存的修改：

```powershell
git diff --staged
```

查看远程仓库：

```powershell
git remote -v
```

## 13. 常见错误

### `nothing to commit, working tree clean`

表示当前没有需要提交的修改，不是错误。

### `Your branch is ahead of origin/main`

表示本地已经提交，但还没有推送：

```powershell
git push origin main
```

如果当前在功能分支，使用：

```powershell
git push
```

### `Your branch is behind origin/main`

表示 GitHub 上有新提交，需要同步：

```powershell
git pull --rebase origin main
```

### `Permission denied` 或没有推送权限

检查：

1. 是否已经接受 Collaborator 邀请。
2. 浏览器登录的 GitHub 账号是否正确。
3. 当前仓库远程地址是否正确：`git remote -v`。
4. 是否有权限向目标分支推送。

### 推送被拒绝

通常是其他成员先推送了新提交。先同步，再推送：

```powershell
git pull --rebase origin main
git push origin main
```

如果出现冲突，不要反复执行命令，应先解决冲突。

## 14. 每次开发的最短检查清单

开始工作：

```powershell
git switch main
git pull --rebase origin main
git switch -c feature/你的功能名
```

完成工作：

```powershell
npm run build
git status
git diff
git add -A
git status
git commit -m "清楚说明本次修改"
git push -u origin feature/你的功能名
```

然后在 GitHub 创建 Pull Request，请组员检查并合并。

## 15. 遇到问题时需要提供的信息

向组员求助时，不要只说“Git 出错了”。请提供：

```powershell
git status
git branch --show-current
git log --oneline -5
git remote -v
```

同时复制完整错误信息，并说明执行错误前运行了什么命令。不要发送 `.env`、密码、访问令牌或其他密钥。
