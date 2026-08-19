# Git 项目管理常用指令与用法

本文面向日常项目管理和个人平台开发，目标是避免误删、误覆盖和远端同步混乱。默认你在项目根目录执行命令。

## 0. 基本原则

- 每次动手前先看状态：`git status -sb`
- 提交前先看改了什么：`git diff`
- 不确定远端有没有变化时，先 `git fetch origin`
- 不要随手用 `git push --force`
- 不要用 `git reset --hard` 处理你还没理解的变更
- 一次提交只解决一个清晰目标

## 1. 查看状态

查看当前分支、暂存区和工作区：

```bash
git status -sb
```

查看当前分支和上游分支：

```bash
git branch -vv
```

查看远端地址：

```bash
git remote -v
```

查看最近提交：

```bash
git log --oneline --decorate --max-count=10
```

查看文件修改内容：

```bash
git diff
```

查看已经暂存、即将提交的内容：

```bash
git diff --staged
```

## 2. 初始化项目并连接 GitHub

如果本地还不是 Git 仓库：

```bash
git init
```

配置提交身份：

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

只给当前仓库配置身份：

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

连接远端仓库：

```bash
git remote add origin https://github.com/<user>/<repo>.git
```

如果已经有 `origin`，需要改地址：

```bash
git remote set-url origin https://github.com/<user>/<repo>.git
```

## 3. 添加、提交、推送

查看状态：

```bash
git status -sb
```

添加所有改动：

```bash
git add .
```

只添加某个文件：

```bash
git add README.md
```

提交：

```bash
git commit -m "Describe the change"
```

第一次推送当前分支到 GitHub：

```bash
git push -u origin main
```

之后推送：

```bash
git push
```

## 4. 拉取远端更新

只获取远端信息，不改工作区：

```bash
git fetch origin
```

查看本地和远端差异：

```bash
git log --oneline --left-right --graph main...origin/main
```

用 merge 方式拉取：

```bash
git pull --no-rebase
```

用 rebase 方式拉取：

```bash
git pull --rebase
```

建议：个人项目可以用 merge，团队分支同步常用 rebase，但要先理解它会改写本地未推送提交的历史。

如果本地仓库和 GitHub 初始化仓库各有独立首提交，需要允许合并无共同祖先的历史：

```bash
git pull origin main --allow-unrelated-histories --no-rebase
```

## 5. 分支管理

查看分支：

```bash
git branch
```

创建并切换到新分支：

```bash
git switch -c feature/uds-socketcan-probe
```

切换分支：

```bash
git switch main
```

把当前分支改名为 `main`：

```bash
git branch -M main
```

推送新分支并建立上游关系：

```bash
git push -u origin feature/uds-socketcan-probe
```

删除本地分支：

```bash
git branch -d feature/uds-socketcan-probe
```

删除远端分支：

```bash
git push origin --delete feature/uds-socketcan-probe
```

## 6. 常见冲突处理

拉取时出现冲突后，先看冲突文件：

```bash
git status
```

打开冲突文件，你会看到类似：

```text
<<<<<<< HEAD
本地内容
=======
远端内容
>>>>>>> origin/main
```

手工编辑成最终想保留的内容，然后：

```bash
git add <conflicted-file>
git commit
```

如果冲突文件里你确定要保留本地版本：

```bash
git checkout --ours <file>
git add <file>
git commit
```

如果确定要保留远端版本：

```bash
git checkout --theirs <file>
git add <file>
git commit
```

放弃这次 merge：

```bash
git merge --abort
```

放弃这次 rebase：

```bash
git rebase --abort
```

## 7. 撤销与恢复

撤销某个未暂存文件的本地修改：

```bash
git restore <file>
```

取消暂存，但保留文件修改：

```bash
git restore --staged <file>
```

修改最后一次提交信息：

```bash
git commit --amend -m "New commit message"
```

撤销一个已经提交的变更，生成新的反向提交：

```bash
git revert <commit-sha>
```

查看某个文件历史：

```bash
git log --oneline -- <file>
```

从某个历史版本恢复文件：

```bash
git restore --source=<commit-sha> -- <file>
```

高风险命令：

```bash
git reset --hard
git push --force
```

这两个命令会丢弃或覆盖历史。除非你明确知道后果，否则不要用。

## 8. 暂存临时工作

临时保存当前未提交改动：

```bash
git stash push -m "temporary work"
```

查看 stash：

```bash
git stash list
```

恢复最近一次 stash，并从 stash 列表删除：

```bash
git stash pop
```

恢复但保留 stash：

```bash
git stash apply
```

删除某个 stash：

```bash
git stash drop stash@{0}
```

## 9. 标签与版本

创建轻量标签：

```bash
git tag v0.1.0
```

创建带说明的标签：

```bash
git tag -a v0.1.0 -m "First runnable workbench baseline"
```

推送标签：

```bash
git push origin v0.1.0
```

推送所有标签：

```bash
git push --tags
```

查看标签：

```bash
git tag
```

## 10. 项目管理推荐工作流

### 个人主线开发

适合学习项目和个人平台：

```bash
git status -sb
git pull --no-rebase
# 修改代码和文档
git diff
git add .
git commit -m "Add UDS backend probe evidence"
git push
```

### 功能分支开发

适合多人协作或较大改动：

```bash
git switch main
git pull --no-rebase
git switch -c feature/<short-name>
# 修改代码和文档
git add .
git commit -m "Implement <feature>"
git push -u origin feature/<short-name>
```

然后在 GitHub 上开 Pull Request。

### 发布前检查

```bash
git status -sb
git diff --staged
python -m unittest discover -s tests -v
git log --oneline --max-count=5
```

## 11. 常见错误与处理

### `Author identity unknown`

原因：没有配置 `user.name` 或 `user.email`。

处理：

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### `non-fast-forward`

原因：远端有你本地没有的提交。

处理：

```bash
git fetch origin
git pull origin main --no-rebase
git push
```

如果是本地和远端各自初始化过：

```bash
git pull origin main --allow-unrelated-histories --no-rebase
git push
```

### `Need to specify how to reconcile divergent branches`

原因：Git 要你明确 pull 时用 merge、rebase 还是只允许 fast-forward。

一次性使用 merge：

```bash
git pull --no-rebase
```

设置当前仓库默认使用 merge：

```bash
git config pull.rebase false
```

### `CONFLICT (add/add): Merge conflict in README.md`

原因：本地和远端都新增了同名文件。

保留本地：

```bash
git checkout --ours README.md
git add README.md
git commit
```

保留远端：

```bash
git checkout --theirs README.md
git add README.md
git commit
```

## 12. 提交信息建议

提交信息用一句话说明“做了什么”，例如：

```text
Bootstrap automotive workbench
Add UDS backend probe evidence
Document SocketCAN setup workflow
Fix DBC range validation
```

常用动词：

- `Add`: 新增能力
- `Fix`: 修复问题
- `Update`: 更新已有内容
- `Refactor`: 重构但不改变行为
- `Document`: 文档变更
- `Test`: 增加或调整测试

## 13. 本项目建议

本项目每次平台升级建议至少包含：

- 代码或文档改动
- 对应测试或 smoke command
- `docs/project/progress-log.md` 进度记录
- 清晰提交信息

推荐提交前运行：

```bash
git status -sb
git diff
PYTHONPATH=src .venv-linux/bin/python -m unittest discover -s tests -v
git add .
git diff --staged
git commit -m "<clear message>"
git push
```
