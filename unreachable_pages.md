# 小程序页面 / 组件可达性分析

> 生成日期：2026-07-27（**覆盖 2026-05-14 首版**）
> 复现方式：`py snowmeet_ai_doc/scan_unreachable_pages.py`
> 覆盖范围：`snowmeet_wechat_mini` 全部注册页面 + `components/` 下全部自定义组件

## 结论

| 指标 | 数量 |
|---|---|
| 注册页面 | **90**（主包 89 + 分包 1） |
| 自定义组件 | **48** |
| 有代码入口的页面 | 85 |
| 无代码入口但**有意保留**的页面 | 5（见下） |
| **孤儿页面** | **0** |
| **孤儿组件** | **0** |

2026-07-27 清理后已收敛。下次新增页面/组件后重跑脚本即可。

---

## 无代码入口、但必须保留的 5 个页面

静态分析看不到它们的入口，**不代表它们是死的**——入口在代码之外。

| 页面 | 入口性质 | 说明 |
|---|---|---|
| `pages/order/payment_entry` | 扫码落地 | 顾客扫店员支付二维码。代码里解析 `options.q` |
| `pages/order/identity_verify` | 扫码落地 | 储值付租金/次卡消费前的微信身份核验。解析 `options.q` |
| `pages/mine/ticket/ticket_bind` | ⚠️ 待核实 | 绑定优惠券。用 `/core/` 旧接口，疑似扫券码入口，**删前务必去公众平台核对规则** |
| `pages/register/reg` | ⚠️ 待核实 | 会员授权 + 「已和当前账户合并」提示。用到 `member-auth` 组件 |
| `pages/register/out_reg` | ⚠️ 待核实 | 只有一条 msg + 返回按钮，疑似跳板页 |

**保留决定会往下传递**：`reg` 保留 → 它唯一使用的 `components/user_info/auth_cell` 也必须保留。脚本里的 `KEEP_PAGES` 就是为此存在——实测把 `reg` 当死页，`auth_cell` 立刻被误报成孤儿。

---

## 代码外入口：公众平台扫码规则

「扫普通链接二维码打开小程序」的规则配在**微信公众平台后台**，不在代码里，任何静态分析都看不到。小程序侧生成的 `mapp/...` 链接如下，每一条背后都对应一条平台规则：

| 链接前缀 | 目标页面 | 生成位置 |
|---|---|---|
| `mapp/order_payment` | `pages/order/payment_entry` | [order-payment/index.js:239](../snowmeet_wechat_mini/components/order-payment/index.js#L239)、[rent_order_detail.js:1483](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js#L1483) |
| `mapp/order_verify` | `pages/order/identity_verify` | [order-payment/index.js:137](../snowmeet_wechat_mini/components/order-payment/index.js#L137)、[rent_order_detail.js:1350](../snowmeet_wechat_mini/pages/admin/rent/rent_order_detail/rent_order_detail.js#L1350) |
| `mapp/admin/care/care_order_detail/care_order_detail` | 养护订单详情 | [print_care_label.js:298](../snowmeet_wechat_mini/components/care/print_care_label.js#L298) 养护标签二维码 |
| `mapp/fnb/mat_detail` | `pages/admin/fnb/mat_expire_detail` | [print_food_label.js:26](../snowmeet_wechat_mini/components/fnb/print_food_label/print_food_label.js#L26) 食材标签二维码 |
| `mapp/order/payment_entry`（旧） | 旧版支付落地 | [components/payment/payment.js:160](../snowmeet_wechat_mini/components/payment/payment.js#L160) |
| `mapp/order/order_entry/`（旧） | 旧版订单入口 | [components/payment/payment.js:85](../snowmeet_wechat_mini/components/payment/payment.js#L85) |

**已打印出去的旧标签、旧二维码指向哪些页面，只有平台规则列表说了算。删任何页面前先去核对。**

---

## 判定口径（改脚本前先读）

### 页面可达
把每个活文件里的**所有字符串字面量**取出来，按三种方式尝试解析成注册页面路径，**精确命中**才算入口：

1. 绝对：`'/pages/admin/member/member_list'`
2. 相对本文件目录：`admin.js` 里的 `'rent/new_rent_list'` → `pages/admin/rent/new_rent_list`
3. 截断 query：`'recept_member_info?memberId=' + x` → `recept_member_info`

两种更简单的做法都试过，都不行：

- **只搜全路径 → 漏判**。本项目大量相对跳转，[admin.js:154](../snowmeet_wechat_mini/pages/admin/admin.js#L154) 还是 `path = 'rent/new_rent_list'` 先赋值再 `navigateTo`。首版报告说「62 个完全孤立」就是栽在这里
- **只搜 basename → 太松**。名字在注释里出现一次就被当成"被调用"

### 组件可达
被某个活文件的 `usingComponents` 注册，**且它的标签真的出现在那个文件的 wxml 里**。全局注册（app.json）的组件：标签出现在任意活 wxml 里即可。

**只看注册会漏掉一大批"注册了从来不用"的死组件**——2026-07-27 删的 5 个组件全是这种：`usingComponents` 里挂着，wxml 里零使用，JS 里也没有 `selectComponent`。

### 迭代到不动点
删掉的东西可能让别的东西变孤儿（`pay_additional` 删掉 → `pay_method` 组件变孤儿），所以反复算到没有新增为止。

---

## 已知陷阱

**微信开发者工具的「未打包 / 无依赖」列表 ≠ 可删清单。**

那个面板里混着 `package.json`、`package-lock.json`、`project.private.config.json`，以及整个 `miniprogram_npm/@vant/weapp/*`。删掉它们的后果：

- `package.json` 没了就构建不了 npm
- `miniprogram_npm/` 是「构建 npm」的产物，下次构建全量长回来，删了白删
- **「未打包」的意思正是「已经没进上传包」**，删了一个字节的包体积都省不下来
- vant 组件之间有传递依赖，而这些二级依赖**没有任何页面直接注册**：`van-calendar`→`toast`、`van-tree-select`→`sidebar`/`sidebar-item`、`van-uploader`→`loading`、`van-tabs`→`info`/`sticky`。按列表逐个删会砍掉在用组件的依赖，且**要真机跑到那个页面才报错**

顺带记一笔：`weui-miniprogram/*`（`mp-cells` / `mp-cell` / `mp-tabbar`）既不在 `miniprogram_npm/` 也不在 `node_modules/`，它由 [app.json](../snowmeet_wechat_mini/app.json) 的 `"useExtendedLib": { "weui": true }` 提供。写检查脚本时如果只查 npm 目录，会把 30+ 个文件误报成"悬空注册"。

---

## 2026-07-27 清理记录

### 删除的页面（6）

| 页面 | 判据 |
|---|---|
| `pages/admin/rent/set_award` | 零入口；`/core/` 旧接口，写已停用的 `rent_list` 表 |
| `pages/admin/rent/pay_additional` | 零入口；旧版追加支付，已被 `rent_append` + 订单详情追加区取代 |
| `pages/admin/rent/rent_item_change` | 零入口；旧版租赁物更换，新版详情页已内建更换弹窗 |
| `pages/admin/printer/gprinter/print_task` | 零入口；旧打印任务页 |
| `pages/blt/beacon_scan` | 零入口；蓝牙 Beacon 扫描调试页（2026-05-30 建） |
| `pages/admin/background/set_session_key` | 零入口；调试用手动设 sessionKey |

连带清理：`app.json` 6 行注册、`project.config.json` 与 `project.private.config.json` 各一个指向已删页面的自定义编译启动页。

### 删除的组件（5）

| 组件 | 判据 |
|---|---|
| `components/auth/` | 5 个页面注册了但**没有任何 wxml 用到 `<auth>` 标签** |
| `components/rent/cart_list_pay` | 同上（注册方 `rent_recept.json`） |
| `components/ticket_selector/ticket_selector` | 同上（注册方 `recept_member_info.json`） |
| `components/user_info/user_info` | 同上（注册方 `recept_member_info.json`） |
| `components/pay_method/` | 级联孤儿：唯一使用方 `pay_additional` 被删后无人引用 |

### 同目录下**保留**的组件（别误删）

- `components/ticket_selector/ticket_list` ← 旧版养护开单 [care_recept.json:4](../snowmeet_wechat_mini/components/care/care_recept.json#L4) 在用
- `components/user_info/member_info` ← app.json 全局注册 `member-info`
- `components/user_info/auth_cell` ← app.json 全局注册 `member-auth`，`reg` 页在用
- `pages/admin/printer/gprinter/ticket` ← [ticket_template_list.js:125](../snowmeet_wechat_mini/pages/admin/ticket/ticket_template_list.js#L125) 会跳过去（票据打印链路）

> 清理过程中曾用 `git rm -r pages/admin/printer/gprinter` 删整个目录，把同目录的活页面 `ticket.*` 一起删了，已还原。**按目录批量删之前先确认目录里没有别的活文件。**
