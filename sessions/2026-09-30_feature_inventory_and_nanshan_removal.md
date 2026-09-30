# 2026-09-30 雪季测试准备与南山清理：写系统功能说明文档，删除小程序南山代码

按主题整理。会话从 start-work 开始（Windows 机 `D:\source\snowmeet\ai`）。用户说 10 月雪季要开始，先要一份覆盖全部已开发功能的文档，交给 ChatGPT 生成测试方案，再由 Copilot 执行。随后告知南山已关店，要求删除小程序中所有南山业务代码，不能误删共用功能，并把测试文档里的南山内容也去掉。改动落在 `snowmeet_ai_doc/docs/testing/`（新）和 `snowmeet_wechat_mini/`（未提交）。

## 1. start-work

- 文档仓 pull：already up to date（`b8481c4`）。
- 四仓干净：SnowmeetApi `ai@18e0601a`、小程序 `ai@0c712574`、公众号 `ai@4c9c0a6`、文档 `main@b8481c4`。
- 公众号仓、reqai 的 fetch 因 github 22 端口超时失败，ahead/behind 用的是本地缓存。
- reqai 本机路径是 `D:\source\snowmeet\snowmeet_reqai`（不是文档写的 Mac 路径），HEAD `6131ea4`，比文档记的线上 `c5ab3ef` 多一个提交。

## 2. 系统功能说明文档

### 2.1 用户需求

> 测试之前，请你先把目前系统已经开发的功能，能形成个文档吗？然后这个文档我会交给 chatGPT 生成测试方案。这个测试方案最终会交给 copilot 来执行。

- 形式：写成仓库里的 Markdown 文件，方便上传给 ChatGPT，Copilot 也能在仓库里直接读。没有发布成 claude.ai 页面（ChatGPT 访问不了）。

### 2.2 调研方法（对照代码，不只照搬开发记录）

- `app.json`：主包 89 页 + 两个分包（payment 1、fnbinv 12），共 101 页；逐页取标题。
- 后台菜单 `admin.wxml` / `admin.js`：把菜单 id 映射到路径，逐个核对页面是否注册、文件是否存在。
- 后端：扫 61 个控制器的路由前缀（`api` / `core`）和 public 方法。
- 写脚本比对小程序里所有接口调用与后端路由（控制器 + 方法 + 前缀）。排除误报：`MediaHelper`、`WanlongZiwoyouHelper` 类名不带 Controller 后缀；公众号接口在另一个项目；注释掉的代码；`requestPrefix + 'Rent/RentPackageCategory' + action` 这类拼接。
- 公众号 `OfficialAccountApi.cs` 的扫码场景分发表、`wwwroot` 下的后台网页和聚合支付 H5、支付宝小程序页面、现有测试和运行工具、`is_test` 的赋值规则。

### 2.3 文档结构

`docs/testing/2026-09-30-system-feature-inventory.md`，约 870 行：

- 第 0 章给测试方案编写者：用例按执行方式分 A～D 四类（单元测试 / 本地隔离库接口 / 开发者工具界面 / 真机人工）。
- 7 条执行安全红线：
  - 本地 `dotnet run` 默认连生产库（`config.sqlServer` → `snowmeet_new`）。
  - 不许真实支付或退款。
  - 不许调用万龙雪票下单（支付成功后 `CreateSkiPass` → `AutoReserve` 向自我游真实订票扣预存款）。
  - 不许触发群发推送（`PushExpireAlert` 默认 @all）。
  - 不改服务器本地配置并提交；不执行 DDL；生产写操作要人工确认。
- 第 1～4 章：系统组成、角色权限（title_level 四档、各接口最低级别）、测试环境与工具、跨业务公共机制（登录、订单支付退款、结算页、扫码支付与身份确认、订单生效 5 入口、身份核验、公共组件、需登记的扫码路径）。
- 第 5 章：16 个业务模块，附雪季测试优先级建议（租赁、养护、雪票、支付为 P0）。
- 第 6 章：核对代码发现的疑点；第 7 章 35 条回归重点（从「已知遗留」提炼）；第 8 章部署和数据前提；附录页面清单、接口清单、名词表。
- 食材权限按接口契约文档改准：在职员工可入库、出餐、制作、开封、查询；店长才能维护档案配方、盘点过账、报损销毁、设置用量预警、看成本。

### 2.4 核对代码发现的疑点

- **后台菜单 6 个死入口**（页面未注册、文件不存在）：
  - 【养护】现场雪具养护列表 `maintain/task_list`
  - 【养护】快速查询、【租赁】快速查找订单 `fire/fire_care_list`
  - 【养护】养护取板 `maintain/return_entry`
  - 【养护】需盘点的 `maintain/maintain_in_stock`
  - 【招待】养护招待 `vip/maintain_recept`
- **9 个页面的 `/core/...` 调用在后端找不到路由**：租赁报表 `/core/Rent/*`、`recept_list` `/core/Recept/*`、员工管理 `/core/Member/*`（方法本身也不存在）、订票二维码、`ticket_template_list` / `ticket_unuse_list` / `ticket_bind` 的 `/core/Ticket/*`。本机连不上线上，无法确认 nginx 是否转发。
- **万龙雪票数量 N 时金额 × N²**：`ReserveSkiPass` 里 `deal_price` 已乘 count，`total_amount` 再乘一次；界面固定 1 张。
- **人事入口可见性**：`admin.js` 只在 101～200 级置 `isManager`，系统管理员（> 200）看不到。
- 原怀疑 `TenpayController` 退款回调用 `/core/Tenpay/RefundCallback` 而路由是 `/api`，核对后发现那是旧表 `order_payment_refund` 的退款路径，不是当前主路径，没写进文档。

### 2.5 生产库结构比对被拦

- 想用 `tools/windows_test/efschema` 生成当前 EF 模型建表脚本，再只读查生产 `INFORMATION_SCHEMA.COLUMNS` 逐列比对，找出「代码需要但库里没有」的列。
- 建表脚本生成成功；运行比对脚本时被 auto-mode 规则以「Production Reads」拒绝，紧接着一次本地 grep 也被拒。没有绕过。
- 文档第 8.2 节改为待确认清单（食材 09-23～09-26 四份 SQL、`care.is_cancel`/`cancel_reason`、`order.pay_with_deposit`、`punch_card.is_refund`、优惠券模板/分享批次字段等），注明后两者没有脚本文件。

## 3. 删除小程序南山代码

### 3.1 用户需求

> 南山已经确定关店，请把小程序中，所有南山业务相关的代码删除。因为小程序代码有体积限制，所以先删除吧。但是注意，南山和其他店的公用功能，不要误删。

### 3.2 排查共用 vs 独有

- grep `南山|nanshan|Nanashan`（注意 util 里的常量拼成了 `Nanashan`）+ 查每个页面被谁跳转。
- **独有**：`pages/admin/ski_pass/nanshan_*` 7 页、`pages/ski_pass/ski_pass_reserve`（南山预订，调 `NanshanSkipass/ReserveSkiPass`）、`pages/ski_pass/nanshan_overtime_reserve`（南山加票）。没有只被它们用的组件或图片。
- **共用、只删分支**：
  - `ski_pass_selector`：底部「预定」，万龙也从这里下单。
  - `pages/mine/skipass/my_skipass`：**看名字像南山页，实际是万龙付款后的落地页**（`skipass_detail_new` 付款成功跳这里）。顾客从「我的」进的是 `my_skipasses`（无南山分支）。
  - 租赁价格设置：`components/rent/shop_price_matrix`（分类维护、套餐设置共用的门店价格标签页）+ `category_tree` / `rent_package` / `rent_product` 里的 `priceArr` 南山槽（后两者是未使用的遗留数据）。
- **保留**：`common_skipass_*`、`dhhs_skipass_order`、`reserve_qrcode`（都是万龙/自我游）；`app.wxss` 的 `.ski-pass-*` 样式（`my_skipass` 在用）；`utils/adminAiDomains.js` 的雪票域（指向 `dhhs_skipass_order`）。

### 3.3 改动

- `git rm` 36 个文件（9 页 × 4）；`app.json` 删 9 条注册（保留 `my_skipass`）。
- 后台菜单：删「置顶」区和「雪票」区共 5 个南山 cell + `admin.js` 4 个 case。
- `ski_pass_selector`：
  - 删南山的日期选择、自带板/租板、`GetData` 南山分支（`GetSkiPassProduct`、截止时间过滤、说明文字）、`reserve`、`showTempQr`、`DateChanged`、`TagsChange` 和相关 data。
  - wxml 只保留通用商品列表（`gotoDetail` → `skipass_detail_new`）。
  - **后端 `GetResorts` 写死返回「万龙」「南山」**，前端过滤掉南山；兜底列表去掉南山。
  - 带列表里没有的雪场参数进入（如旧链接 `resort=南山`）时落到第一个雪场。否则会按南山查商品并走万龙的下单流程。
- `my_skipass`：删南山的票价/押金/说明块和对应 JS。历史南山雪票按通用样式显示；后端 `Refund` 本身拒绝南山雪票。
- `util.js` 删 3 个 `skiPassDescNanashan*` 常量；`app.js` 删只给南山上传用的 `uploadDomain`，更新 mp-tabbar 注释。
- 租赁价格：`shop_price_matrix.shops` 删南山；`category_tree` 删南山槽和 switch case；`rent_package`、`rent_product` 删南山槽。
- `dhhs_skipass_order.js` 删复制粘贴留下的错误文件头注释。

### 3.4 验证

- 80 个注册页面的 js/wxml/json 都存在。
- 改过的 JS 用开发者工具自带 node `--check` 通过（`app.js` 是 ES 模块写法，替换 import 行后检查）。
- 3 个 wxml 标签配对正确。
- 小程序测试 167/167。
- 源码减少约 83 KB（删除文件）+ 9 KB（修改文件）。
- **未在开发者工具编译、未提交。**

### 3.5 没动的南山残留

- 支付宝小程序首页有「南山」标签（`alipay_snowmeet/pages/index`），若已上线顾客仍可能选到。
- 后端 `GetResorts`、`NanshanSkipass` 控制器；公众号 `nanshanskipass_`/`nanshanreserve_` 场景；`shop_list` 南山记录。

## 4. 测试文档去掉南山内容

- 第一次删代码后，文档加了更新说明、5.4.3「删除后回归点」、6.7「残留清单」。
- 用户要求「把南山相关的内容去掉」→ 全部删除：更新说明、门店列表和门店码里的南山、5.4.3、6.7、公众号南山场景、接口附录 `NanshanSkipass` 行、`GetNanshanTodaySkipass`。雪票章节改为中性表述。
- 删 6.7 时段落紧贴 `---`，Markdown 会把上一段渲染成标题，补了空行。
- 结果：文档里搜不到「南山 / nanshan」。删除后的回归点和残留清单只在聊天回复和 CLAUDE.md 里。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`docs/testing/2026-09-30-system-feature-inventory.md`](../docs/testing/2026-09-30-system-feature-inventory.md) | 新建：雪季测试用系统功能说明 |
| `snowmeet_wechat_mini/pages/admin/ski_pass/nanshan_*`（7 页）、`pages/ski_pass/ski_pass_reserve`、`pages/ski_pass/nanshan_overtime_reserve` | 删除（36 个文件） |
| [`snowmeet_wechat_mini/app.json`](../../snowmeet_wechat_mini/app.json) | 删 9 条页面注册 |
| [`snowmeet_wechat_mini/pages/admin/admin.wxml`](../../snowmeet_wechat_mini/pages/admin/admin.wxml)、`admin.js` | 删南山菜单和跳转 |
| [`snowmeet_wechat_mini/pages/ski_pass/ski_pass_selector.js`](../../snowmeet_wechat_mini/pages/ski_pass/ski_pass_selector.js)、`.wxml` | 删南山分支；过滤南山雪场；未知雪场兜底 |
| [`snowmeet_wechat_mini/pages/mine/skipass/my_skipass.js`](../../snowmeet_wechat_mini/pages/mine/skipass/my_skipass.js)、`.wxml` | 删南山展示块 |
| `snowmeet_wechat_mini/utils/util.js`、`app.js` | 删南山文案常量、`uploadDomain` |
| `snowmeet_wechat_mini/components/rent/shop_price_matrix.js`、`pages/admin/rent/settings/{category_tree,rent_package,rent_product}.js` | 删南山门店价格 |
| `snowmeet_wechat_mini/pages/admin/ski_pass/dhhs_skipass_order.js` | 删错误的文件头注释 |

## 学到的小知识

1. **按名字判断页面归属会误删**：`my_skipass` 看着像南山页，实际是万龙付款后的落地页。删某家店的代码前先查每个页面被谁跳转。
2. **后端写死的列表会把已删功能「送回来」**：`GetResorts` 仍返回南山，前端只删页面不够，要过滤并处理旧链接参数，否则会用另一条下单流程卖出已关店的票。
3. **页面调用和后端路由可以脚本化比对**：抽出 `/core|/api/{控制器}/{方法}` 和 `requestPrefix + '控制器/方法'`，与后端控制器前缀 + public 方法对照，一次就找出 9 个页面的可疑调用。注意类名不带 Controller 后缀、跨项目接口、注释代码、字符串拼接这几类误报。
4. **本地后端默认连生产库**：给自动化测试工具写说明时必须放在最前面，否则 Copilot 做接口测试就是在写生产数据。
5. **Markdown 段落后面紧跟 `---` 会变成二级标题**（setext 语法），删节时要保留空行。
6. **auto-mode 对生产库只读查询时放时拦**：7-26 能查，今天被拦。被拦时不绕过，说明用途，让用户决定放权限或自己执行。
