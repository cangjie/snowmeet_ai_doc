# 2026-09-23 食材管理：小程序客户端实现 + codex 服务端接口验证

本场接续 09-22 的食材管理服务端交接（codex 实现，`ai@9ee8fd9`）。用户给出 Claude Design 的需求 deck 和原型，要求 Claude 做三件事：「第一，给出你对于需求的理解；第二，验证 codex 开发的服务器端接口是否可用；第三，实现小程序的客户端。」

改动落在三处：`snowmeet_wechat_mini/pages/fnbinv/`（新分包）、`SnowmeetApi`（两个菜品接口和测试）、`snowmeet_ai_doc`（验证报告、修正 SQL、本归档）。

## 1. 需求资料与理解

### 1.1 资料来源

- Claude Design 链接打不开：DesignSync 只限 `/design-sync` 流程使用。
- 本机 `~/Downloads/mat/` 有 09-19 的导出版：`食材管理系统 Deck.dc.html`（18 页）和 `食材管理.dc.html`（10 屏、8 tab 的单页原型，含完整状态逻辑和样本数据）。
- 同目录的 `CLAUDE.md` 规定，新客户端沿用「我的X」系列的 token：`pages/mine/ticket/ticket_card.wxss`，底色 #F0F2F7、主蓝 #2563EB、卡片圆角 18px、胶囊按钮。

### 1.2 需求要点

- 两级分类：二级分类决定储存方式、保质期（储存方式 × 生产月份，6–9 月为高温档）、临期阈值和计量方式。
- 入库八步：分类 → 名称 → 拍照（必填）→ 批次号 → 储存 → 日期（三项独立，可 OCR）→ 包装 → 数量。
- 封装须先开封（一次一件）才可用；散装入库即可用。
- 核销五链路：入库、开封、制作、出餐（FEFO，欠料不扣负）、销毁 / 报损 / 盘点。
- 临期三档：已过期、开封后临期、未开封临期；已过期批次进销毁清单逐批确认。

### 1.3 以 09-21/22 用户决定覆盖原型

- 出餐：原型是订单系统推单，改为员工手动建厨房单。
- 菜品：原型有多规格（大份），改为一菜一份「标准份」；出餐时不做现场微调。
- 企业微信 H5、外卖平台都后置。

## 2. 规划阶段的用户拍板（第一轮）

| 问题 | 决定 |
|---|---|
| 没有「本店菜品列表」接口 | Claude 补一个只读的 `FnbRecipe/ListDishes` |
| 看板的损耗率、周转没有数据来源 | 首版不做 |
| 入库接口必须传单价，原型里没有 | 所有人可见，选填，留空按 0 |
| 写入类接口在哪里验证 | 本地隔离库 + 生产只读 |

## 3. 服务端验证

### 3.1 生产只读核对（发现阻塞）

- 生产 API 主机 161.189.64.210:443：本机超时，关闭沙箱后同样超时，**部署状态无法核实**。
- 生产库 SELECT（本机需 `ODBCSYSINI=/usr/local/Cellar/unixodbc/2.3.4/etc` + Driver 13）：
  - `fnb_unit` 5 行正确；食材新表全部为空；
  - 餐饮商品 7 个（咖啡、果汁饮品），`shop_id` 为 45855/45862/45863，都不在 `shop_list`（1/3/4/5/9/10/11）；
  - 在职员工 29 人，25 人 `base_shop_id` 为空。
- 结论：按 `FnbAccess.CanAccess`（`base_shop_id == shopId`），几乎没人能用；也没有员工能建厨房单。

### 3.2 用户拍板（第二轮）

- 餐厅门店：「新建一个"多呆一会儿吧"，但是目前仅仅这一家餐饮业务的门店，门店名称完全可以不用在界面上体现」。
- 权限：改数据，不改代码。
- 菜品来源：配方页让店长建菜品，即新增 `SaveDish`。
- 修正脚本：[sql/2026-09-23_fnb_restaurant_shop.sql](../sql/2026-09-23_fnb_restaurant_shop.sql)。
  - 新门店：sale/care/rent=0，restuarant=1，sort=900，code `DDY`；
  - 员工 id 待用户填写。

### 3.3 新增服务端代码（按 TDD）

- [`Services/Fnb/FnbDishService.cs`](../../SnowmeetApi/Services/Fnb/FnbDishService.cs)：
  - `ListAsync`：本店有效、未隐藏、有效餐饮分类下的商品，带默认规格、已发布版本、草稿号；
  - `SaveAsync`：按 `categoryName` 找或建餐饮分类；新建菜品时自动建「标准份」；只能改本店菜品。
- [`FnbRecipeController`](../../SnowmeetApi/Controllers/Fnb/FnbRecipeController.cs)：`ListDishes`（员工）、`SaveDish`（店长）。
- 先放一个抛 `NotImplementedException` 的空壳看到 2 条集成测试失败，再实现到通过。全量结果：集成 8/8，单元 344 过、8 跳过。

### 3.4 HTTP 全链路冒烟

- 新增 [`run_fnb_http_smoke.py`](../../SnowmeetApi/SnowmeetApi.Tests/run_fnb_http_smoke.py)：
  - 复用集成运行器的隔离库 bootstrap，再复制会话相关 5 张表的结构；
  - 灌入 3 名员工（同店 200、同店 100、他店 300）和真实格式的 `mini_session`；
  - 本地用临时 `config.sqlServer` 和复制过去的 appsettings 启动 API，用 HTTP 跑 11 组场景。
- 第 1 轮「旧接口保护」是**假通过**：临时目录缺 appsettings，`FnbMaterialController` 构造时就 NRE 500，而断言只写了 `code != 0`。修脚本并收紧断言后，第 2 轮是真通过。
- 最终 80 项：77 过，3 败（两轮稳定复现）：
  1. 已过期批次能入库（`FnbReceiptRules` 不校验到期日）；
  2. 10 个并行 `PostServe` 出现 500：死锁 1205，裸 `SqlException`；
  3. 同一 requestId 并行 `PostReceipt` 出现 500：死锁被 EF 包成 transient `InvalidOperationException`，`PostReceipt` 没有捕获。
- 数据始终一致：只生成 1 张单，库存不为负，重试成功。按计划只报告，不修。
- 报告：[2026-09-23-fnb-inventory-api-verification.md](../docs/superpowers/plans/2026-09-23-fnb-inventory-api-verification.md)。

## 4. 小程序客户端

### 4.1 结构

- 分包 `pages/fnbinv`（避免撑大主包），每页一个目录；底部 `fnb-tabbar` 用 redirectTo 切换，写法仿 `reception_tabbar`。
- 页面：stock、expiry、destroy、batch、inbound、cats、prep、recipe、serve、count、dash。
- 组件：fnb-tabbar、qty-stepper（`miniprogram_npm` 里没有 van-stepper）、photo-field（复用 `FnbMaterial/UploadPhoto`，用途「食材批次」）。
- 复用：`ocr_scan_layer`、`print_food_label`、`date-range-picker`（single 模式）、van-popup、van-uploader。
- 门店：取 `staff.base_shop_id`；未绑定时整页提示原因，不显示门店名。

### 4.2 common 纯函数模块（全部先写测试）

- `api.js`：自包 `wx.request`，保留 code；500、断网、code 4 标记为可重试；`getAll` 分页取全。
- `request-id.js`：同一动作失败重试沿用 requestId，成功后换新号。
- `units.js`：g/ml/piece 满 1000 显示为 kg/L；小数位按原型口径（小于 0.1 才保留 3 位）。
- `expiry.js`：与服务端同口径（月末截断）；三档临期分组；逐月规则归纳成「全年 / 分档」，保存时只写有变化的月份。
- `forms.js`：
  - 入库请求体按四种效期来源（package / manual / category / estimated）构造；
  - 前端拦截已过期批次、生产日期晚于到期日期；
  - `nextBatchNo` 递增避让同号。
- `stock-view.js`、`catalog.js`、`recipe.js`、`kitchen.js`、`stocktake.js`、`dash.js`：各页的视图模型。

### 4.3 页面冒烟与修掉的 bug

- [`tests/fnbinv_pages.test.js`](../../snowmeet_wechat_mini/tests/fnbinv_pages.test.js)：假后端 + 假 wx，11 页逐页 onLoad，并测 9 条关键写操作。
- 抓出的真 bug：
  1. 库存页传给 `buildStockRows` 的键名是 `batches`，函数要的是 `rows`，**列表永远为空**；
  2. 制作页 `refresh()` 在改批数或储存方式时，会把手选的到期日冲掉。
- 自审修 1 处：生产日期晚于到期日期要在加入入库单前拦下。
- 全量 `npm test` 113/113。静态检查（`node --check`、JSON、WXML 配对、组件路径、分包文件）0 问题。

### 4.4 入口

- [`admin.wxml`](../../snowmeet_wechat_mini/pages/admin/admin.wxml) / `admin.js`：「【餐饮】食材过期提醒」改为「【餐饮】食材管理」，指向 `/pages/fnbinv/stock/stock`。
- [`mat_expire_detail.js`](../../snowmeet_wechat_mini/pages/admin/fnb/mat_expire_detail/mat_expire_detail.js)：扫码进入（`options.q`）时 redirect 到新批次页，不用改公众平台的二维码规则。

## 5. 收尾状态

- 最终整体审查：审查子代理触发会话额度上限（429），改为作者自审，并已如实告知用户。
- 用户问「现在我人工可以开始测试了吗？」。答复：还差执行 SQL 和部署 API，另外人工测试是在生产库上进行，会留下数据。
- 用户表示会先完成这两步；Claude 提醒，如果服务器靠 git pull 更新，要先让 Claude 提交并推送。
- 两个业务仓都未提交。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Services/Fnb/FnbDishService.cs` | 新增：菜品列表与保存 |
| `SnowmeetApi/Controllers/Fnb/FnbRecipeController.cs` | 新增 `ListDishes`、`SaveDish` |
| `SnowmeetApi/SnowmeetApi.Tests/FnbSqlServerIntegrationTests.cs` | 新增 2 条 `SaveDish*` 用例 |
| `SnowmeetApi/SnowmeetApi.Tests/run_fnb_http_smoke.py` | 新增 HTTP 全链路冒烟运行器 |
| `snowmeet_wechat_mini/pages/fnbinv/**` | 新分包：11 页 + 3 组件 + common 模块 |
| `snowmeet_wechat_mini/tests/fnbinv_*.test.js` | 8 个测试文件，67 条 |
| `snowmeet_wechat_mini/app.json` | 注册 `fnbinv` 分包 |
| `snowmeet_wechat_mini/pages/admin/admin.{js,wxml}` | 菜单入口 |
| `snowmeet_wechat_mini/pages/admin/fnb/mat_expire_detail/mat_expire_detail.js` | 扫码转新批次页 |
| `snowmeet_ai_doc/sql/2026-09-23_fnb_restaurant_shop.sql` | 门店与员工绑定修正（待用户执行） |
| `snowmeet_ai_doc/docs/superpowers/plans/2026-09-23-fnb-inventory-api-verification.md` | 接口验证报告 |
| `snowmeet_ai_doc/docs/superpowers/plans/2026-09-22-fnb-inventory-api-contract.md` | 补 ListDishes / SaveDish |

## 学到的小知识

1. **测试通过要看断言本身有没有意义**：`code != 0` 对 HTTP 500 也成立。第 1 轮的「旧接口保护」其实是本地缺配置文件导致的 500，断言要同时锁定 HTTP 状态和业务 code / 消息。
2. **SQL Server 死锁的两种外形**：裸 `SqlException(1205)`，或被 EF 包成「transient failure」的 `InvalidOperationException`（内层是 `DbUpdateException`）。只 catch 其中一种，另一种就会变成 500。
3. **纯函数测试覆盖不到胶水层**：参数名写错（`batches` 与 `rows`）这种 bug，要靠页面级冒烟（捕获 `Page()` 定义、假 setData、假后端）才能抓到。
4. **ASP.NET Web 默认 JSON 允许从字符串读数字**：BIGINT id 以字符串回传（如 `recipeId: "21"`）可以正常绑定，冒烟已验证。
5. **`GenBatchNo` 按已落库批次计数**：同一次会话里连发会拿到同号，客户端必须自己避让。
