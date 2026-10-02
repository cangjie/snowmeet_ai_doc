# 2026-10-02 接口改动分析、旧版演示分包、库结构清单：服务端 ai 分支到底改了多少，以及让新旧版能并排对比

按主题整理。会话在 Windows 机上进行。起点是 start-work，然后依次做了四件事：分析服务端 `ai` 分支对旧接口的改动、追查分支来源、在新版小程序里嵌入可删除的「旧版演示」分包、整理 5 月以来的数据库结构变更。

## 1. start-work

- 文档仓库已是最新（`0083352`）。github.com 的 22 端口间歇超时，小程序、公众号、支付宝、reqai 四个仓库 fetch 失败。
- reqai 在这台机器上的路径是 `D:\source\snowmeet\snowmeet_reqai`（skill 里写的是 Mac 路径，本次已在 start-work SKILL.md 补上）。
- **10-01 的工作没跑 end-work**：员工账号管理（`pages/staffadmin/`、绑定码、自助登记、超级管理员、权限等级）。
  - 小程序 `fed5a59f`～`d5613602`、SnowmeetApi `446f955e`～`3c9dc278` 已提交；
  - 文档仓库的 `sql/2026-10-01_staff_bind_code.sql` 未跟踪（本次随 end-work 一起提交）；
  - 公众号仓库 `OfficialAccountApi.cs` 两条入职回复的链接改到 `pages/staffadmin/selfreg/selfreg`，未提交。
- 09-30 南山删除的 50 个改动已在小程序 `cb1513e1` 提交。

## 2. 服务端 ai 分支：今年 4 月以来改过老接口吗？

### 2.1 方法
- 写 Python 解析控制器里的 C# 方法（处理注释、字符串掩码、括号匹配、文件级 namespace、主构造函数）。
- 公开、非静态、非 `[NonAction]` 的方法算接口。只改空格或注释的不算改动。
- 再按方法名建调用图，找出「接口自身没改、但调用了改过的公共函数」的老接口。

### 2.2 结论（以分支起点 `9b4d35f1` 为基线）
- 381 个老接口：37 个改了实现，7 个末尾加了可选参数，0 个删除或改地址/GET/POST，其余没动。新增 175 个，其中 133 个在 17 个新控制器里。
- 对老调用方不兼容的：
  - `Ticket/SetTicketToShare`、`AcceptTicket` 的返回改成 ApiResult 包装，身份改用 member_id；
  - `MemberLogin` 不再自动建会员，也不再自动合并旧会员；
  - 商品模型去掉 `shop`；
  - `GetMySkipass` 只按 member_id 查；
  - `Care/GetProducts` 门店名改为精确匹配；
  - `AppendRental` 两个参数都不传时改为追加空白租赁；
  - 模型里的租赁状态计算重写，`isPackage` 和养护状态的语义也变了。
- 有影响面的公共函数：`GetStaffBySessionKey`（101 个员工接口依赖它，现在多认工作手机的微信）、`GetOrder`、`GetCommonOrders`（「临时订单」判断原来写反了，已修正）。
- 修正了几个旧 bug：`GetMyTickets` 过期判断写反、`RefundCore` 退款结清后作废未提交的追加租赁草稿等。

## 3. ai 分支什么时候建的

- Git 不记录分支创建时间，靠旁证推断：
  - `migrate_to_new_season` 最后一次提交是 04-14 21:48 `9b4d35f1`，完整包含在 `ai` 里；
  - `ai` 独有的第一次提交是 05-01 20:20；
  - 小程序 `ai` 在 05-01 17:25 有「first ai」提交；
  - CLAUDE.md 的开发日志从 05-01 开始。
- 结论：**两个仓库都在 2026-05-01 开出 `ai` 分支。** 之后两个仓库的 `migrate_to_new_season` 都没再改过；小程序的 `migrate_to_new_season` 停在 03-09。

## 4. 旧版演示分包

### 4.1 需求和拍板
- 用户的需求：
  - 在最新版里加一个回旧版的入口；
  - 旧版的接口改连 `https://mini.snowmeet.com`，作为独立演示；
  - 三个约束：体量是否超 2M；没改过的库和组件新旧共用；旧版能随时删除，不留垃圾。
- 用户补充：**旧版 = master 的最后一次提交**（小程序 `584b9466`，03-30）；**现有新版不能受任何影响**。
- 用户的选择：
  - 入口放在后台首页，仅管理员可见；
  - 只改接口和上传的域名，图片显示、公众号二维码服务、二维码内容保持原样。

### 4.2 体量
- 微信官方限制：主包和每个分包各 ≤ 2M，合计 ≤ 30M（第三方代开发的是 20M）。
- 用依赖遍历只算真正会打包的文件。新版主包源码 2438 KB，估算压缩后约 1808 KB，本来就接近 2M。
- 旧版要复制的约 1.25 MB，单独放一个分包 `legacy`；主包只多 4 KB（`app.json` 页面清单 + 入口）。

### 4.3 共用和复制的判定
- 按「单元」判定（同名的 js/json/wxml/wxss/wxs 算一个），满足下面全部条件才共用：
  - 与新版字节相同；
  - 新版主包也在用；
  - 不读 `getApp` 的域名或登录态、不发请求、不写死 http 地址；
  - 依赖闭包也都能共用。
- 结果：共用 74 个单元（vant、部分 firstui、打印库、weui/common 样式等）。
- 例外：打印码表 `encoding-indexes.js` 在 08-27 从 518 KB 精简到 146 KB，保留了打印用的 gb18030，旧版直接用新的。
- 复制：112 个页面 + 54 个单元（rent/care/retail 组件、`utils/data.js`、`utils/util.js` 等）。

### 4.4 生成器的改写规则（`tools/legacy/build_legacy.py`）
- 路径：
  - 复制件的绝对路径加 `/legacy`；
  - 指向共用件的相对路径重新计算；
  - npm 组件名改成明确的绝对路径。
- `/pages/` 跳转全部改成 `/legacy/pages/`。
- `getApp()` → `__L`，也就是 `require` 到 `legacy/legacy_app.js`；页面的 `Page(` → `__L.Page(`。
- 蓝牙、`connectSocket`、键盘监听、`setInterval`、`setTimeout` 改成走 `__L.lwx` 记账。
- 只有 `/api/`、`/core/` 开头的地址改成 `mini.snowmeet.com`。
- 旧 `app.json` 的全局组件，按每个文件 wxml 实际用到的标签注入到该文件自己的 json。
- 旧版后台首页和首页顶部注入「返回新版」条。
- `app.json` 只做纯插入，可重复生成。

### 4.5 legacy_app.js
- 代替旧 `app.js`：
  - `globalData` 用演示域名；
  - 自己登录演示服务器，登录态只存在本模块；
  - 不写 storage，也不写 `domain.txt`。
- 不 require 任何文件（原先 require util.js 会循环依赖，改成内联一份 `performWebRequest`）。
- `Page` 包装：
  - 隐藏导航栏「回首页」按钮；
  - 只读检查新版登录信息里的管理员身份，不是管理员就 `reLaunch` 回新版首页。
- `exitToNew()`：释放旧版自己开的蓝牙、socket、定时器和监听，然后 `reLaunch` 回新版后台首页。

### 4.6 新版的改动
- 只有 3 处带标记的纯插入：
  - `app.json` 的 legacy 分包配置；
  - `pages/admin/admin.wxml` 和 `pages/admin/admin.js` 里 `legacy-demo begin`～`end` 之间的内容。
- 进入旧版用 `wx.reLaunch`，保证旧版运行期间没有新版页面同时存在。

### 4.7 验证
- `check_legacy.py` 全部通过：
  - 新版零改动：去掉插入后与 HEAD 逐字节相同；
  - 隔离：引用都能找到，没有指向新版其他分包的引用，没有 `getApp`、裸 `Page`、写 storage、未记账的资源调用；
  - 共用的单元新版都还在用。
- 估算 `legacy` 约 1271 KB；164 个 JS/WXS 用 node 16 解析，全部通过；小程序测试 194/194。
- 开发者工具编译时用户叫停：服务器还没搭好，测试暂缓。
- 剩下的工作写成 Copilot 待办：`docs/legacy-demo/2026-10-02-legacy-demo-todo.md`。

## 5. 5 月起的数据库结构变更

- 来源：`sql/` 下 34 个脚本 + 数据模型的改动 + 开发记录。整理结果：`docs/db/2026-10-02-schema-changes-since-0501.md`。
- 新建 25 张表、2 个视图；10 张旧表加了约 40 列；只有 1 列改了可空性（`ticket_template.available_days`）；没删过表或列（`product.shop` 的删除暂缓）。
- **约 22 列没有脚本存档**，例如：
  - `order.wechat_unverified`、`pay_with_deposit`；
  - `order_payment.is_proxy_pay`、`customer_open_date`；
  - `care` 的 4 列；
  - `ticket_template` 的 7 个海报字段；
  - `punch_card` 的装备列。

  照 `sql/` 目录重建库会缺这些列。
- 对旧版服务端来说这些改动都只是新增，演示服务器连当前库从结构上能跑。
- 生产库只读核对被 auto-mode 的「生产读取」规则拒绝；接着本地查文档里的执行记录也被拒。按规则停下，把只读 SQL 写进清单第八节，交给用户。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [`tools/legacy/legacy_lib.py`](../tools/legacy/legacy_lib.py) | 依赖遍历，判定复制还是共用 |
| [`tools/legacy/build_legacy.py`](../tools/legacy/build_legacy.py) | 生成 `legacy/`，插入 `app.json` |
| [`tools/legacy/legacy_app.template.js`](../tools/legacy/legacy_app.template.js) | 旧版独立 App、资源记账、管理员拦截 |
| [`tools/legacy/check_legacy.py`](../tools/legacy/check_legacy.py) | 零改动、隔离、体积检查；`--removed` |
| [`docs/legacy-demo/2026-10-02-legacy-demo-todo.md`](../docs/legacy-demo/2026-10-02-legacy-demo-todo.md) | 交给 Copilot 的待办和红线 |
| [`docs/db/2026-10-02-schema-changes-since-0501.md`](../docs/db/2026-10-02-schema-changes-since-0501.md) | 5 月起的库结构变更清单 |
| `snowmeet_wechat_mini/legacy/`（635 个文件，未提交） | 生成的旧版演示 |
| `snowmeet_wechat_mini/app.json`、`pages/admin/admin.{wxml,js}`（未提交） | 3 处带标记的插入 |
| [`.claude/skills/start-work/SKILL.md`](../.claude/skills/start-work/SKILL.md) | 补 reqai 的 Windows 路径、22 端口超时的处理 |

## 学到的小知识

1. **Edit 工具会去掉行尾空格**：在有行尾空格的行附近插入内容，原行会被改动。凡要求「纯插入、逐字节还原」的，必须用 HEAD 逐字节比对来兜底。
2. **共用要看单元和依赖闭包**：组件的 js 读 `getApp()`，同名的 wxml/json 看起来无害，按文件判断会误判成可共用。
3. **小程序的全局资源是 App 级的**：WebSocket 同时最多 5 个、蓝牙连接、`onKeyboardHeightChange`、定时器在页面销毁后仍会留着，旁路功能退出时必须逐项释放。
4. **「回首页」按钮会绕过退出清理**：用 `reLaunch` 进入的页面没有返回栈，导航栏会出现回首页按钮，要在 `onShow` 里 `hideHomeButton`。
5. **对旧代码来说，库结构变更是否兼容看三点**：新列要可空或带默认值；没删旧代码用到的列；旧模型没映射被改类型的列。三条都满足，旧服务端就能直接连新库。
