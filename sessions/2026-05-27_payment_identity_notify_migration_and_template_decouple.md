# 2026-05-27 PaymentIdentity 决策时机迁回 notify + 真机测试核查清单 + 小程序解除 pages/template 引用

按时间线/主题整理。会话起始 start-work（snowmeet_ai_doc pull 已 up to date，HEAD 含 2026-05-21 的养护明细合并 sheet 工作）。距上次会话 5 天间隔，期间数据导出线告一段落，转回 2026-05-14 留的支付前身份验证线。三条主线：① PaymentIdentity 决策时机从"立即生效"迁到 notify 回调；② 为接下来的真机测试准备核查清单；③ 用户随后追加要求：小程序解除对 `pages/template/` 的所有引用。

## 1. 进度盘点：支付前身份验证当前状态

用户问"只需要顾客扫一次码的小程序开发到哪一步了"。直接看代码 + git log 确认：

- **两个仓库均在 `ai` 分支、与 origin/ai 同步**
- **最后改动都在 2026-05-14**：
  - SnowmeetApi: `8fae4582 bug` / `2750e00c pay test`（5-14）触动 PaymentIdentityController，之后 13 天无 commit 触及这条线
  - snowmeet_wechat_mini: `fa5f5b0c new payment` / `53b851cd entry`（5-14）触动 payment_entry/pay-identity-confirm
- 全部精力在 5-14 后转入数据导出（养护/零售/雪票财年导出、明细合并 sheet、孤儿核对等）

**确认现状**（与 CLAUDE.md 2026-05-14 节一致）：

| 模块 | 状态 | 缺啥 |
|---|---|---|
| 后端 `PaymentIdentityController.cs`（569 行 + sessionKey 兜底） | ✅ 编译 + swagger 烟测过 | 仅"立即生效"待迁 |
| 后端 DB schema（`wechat_unverified` + `is_proxy_pay`） | ✅ 用户已 ALTER TABLE | — |
| 前端 `components/pay-identity-confirm/`（4 文件，4 态卡片） | ✅ 静态完整 | — |
| 前端 `pages/order/payment_entry.{js,wxml,json}` 接入 identity 状态机 | ✅ | — |
| 真机端到端测试 | ⏳ 未做 | 需部署 ai 后端 + 重编小程序 + 真账号 |
| 支付宝真实手机号解密 | ⏳ 仍是 stub（`phoneMock` 走通） | 接 `alipay.system.oauth.token` + `user.info.share` |
| **决策时机迁到 notify 回调** | ⏳ 是本次目标 | 见下文 |

## 2. 决策时机迁回 notify 回调（SnowmeetApi）

### 2.1 问题与原方案

**之前（5-14 mvp 简化版语义）**：用户在 `payment_entry` 点完「正常支付（订单转归我）」/「替人代付」/「确认并继续」（4 状态中 self / proxy / confirm_direct 三种确认动作），`PaymentIdentityController` 立即落库 4 个字段：
- `Order.member_id`（订单归属，self/direct_to_scanner 走这条）
- `OrderPayment.member_id`（付款方）
- `OrderPayment.is_proxy_pay`（代付标记）
- `Order.wechat_unverified`（支付宝场景一律置 true）

**潜在 bug**：用户选完确认按钮后**关闭小程序不付款**（中途放弃），`Order.member_id` 已被错误改写。CLAUDE.md 5-14 自留笔记标注「本期为简化采用'用户确认即落地'」。

### 2.2 方案选择（架构权衡）

调研发现两个 notify (`TenpayController.cs:433` 微信 / `AliController.cs:634` 支付宝) 都汇聚到 `OrderController.DealSuccessPaidOrder(orderId, paymentId)` — 天然唯一挂载点。

**方案 A（更彻底）**：加 `OrderPayment.pending_identity_choice` (string) + `pending_scanner_member_id` (int?) 暂存列；用户选择仅写暂存；notify 后消费暂存写正式字段
- ❌ 需要 ALTER TABLE 加列、改 schema、迁数据
- ✅ 意图与最终落地完全解耦

**方案 B（按字段语义拆层，推荐）**：
- `OrderPayment.member_id` / `is_proxy_pay` 是付款方意图（这笔 payment 的发起方信息），与支付是否成功无关 → 用户选完即写
- `Order.member_id` / `wechat_unverified` 是订单归属/通道标记 → 仅支付成功才写
- ✅ 不加列、不动 schema、前端零改动
- ✅ 利用字段本身语义自然分桶，比新增 pending_* 暂存表更简洁

用户确认走方案 B。

### 2.3 实现（2 文件改动）

**`PaymentIdentityController.cs`**：
- `_applyChoice`（line 360-415）：删 `order.member_id = scannerMemberId;`（self 分支）/ `if (payerType == "alipay") { order.wechat_unverified = true; }` / `order.update_date = DateTime.Now;` / `_db.order.Entry(order).State = EntityState.Modified;` 共 5 行；保留 op 写入
- `_applyConfirmDirect`（line 417-460）：同上，删 `if (pre.status == "direct_to_scanner") { order.member_id = scannerMemberId; }` / wechat_unverified 写入 / order 持久化 共 7 行
- `order` 变量保留（仍用于 `if (order == null || op == null)` 检查）
- 加注释「决策时机迁回 notify：此处只在 OrderPayment 上写付款方意图，Order.member_id / wechat_unverified 由 DealSuccessPaidOrder 在支付成功回调时同步」

**`OrderController.cs DealSuccessPaidOrder`**（line 1753 起）：`UpdateOrder` 调用前插同步逻辑：

```csharp
if (paymentId != null)
{
    OrderPayment paidOp = await _db.orderPayment.Where(p => p.id == paymentId.Value)
        .AsNoTracking().FirstOrDefaultAsync();
    if (paidOp != null)
    {
        if (paidOp.is_proxy_pay == false && paidOp.member_id != null && order.member_id == null)
        {
            order.member_id = paidOp.member_id;
        }
        if (paidOp.pay_method != null && paidOp.pay_method.Trim() == "支付宝" && !order.wechat_unverified)
        {
            order.wechat_unverified = true;
        }
    }
}
```

**关键设计**：
- `is_proxy_pay == false` 守卫确保代付订单仍归原会员（不被 op.member_id 覆盖）
- `order.member_id == null` 守卫确保不覆盖已有归属
- 不手写 CoreDataModLog：`UpdateOrder` 内置 `Util.GetUpdateDifferenceLog(oriOrder, order, ...)` 自动比 oriOrder vs order 生成 diff 日志，scene=`支付成功`

### 2.4 验证

- `dotnet build`：0 错误 / 14 警告（全为历史文件 `Util.cs:WebRequest.Create` 等，新改动 0 新增警告）
- diff 统计：`PaymentIdentityController.cs` −22 +6 / `OrderController.cs` +18，合计净减 16 行
- 本机自动 commit `3f1dbac1 payment`（end-work hook 触发，待手动 push 到 origin/ai）

## 3. 真机测试核查清单

新建 [`payment_identity_real_device_test_checklist.md`](payment_identity_real_device_test_checklist.md)（~200 行）。给用户接下来部署完后照着跑用。

### 3.1 结构

- **0. 前置部署**：后端 ai 分支部署 / DB schema 二次确认（含 SQL）/ 小程序拉 ai 重编 / 准备 A/B/C 三个真机账号
- **1. 5 场景矩阵**（按 `_resolveStatus` 状态机决策树）：
  1. `direct`（A 扫自己单）— 不走 PaymentIdentity，作 baseline
  2. `direct_to_scanner`（订单无主、B 扫码）— 关键场景
  3. `choose_identity → self`（订单已匹配 A、B 选转归我）— 关键场景
  4. `choose_identity → proxy`（B 选替人代付）— 验证代付不同步
  5. `phone_required`（C 未绑手机号一键授权）
- **2. 支付宝通道**（如已对接，额外断言 `wechat_unverified` 延迟同步）
- **3. 异常路径 E1-E4**（迁移生效的核心证据）：
  - E1：choose self 后关闭小程序未支付 → Order.member_id 应保持原 A 不变
  - E2：direct_to_scanner 确认后未付 → Order.member_id 应保持 NULL
  - E3：choose proxy + 支付成功 → Order.member_id 仍是 A（不被 op.member_id 覆盖）
  - E4：同 paymentId 多次 ConfirmPayIdentity → 幂等锚生效
- **4. 排查指南**：5 类失败路径（迁移失效 / notify 钩子失效 / UI 不显示 / 一键授权失败 / 兜底接口调试）

### 3.2 每场景两阶段验证（核心设计）

- **阶段 A**：用户点完身份确认按钮立刻查 DB → 期望仅 `OrderPayment` 应有变化、`Order` 不变（迁移生效的核心断言）
- **阶段 B**：完成支付（或主动放弃）后查 DB → 期望 OP 不回滚 / Order 按规则同步（或不变）

每场景给可拷贝的 SQL 校验语句。

## 4. 小程序解除 `pages/template/` 引用（snowmeet_wechat_mini）

用户在 PaymentIdentity 工作中途追加要求："`pages/template/` 下任何文件不允许被引用，已引用的需要把引用的文件 copy 到自己的目录下。"

### 4.1 调查

`pages/template/` 目录有 32 个文件：`stitch/{_1,_2,_3,_4,_5}/index.{js,json,wxml,wxss}` × 5 + `stitch/tokens.wxss` + `stitch/alpine_operational_minimalist/DESIGN.md` + 5 个 screen.png + 5 个 code.html。是 Alpine Operational Minimalist 设计稿原型，仅作设计参考，不该被生产代码依赖。

grep `pages/template` 全项目（排除 template 内部互相引用）盘点 9 处外部提及：

| # | 类型 | 位置 | 处理方式 |
|---|---|---|---|
| 1 | **硬引用**（编译期） | `pages/payment/settle/index.wxss:1` `@import "/pages/template/stitch/tokens.wxss"` | copy tokens.wxss 到 settle/，改 import 为 `./tokens.wxss` |
| 2 | **硬引用**（page 注册） | `app.json:107` 注册 `pages/template/stitch/_5/index` 为正式页面 | 移除注册行 |
| 3-7 | 注释提及路径 | 5 处 wxml/js/wxss 头部注释「设计参考」/「视觉参考」/「mirror of」 | `pages/template/stitch/_X` → `Alpine Operational Minimalist stitch _X`（保留设计语义、去具体路径） |
| 8 | 开发者工具配置 | `project.private.config.json` 2 个 list 项 `stitch` 和 `pages/template/stitch/_2/index` | 删两个自定义启动页（项目被 git 跟踪，跨开发者同步） |

### 4.2 实施

**改 9 文件 + 新增 1 文件，−15 行净减**：

```
新建 pages/payment/settle/tokens.wxss            (212 行，copy 自 template，去掉 "Source: pages/template/..." 注释)
改   pages/payment/settle/index.wxss              @import → ./tokens.wxss
改   app.json                                     移除 _5/index page 注册
改   project.private.config.json                  删 2 个 template 启动页
改   components/reception/rent_recept_form/rent_recept_form.js / .wxml   注释 _2/_4 → 通用描述
改   pages/admin/reception/recept_package.wxml    注释 _3 → 通用描述
改   pages/admin/reception/recept_entry.wxml / .wxss   注释 _1 → 通用描述
```

### 4.3 校验

```
grep "pages/template" 全项目 (排除 template 自身) → 0 处 ✓
grep "tokens.wxss"   全项目              → 仅 1 处指向 settle 自己目录的本地副本 ✓
```

**`pages/template/` 目录本身保留**：用户未要求删，且其内部 5 个 `_X/index.wxss` 都 `@import "../tokens.wxss"` 闭环引用，作为设计原型留着无害。**关键里程碑：现在删 template 对小程序运行/编译零影响。**

snowmeet_wechat_mini 已自动 commit `7d1ec793 remove inter ref` + merge + push 到 origin/ai（end-work hook 触发）。

## 关键改动文件

| 仓库 | 文件 | 操作 |
|---|---|---|
| SnowmeetApi (ai) | `Controllers/Order/PaymentIdentityController.cs` | `_applyChoice` / `_applyConfirmDirect` 删 order 写入共 12 行 |
| SnowmeetApi (ai) | `Controllers/OrderController.cs` | `DealSuccessPaidOrder` `UpdateOrder` 前插 15 行 op 同步 |
| snowmeet_ai_doc | `payment_identity_real_device_test_checklist.md` | 新建（~200 行真机测试核查清单） |
| snowmeet_wechat_mini (ai) | `pages/payment/settle/tokens.wxss` | 新建（212 行 copy 自 template/stitch/tokens.wxss） |
| snowmeet_wechat_mini (ai) | `pages/payment/settle/index.wxss` | `@import` → `./tokens.wxss` |
| snowmeet_wechat_mini (ai) | `app.json` | 移除 `pages/template/stitch/_5/index` page 注册 |
| snowmeet_wechat_mini (ai) | `project.private.config.json` | 删 2 个 template 自定义启动页 |
| snowmeet_wechat_mini (ai) | `components/reception/rent_recept_form/{js,wxml}` | 注释路径改通用描述 |
| snowmeet_wechat_mini (ai) | `pages/admin/reception/{recept_entry.{wxml,wxss},recept_package.wxml}` | 注释路径改通用描述 |

## 学到的小知识

1. **决策时机迁移最干净的实现是按字段语义拆层**：`OrderPayment.member_id` 是付款方记录（用户发起 payment 时就该写），`Order.member_id` 是订单归属（支付成功才能改）。两者本就不同语义，立即生效 vs 延迟生效按字段语义自然分桶，不需要 pending_* 暂存列。如果一开始字段建模时就有"付款方 vs 订单归属"两套字段，本次根本不会有"立即生效 vs 延迟生效"的争议
2. **`UpdateOrder` 的 `Util.GetUpdateDifferenceLog` 自动 diff 日志**：调用方修改 order 字段后调 UpdateOrder，CoreDataModLog 由 UpdateOrder 内部按 oriOrder vs order 比对自动生成，scene 参数控制日志 scene 字段。新功能写 order 落库前先看是否能借 UpdateOrder，比自己手 add log 更安全（不漏字段、自动 prev/current diff）
3. **wepay/alipay notify 汇聚点**：`OrderController.DealSuccessPaidOrder(orderId, paymentId)` 是 `TenpayController.cs:433` + `AliController.cs:634` 双通道唯一汇聚。任何"支付完成后才做"的逻辑都该挂这里
4. **小程序的 `@import` / `usingComponents` 暗依赖**：wxss `@import` 语法和 CSS 一致，看着没注释里那么显眼。清理"不允许引用某目录"类需求时，grep 目录名之外还要 grep 该目录里的关键文件名（tokens.wxss 等）兜底
5. **`project.private.config.json` 虽叫 "private" 但被 git 跟踪**（不在 .gitignore）：里面的"自定义编译启动页"配置跨开发者同步。如有指向已删除文件的预设会导致同事打开工具时报"页面不存在"。删 pages 时要顺手扫这个文件
6. **PowerShell `Set-Location` 与 `cd` 的隔离差异**：本会话用 Bash `cd` 后跑 `git status` 显示无改动，但 `Set-Location` + `git status` 显示真实状态。Windows 上多 shell 切换时 git 看到的 working dir 可能与你 cd 的位置不一致；PowerShell 路径更可靠
7. **end-work Stop hook 实测已在本机生效**：本会话 SnowmeetApi 改动被自动 commit 成 `3f1dbac1 payment`（未 push）、snowmeet_wechat_mini 自动 commit `7d1ec793 remove inter ref` 并 merge + push 到 origin/ai。手动还要补 push SnowmeetApi（hook 写在 SnowmeetApi 仓库的范围可能没覆盖到 push）
