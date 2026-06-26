# 2026-06-26 旧接待加新版入口 + 删孤立组件 + 退款/支付页 bug + 次卡使用记录回补

接续 6-24 后续打磨。本场杂项偏多：旧版接待页加新版入口、清死代码组件、定位扫码"支付记录不存在"、修支付宝总计/退押金两 bug，最后一个较大任务是从 rental 反推次卡使用记录回补 `punch_card_used`（plan 流程 + 落库 17 条）。代码改动散落 `snowmeet_wechat_mini` / `alipay_snowmeet` 工作区**未提交**；数据回补脚本入 `snowmeet_ai_doc`。

## 1. 旧版接待页加「进入新版」按钮

- 页面是旧版 [`pages/admin/recept/recept_entry`](../snowmeet_wechat_mini/pages/admin/recept/recept_entry.wxml)（标题"业务接待用户身份验证"，含扫码/手机号/散客三块）。
- wxml 在"散客"下方加"新版接待"`mp-cells` 区块 + 蓝色 `进入新版` 按钮；js 加 `goNewVersion()` → `wx.navigateTo` 跳 `/pages/admin/reception/recept_entry`（新版开单入口）。

## 2. 删自定义孤立组件（47 文件）

- 起因：微信开发者工具上传报"241 个文件未打包（无依赖文件）"，用户要全删。
- **关键澄清：「未打包/无依赖」≠ 可安全删**。分三类，删法不同：
  - `package.json`/`package-lock.json`：npm 构建必需，删了"构建 npm"崩
  - `miniprogram_npm/@vant/weapp/*`：构建 npm 产物，列出的全是没被任何 usingComponents 引用的 vant 组件（在用的 24 个不在列表里）；手动删下次构建又生成、且本就被微信自动排除上传，删了白删
  - `project.private.config.json`：工具配置，会重建
- 用户选"只删自定义孤立组件"。逐个核实无引用后删（drag 那两个匹配是 `/index` grep 假阳性，精确核实确实无引用）。
- 删除：`drag.wxss`/`vtab.wxss` + `components/{drag,mi7_order,order_type,recept}` 整目录 + `date_selector/date_selector_double.*`（保留在用的 `date_selector.*`）+ `components/rent/{order_summary,rental_list}.*`（`components/rent/` 其余在用全保留）。共 git 标记删除 47 文件。
- 残留：`components/rent/recept_package.wxss` 头一句注释写错成 `/* order_summary.wxss */`，无害，未动。

## 3. 「支付记录不存在」根因（paymentId=42662）

- 报错来自 [`PaymentIdentityController._resolveStatus`](../SnowmeetApi/Controllers/Order/PaymentIdentityController.cs#L212)：查 `id=42662 AND valid=1` 查不到。
- DB 直查订单 71796：三条支付单 42662(微信,valid=0)/42663(支付宝,valid=0)/42664(支付宝,**valid=1**)。
- 真相：店员切换过支付方式，每次 `InvalidatePendingOrderPayments` 把旧单置 valid=0 新建一条。顾客扫的是**过期的旧二维码**（42662，且 payerType=alipay 配的是微信旧单，不匹配）。**符合设计、非 bug**，但顾客侧体验差。
- 未改代码（可选改进：valid=0 时回查当前有效单或给"二维码已失效"明确提示）。

## 4. 支付宝小程序支付页总计显示 ¥0（bug）

- 现象：`alipay_snowmeet` 支付页"总计 ¥0.00 / 需要支付 ¥0.01"对不上（订单 71796，雪杖 ¥0.01 押金）。
- 根因：[`payment_entry/index.js`](../alipay_snowmeet/pages/payment_entry/index.js) 总计绑 `order.total_amount`，而**租赁订单 total_amount 恒为 0**，真实应付在 `paying_amount`。微信端 6-20 已修，支付宝端（独立代码库）没跟上。
- 修复（照搬微信端两处）：总计改 `order.paying_amount || 0`；日租金优先用 `pricePresets`（付款前 rental_detail 未生成）。

## 5. rent_order_detail 退款两 bug

### 5.1 未支付订单显示应退押金 ¥0.01
- 根因：[`rent_order_detail.js:432`](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js#L432) 押金基数用 `order.totalGuarantyAmount`（配置应收押金），未付订单也算可退。
- 这是 6-20续3 修复（已付订单 71766 应退算成 0）的反向副作用。
- 修复：基数封顶到实收 `Math.min(totalGuarantyAmount, order.paidAmount||0)` → 未付(paidAmount=0)应退 0；已付 71766 仍 0.01，不破坏旧修复。

### 5.2 退款按钮 disabled 样式却可点
- 根因：`van-button` 同时写 `disabled` + **`bindtap`**；vant 的 disabled 只拦内部 `click`、拦不住 `bindtap`（组件根节点原始 tap）。
- 修复：`bindtap="onRefund"` → `bind:click="onRefund"`；并在 `onRefund` 入口加防御性守卫（与 wxml disabled 同条件，未全退租给 toast）。

## 6. 次卡使用记录回补 punch_card_used（plan 流程 + 落库）

需求：`punch_card_used` 表 0 行，从 rental 反推**租赁**次卡使用记录回补；`rental.memo` 含"次卡"且有效订单；租赁一天算 1 次。

### 6.1 数据摸查（只读）
- `memo LIKE '%次卡%'` 有效 rental 共 **31 条 / 22 订单**，全 order.valid=1 & rental.valid=1。
- `punch_card` 仅 12 张租赁卡（2026-03 建），覆盖不全。

### 6.2 用户拍板的口径
- **天数 = `end_date−start_date+1`，end_date 空算 1 天**（不用 rental_detail 租金行数，那个有 0 和 211 异常）
- 会员→卡：member_id + biz_type='租赁'，仅"恰好 1 张"自动回补
- 无卡 10 条人工核；多卡（会员 30870，卡 22/23）3 条人工核；settled=0（17766，211 天虚账）跳过
- 每条 rental 各记一条 + 累加 punches

### 6.3 分桶 + 落库
- 自动回补 **17** / 无卡人工核 10 / 多卡人工核 3 / 跳过 1。
- 新建脚本 [`backfill_punch_card_used.py`](../snowmeet_ai_doc/backfill_punch_card_used.py)（pyodbc，默认 dry-run、`--apply` 落库、幂等）。
- 落库：`punch_card_used` 插 17 行；8 张卡 punches 重算写回，逐卡与 used 合计一致、均 ≤ total 无溢出。
- 未处理 13 条留 [`punch_card_used_manual_review.csv`](../snowmeet_ai_doc/punch_card_used_manual_review.csv)。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/admin/recept/recept_entry.{wxml,js}` | 加"进入新版"按钮 + goNewVersion |
| `snowmeet_wechat_mini/` 47 文件 | 删自定义孤立组件 |
| `alipay_snowmeet/pages/payment_entry/index.js` | 总计改 paying_amount + 日租金 pricePresets |
| `snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/{js,wxml}` | 押金基数封顶实收 + van-button bind:click + onRefund 守卫 |
| `snowmeet_ai_doc/backfill_punch_card_used.py` | 新建：次卡使用记录回补脚本（已 apply 17 条） |
| `snowmeet_ai_doc/{backfill_punch_card_used.sql, punch_card_used_manual_review.csv}` | 生成的 SQL + 13 条人工核 CSV |

## 学到的小知识

1. **微信"未打包/无依赖文件"≠ 可删**：package.json/miniprogram_npm/project 配置都在列表里但删不得（npm 构建依赖 / 构建产物会重生成 / 工具重建）。只有自定义 component（必须 usingComponents 静态引用）确凿无引用才安全删。
2. **`van-button` 的 disabled 只拦 `bind:click`、拦不住 `bindtap`**：原始 tap 抓组件根节点，绕过 vant 内部 disabled 判断。要靠 disabled 屏蔽点击必须用 `bind:click`，并在 handler 加守卫双保险。
3. **应退押金基数要封顶到实收**（`min(配置押金, paidAmount)`）：`totalGuarantyAmount` 只是配置应收，未付订单会算出虚假应退。这是 6-20续3 改用配置押金修已付订单的反向副作用。
4. **支付宝小程序是独立代码库**，微信端修过的同类 bug（总计用 paying_amount 而非恒 0 的 total_amount）要单独同步过去。
5. **扫码"支付记录不存在"多是过期二维码**：切换支付方式后旧 OP 被置 valid=0，`CheckPayerIdentity` 只认 valid=1。先 DB 查该 paymentId 的 valid + 同订单有效单。
6. **Driver 13 连接串不认 `Encrypt=True`**（要 `yes/no`）：config.sqlServer 是 Driver 18 写法，Intel Mac 跑要归一化 Encrypt=yes + TrustServerCertificate=yes。
7. **punch_card/punch_card_used 仍无 EF 模型**，纯 DB 回补；`id` 均 IDENTITY，insert 省略；punch_count 默认 1、valid 默认 1、create_date 默认 getdate()。
