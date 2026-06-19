# 2026-06-19 start-work/end-work 跨机一致固化 + 6-17 工作考古

本场不是常规开发，而是工作流维护 + 一次「考古」。用户先让总结 6-17 的工作（CLAUDE.md 开发日志缺 6-16/6-17），随后引出真正诉求：**start-work/end-work 要在所有电脑上执行效果一致**。改动落在 `snowmeet_ai_doc/.claude/skills/`（doc 仓），业务代码零改动。

## 1. 6-17 工作考古（无 git diff，靠文件 mtime + 代码现状推断）

工作目录 `D:\source\snowmeet\ai` 本身非 git 仓，无法 diff。按 6-17 文件 mtime 聚类（排除两批同时刻的批量同步 10:29:53 / 15:31:26-40，那是代码同步不是逐个编辑），真正单独编辑的文件集中在下午 15:59 之后。

### 1.1 主线：租赁物「更换」功能（前后端完整闭环，高置信度，已读码确认）

- 上午同步进设计稿 [templates/rent/order_detail_change_rent_item.html](../templates/rent/order_detail_change_rent_item.html)
- 后端 [RentController.cs](../../SnowmeetApi/Controllers/RentController.cs)（15:59）：`GetChangeCompatibleCategory`/`QueryChangeCompatibleCategory`（拉可更换兼容品类）、`ChangeRentItem`/`ChangeRentItemByStaff`（原件置「已更换」+ 建新件 + 写 `core_data_mod_log`「更换租赁物」）、`GetRentItemChanges`/`GetRentItemChangesLog`（更换记录递归链）
- 前端 [data.js](../../snowmeet_wechat_mini/utils/data.js)（16:02）：`queryRentItemChangeCompatibleCategory` promise
- 前端 [rent_order_detail.{js,wxml,wxss}](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js)（20:38–21:38）：`_chg*` 更换弹窗（选兼容品类 picker / 无编码切换 / 扫码 / 备注 + 二次确认）→ `Rent/ChangeRentItemByStaff`；「更换记录」展开 `getRentItemChange`→`GetRentItemChanges`；已更换物 `_replaced` 置灰 / 不计件 / 隐藏发放记录

### 1.2 主线：支付身份确认即落库扫码方 openid（后端，高置信度，已读码确认）

- [PaymentIdentityController.cs](../../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs)（21:30）新增 `_persistPayerOpenId`，在 `_applyChoice` / `_applyConfirmDirect` 调用：身份确认那一刻就把扫码方第三方 openid 落到 `order_payment`（微信→`open_id`，支付宝→`ali_buyer_id`），修「此前身份确认只写 `member_id`、openid 已解析却漏写表」。与 auto-memory 的「Payment identity flow openid 列约定」是同一条线

### 1.3 下午一批前端小改（置信度低，未精确还原）

- order-payment 组件、rent_recept_form、旧版 rent_details（16:09–16:32）也被动过，通读未见明显新功能特征；无 diff 基线无法还原具体行
- `config.sqlServer`（20:24）只是本机数据库连接配置，非业务改动

### 1.4 待办提醒（基于代码事实）

- 更换功能 + openid 落库都在后端 → 需重新部署 SnowmeetApi 才生效
- [rent_order_detail.js](../../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js) 第 956 行临时诊断 `console.log('[储值付租金] tap',…)`（6-15 续3 标记的待删项）6-17 仍在，上线前删

## 2. start-work/end-work 跨机一致修复（本场真正的产出）

### 2.1 诊断：为什么「每台机不一样」

- 查清现状：skill 文件在 `snowmeet_ai_doc/.claude/skills/`（入 git、跨机一致）；这台机工作目录 `D:\source\snowmeet\ai` 的 `.claude` 无 skills、全局 `~/.claude/skills` 不存在 → Claude Code 是**递归扫到子目录** `snowmeet_ai_doc/.claude/skills/` 才发现这俩 skill 的
- **根因**：end-work 的「自动 git push」「不需确认」这些行为，历史上靠 **Mac 那台的 Stop hook + 本机 auto-memory** 实现，而 `settings.local.json`（hook 所在）和 memory **都不入 git、不跨机**。这台 Windows 机 `settings.local.json` 里根本没 hook → 换机就不 push。**关键动作没写进唯一跨机的 SKILL.md。**

### 2.2 修复：把关键动作固化进 SKILL.md（git 跨机）

- [end-work/SKILL.md](../.claude/skills/end-work/SKILL.md)：加「⚠️ 跨机一致原则」；Process 补 **git pull（第 1 步）+ git add/commit/push（第 6 步固定收尾）**；删「draft → 等用户确认」改直接落盘；加「memory 对账」步骤
- [start-work/SKILL.md](../.claude/skills/start-work/SKILL.md)：加「跨机一致 & memory」小节 + 新电脑首次使用确认点

### 2.3 settings.local.json 转本机不跟踪

- 发现 `.claude/settings.local.json` 被 git 跟踪、内容还是旧 Mac permission 路径（`/Users/cangjie/...`）→ 另一个跨机互相覆盖源
- `git rm --cached` + 写进 `.gitignore`；副作用：其它电脑 pull 后会删本地该文件（过时 Mac 配置，可接受，各机自行重建）
- 已 commit `89c730f` + push origin/main（本会话单独推送，先于 end-work 归档）

### 2.4 跨机一致的最后一环（发现机制，需人保证）

每台新电脑首次确认 3 点：① `snowmeet_ai_doc/` clone 在 `<工作目录>/snowmeet_ai_doc/` ② 在父工作目录启动 Claude Code ③ `/start-work`、`/end-work` 在 skill 列表里。没出现就直接在 `snowmeet_ai_doc` 目录里启动（则 `.claude/skills` 是项目根级，必被发现）

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [.claude/skills/end-work/SKILL.md](../.claude/skills/end-work/SKILL.md) | 跨机一致原则 + git pull/commit/push 固化 + 删等确认 + memory 对账 |
| [.claude/skills/start-work/SKILL.md](../.claude/skills/start-work/SKILL.md) | 跨机一致 & memory 小节 + 新机确认点 |
| [.gitignore](../.gitignore) | 加 `.claude/settings.local.json` |
| `.claude/settings.local.json` | `git rm --cached`（停止跟踪，保留工作区文件） |

## 学到的小知识

1. **Skill 工具加载的是会话启动时缓存的 SKILL.md**：本场改完 SKILL.md 并 commit 后，会话内触发 `/end-work` 拿到的仍是旧版（带「Ask for confirmation」、无 push 步骤）。SKILL.md 改动要**下次会话**（重新加载）才生效；本会话按新版约定手动执行
2. **Claude Code 会递归发现子目录的 `.claude/skills`**：工作目录非 git 仓、其 `.claude` 无 skills、全局也无，skill 仍能用 → 唯一来源是子目录 `snowmeet_ai_doc/.claude/skills`。这是「把 skill 放进 git 子仓还能被发现」的基础
3. **「每台机不一样」的根源 = 关键行为依赖了不跨机的载体**：hook（`settings.local.json`，gitignored / 本机）+ auto-memory（本机）。要跨机一致，逻辑必须写进随 git 走的 SKILL.md，不能靠 hook/memory
4. **memory vs doc 的正确分工**：doc（CLAUDE.md / sessions，git 跨机）是项目知识真源；memory（本机）只放个人偏好 + 指向 doc 的精简书签。end-work 新增「memory 对账」把项目类 fact 下沉到 doc
5. **`git rm --cached` 的跨机副作用**：停止跟踪 + commit 后，其它机器 pull 会删除它们工作区的该文件（git 视为删除）。对机器本地配置文件要权衡——本场因内容是过时 Mac 配置，可接受
6. **非 git 工作目录无法考古 diff**：6-17 的改动只能靠文件 mtime 聚类 + 读代码现状推断，下午那批小改无法精确还原 —— 这恰恰反证了 end-work 实时归档的价值
