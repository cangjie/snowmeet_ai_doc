# 易龙雪聚（Snowmeet）系统功能说明 — 雪季上线测试用

- 编写日期：2026-09-30
- 编写方式：对照当前代码逐页、逐接口核对，再结合开发记录（`snowmeet_ai_doc/CLAUDE.md` 与 `sessions/`）整理。
- 代码基准版本：

| 仓库 | 分支 | 提交 |
|---|---|---|
| `SnowmeetApi`（后端） | ai | `18e0601a` |
| `snowmeet_wechat_mini`（微信小程序） | ai | `0c712574` |
| `SnowmeetOfficialAccount`（公众号后台） | ai | `4c9c0a6` |
| `reqai`（管理员 AI 帮助后端，独立项目） | main | `6131ea4` |
| `alipay_snowmeet`（支付宝小程序） | — | 工作目录现状 |

- 用途：交给 ChatGPT 生成测试方案，测试方案再交给 Copilot 执行。

---

## 0. 给测试方案编写者的说明

### 0.1 这份文档包含什么

第 1～4 章讲系统组成、角色、测试环境和跨业务的公共机制。第 5 章按业务模块逐一说明功能、流程、业务规则和关键接口。第 6 章列出这次核对代码时发现的疑点，第 7 章是历史上出过问题的回归重点，第 8 章是测试开始前必须确认的部署和数据前提。附录是全部页面清单、后端接口清单和名词解释。

### 0.2 测试方案需要标明每条用例的执行方式

系统里有相当一部分功能只能在真机上验证（真实支付、蓝牙打印、扫码、摄像头识别、微信分享、公众号推送）。测试方案应给每条用例标明执行方式，建议分四类：

| 执行方式 | 谁来执行 | 适用范围 |
|---|---|---|
| A. 自动化单元测试 | Copilot | 后端 `SnowmeetApi.Tests`、小程序 `tests/*.test.js` 里的纯规则 |
| B. 本地隔离库接口测试 | Copilot | 在本机 LocalDB 建隔离库后调用本地后端接口（见 3.2） |
| C. 微信开发者工具界面测试 | Copilot 或人工 | 页面交互、表单校验、列表筛选，可用 `miniprogram-automator` 驱动 |
| D. 真机人工测试 | 人工 | 支付、退款、扫码、蓝牙打印、摄像头、分享、公众号/企业微信消息 |

### 0.3 执行安全红线（必须原样写进测试方案，Copilot 必须遵守）

1. **本地启动的后端默认连接生产库。** `SnowmeetApi/config.sqlServer` 指向生产 SQL Server（`snowmeet_new`）。没有换成隔离库之前，不得调用任何会写数据的接口。
2. **不得发起真实支付或退款。** 微信支付、支付宝都是真实商户号，钱是真的。支付、退款相关用例一律归入 D 类，由人工小额（0.01 元）执行。
3. **不得调用万龙雪票下单。** 万龙雪票支付成功后，后端会向第三方「自我游」真实订票并扣预存款（见 5.4）。
4. **不得触发群发推送。** 食材过期提醒 `FnbMaterial/PushExpireAlert` 默认发给企业微信全员；公众号客服消息会真实发给顾客。
5. **不改服务器本地配置并提交。** `config.sqlServer`、`config.fnbAlertReceivers` 等文件不入 git，改了会影响他人。
6. **数据库结构变更（DDL）不由 Copilot 执行**，只由负责人执行。
7. **生产环境的任何写操作都要人工确认后再做**，并用测试员工账号操作（测试订单会被自动标记，见 3.4）。

---

## 1. 系统组成

| 组成 | 代码位置 | 技术 | 线上地址 | 说明 |
|---|---|---|---|---|
| 微信小程序 | `snowmeet_wechat_mini/` | 原生小程序 JS + Vant WeApp | AppID `wxd1310896f2aa68bb` | 顾客端（雪票、次卡、我的）+ 店员后台（「我的 → 我是管理员」） |
| 后端 API | `SnowmeetApi/` | ASP.NET Core + EF Core + SQL Server | `https://mini.snowmeet.top` | 新接口 `/api/{控制器}/{方法}`，旧接口 `/core/{控制器}/{方法}` |
| 公众号后台 | `SnowmeetOfficialAccount/` | ASP.NET Core 7 | `https://wxoa.snowmeet.top` | 关注事件、带参二维码扫码事件、客服消息 |
| 支付宝小程序 | `alipay_snowmeet/` | 支付宝小程序 | appId `2021006157624571` | 仅 3 页：首页、雪票订单、支付页 |
| 后台网页 | `SnowmeetApi/wwwroot/background/` | 静态 HTML | `mini.snowmeet.top/background/` | 扫码登录后看报表、上传七色米订单 |
| 聚合支付 H5 | `SnowmeetApi/wwwroot/unipay/` | 静态 HTML | `mini.snowmeet.top/unipay/` | 顾客扫固定码输入金额付款 |
| 食材过期提醒 H5（旧） | `SnowmeetApi/wwwroot/fnb/mat_expire/` | 静态 HTML | 企业微信内打开 | 已被新的食材管理取代，仍保留 |
| 管理员 AI 帮助后端 | 独立仓库 `cangjie/snowmeet_reqai`（本机 `D:\source\snowmeet\snowmeet_reqai`） | Python FastAPI | `snowmeet.goldenma.xyz` | 后台页面帮助、自然语言查询租赁订单 |
| 数据库 | — | SQL Server 2022，库 `snowmeet_new` | 生产服务器 | 后端与公众号后台共用同一个库 |

另有一台图片服务器 `snowmeet.wanlonghuaxue.com`，目前小程序的图片上传和显示临时改用 `mini.snowmeet.top`（`utils/data.js` 的 `IMAGE_HOST`）。

**门店**（`shop_list` 表）：万龙体验中心、万龙服务中心、崇礼旗舰店、渔阳、怀北、总部；餐饮门店「多呆一会儿吧」需执行 SQL 后才存在（见第 8 章）。门店决定订单号前缀和收款的微信商户号。

**业务线**（订单 `order.type`）：租赁、养护、零售、雪票、聚合（聚合支付）、餐饮（食材管理的厨房单）。

---

## 2. 角色与权限

### 2.1 用户角色

| 角色 | 如何识别 | 能用的功能 |
|---|---|---|
| 顾客（未注册） | 小程序登录后有会话 `sessionKey`，但没有会员号 | 浏览雪票和次卡，下单时会被要求授权手机号 |
| 会员 | `member` 表，通过手机号或微信 openid 关联 | 买雪票、买次卡、我的雪票/优惠券/储值/次卡 |
| 散客 | 店员开单时不填手机号或匹配不到会员 | 可以开租赁单；非雪季养护单必须有会员 |
| 店员 | `staff` 表，`title_level` 分级 | 「我的」页出现「我是管理员」入口，进入后台菜单 |

### 2.2 店员级别

| `title_level` | 含义 |
|---|---|
| 100 | 店员 |
| 200 | 店长 |
| 300 | 系统管理员 |
| 1000 | 超级管理员 |

后台菜单按级别显示：`title_level > 200` 才能看到「次卡商品管理」「卡类产品销售」「租赁分类维护」「租赁套餐设置」。

接口权限要点：

| 功能 | 最低级别 |
|---|---|
| 会员管理（搜索、详情、标签、充值、发卡、发券、注册、改资料） | 200 |
| 会员合并 | 300 |
| 开单页会员资产（`MemberAdmin/GetMemberAssetsByStaff`）、选卡列表 | 100 |
| 养护价格维护 | 300 |
| 优惠券模板维护、分享记录 | 200 |
| 次卡商品管理、卡类产品销售列表 | 200 |
| 管理员 AI 帮助 | 200 |
| 食材管理：在职员工可建厨房单、入库、开封、制作、出餐和查询；店长（≥200）才能维护档案与配方、盘点过账、报损销毁、设置用量预警、查看成本和金额 | 100 / 200 |

食材管理还要求店员的 `staff.base_shop_id` 等于操作门店，否则提示「无门店权限」。

---

## 3. 测试环境与工具

### 3.1 环境一览

| 环境 | 怎么用 | 限制 |
|---|---|---|
| 生产 | 小程序正式版/体验版默认请求 `mini.snowmeet.top` | 本机（Windows、Mac）都访问不到它的 443 端口，只能在微信开发者工具或真机上看 |
| 本地后端 | 在 `SnowmeetApi` 目录运行 `dotnet run`，Swagger 在 `https://localhost:5000/swagger` | **默认连生产库**；Windows 上 dotnet 不在 PATH，用 `C:\Program Files\dotnet\dotnet.exe` |
| 本地隔离库 | LocalDB，见 3.2 | 目前的脚本只建食材测试需要的表 |
| 微信开发者工具 | `C:\Program Files (x86)\Tencent\微信web开发者工具` | 手机号授权不返回真实号码；不能真实支付；扫码、蓝牙、摄像头受限；`wx.showShareImageMenu` 在模拟器必失败；「扫普通链接二维码打开小程序」只能真机 |
| 真机 | 体验版 | 所有 D 类用例 |

小程序可以在「我的 → 选择环境」（仅开发版、体验版可见）临时切换后端域名。

### 3.2 现有自动化测试

| 测试 | 位置 | 运行方法 | 最近结果 |
|---|---|---|---|
| 小程序单元测试 | `snowmeet_wechat_mini/tests/`（16 个文件：管理员 AI、食材、租赁列表 AI、门店选择器、会话） | Windows：在 `snowmeet_wechat_mini` 目录执行 `"C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe" ../snowmeet_ai_doc/tools/windows_test/run_tests.js tests/*.test.js`；有 Node 18+ 时可直接 `npm test` | 167/167 通过 |
| 后端单元测试 | `SnowmeetApi/SnowmeetApi.Tests/`（xUnit，覆盖养护定价、优惠券模板/转赠/分享/可见性、食材规则、管理员 AI 协议、订单查询规则等） | `dotnet test SnowmeetApi.Tests` | 362 个通过 |
| 食材集成测试 | `snowmeet_ai_doc/tools/windows_test/run_integration_localdb.py` | 先 `dotnet build SnowmeetApi.Tests`，再 `py run_integration_localdb.py`；它在 LocalDB 建 `snowmeet_fnb_test_*` 隔离库，跑完自动删库 | 24/24 通过 |
| 食材接口冒烟 | `SnowmeetApi/SnowmeetApi.Tests/run_fnb_http_smoke.py` | 本地后端连隔离库后执行 | 80 项中 77 过（3 个已知问题见 5.10） |

**扩展隔离库的建议**：`snowmeet_ai_doc/tools/windows_test/efschema` 可以按后端的 EF 模型生成全部表的建表脚本（`ef_create.sql`）。若要对租赁、养护等模块做 B 类接口测试，可用它在 LocalDB 建一个完整的隔离库，让本地后端临时连它。连接串由后端工作目录下的 `config.sqlServer` 文件决定，切换时不能把改过的文件提交或留在服务器上。

### 3.3 接口鉴权

- 小程序调用接口时在查询参数里带 `sessionKey`（`mini_session.session_key`）。会话有过期时间，过期后接口返回「没有权限」。
- `sessionType` 默认 `wechat_mini_openid`；支付宝为 `alipay_payerid`；企业微信 H5 为 `wecom_userid`。
- 店员身份由 sessionKey 反查 openid，再按任职时间窗匹配 `staff`。
- 大多数新接口返回统一格式 `{ code, message, data }`，`code=0` 表示成功；食材接口另有 `code=2`（会话失效）、`3`（无权限）、`4`（需刷新重试）。

### 3.4 测试订单如何标记

订单表有 `is_test` 字段，报表和列表可以按它筛选：

- 租赁、养护开单保存草稿时，若请求的域名不是 `mini.snowmeet.top`（例如本地后端），订单自动标为测试单。
- 员工 id 为 28、31、34 的账号下的单自动标为测试单（`Order/PlaceOrder`）。「苍杰（测试）」（员工 id 31）是建议的测试账号。

---

## 4. 跨业务的公共机制

### 4.1 登录与会员识别

- 小程序启动时 `wx.login` 取 code，调用 `MiniAppHelper/MemberLogin` 建立会话。未注册用户会话里的会员号为空，**登录时不创建会员**。
- 会员在以下时机创建：顾客授权手机号（支付前身份确认、购买次卡、查看优惠券详情等）；店员注册会员；支付宝支付成功回调时按手机号找会员或新建。
- 手机号找会员只看 `member_social_account.type='cell'` 的记录。`type='contact'` 是开单或合并时留下的联系电话，不参与匹配。
- 已被合并的会员（`merge_id` 非空）不出现在会员列表。

### 4.2 订单、支付与退款的数据结构

- `order`：订单。字段 `type` 区分业务，`code` 是正式订单号，`valid=0` 是开单中的草稿，下单后 `valid=1`。
- 订单号格式 `{门店码}_{业务码}_{yyMMdd}_{5 位序号}`，例如 `WT_ZL_251021_00001`。门店码：WT 万龙体验中心、WF 万龙服务中心、QJ 崇礼旗舰店、ZB 总部；业务码：ZL 租赁、YH 养护、LS 零售、XP 雪票。序号取当天同前缀订单数加 1，并发时可能出现重复号和跳号。
- `order_payment`：每一笔支付。支付方式有微信支付、支付宝、储值支付、现金、挂账、次卡支付等；状态为待支付、支付成功；`valid=0` 表示已作废。一个订单可以有多笔支付（例如原押金 + 追加押金）。
- `payment_refund`：退款。判定一笔退款已发起：`state=1` 或 `refund_id` 非空。
- `discount`：减免记录。`order_share` / `payment_share`：分账（推荐人、合作方）。
- `core_data_mod_log`：关键数据的修改日志，大部分改价、改状态、合并等操作都会写。

### 4.3 通用结算页

路径 `pages/payment/settle/index?orderId=`。租赁、养护开单去结算后都进入这里。

- 三种收款方式：微信（生成二维码，顾客用微信扫码支付）、支付宝（二维码打开支付宝小程序支付）、其他方式（现金、挂账等，店员点「确认收款」二次确认后生效）。
- 二维码下方实时显示状态：等待扫码 → 顾客已扫码 → 顾客支付中 → 已收款（或已取消）。靠每 2 秒轮询 `Order/GetPaymentLiveStatus` 加 WebSocket 推送。
- 切换支付方式时，旧的待支付记录会被作废，同时关闭微信/支付宝预下单；撤回失败则不允许切换。
- 「转发二维码给微信好友」：真机弹出微信分享面板，模拟器里会退化成图片预览。
- 0 元且已生效的订单直接显示已收款。
- 收款后弹窗：「查看订单」按订单类型跳租赁或养护详情；「继续开单」回接待首页。
- 养护单使用了储值、次卡、券等权益时，走身份核验再核销的流程（见 5.3）。

### 4.4 顾客扫码支付页

路径 `pages/order/payment_entry?paymentId=`（扫二维码进入时参数在 `q` 里）。支付宝小程序有同名页面。

- 显示订单信息、租赁或养护明细、金额。**金额和支付状态以本次扫码的这一笔支付为准**，而不是整个订单。
- 支付前身份确认（`PaymentIdentity/CheckPayerIdentity`、`ConfirmPayIdentity`），状态：
  - `direct`：扫码人就是订单会员，直接支付。
  - `direct_to_scanner`：订单没有会员，支付后订单归扫码人。
  - `choose_identity`：订单属于别人，扫码人选「正常支付（订单转归我）」或「替人代付（订单仍归原会员）」。
  - `care_member_required`：养护单用微信支付，但扫码人不是订单会员，隐藏支付按钮。
  - `error`：支付记录不存在等。扫码后提示「支付记录不存在」通常是二维码已过期（店员切换了支付方式）。
- 扫码人没绑手机号时，身份按钮直接弹出微信原生的手机号授权；拒绝授权也能继续支付。
- 代付时记录代付人手机号（`order_payment.cell`）和代付标记。**订单归属只在支付成功回调后才改**，代付不改归属。

### 4.5 支付成功回调与订单生效

- 微信回调 `/api/Tenpay/TenpayPaymentCallBack/{商户}`，支付宝回调 `/api/Ali/CallBack`，都进入 `DealSuccessPaidOrder`。
- 按业务生效：租赁（发放立即租赁的装备等）、养护（生成任务链、核销卡券）、雪票（生成雪票，万龙向自我游下单，送券）、零售（顾客买次卡则发卡）、聚合（送免费打蜡券）。
- 订单生效共有 5 个入口：支付回调（含「确认收款」）、旧版 0 元养护单、`PlaceCareOrder` 无权益 0 元单、储值支付 `PayWithDeposit`、养护核销 `WriteoffCareOrder`。每个入口都会用开单时填的姓名、性别补全会员资料（只填空，不覆盖）。
- 订单字段 `wechat_unverified`：**值为 1 表示已通过微信核验是会员本人**（名字与含义相反）。会员本人用微信支付成功时置 1。

### 4.6 退款

- 接口 `Order/Refund/{orderId}`，按支付笔分别退回原支付渠道。
- 订单有多笔可退支付时，界面弹出逐笔输入表格（支付方式、可退金额、实际退款），各笔之和必须正好等于应退金额。
- 储值支付的部分不走退款。

### 4.7 身份核验（储值付款、养护用权益时）

店员端弹出二维码（`https://mini.snowmeet.top/mapp/order_verify?verifyOrderId=`），顾客用微信扫码进入 `pages/order/identity_verify`，扫码人与订单会员一致则核验通过；店员端每 2 秒轮询 `PaymentIdentity/GetWechatVerifyStatus`。

### 4.8 公共组件

| 组件 | 作用 | 要点 |
|---|---|---|
| `components/shop_selector` 门店选择 | 各列表页和开单页选门店 | 自动用蓝牙信标定位（最长 30 秒）；手动选择后停止扫描，不会被定位结果覆盖；定位到万龙且店员基地店也是万龙时，改用店员自己的基地店 |
| `components/date-range-picker` 日期选择 | 列表查询的日期范围或单日 | 快捷键今天/昨天/本周/上周；日历第一次点开才创建（影响首屏速度） |
| `components/list-pager` 翻页 | 列表分页 | 首页/上一页/下一页/末页、跳页、每页条数（默认 50）；查询中禁用。列表页从详情返回时保留页码和筛选条件重新查询 |
| `components/admin-page-help` AI 帮助 | 后台页右下角悬浮图标 | 可拖动，见 5.13 |
| `components/care/print_care_label`、`components/fnb/print_food_label` | 蓝牙标签打印 | 只能真机；食材标签 60×40mm，可设份数 |

### 4.9 需要在微信公众平台登记的扫码路径

「扫普通链接二维码打开小程序」只在真机生效，体验版需填测试链接：

| 链接前缀 | 打开的页面 |
|---|---|
| `https://mini.snowmeet.top/mapp/order_payment` | 顾客扫码支付页 |
| `https://mini.snowmeet.top/mapp/order_verify` | 身份核验页 |
| `https://mini.snowmeet.top/mapp/admin/care/care_order_detail/care_order_detail` | 养护订单详情（养护标签二维码） |
| `https://mini.snowmeet.top/mapp/fnb/mat_detail` | 食材批次详情（食材标签二维码） |

---

## 5. 业务模块

> 雪季测试优先级建议：P0 = 5.1 接待开单、5.2 租赁、5.3 养护、5.4 雪票、4.3～4.6 支付退款；P1 = 5.6 次卡、5.7 会员、5.8 储值、5.9 优惠券；P2 = 其余。食材管理（5.10）上线时间由负责人决定。

### 5.1 店铺接待开单（租赁、养护共用入口）

**入口**：后台「【接待】店铺接待」→ `pages/admin/reception/recept_entry`。

**流程**：

1. **录入顾客**（`recept_entry`）：选门店；填姓名、手机号、性别（都可空，空则为散客）。手机号是 11 位或以 `+` 开头的国际号码时，自动匹配会员并回填姓名、性别，页面上常驻一条提示；会员缺姓名或性别时显示琥珀色警示。选择业务：租赁或养护。
2. **找回中断的订单**：弹窗列出当天本门店未完成的开单草稿（`Rent/GetReceptingOrders`），点击后回到开单页继续，购物车内容完整还原。
3. **开单**（`recept_new`）：顶部会员条显示储值、次卡剩余、龙珠、券、季卡（卡只显示当前业务线可用的），可跳会员详情。下方按业务显示租赁表单或养护表单。**每次修改都会自动保存草稿**（`Rent/SaveRentRecept` 或 `Care/SaveCareRecept`，保存请求会排队，不会并发重复建单）。
4. **去结算** → 通用结算页 → 收款。

**规则**：

- 草稿阶段订单和明细都是 `valid=0`；去结算后变为 `valid=1` 并生成订单号。
- 找回中断的订单时，订单门店沿用订单创建时的门店，即使当前选的是别的门店（这一点待负责人决定是否要改，见 6.5）。

**旧页面**：后台「【接待】未完成的接待」→ `pages/admin/recept/recept_list`（见 6.2 路由疑点）。后台「【租赁】未完成的接待」实际也跳到新的接待首页。

### 5.2 租赁

#### 5.2.1 租赁开单（表单组件 `components/reception/rent_recept_form`）

- **添加套餐**（`recept_package`）：按套餐类型筛选（全部、双板、单板、雪服、护具、其他），可选多个套餐、每个多份。万龙系门店新建时默认「立即租赁」。雪服、护具等不需要编码的品类默认勾选「无编码」。
- **搜索单品**：按品类模糊搜索租赁物（`Rent/GetRentProductFuzzy`），状态不是「正常」的租赁物（如租赁中）置灰不可选；同一购物车内编码不能重复。
- **扫描条码**：目前只弹提示，未实现。
- **无码物品**：新建一个空白商品，先在分类树里选分类；切换分类会自动重建附件项（如双板自带雪杖）。
- **每个商品（rental）卡片**：
  - 租赁模式：立即租赁、先租后取、延时租赁。选模式时自动设置起租日期时间（立即/先租后取为今天当前时分，延时为明天 0 点）。套餐内装备模式不一致时显示橙色警示图标。
  - 起租日期用日历选择，也可点「今」「明」快捷设置。
  - 押金、日租金点击后弹出数字键盘输入，再二次确认。押金显示净额（押金减已减免），另显示「已减免」。
  - 备注。
- **每件装备（rentItem）**：编码（点开搜索或扫码）、名称、分类、「无编码」「不需要」开关（不需要的整张卡片置灰）、备注、租赁模式。
- **录入完整性提示**：装备级提示「分类未选」「编码未填」「名称未填」「模式未选」；商品级提示「模式未选」「起租时间未填」「N 件未录入」。有未录入完整的商品时，结算按钮不可点，折叠状态下商品名变红。
- **购物车**：按添加时间或按分类（套餐在前）排序；左滑删除。
- **去结算**：先等草稿保存完成，再调用 `Order/PlaceRentOrder` 生成订单号、写押金记录，然后进入结算页。

#### 5.2.2 租赁订单列表（`pages/admin/rent/new_rent_list`）

- 筛选：门店、日期范围、状态、测试单、招待、减免、次卡（包含/不含）、零售（包含/不含）、关键字等；服务端分页（`Order/GetOrdersByStaffPaged`）。
- 每单显示状态、支付方式（剔除储值和次卡后拼接）、总计租金、左侧标签（如「储」储值、「卡」次卡、「零」含零售、招待等）。招待单显示被豁免前的租金。
- **租赁状态（8 种）**：了结关闭、未支付（没付清）、未开始（已付但未起租）、租赁中、部分归还、全部归还、部分退押金、全额退押金。退押金状态以实际退款金额为准，归还装备本身不代表已退押金。
- 支持用自然语言查询（见 5.13）。
- 从详情返回时保留页码和筛选条件。

#### 5.2.3 租赁订单详情（`pages/admin/rent/rent_order_detail/rent_order_detail`）

**订单信息**：姓名、订单号、手机号（可拨打）、门店。

**支付信息**：支付总额、退款总额、支付笔数、退款笔数；可展开支付明细，代付的记录标红并显示打码的代付人手机号。订单未付清时显示「去支付 ¥金额」按钮，跳结算页。

**租赁信息**：

- 两种视图：「按租赁商品」和「按租赁物」，两者都可以操作装备。
- 每个商品显示起租、退租时间（退租时间按装备全部归还的最晚时间计算）、费用、小计、备注。
- **招待开关**：设为招待后该商品小计归 0，订单应收不再计入它的租金（`Rent/SetRentalEntertainByStaff`）。
- **租金明细**：按天一行（租金、超时费、减免）。点某天弹窗修改三项：打开时输入框为空，原值作为提示；留空表示不改。勾选「免除本日全部费用」后当天三项作废（金额保留，可取消勾选恢复），列表中该行划线。超时费按天记录（`Rent/UpdateRentalDayChargesByStaff`）。
- **装备操作**：发放、归还、设为未归还、暂存、更换（选兼容品类，可扫码，记录更换历史）、赔偿（弹窗输入金额）、备注。被换下的装备置灰、不计件数、不显示发放记录。「全部归还」可一次归还整单装备。
- 从未归还列表点进来时（带 `rentItemId` 参数），只展开目标装备所在的商品并滚动过去。

**退押金区**：

- 显示总计押金、租金、超时费、赔偿，以及应退押金。应退押金 = 实收押金（不超过配置押金）− 应收租金等费用 + 已用储值支付的租金。
- 申请退款的前提：所有装备都已退租。多笔支付时逐笔分配（见 4.6）。
- **储值付租金**：会员有可用储值时显示。勾选前需要顾客扫码完成身份核验（见 4.7）。勾选后租金改由储值支付，押金全额退。
- **次卡消费**：会员有租赁次卡、且装备都已归还时可勾选；同样需身份核验。次卡抵扣含雪板、雪鞋的租赁商品的租金，一个商品一天用一次。勾选时只是预览，点「申请退款」时才真正核销。没有可退金额时按钮变为「确认核销」。
- **购买次卡**（店员向顾客推销）：选卡 → 试算（应退押金 + 立即核销省下的租金，与卡价比较）→ 多退或补差价（补差价可扫码支付或现金，不支持储值）。**钱到账后才发卡和核销**。订单详情里单独显示「次卡销售」记录。

**追加租赁商品区**：显示追加草稿和待支付的追加。点入口进入 `pages/admin/rent/rent_append`，可加套餐、单品（带编码）、无码物品，修改实时保存为草稿。确认追加时：需补押金则去结算页支付后生效；不需要付款则二次确认后直接生效。草稿可删除；订单全部退款时未确认的草稿自动作废。

#### 5.2.4 未归还租赁物（`pages/admin/rent/unreturned`）

按分类、按订单、按顾客三种方式归类（按顾客以手机号汇总）；可搜索编码、名称、分类、顾客名、手机号；点击装备跳订单详情并定位。

#### 5.2.5 其他租赁功能

| 功能 | 页面 | 说明 |
|---|---|---|
| 租赁报表 | `pages/admin/rent/rent_report` | 当日下单、当日结算等统计（见 6.2 路由疑点） |
| 查询租赁物 | `pages/admin/rent/search_fuzzy` | 按编码、名称模糊搜索 |
| 租赁分类维护 | `pages/admin/rent/settings/category_tree` | 分类树、各门店押金和价格（系统管理员） |
| 租赁套餐设置 | `settings/rent_package_list` → `rent_package` | 套餐包含的分类、价格（系统管理员） |
| 租赁物列表/添加/详情 | `settings/rent_product_list`、`rent_product_add`、`rent_product` | 编码、品牌、分类、图片；状态字段「正常」「租赁中」由发放、归还自动维护 |
| 后台网页报表 | `wwwroot/background/rent/rent_report_new.html` 等 | 扫码登录后查看 |

#### 5.2.6 后台自动逻辑

- **按天计租**（续租）：每天为在租的商品生成当天租金明细。只有至少一件装备处于「已发放」或「暂存」时才计费。
- **关单**（`Rent/CloseOrder`）：满足全部条件才关单——没有未退租的装备、应退押金为 0、应收已收齐。
- 起租、退租时间优先取租金明细，没有有效明细时改用装备的发放、归还记录。

### 5.3 养护

#### 5.3.1 养护开单（表单组件 `components/reception/care_recept_form`）

- **装备**：类型（双板、单板等）；会员有同类型养护记录时弹出「历史装备」供点选带入品牌和长度，也可手动填新装备；品牌（可新增）、长度、照片。照片与「品牌+长度」至少填一项。
- **服务项**：修刃（可填角度）、热蜡（自动带上刮蜡）、机打蜡、维修项（多选，可加附加费）、立等（加急）、非雪季（「立等现修」或「寄存后修」）、减免、质保、招待、备注。
- **券和卡**（选择弹层，券 tab 和卡 tab，券与卡互斥）：
  - 券按模板的业务类型过滤。常用模板：12 免费打蜡券（机打蜡）、16 老顾客优惠券（减免）、17/18 非雪季券。
  - 卡 tab 列出次卡（已用/剩余）和季卡（上次使用时间、绑定装备）；今天已用过的季卡置灰。选中绑定了装备的季卡后，装备信息自动带入并锁定。
  - 也可以扫顾客券详情页的二维码直接用券；如果券属于另一个会员，确认后切换开单顾客。
- **使用储值支付**（会员有储值时显示的复选框）：目前只记录意向到订单（`order.pay_with_deposit`）。
- **价格全部由服务端计算**：每次修改都调用 `Care/CalcCareCharge`，把整件装备的状态和本次改动的字段发给服务端，服务端返回价格、默认服务项和联动后的服务项。
- **去结算**：`Order/PlaceCareOrder` 按服务端规则重新定价、生成订单号。非雪季单必须有会员。没有用任何权益的 0 元单（质保、招待）立即生效；用了储值、卡、券导致的 0 元单要先核验身份。

#### 5.3.2 养护定价规则

- 计费项只看修刃和热蜡，机打蜡、刮蜡不计费。
- 对应商品（分类代码 `0203`，按门店 `shop_id` 取价）：双项、单项、双项加急、单项加急。某门店没配加急价时按非加急价收。
- 非雪季「立等现修」对应商品「非雪季养护」；「寄存后修」按项数取双项或单项。
- 券的商品规则按门店、商品配置：一口价优先，其次折扣率，再次立减。没配规则时回退老规则（券 16 减免 20 或 30）。券的减免是保底：店员手动加大的减免不会被券冲掉。
- 选卡的装备收费为 0。例外：机打蜡季卡升级为热蜡或加修刃时，按券 12 的规则补差价。
- 季卡规则：单项/双项由卡上的 `care_project_count` 决定；第一次使用时把本次装备绑定到卡上（装备信息不全则不绑定）；每张季卡每天只能用一次。
- 质保、招待收费为 0。

#### 5.3.3 核销与生效

- 用了储值或卡券的单，顾客需扫码核验身份，之后 `Order/WriteoffCareOrder` 扣储值并生效。
- 顾客用微信支付即视为核验本人；扫码人不是订单会员时不允许用微信支付。支付宝支付前需先用微信核验。
- 生效时生成任务链（安全检查 → 修刃 → 热蜡或机打蜡 → 刮蜡 → 维修 → 寄存或快递（非雪季）→ 发板），核销次卡（季卡不扣次数，都会写使用记录）和券；非雪季单会发非雪季券。

#### 5.3.4 养护订单详情（`pages/admin/care/care_order_detail/care_order_detail`）

- 非雪季订单顶部显示琥珀色横幅，写明立等现修和寄存后修各几件。
- 订单信息、支付信息、订单备注、订单级退款（金额 + 备注，备注默认填装备的取消原因；可退金额为 0 时按钮不可点）。
- **每件装备的卡片**：
  - 服务标签、照片（没有照片时可在安全检查区补传）、券卡图标（点击看详情）。
  - **任务时间线**：当前任务显示大按钮「开始 XX」「结束 XX」和提示语；进行中显示已用时间；结束时显示耗时，耗时不足 60 秒要二次确认；别人执行中的任务可「强行中止」。
  - **安全检查**：录入并「确认安全」，默认带出该会员上次的检查数据；未提交的修改不会因页面刷新丢失。
  - **寄存或快递**（非雪季）：寄存、快递、万龙寄存柜，快递可填单号。
  - **发板核销，四种方式**：扫码取板（顾客扫公众号二维码，本人则自动完成）、验证码、拍照凭证、店长确认。
  - **取消养护**（在未全部完成、也不是只剩发板时可用）：弹窗必须填写取消原因，再用上面四种方式之一核验。
  - **编辑装备**：品牌、长度、序列号（左右）、雪杖、招待/质保、备注、照片增删。
  - **打印标签和小票**（蓝牙打印），二维码可直接打开该装备的详情。
- 带 `careId` 参数进入时只展开这件装备。

#### 5.3.5 其他养护功能

| 功能 | 页面 | 说明 |
|---|---|---|
| 养护订单列表 | `pages/admin/care/care_order_list` | 筛选门店、日期、测试、招待、减免、非雪季、次卡、手机号、备注；分页；标签「质」「非」「券」；订单状态只有「临时订单」「正常订单」 |
| 未完成养护装备 | `pages/admin/care/care_unfinished_list` | |
| 未发板装备 | `pages/admin/care/care_unpicked_list` | |
| 养护价格维护 | `pages/admin/care/care_product_admin/care_product_admin` | 维护分类 `0203` 下的商品和门店价格（系统管理员） |
| 后台网页报表 | `wwwroot/background/maintain/*.html` | |

### 5.4 雪票

雪季重点。雪票通过第三方「自我游」代订（目前为万龙雪场）。

#### 5.4.1 顾客购买

入口：底部菜单「预定」→ `pages/ski_pass/ski_pass_selector`，按雪场切换标签（`SkiPass/GetResorts`）。带着列表里没有的雪场参数进入时，自动落到第一个雪场。

- 列出所选雪场的商品（`SkiPass/GetProductsByResort`）→ `skipass_detail_new` 选日期（每日价格不同）、填姓名、手机号、身份证 → `SkiPass/ReserveSkiPass` 建单 → 微信支付 → 跳 `pages/mine/skipass/my_skipass`。自我游账户预存款不足时不能下单。
- **支付成功后**（`SkiPassController.CreateSkiPass`）：自动向自我游真实下单（`AutoReserve`）；每张雪票发一张券；设置取票通知。
- **推荐人**：从店员推广码（`reserveskipassbystaff_` 场景）进入或会员绑定了推荐人时，订单记录推荐店员并生成分账。
- **我的雪票**（`pages/mine/skipass/my_skipasses`，从「我的」进入；付款后落地页是 `my_skipass`）：查看雪票；出票前可取消（`SkiPass/Cancel`）或申请退款（`SkiPass/Refund`）。

#### 5.4.2 店员操作

| 功能 | 页面 | 主要接口 |
|---|---|---|
| 自我游雪票管理（上下架、改每日价格） | `pages/admin/ski_pass/common_skipass_list` → `common_skipass_detail` | `SkiPass/GetProductsByResort`、`Product/SetHidden`、`SkiPass/ModDailyPrice` |
| 大好河山雪票订单 | `dhhs_skipass_order` | `SkiPass/GetDHHSReservedSkipasses` |
| 订票二维码（店员推广码） | `reserve_qrcode` | 公众号 `GetOALimitQrCodeBySessionKey` |
| 大好河山对账单（网页） | `wwwroot/background/skipass/dhhs_list.html` | |

支付宝小程序另有雪票订单页 `alipay_snowmeet/pages/ski_pass_order`。

**风险提示**：见 6.4（数量大于 1 时金额计算）。

### 5.5 零售

- 零售销售在七色米收银系统里完成，本系统记录零售订单（`order.type='零售'`），每行零售记录（`retail`）的实收金额是 `deal_price`，七色米订单号记在 `mi7_code`。
- 零售类型 `order_type`：普通、招待、租赁附加（租赁退押金时卖次卡）。
- 店员页面：后台「【零售】订单列表」→ `pages/admin/retail/retail_order_list`（按条件查询）→ `retail_order_detail`（修改订单和明细、上传图片）。
- 后台网页：`wwwroot/background/mi7_upload/upload_orders.html` 上传七色米订单明细；零售、七色米报表。
- 顾客自助买次卡也会生成零售订单（见 5.6）。

### 5.6 次卡与季卡

**概念**：次卡按次数使用；季卡不限次数（`punch_card.total` 为空），每天限用一次。两种卡都分租赁和养护两个业务。

| 功能 | 页面 | 说明 |
|---|---|---|
| 次卡/季卡商品维护 | `pages/admin/rent/punchcard_products/punchcard_products` → `punchcard_product_detail` | 业务（租赁/养护）× 卡型（次卡/季卡）；名称、价格、次数（仅次卡）、单项/双项（养护）、图片、富文本简介、使用规则、**收款门店**（必填，决定钱进哪个商户号，不限制使用门店）、上下架、删除 |
| 顾客购买 | 底部菜单「次卡」`pages/punchcard/punchcard_shop` → `punchcard_detail` → `punchcard_confirm` | 必须先授权手机号；建单 `Rent/PlaceMyPunchCardOrder` → 确认页 → `Rent/StartMyPunchCardPayment` → 微信支付 → 支付成功后发卡 |
| 我的次卡 | `pages/mine/my_punchcards` | 显示开卡日期；已退款的卡标灰 |
| 次卡使用明细 | `pages/mine/punchcard_usage` | 按订单汇总核销记录；**自助退款**：卡从未使用过、且是用微信或支付宝买的，可原路退款；其他情况显示原因并提示联系店员 |
| 店员查看卡的使用明细 | 同上页加 `?staff=1`，从会员详情的次卡行进入 | |
| 卡类产品销售列表 | `pages/admin/rent/punchcard_sales/punchcard_sales` | 按销售方式显示角标；季卡可改绑定装备的品牌和长度 |
| 店员发卡 | 会员详情 → 发次卡 | 按商品发放（`MemberAdmin/GrantPunchCard`） |
| 租赁时卖卡、租赁核销 | 租赁订单详情 | 见 5.2.3 |
| 养护核销 | 养护开单选卡 | 见 5.3 |

已退款的卡在所有核销入口都不再出现。

### 5.7 会员

| 功能 | 页面 | 说明 |
|---|---|---|
| 会员列表 | `pages/admin/member/member_list` | 按姓名、手机号搜索；参与业务多选、标签多选筛选；分页 |
| 会员详情 | `member_detail` | 改姓名、性别、手机号；标签增删；资产（储值、次卡、券、龙珠）；充值储值（类型、七色米订单号、备注、金额）；发次卡；发券；最近订单（按业务分 tab，可点进详情）；**合并**（系统管理员：把当前会员的订单、储值、龙珠、次卡、优惠券迁到目标会员，当前会员失效，手机号作为联系电话挂到目标会员，不可撤销） |
| 注册会员 | `member_register` | 手机号注册，可配开卡礼包（券、次卡）逐项发放，可充初始储值；结果逐项显示成功或失败 |
| 标签库维护 | `member_tag_admin` | 显示每个标签的使用人数；合并标签；使用人数为 0 才能删；新增 |
| 顾客注册 | `pages/register/reg` | |

储值充值类型：储值送装备、二手回收、零售赠送、预定、其它赠送。

### 5.8 储值

| 功能 | 页面 | 说明 |
|---|---|---|
| 我的储值（顾客） | `pages/mine/deposit/deposit_list` | |
| 会员储值账户 | `pages/admin/deposit/deposit_account_list` → `deposit_account_detail` | 按手机号搜会员，显示总储值、已消费、可用；流水里充值行带类型、七色米单号、备注，消费行带订单号 |
| 储值账户列表（旧） | `pages/admin/deposit/deposit_list` → `deposit_detail` | 可修改账户信息 |
| 新增储值（旧） | `deposit_charge_search` → `deposit_charge` | |
| 储值资金流水 | `deposit_balance` | |

储值的使用场景：租赁「储值付租金」、养护「使用储值支付」、`Order/PayWithDeposit`。

### 5.9 优惠券

**顾客端**：

| 功能 | 页面 | 说明 |
|---|---|---|
| 我的优惠券 | `pages/mine/ticket/ticket_list` | 未使用、已使用、已分享三个 tab；券码每 3 位一段显示 |
| 优惠券详情 | `ticket_detail` | 二维码内容就是券码，供店员扫码用券；没验证手机号时整页遮罩，要求授权手机号 |
| 转赠 | `ticket_detail` 分享卡片 → 对方打开 `ticket_share` | 只有模板允许转赠的券可以（目前 12、16）；接收人必须关注公众号，扫码关注后服务端自动接受，并用公众号客服消息通知接收人；分享中可撤回；已分享 tab 显示转出且被接受的券（同一张券来回转手以最后一次方向为准） |
| 领取店员分享的券 | `ticket_claim` | 已关注公众号则自动领取 |
| 绑定优惠券 | `ticket_bind` | 见 6.2 路由疑点 |

**店员端**：

| 功能 | 页面 | 说明 |
|---|---|---|
| 优惠券管理 | `pages/admin/ticket/coupon_admin/coupon_admin` → `coupon_detail` | 搜索；按发券人多选筛选（在职的排前面） |
| 模板设置 | `template_admin` → `template_edit` | 业务类型（零售、养护、租赁、餐饮）；有效期（固定截止日、启用后 N 天、永久，三选一）；按门店商品配置一口价/折扣率/立减；海报图上传和二维码位置；「分享」区：生成群分享海报（动态码或静态码）、分享小程序卡片（给一个人，或给群里每人一张）、分享记录（默认最近一周，全店可见，只能撤回自己的） |
| 优惠券核销 | `use_entry` | 扫码核销 |
| 发放优惠券（打印） | `ticket_template_list` | 见 6.2 |
| 待核销的优惠券 | `ticket_unuse_list` | 见 6.2 |

**员工发券只有三条途径**，都记录发券人：会员详情发券（渠道「系统后台」）、分享小程序卡片（渠道「店员分享」）、固定二维码（公众号 `ticketqr_{批次}`，同一模板每人每天限领一张）。老的 `getticket_` 固定码已停用，扫码后提示活动已结束。

**自动发券**：买雪票送券；聚合支付成功送免费打蜡券；非雪季养护生效送券；发板完成送券。

**券能否在开单时选到**：券必须 `valid=1`、未使用、未过期、模板业务类型匹配。

### 5.10 餐饮食材管理

入口：后台「【餐饮】食材管理」→ `pages/fnbinv/stock/stock`（分包 `pages/fnbinv/`）。门店是「多呆一会儿吧」，需先执行门店 SQL 并把后厨员工的 `base_shop_id` 设为该门店（见第 8 章）。接口按每个方法的权限要求见 `snowmeet_ai_doc/docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md`。

底部 8 个 tab：

| Tab | 页面 | 功能 |
|---|---|---|
| 库存 | `stock` | 在库食材列表；顶部临期卡和用量预警卡；「库存低」标签；每种食材可「设置」预警比例或数量 |
| 入库 | `inbound` | 选已有食材或直接录入新食材；生产日期默认今天，按保质期自动算到期日，也可手改到期日；含量单位；照片选填；单价选填；批次号；拍照识别日期（OCR）；确认后直接过账；过账后 10 分钟内、该批次还没有其他操作时，本人或店长可删除 |
| 分类 | `cats` | 名称、储存方式、是否半成品；删除后可重建同名分类 |
| 制作 | `prep` | 半成品按配方扣原料，产出数量按半成品单位；缺料时可「开封 1 袋」；照片选填 |
| 配方 | `recipe` | 菜品只填名称和用料；可新建半成品（一步建食材和配方）；千克、升的用料自动换算为克、毫升 |
| 出餐 | `serve` | 手动建厨房单：一单一道菜 × 份数，按配方扣料，用量可微调；建单前逐项提示库存，缺的是整包未开封时可直接开封；库存不足不拦截，记为欠料，之后可「补扣欠料」（出餐后已盘点过的食材不补扣）；扣料后 10 分钟内本人或店长可编辑或删除（配料退回原批次）；可筛选近 7 天有欠料的单 |
| 盘点 | `count` | 生成快照 → 录实盘数 → 预览差异 → 过账（过账需店长） |
| 看板 | `dash` | 概览、损耗、临期汇总 |

另外 4 页：临期与过期 `expiry`、用量预警 `lowstock`（预警条件：可用量 ≤ 最近一次入库或制作量 × 10%，可按食材修改）、过期食材销毁 `destroy`、批次详情 `batch`。

**旧版食材过期提醒**（保留）：小程序 `pages/admin/fnb/mat_expire_list`、`mat_expire_detail`（录入批次、OCR 扫名称和日期、打印食材标签），企业微信 H5 `wwwroot/fnb/mat_expire/`，推送接口 `FnbMaterial/PushExpireAlert`（**会真实推送给企业微信**）。

**已知问题**：已过期的批次仍能入库（只有前端拦截）；并发过账可能数据库死锁，返回 HTTP 500（数据不受影响，重试可成功）；批次列表没有「只看在库」过滤，历史批次多了会变慢；同一张入库单里未提交的几条可能拿到相同批次号（前端已递增避让）；入库页还留有临时的耗时日志；到期日期日历可选范围很大，第一次点开约卡 5 秒。

### 5.11 聚合支付

- 顾客扫固定二维码打开 `mini.snowmeet.top/unipay/index.html`，输入金额 → `Order/CreateUnipayOrder`（门店写死为崇礼旗舰店；在微信里走微信支付，否则走支付宝）。
- 支付成功后顾客扫公众号码（`unipay_` 场景）获得一张免费打蜡券。
- 店员页面：后台「【支付】聚合支付」→ `pages/admin/unipay/unipay`、订单查询 `unipay_list`、订单详情 `unipay_detail`（可退款）。

### 5.12 员工管理

- 新员工入职：`pages/admin/staff_reg_qrcode` 显示注册二维码，新员工扫公众号码（`snowmeet_staff_reg` 场景）或在公众号发「我要入职」。
- 员工列表、员工信息：`pages/admin/staff/staff_list`、`staff_detail`。
- 入口可见性和接口路由都有疑点，见 6.2、6.6。

### 5.13 管理员 AI 帮助与自然语言查询

- 后台页右下角的悬浮图标（可拖动，限制在屏幕内）。点开显示本页的操作说明，可以追问。回答只讲功能、规则、步骤和常见错误，不显示代码、字段、接口名。加载中可点「停止」。需要 `title_level ≥ 200`。
- 租赁订单列表支持自然语言查询，例如「四月的租赁订单」「只看未支付的」。系统把问题解析为日期、门店、状态等条件，执行只读查询，返回文字汇总，并跳转到套用了这些条件的列表页；之后可继续用自然语言修改条件或回顾条件。其他业务页面暂不支持数据查询。
- 限制：门店名必须和系统里完全一致（例如说「万龙店」会失败，系统里叫「万龙服务中心」），失败时只显示「暂时无法获得回答」；不支持金额区间条件。
- 调用链：小程序 → `AdminAi/*` → reqai（`snowmeet.goldenma.xyz`）。每次调用记录在 `admin_ai_request_log` 表。

### 5.14 公众号后台

- 关注、取关时更新 `member.following_wechat`。
- 带参二维码扫码事件（场景值以下划线分段，第一段决定处理方式）：

| 场景 | 作用 |
|---|---|
| `ticket_gift_*` | 优惠券转赠：关注后自动接受 |
| `ticket_share_*` | 店员分享批次：关注后自动领取 |
| `ticketqr_*` | 固定二维码发券 |
| `getticket_*` | 已停用，回复活动已结束 |
| `care_*` | 养护扫码取板核验 |
| `recept_*` | 店铺接待扫码 |
| `reserveskipass`、`reserveskipassbystaff_*` | 雪票预订、店员推广 |
| `oper_ticket_*` | 店员扫券后回复开单链接（券详情页二维码已改为纯券码，这条路基本不再触发） |
| `unipay_*` | 聚合支付后送打蜡券 |
| `snowmeet_staff_reg` | 员工注册 |
| `pay`、`confirm`、`me`、`contact` 等 | 其他 |

- 对外接口：临时带参二维码 `OfficialAccountApi/GetOAQRCodeUrl`、永久码 `GetOALimitQrCodeBySessionKey`、按 openid 发客服消息 `SendTextMessageByOpenId`。
- 全部需要真实微信扫码，属于 D 类测试。

### 5.15 后台网页

- 登录：打开 `mini.snowmeet.top/background/index.html` 显示二维码，店员在小程序后台点「【扫码】登录后台」扫码（`BackgroundLoginSession/SetSessionKey`）。
- 报表：租赁订单报表、租赁业务报表、养护业务报表、零售和七色米报表、上传七色米订单、大好河山对账单、微信支付报表。

### 5.16 支付宝小程序

`alipay_snowmeet/` 只有首页、雪票订单、支付页。支付页与微信小程序的 `payment_entry` 对应，但是**独立代码**，微信端修过的问题要单独验证。需在支付宝开发者工具单独编译。手机号解密依赖支付宝开放平台的签名配置。

---

## 6. 本次核对代码发现的疑点（建议测试时优先确认）

### 6.1 后台菜单里有 6 个入口指向不存在的页面（确定打不开）

这些页面没有在 `app.json` 注册，文件也不存在：

| 菜单项 | 跳转路径 |
|---|---|
| 【养护】现场雪具养护列表 | `/pages/admin/maintain/task_list` |
| 【养护】快速查询 | `/pages/admin/fire/fire_care_list?bizType=care` |
| 【养护】养护取板 | `/pages/admin/maintain/return_entry` |
| 【养护】需盘点的 | `/pages/admin/maintain/maintain_in_stock` |
| 【租赁】快速查找订单 | `/pages/admin/fire/fire_care_list?bizType=rent` |
| 【招待】养护招待 | `/pages/admin/vip/maintain_recept` |

### 6.2 页面调用的旧接口路径在后端代码里找不到对应路由

下列页面调用 `/core/...`，但后端对应的控制器只有 `/api/...` 路由，或者根本没有这个方法。**除非线上服务器另有转发，否则这些调用会返回 404。** 本机访问不到线上，无法确认，需在开发者工具或真机上各点一次：

| 页面 | 调用 | 后端情况 |
|---|---|---|
| 租赁报表 `rent_report` | `/core/Rent/GetCurrentDayPlaced` 等 4 个 | Rent 控制器只有 `/api` |
| 今日未完成的店铺接待 `recept_list` | `/core/Recept/GetUnSubmitRecept` | Recept 控制器只有 `/api` |
| 员工列表、员工信息、新员工入职 | `/core/Member/GetStaffList`、`GetWholeMemberInfo`、`SetStaffInfo`、`RegStaff`、`GetMemberByCell` | Member 控制器只有 `/api`，且没有这些方法 |
| 订票二维码 `reserve_qrcode` | `/core/Member/GetMemberByCell` | 同上 |
| 发放优惠券 `ticket_template_list` | `/core/Ticket/GetChannels` | Ticket 控制器只有 `/api` |
| 待核销的优惠券 `ticket_unuse_list` | `/core/Ticket/GetTicketsByUser`、`/core/Ticket/Use` | 同上 |
| 绑定优惠券 `ticket_bind` | `/core/ticket/bind`、`/core/ticket/getticket` | 同上 |

### 6.3 已知未解决的问题

- 养护「取消养护」弹窗：填了取消原因后点「扫码取板」仍提示未填，二维码不自动生成。代码里还留有临时诊断提示（`care_order_detail.js` 中标注 `TEMP DEBUG`）。
- 入库页临时耗时日志未删（`pages/fnbinv/inbound/inbound.js` 标注 `TEMP 耗时诊断`）。

### 6.4 万龙雪票数量大于 1 时金额可能算错

`SkiPassController.ReserveSkiPass` 里雪票成交价已经乘了数量，订单总额又乘了一次数量，数量为 N 时订单金额会是单价 × N²。目前购票界面固定只买 1 张，所以界面上不会出现，但直接调用接口传 `count=2` 可以复现。

### 6.5 找回中断的订单时门店可能与当前所选不一致

找回的订单沿用创建时的门店，页面上显示的当前门店可能是另一家，养护计价也按订单的门店算。是保留原门店并加提示，还是改成当前门店，待负责人决定。

### 6.6 人事入口的可见性

按代码，「【人事】新员工入职」「【人事】员工列表」只对 `title_level` 在 101～200 之间（店长）的员工显示，系统管理员（大于 200）看不到。需确认是否符合预期。

---

## 7. 回归重点（历史上出过问题的地方）

测试方案应覆盖以下场景，确保旧问题没有复发：

**租赁**
1. 找回中断的订单后，改租金、加套餐能正确保存（曾经保存失败但界面显示成功）。
2. 没有价格配置的品类（如雪杖）改日租金能保存。
3. 开单时装备的「立即租赁」标记、起租日期时间在保存后不丢失。
4. 免除某天租金后，起租、退租时间和订单状态仍然正确（曾经退回「未开始」）。
5. 装备全部归还后显示退租时间；归还但未退款时状态是「全部归还」而不是「全额退押金」。
6. 未支付的订单应退押金为 0；已付订单应退押金不为 0。
7. 按钮置灰时确实点不动（曾经置灰的退款按钮仍能点）。
8. 已付款的订单满足条件后能正常关单（曾经所有已付款订单都关不了）。
9. 未发放装备的商品不按天计租（曾经产生大量虚账）。
10. 招待商品小计为 0，列表显示毛租金。
11. 储值付租金并退款时押金能真正退回，且不产生 0 元储值支付记录。
12. 同一订单多笔支付时，顾客扫追加押金的二维码看到的是这一笔的金额和状态（微信、支付宝两端）。
13. 多笔支付的退款金额分配必须正好等于应退金额。

**养护**
14. 连续快速修改不会重复建单，已选的卡不会被冲掉，去结算一次成功。
15. 选卡计价 0 元；机打蜡季卡升级补差价；限装备季卡锁定装备；季卡当天已用则不可选。
16. 券的减免不覆盖店员手动加大的减免。
17. 顾客用另一个会员号付款后，次卡仍能正确核销（曾经静默不核销）。
18. 0 元招待单「确认生效」能成功。
19. 养护单退款不报 500。
20. 安全检查默认值在补传照片等操作后不丢失。

**支付与会员**
21. 代付时微信支付能弹出支付窗口（曾因 openid 为空弹不出）。
22. 支付宝支付成功后 `order_payment.open_id` 有值，并按手机号绑定会员。
23. 扫码人就是订单会员时不报身份状态错误。
24. 订单生效的 5 个入口都能补全会员空缺的姓名、性别。
25. 新顾客（没有会员号）授权手机号、购买次卡不报错。

**优惠券与次卡**
26. 新发的券 `valid=1`，能在开单时选到。
27. 同一张券转赠给不同的人时，不会沿用上一个人的关注记录。
28. 已退款的次卡在所有核销入口都不出现；从未用过的卡可以自助退款，退过的不能重复退。
29. 查询「全部卡型」时季卡能显示（曾经只显示次卡）。

**公共组件**
30. 手动选门店后不会被蓝牙定位结果改回去（曾导致养护订单查不到）。
31. 日期组件默认高亮的快捷键与实际查询范围一致。
32. 列表页从详情返回保留页码和筛选。
33. 上传图片失败时有提示，不会出现空白图片框。

**雪票与商品**
34. 崇礼旗舰店能查到万龙雪票商品（曾按门店名筛选导致查不到）。
35. 养护商品改名后价格仍正确（曾按商品名关键词匹配导致服务费变 0）。

---

## 8. 测试开始前必须确认的部署和数据前提

### 8.1 版本

- 生产后端是否已部署到 `SnowmeetApi ai@18e0601a`（含 9 月 30 日的 OCR 日期规则）。9 月 27 日负责人说已部署 `9db5d2a9`，未核实。
- 小程序体验版、正式版是否是 `ai@0c712574`。**先部署后端，再发布小程序**，否则小程序会调用不存在的接口。
- reqai 线上版本：开发记录写的是 `main@c5ab3ef`，本机最新是 `6131ea4`（多一个提交：按业务域拆分 action 类型），线上是否已部署未记录。
- 公众号后台 `ai@4c9c0a6` 是否已部署。

### 8.2 数据库结构

后端的数据模型已经使用下列表和列。**生产库缺少其中任何一个，部署后相关查询都会报 500。** 本次想做一次只读的结构比对，但没有获得执行权限，需要负责人确认：

| 内容 | 脚本 | 记录中的状态 |
|---|---|---|
| 食材门店「多呆一会儿吧」+ 后厨员工 `base_shop_id` | `sql/2026-09-23_fnb_restaurant_shop.sql`（需填员工 id） | 未确认执行 |
| 食材档案属性下沉 | `sql/2026-09-24_fnb_item_expiry_settings.sql` | 未确认执行 |
| 半成品分类 | `sql/2026-09-25_fnb_category_prepared.sql` | 未确认执行 |
| 用量预警 | `sql/2026-09-26_fnb_item_low_stock.sql` | 未确认执行 |
| 食材主体表 | `sql/2026-09-22_fnb_inventory_other_tables.sql` 等 | 9 月 22 日已核对存在 |
| `care.is_cancel`、`care.cancel_reason` | 无脚本文件 | 未确认 |
| `order.pay_with_deposit` | 无脚本文件 | 未确认 |
| `punch_card.is_refund` | `sql/2026-07-25_punch_card_add_is_refund.sql` | 未确认 |
| `product.usage_rules`、`care_project_count` | `sql/2026-07-25_*`、`2026-07-26_*` | 7 月 26 日已确认执行 |
| 优惠券模板新字段、分享批次表、海报字段 | `sql/2026-08-18_*`、`2026-08-20_*`、`2026-08-21_*` 及 8 月 28 日的海报字段 | 未确认 |
| 管理员 AI 请求日志表 | `sql/2026-09-07_admin_ai_request_log.sql` | 9 月 7 日已部署 |

建议在测试前做一次「后端数据模型与生产库结构的逐列比对」：用 `tools/windows_test/efschema` 生成建表脚本，再与生产库的 `INFORMATION_SCHEMA.COLUMNS` 对比，只读即可。

### 8.3 外部配置

- 微信公众平台「扫普通链接二维码打开小程序」已登记 4.9 的全部路径。
- 小程序 uploadFile、downloadFile 合法域名包含 `mini.snowmeet.top`。
- 企业微信应用 1000009 已配置可信域名；服务器上 `config.fnbAlertReceivers` 已配置提醒接收人。
- 自我游账户有足够预存款（万龙雪票）。
- 蓝牙标签打印机已在 `printer` 表登记。

---

## 附录 A：小程序页面清单

入口说明：「底部菜单」= 顾客首页底部 tab；「我的」= 我的页面；「后台」= 我的 → 我是管理员 → 后台菜单；「流程内」= 由其他页面跳转；「扫码」= 扫二维码进入。

| 页面路径 | 标题 | 入口 |
|---|---|---|
| `pages/index/index` | 首页（自动跳转到购买次卡） | 启动 |
| `pages/mine/mine` | 我的 | 底部菜单 |
| `pages/admin/admin` | 管理后台 | 我的 |
| `pages/ski_pass/ski_pass_selector` | 雪票预定 | 底部菜单「预定」 |
| `pages/ski_pass/skipass_detail_new` | 万龙雪票详情 | 流程内 |
| `pages/mine/skipass/my_skipasses` | 我的雪票 | 我的 |
| `pages/mine/skipass/my_skipass` | 我的雪票（旧） | 流程内 |
| `pages/punchcard/punchcard_shop` | 购买次卡 | 底部菜单「次卡」 |
| `pages/punchcard/punchcard_detail` | 次卡详情 | 流程内 |
| `pages/punchcard/punchcard_confirm` | 确认订单 | 流程内 |
| `pages/mine/my_punchcards` | 我的次卡 | 我的 |
| `pages/mine/punchcard_usage` | 次卡使用明细 | 流程内 |
| `pages/mine/ticket/ticket_list` | 我的优惠券 | 我的 |
| `pages/mine/ticket/ticket_detail` | 优惠券详情 | 流程内 |
| `pages/mine/ticket/ticket_share` | 接受优惠券赠送 | 分享卡片 |
| `pages/mine/ticket/ticket_claim/ticket_claim` | 领取优惠券 | 分享卡片 |
| `pages/mine/ticket/ticket_bind` | 绑定优惠券 | 流程内 |
| `pages/mine/deposit/deposit_list` | 我的储值 | 我的 |
| `pages/register/reg` | 会员注册 | 流程内 |
| `pages/register/out_reg` | 外部注册 | 流程内 |
| `pages/order/payment_entry` | 支付订单 | 扫码 |
| `pages/order/identity_verify` | 身份核验 | 扫码 |
| `pages/payment/settle/index` | 支付结算 | 流程内 |
| `pages/admin/reception/recept_entry` | 店铺接待 | 后台 |
| `pages/admin/reception/recept_new` | 开单 | 流程内 |
| `pages/admin/reception/recept_package` | 选择套餐 | 流程内 |
| `pages/admin/recept/recept_list` | 今日未完成的店铺接待 | 后台 |
| `pages/admin/rent/new_rent_list` | 租赁订单列表 | 后台 |
| `pages/admin/rent/rent_order_detail/rent_order_detail` | 租赁订单明细 | 流程内 |
| `pages/admin/rent/rent_append` | 追加租赁商品 | 流程内 |
| `pages/admin/rent/unreturned` | 未归还租赁物 | 后台 |
| `pages/admin/rent/rent_report` | 租赁报表 | 后台 |
| `pages/admin/rent/search_fuzzy` | 查询租赁物 | 后台 |
| `pages/admin/rent/settings/category_tree` | 租赁分类维护 | 后台（系统管理员） |
| `pages/admin/rent/settings/rent_package_list` | 套餐列表 | 后台（系统管理员） |
| `pages/admin/rent/settings/rent_package` | 套餐详情 | 流程内 |
| `pages/admin/rent/settings/rent_product_list` | 租赁商品列表 | 后台 |
| `pages/admin/rent/settings/rent_product` | 租赁商品详细信息 | 流程内 |
| `pages/admin/rent/settings/rent_product_add` | 添加租赁商品 | 后台 |
| `pages/admin/rent/punchcard_products/punchcard_products` | 次卡商品管理 | 后台（系统管理员） |
| `pages/admin/rent/punchcard_products/punchcard_product_detail/punchcard_product_detail` | 次卡/季卡商品维护 | 流程内 |
| `pages/admin/rent/punchcard_sales/punchcard_sales` | 卡类产品销售 | 后台（系统管理员） |
| `pages/admin/care/care_order_list` | 养护订单列表 | 后台 |
| `pages/admin/care/care_order_detail/care_order_detail` | 养护订单 | 流程内、扫码 |
| `pages/admin/care/care_unfinished_list` | 未完成养护装备 | 后台 |
| `pages/admin/care/care_unpicked_list` | 养护未发板装备 | 后台 |
| `pages/admin/care/care_product_admin/care_product_admin` | 养护价格维护 | 后台 |
| `pages/admin/member/member_list` | 会员管理 | 后台 |
| `pages/admin/member/member_detail` | 会员详情 | 流程内 |
| `pages/admin/member/member_register` | 注册会员 | 流程内 |
| `pages/admin/member/member_tag_admin` | 标签库维护 | 流程内 |
| `pages/admin/deposit/deposit_account_list` | 储值账户 | 后台 |
| `pages/admin/deposit/deposit_account_detail` | 储值账户详情 | 流程内 |
| `pages/admin/deposit/deposit_list` | 储值账户列表（旧） | 后台 |
| `pages/admin/deposit/deposit_detail` | 储值账户详情（旧） | 流程内 |
| `pages/admin/deposit/deposit_charge_search` | 新增储值 | 后台 |
| `pages/admin/deposit/deposit_charge` | 新增储值 | 流程内 |
| `pages/admin/deposit/deposit_balance` | 储值资金流水 | 后台 |
| `pages/admin/ticket/coupon_admin/coupon_admin` | 优惠券管理 | 后台 |
| `pages/admin/ticket/coupon_detail/coupon_detail` | 优惠券详情 | 流程内 |
| `pages/admin/ticket/template_admin/template_admin` | 优惠券模板 | 后台 |
| `pages/admin/ticket/template_edit/template_edit` | 模板设置 | 流程内 |
| `pages/admin/ticket/use_entry` | 优惠券核销 | 后台 |
| `pages/admin/ticket/ticket_template_list` | 发放优惠券 | 后台（「【优惠券】打印」） |
| `pages/admin/ticket/ticket_unuse_list` | 待核销的优惠券 | 流程内 |
| `pages/admin/ski_pass/common_skipass_list` | 自我游雪票管理 | 后台（「大好河山雪票管理」） |
| `pages/admin/ski_pass/common_skipass_detail` | 雪票商品详情 | 流程内 |
| `pages/admin/ski_pass/dhhs_skipass_order` | 大好河山雪票 | 后台（「自我游订单」） |
| `pages/admin/ski_pass/reserve_qrcode` | 订票二维码 | 后台 |
| `pages/admin/retail/retail_order_list` | 零售订单列表 | 后台 |
| `pages/admin/retail/retail_order_detail` | 零售订单详情 | 流程内 |
| `pages/admin/unipay/unipay` | 聚合支付 | 后台 |
| `pages/admin/unipay/unipay_list` | 聚合支付订单查询 | 流程内 |
| `pages/admin/unipay/unipay_detail` | 聚合支付订单详情 | 流程内 |
| `pages/admin/staff/staff_list` | 员工管理 | 后台（店长） |
| `pages/admin/staff/staff_detail` | 员工信息 | 流程内 |
| `pages/admin/staff_reg_qrcode` | 新员工注册二维码 | 后台（店长） |
| `pages/admin/staff_reg` | 员工注册 | 扫码 |
| `pages/admin/env` | 选择环境 | 我的（开发版、体验版） |
| `pages/admin/fnb/mat_expire_list/mat_expire_list` | 食材库存（旧） | 标签深链 |
| `pages/admin/fnb/mat_expire_detail/mat_expire_detail` | 录入批次（旧） | 流程内、扫码 |
| `pages/fnbinv/stock/stock` | 食材库存 | 后台 |
| `pages/fnbinv/inbound/inbound` | 每日入库 | 食材底部 tab |
| `pages/fnbinv/cats/cats` | 分类维护 | 食材底部 tab |
| `pages/fnbinv/prep/prep` | 半成品制作 | 食材底部 tab |
| `pages/fnbinv/recipe/recipe` | 菜品配方 | 食材底部 tab |
| `pages/fnbinv/serve/serve` | 出餐扣减 | 食材底部 tab |
| `pages/fnbinv/count/count` | 盘点核对 | 食材底部 tab |
| `pages/fnbinv/dash/dash` | 数据看板 | 食材底部 tab |
| `pages/fnbinv/expiry/expiry` | 临期与过期 | 流程内 |
| `pages/fnbinv/lowstock/lowstock` | 用量预警 | 流程内 |
| `pages/fnbinv/destroy/destroy` | 过期食材销毁 | 流程内 |
| `pages/fnbinv/batch/batch` | 批次详情 | 流程内 |

## 附录 B：后端接口清单

路由格式：`/api/{控制器}/{方法}` 或 `/core/{控制器}/{方法}`。只列 public 接口方法名，参数见代码或 Swagger（`/swagger`，仅开发环境开启）。

| 控制器（路由前缀） | 方法 |
|---|---|
| Order（api） | GetShops, GetRetailOrders, GetRetailOrder, UpdateOrderByStaff, UpdateFdOrderByStaff, GetRetailDetail, UpdateRetail, CreateUnipayOrder, PlaceOrder, CancelOrder, GetOrdersByStaff, GetOrdersByStaffPaged, GetOrderByCustomer, GetOrderByStaff, SetDiscount, GetWepayPayment, GetAlipayPaymentQrCode, WechatPayByOrderPayment, GetAlipayMiniPayment, AlipayPayByOrderPayment, WechatPay, EffectUnpaidOrder, CancelPaying, GetUnCommonPayMethod, LoadLogs, LogShowWechatQrCode, GetOrderFromPaymentByCustomer, GetPaymentLiveStatus, UpdateOrderWithDetailByStaff, Refund, PlaceRentOrder, PlaceCareOrder, PayWithDeposit, WriteoffCareOrder, GetOrderBalance, SetOrderCloseStatus |
| Rent（api） | 租赁分类/价格/套餐/租赁物维护：GetRentPriceList, AddCategory, GetAllCategories, GetTopRentCategories, GetSubRentCategories, GetRentCategory, UpdateCategory, AddRentPackage, GetRentPackageList, GetRentPackage, AddRentProduct, ModRentProduct, GetRentProduct, GetRentProductByBarcode, GetRentProductFuzzy 等；开单：SaveRentRecept, GetReceptingOrders, GetReceptingOrder；订单操作：SetRentItemStatus, ReturnAllRentItems, UpdateRentItemByStaff, UpdateRentalByStaff, UpdateRentalDayChargesByStaff, SetRentalEntertainByStaff, SetRentItemRepairAmount, UpdateRentalGuarantyByStaff, QueryChangeCompatibleCategory, ChangeRentItemByStaff, GetRentItemChanges, GetRentItemLogByStaff；追加：AppendRental, RemoveAppendingRental, SaveAppendings；次卡：GetRentalPunchCardInfo, UseRentalPunchCard, GetPunchCardProducts, GetPunchCardProduct, GetAllPunchCardProducts, DeletePunchCardProduct, GetMyPunchCards, CheckMyPunchCardPurchase, PlaceMyPunchCardOrder, GetMyPunchCardOrder, StartMyPunchCardPayment, GetMyPunchCardUsages, RefundMyPunchCard, GetPunchCardSalesByStaff, GetPunchCardUsagesByStaff, UpdatePunchCardEquipByStaff, PreparePunchCardSale, StartPunchCardSaleQr, FinalizePunchCardSale；其他：CloseOrder, GetUnReturnedRentItemsByStaff, GetOrdersFuzzyByStaff, GetConfirmedRentOrder 及旧版方法（共约 120 个） |
| Care（api） | UpdateBrandByStaff, GetBrands, GetCareByStaff, UpdateCareByStaff, GetCareProducts, GetProducts, CalcCareCharge, SetPickImageId, SetTaskStatus, CreateVerifyCode, VeriCareFinishCode, GetReport, GetMemberCaredEquipments, GetUnpickedCareItemsByStaff, GetIncompleteCareItemsByStaff, GetMemberLatestSafeCheck, SaveCareRecept |
| CareProductAdmin（api） | GetCareProductsByStaff, SaveCareProductByStaff, DeleteCareProductByStaff |
| PaymentIdentity（api） | CheckPayerIdentity, ConfirmPayIdentity, VerifyWechatIdentity, GetWechatVerifyStatus |
| Tenpay（api） | TenpayPaymentCallback, RefundCallback, ImportTrans, ImportFlow, GetWepayBalance, CreateStatement |
| Ali（api） | CallBack, AppGateway, GetUnSettledAmount 等 |
| MemberAdmin（api） | SearchMembersByStaff, GetMemberDetailByStaff, UpdateMemberProfile, AddMemberTag, RemoveMemberTag, GetTagLibrary, GetTagLibraryWithStats, MergeTagPreset, DeleteTagPreset, AddTagPreset, RegisterMemberByPhone, ChargeMemberDeposit, GetPunchCardPresets, GrantPunchCard, GetCouponTemplates, GrantCoupon, MergeMemberByStaff, GetMemberAssetsByStaff, GetMemberCardsByStaff, SearchDepositAccountsByStaff, GetDepositAccountDetailByStaff |
| Member（api） | ChangeCellNumByStaff, GetMemberByNum, GetMember, UpdateMemberInfo, VerifyCell, StopQueryMemberBindCell, GetMyInfo |
| MiniAppHelper（api） | MemberLogin, PushMessage, OpenMiniProgram |
| MiniAppUser（core） | UpdateWechatMemberCell, GetStaffList, GetMemberByCell 等 |
| Deposit（core） | GetMemberAvaliableAmount, DepositCharge, GetAccounts, GetMyAccounts, SearchMember, GetMember, SearchDepositAccounts, GetAccount, ModAccountInfo, GetAllBalance 等 |
| Ticket（api） | GetMyTickets, GetMySharedTickets, CheckTransferFollow, SetTicketToShare, AcceptTicket, AcceptTicketByOaFollow, CancelShare, GetTicket, GetTemplateList, GetTicketTemplateById, GenerateTickets, GetMemberTicketsByStaff, GetTicketsByUser, Use, Bind 等 |
| TicketAdmin（api） | SearchTicketsByStaff, SearchTicketMembersByStaff, GetTicketDetailByStaff, GetMemberCouponsByStaff, GetIssuerOptions, GetTemplateOptions |
| TicketTemplateAdmin（api） | GetTemplateListByStaff, GetTemplateDetailByStaff, SaveTemplateByStaff, SaveProductRuleByStaff, DeleteProductRuleByStaff, ShareTemplateByStaff, CreateQrCodeBatchByStaff, GetShareBatches, RevokeShareBatch, GetProductOptionsByStaff |
| TicketShare（api） | GetShareBatch, ClaimSharedTicket, ClaimSharedTicketByOaFollow, ClaimByOaScan |
| TicketPoster（api） | Generate |
| SkiPass（core） | GetResorts, GetSkiPassDetailInfo, GetSkiPassProduct, GetSkipass, GetMySkipass, Cancel, Refund, ReserveSkiPass, GetProductsByResort, GetProduct, ModDailyPrice, GetDHHSReservedSkipasses, SetNotify |
| WanlongZiwoyouHelper（core，自我游） | GetProductList, Book, GetProductDetail, GetProductPrice, GetOrder, GetProductById, CallBack, GetOrderListByPage, GetBalance, GetOrderBills |
| Product（core） | SetHidden, GetSkiPassProduct, GetProduct 等 |
| Category（api） | AddNewCategory, UpdateCategory, GetSingleLevelCategory, ModProduct, AddProduct, GetProduct, GetCategoryProducts, UpdateProductStock |
| Retail（api） | ShowMi7Order, GetOrdersByMi7Code, PlaceOrder |
| Mi7Order（core） | AddSupplementOrder, Enterain, PaySupplement, GetSaleReport, GetMi7OrderById, GetMi7Order, ModMi7Order |
| Fnb 系列（api） | FnbCatalog（单位、分类、保质期规则、食材、用量预警设置）、FnbInventory（入库、删除入库、开封、报损、制作、批次、库存、标签数据、低库存、单据、流水）、FnbKitchen（厨房单增删改、出餐、欠料、补扣）、FnbRecipe（菜品、规格、配方草稿与发布）、FnbStocktake（快照、录数、预览、过账）、FnbReport（概览、损耗、临期汇总）、FnbMaterial（旧版过期提醒）、FnbWeCom |
| AdminAi（api） | AskAdminAssistantByStaff, GetPageHelpByStaff, AskPageHelpByStaff, QueryRentOrdersByNaturalLanguage |
| QrCode（api） | CreateNewScanQrCodeByStaff, StopQeryScan, QueryCell, GetTodayAuthCellList, GiveAuth, StartReceptWithoutScan |
| Printer（api） | GetPrinters, GetPrinterByScene, GetAllPrinters, RefreshPrintTask, ReplyFetched |
| UploadFile（api） | UploadFileWithThumb, UploadFile, GetFile, GetUploadList, Upload |
| MediaHelper（api） | GetQRCode, ShowImageFromOfficialAccount |
| Ocr（core） | GeneralBasicOCR |
| BackgroundLoginSession（api） | GetLoginQrCodeUrl, SetSessionKey 等 |
| OrderShare（api） | GetPaymentShares, CreateShare, SharePayment, ExecuteWLShare |
| Point（api，龙珠） | GetMemberTotalPoints, GetMyPointsSummary, GetMyPointsBalance, SetPoint 等 |
| ShopSaleInteract（core） | GetInterviewIdByScene, GetScanInfo, SetOpenIdByCell, GetAuthList, Auth |
| 其他旧控制器 | Recept、MaintainLive、MaintainLogs、Experience、OrderPayment、OrderRefund、ServiceMessage、WeCom、DD、Excel、Vip、Tiktok 等，多为旧流程，雪季测试不作重点 |

公众号后台（`wxoa.snowmeet.top`）：`/api/OfficialAccountApi/PushMessage`（微信服务器消息入口）、`GetOAQRCodeUrl`、`GetOALimitQrCodeBySessionKey`、`SendTextMessageByOpenId` 等。

## 附录 C：名词解释

| 名词 | 含义 |
|---|---|
| rental | 租赁订单中的一个商品（一个套餐或一个单品） |
| rentItem | 商品里的一件具体装备，有编码 |
| 立即租赁 / 先租后取 / 延时租赁 | 租赁模式；立即租赁在生效时直接发放 |
| 暂存 | 顾客把装备暂时存回店里，仍在租期内 |
| 招待 | 免费提供，租金或服务费计 0 |
| 质保 | 养护的保修服务，计 0 |
| 非雪季养护 | 雪季外的养护，分立等现修（now）和寄存后修（later） |
| 发板 | 养护完成后把装备交还顾客，是养护任务链的最后一步 |
| 核销 | 使用次卡、券或储值抵扣并记录 |
| 次卡 / 季卡 | 按次数 / 按雪季不限次（每天一次）的预付卡 |
| 龙珠 | 会员积分 |
| 七色米 | 零售门店使用的收银系统，订单号以 XSD 开头 |
| 自我游 | 万龙雪票的第三方代订平台 |
| 大好河山 | 雪票合作渠道（与自我游相关的对账） |
| 草稿单 | 开单中还没去结算的订单，`valid=0` |
| 代付 | 扫码付款的人不是订单会员，付款后订单仍归原会员 |
| is_test | 测试订单标记，见 3.4 |
| sessionKey | 小程序登录会话的密钥，接口鉴权用 |
| beacon | 门店的蓝牙信标，用于自动识别所在门店 |
