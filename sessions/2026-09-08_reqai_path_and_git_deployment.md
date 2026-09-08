# 2026-09-08 reqai 路径统一与 Git 部署缺口：本机目录改名、线上改动待入库

按主题整理。本场先统一独立 reqai 项目的本机目录名，随后发现前一场为快速修复线上接口而使用 `scp` 直接部署，代码并未提交到 reqai Git 远端。这是一个必须在后续收口的部署一致性缺口。

## 1. 本机目录统一

- 本机独立仓从 `/Users/cangjie/Projects/snowmeet/snowmeet_reqai` 改名为 `/Users/cangjie/Projects/snowmeet/reqai`。
- Git 工作树、remote `git@github.com:cangjie/snowmeet_reqai.git` 和未提交改动均完整保留。
- 更新 `start-work` skill 与 `CLAUDE.md`，以后启动状态核查按 `reqai` 定位。
- 名称与另一台电脑及 Claude 的项目识别方式统一。

## 2. 发现的部署缺口

- 用户指出 reqai 本地 Git 工作区没有 commit。
- 前一场 reqai 生产修复通过 `scp` 传入 `/home/ubuntu/reqai/backend/` 后重启服务。
- 该方式让线上立即生效，但远端 Git 仓库没有对应提交。
- 后续服务器 `git pull`、重建或新机部署可能覆盖线上变更。
- reqai 当前本机改动包含管理员页面帮助、服务认证、查询意图、schema=5 migration 与结构化输出 effort 修复。

## 3. 后续第一优先级

1. 在 `/Users/cangjie/Projects/snowmeet/reqai` 审阅并提交本次 reqai 改动。
2. 推送到 `cangjie/snowmeet_reqai` 的 `main`。
3. 服务器 `/home/ubuntu/reqai` 以 Git 同步到该 commit；比对工作树后再保留/合并服务器本地附件功能改动。
4. 再次检查 reqai schema=5、两个服务路由、帮助/查询烟测和 `ari.goldenma.xyz`=200。

## 学到的小知识

1. **线上修复不等于已交付**：`scp + restart` 只能临时恢复服务；可重建的发布必须有对应 Git commit。
2. **独立项目目录名要跨机一致**：启动流程、自动化和 AI 项目识别都会依赖稳定路径。
