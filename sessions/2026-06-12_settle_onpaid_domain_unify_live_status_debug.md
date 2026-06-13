# 2026-06-12 settle 支付完成弹窗 + 全版本域名统一 + 「等待扫码」不刷新长排查

接续租赁开单/结算线。本场起于 start-work，依次做了三件小改（前两件已 commit 进 `snowmeet_wechat_mini`）+ 一场围绕「微信支付二维码顾客扫码后店员端仍显示『等待扫码』」的长 debug（未在会话内闭环，用户后用 copilot 解决）。代码改动落在 `snowmeet_wechat_mini/`，排查涉及 `SnowmeetApi/` 源码 + 生产库 `100.28.143.19/snowmeet_new` 直查。

## 1. settle 页支付完成后弹对话框

需求：顾客支付成功后提示店员，弹框二选一——查看订单详情 / 继续开下一单。正好对应 CLAUDE.md 待办的「父页面 onPaid 处理」。

- [pages/payment/settle/index.js](../../snowmeet_wechat_mini/pages/payment/settle/index.js) `onPaid` 由 `console.log` 改为 `wx.showModal`：
  - title「收款成功」，content 带支付方式
  - confirm「查看订单」→ `wx.redirectTo('/pages/admin/rent/rent_details?id=' + orderId)`（替换已完成的结算页）
  - cancel「继续开单」→ `wx.reLaunch('/pages/admin/reception/recept_entry')`（重置栈回开单入口）
- `reLaunch` 选型依据 [reception_tabbar.js:52](../../snowmeet_wechat_mini/components/reception_tabbar/reception_tabbar.js#L52)「开单」tab 同款（注释「开单入口可能需要重置回根」）
- `paid` 事件三条路径（微信 WS/轮询 `markPaid`、支付宝、其他方式 `effectUnpaidOrder`）都 `triggerEvent('paid')`，故一个 handler 覆盖全部、`_paidHandled` 去重保证只弹一次
- 坑：`wx.showModal` 的 `confirmText/cancelText` **最多 4 字**，所以是「查看订单」/「继续开单」而非完整「查看订单详情」/「继续开下一单」
- 「查看订单」当前写死跳 `rent_details`（仅租赁）；养护/零售详情页未做，注释标了按 `order.type` 扩展
- 已由用户 commit `2f2ddbc5 order finish`

## 2. 全版本域名统一 mini.snowmeet.top

现象：用户反馈测试环境默认域名还是旧 `snowmeet.wanlonghuaxue.com`，不是已改成 `mini.snowmeet.top` 了吗。

### 2.1 根因（两处复制的 switch + typo）

- globalData 默认值（[app.js:219-220](../../snowmeet_wechat_mini/app.js)）确实是 `mini.snowmeet.top`，但**只对正式版生效**
- 登录成功回调里有个 switch：`case 'trail'`/`case 'develop'` → `app.getDomain()`，而 `getDomain()` 先读本地 `domain.txt`、读不到走 catch 兜底——**兜底那行还是写死的 `snowmeet.wanlonghuaxue.com`**（漏改）；且写进 domain.txt 后粘住，改代码也不生效
- **同一段 switch 在 [mine.js](../../snowmeet_wechat_mini/pages/mine/mine.js) onLoad 里复制了第二份**
- `case 'trail'` 是 typo：微信 `envVersion` 体验版真实值是 `'trial'`。所以体验版匹配不上、落到 default 反而用了 globalData 的新域名；开发版（`develop`）才命中 `getDomain()` 拿旧域名 → 出现"开发版旧、体验版新"的诡异不一致

### 2.2 修复

- 删 app.js + mine.js 两处 switch（globalData 默认对所有版本生效）
- `getDomain()` 兜底 `snowmeet.wanlonghuaxue.com` → `mini.snowmeet.top`
- typo `'trail'` → `'trial'`
- 净效果：冷启动不再读 domain.txt → 旧设备 domain.txt 残留自动被忽略、**无需清缓存**。`pages/admin/env` 手动切域名调试页保留，但只在当前会话内有效、冷启动回 mini.snowmeet.top
- 用户拍板「写死的不改，只改 requestPrefix」：[data.js:543](../../snowmeet_wechat_mini/utils/data.js#L543) 上传接口 + ~13 处图片显示前缀（care_recept/retail_recept/admin care order_detail/retail_order_detail）+ 静态图（skipass_detail_new）+ `uploadDomain` CDN 全保留旧域名
- 已由用户 commit `34bf8438 set domain name`

## 3. 活跃页面里用 FirstUI 的清单（纯盘点）

- 全项目 wxml 含 `<fui-` 标签的 16 页，交叉 `unreachable_pages.md` + grep 真实入口后：**14 活 / 2 死**
- 活：餐饮 fd 模块 8 页（fd_category / fd_category_prod_list / fd_category_prod_list_mod / fd_add_prod / fd_order_list / fd_cart / fd_order_confirm / fd_order_detail，全从 [admin.js](../../snowmeet_wechat_mini/pages/admin/admin.js) 的 `nav` 动态分发跳入——正是当初静态 BFS 误判为 C-2 的原因）+ new_rent_list / rent_details / retail_order_list / care_order_list / fire_care_list + order_entry（扫码落地）
- 死：`admin/recept/recept_new`（旧版接待主页，已被 reception/recept_new 取代，仅 app.json + dev config + 注释引用、无运行时 navigateTo）+ `printer/gprinter/print_task`（无运行时入口）
- 新流程页（reception/settle/payment_entry）按「新页面不再引入 fui」约定都没用 fui；fui 存量主体 = 餐饮 fd 模块

## 4. 「微信扫码后店员端仍显示『等待扫码』」长排查

现象（paymentId 42601 → 42602 → 42603）：微信支付出码后，顾客扫码，店员端 `order-payment` 组件一直停在「等待扫码」，不跳「顾客已扫码」。**关键对照：选支付宝就能显示状态。**

### 4.1 逐层排除

- 前端轮询失败是**静默的**：[data.js:170](../../snowmeet_wechat_mini/utils/data.js#L170) `getPaymentLiveStatusPromise` 非 200/code≠0 一律 `resolve(null)` 不弹 toast → 接口拿不到就永远停「等待扫码」不报错
- 接口在、域名对：模拟器 console `getApp().globalData.requestPrefix` = `mini.snowmeet.top`；探活 `GetPaymentLiveStatus/42602?sessionKey=x` 返 200 `{code:1,没有权限}`（鉴权前就返回，证明路由存在 = f455a87）
- `customer_open_date` 列已加（用户确认）
- 枚举比较正常：已支付微信单 42599 打 `GetPaymentLiveStatus` 返 `{stage:"paid"}` → `status==支付成功` 比较 OK，排除源码编码问题

### 4.2 DB 直查定性（突破口）

直连 `100.28.143.19/snowmeet_new`（report 导出同一库，连接串在仓库外 `SnowmeetApi/config.sqlServer`，本机 pyodbc + ODBC Driver 18 + `py`）：

- **`order_payment.customer_open_date` 全表 0 条非空**——这个落「已扫码」的戳**从来没成功落过**，对任何单/任何支付方式都一样
- 直接打 `GetOrderFromPaymentByCustomer/42602` 返 200 + 正常返回订单（71742 / WT_ZL_260612_00007），但 `customer_open_date` 仍 NULL；连打 16 次、新单 42603 同样 None
- 42602 status 字节 `B4FDD6A7B8B6`（GBK「待支付」，LEN=3，无填充/隐藏字符）→ 落戳条件 `status.Trim()=="待支付"` 本应为真

### 4.3 支付宝为何能显示、微信不能

- 看最近支付记录：**支付宝待支付单 `submit_time` 是 SET 的**（生成支付时就写）→ [GetPaymentLiveStatus](../../SnowmeetApi/Controllers/OrderController.cs#L2496) 先命中 `submit_time!=null`→「支付中」分支，**根本不经过那个没落的戳**
- 微信待支付单 `customer_open_date/submit_time/open_id` 全 NULL，「顾客已扫码」**唯一依赖 `customer_open_date`** → 它没落 → 永远「等待扫码」

### 4.4 源码 vs 线上二进制

- committed `f455a87`（本地 + `origin/ai` + 工作区 `git status` 干净）确有落戳：[OrderController.cs:2444](../../SnowmeetApi/Controllers/OrderController.cs#L2444) `trackedPayment.customer_open_date = DateTime.Now;`，且无条件
- `GetPaymentLiveStatus`（接口）与落戳是**同一提交 f455a87、同一处 69 行改动**（`git show --stat f455a87`：OrderController.cs +69 / OrderPayment.cs +3）
- 推论：线上有接口（支付宝能显示）+ 没落戳 → **干净的 f455a87 二进制不可能"有接口没落戳"** → **线上跑的 DLL 不是这份 f455a87 source build 出来的**
- `git log=f455a87` 没错，但运行的二进制是旧的/编到了别处。强烈怀疑 `dotnet publish -o` 目录 ≠ 服务 `ExecStart` 实际加载目录 →「重启/重开单无数次无效」（重启跑同一旧 dll，restart≠rebuild）
- 我未能在会话内拿到服务器 `systemctl cat … ExecStart` + dll 时间戳坐实最后一环；用户中途用 copilot 自行解决了

### 4.5 顺带澄清的测试方式坑

- 模拟器**做不了「扫普通链接二维码打开小程序」**（真机专属）→ 在模拟器里扫那个码进不了小程序、`GetOrderFromPaymentByCustomer` 不被调、戳不落
- 要测落戳：真机扫，或**自定义编译**启动页 `pages/order/payment_entry` + 参数 `paymentId=X` 直接开（onShow 会调 `getOrderFromPaymentByCustomer` 落戳）。payment_entry onLoad 同时支持 `options.paymentId` 直传和扫码 `options.q` 解析

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/pages/payment/settle/index.js` | `onPaid` 加「收款成功」modal（查看订单 redirectTo / 继续开单 reLaunch）— 用户 commit `2f2ddbc5` |
| `snowmeet_wechat_mini/app.js` | 删登录 switch 的 getDomain 覆盖 + getDomain 兜底改 mini.snowmeet.top + typo `'trial'` — 用户 commit `34bf8438` |
| `snowmeet_wechat_mini/pages/mine/mine.js` | 删第二处复制的 getDomain switch |
| `SnowmeetApi/Controllers/OrderController.cs` | （仅排查无改码）确认 `GetOrderFromPaymentByCustomer` 落戳(2444) + `GetPaymentLiveStatus`(2470) 阶段逻辑 |

## 学到的小知识

1. **`wx.showModal` 按钮文案最多 4 字**：confirmText/cancelText 超长会截断；「查看订单」「继续开单」是被这个限制逼出来的
2. **小程序域名按版本切的两处坑**：globalData 默认值只管正式版；测试版走 `getDomain()` 读本地 `domain.txt`，兜底硬编码 + domain.txt 缓存会双重粘住旧值。删掉 startup 的 getDomain 覆盖后冷启动直接用默认值、缓存自动失效，比改兜底更彻底
3. **`envVersion` 体验版是 `'trial'` 不是 `'trail'`**：拼错会让体验版静默落到 default 分支，造成"开发版/体验版行为不一致"的诡异现象
4. **「代码对、线上行为不对」的排查顺序**：先 DB 直查关键字段**全表是否有任何非空**（0 条 = 这功能从没工作过，不是偶发），再核服务实际加载的 dll 是不是最近 publish 的。`git pull` 到位 ≠ 在跑的 dll 被替换；`dotnet publish -o` 必须 = 服务 `ExecStart` 目录，否则编到没在跑的地方、restart 永远旧 dll
5. **同一字段缺失对不同支付通道表现不同**：微信「已扫码」唯一靠 `customer_open_date`，支付宝靠 `submit_time` 先进「支付中」分支绕过——所以同一个 bug（戳没落）只在微信暴露。对照不同通道的字段分布能快速定位"为什么 A 行 B 不行"
6. **模拟器无法测「扫普通链接二维码打开小程序」**：真机专属。测落地页逻辑用自定义编译直接开 `payment_entry?paymentId=X` 绕过扫码
7. **生产库可直连排查**：`100.28.143.19/snowmeet_new`，连接串在 `SnowmeetApi/config.sqlServer`（gitignore），本机 pyodbc + ODBC Driver 18 + `py` 启动器可跑；探接口存在性用假 sessionKey 的 GET（鉴权前返回 = 路由存在）安全无副作用

## 备注

本场最后一环（线上 dll 与 f455a87 source 不一致的根因坐实 + 修复）未在会话内完成，用户用 copilot 自行解决。CLAUDE.md「已知遗留」已记下排查方法（先查 customer_open_date 全表非空 + 核 ExecStart 加载的 dll 时间戳），供后续复现/验证。
