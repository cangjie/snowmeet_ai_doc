# 2026-07-25 次卡/季卡商品维护 admin 功能：从零设计到实现，途中修正编码规则和 UI 风格

按时间线整理。这场会话从 `/start-work` 开始，核心任务是给微信小程序 admin 后台新增一个「养护/租赁 次卡·季卡 商品维护」功能，落在 `SnowmeetApi` 和 `snowmeet_wechat_mini` 两个代码仓，用 plan mode 走完整流程后实现，中途根据用户反馈做了两轮修正。

## 1. 需求与调研

### 1.1 原始需求

用户提出：小程序 admin 目录下增加商品维护功能，维护 `product` 表及附属表，只需要覆盖养护和租赁的次卡、季卡。次卡要有 名称/价格/图片/简介/次数；季卡不需要次数这一项。需要列表页 + 详情维护页两个页面。

### 1.2 调研关键发现（两个并行 Explore agent + 手动深挖）

- 现有 `pages/admin/rent/punchcard_products` 是 2026-07-22「租赁次卡销售」功能的配套管理页：弹层表单，只有 名称/价格/次数/店铺/上下架，**无图片、无简介、只支持租赁一种业务类型**。
- `Product`（表 `product`）已有次卡所需字段：`name`/`sale_price`/`punch_total`（仅次卡有意义）/`content`（自由文本）/`category_code`（关联 `category.code`，次卡权威识别方式）/`images: List<ProductImage>`。**季卡在 `Product`/`Category` 这一层完全没有先例**——`ResolveNextCardCategoryCode`（`RentController.cs`）硬编码只找 `biz_type=="租赁" && name=="次卡"`。
- **两套完全不同的"分类"体系容易混淆**：`Category`（表 `category`，扁平，`biz_type`+`code`+`name`）是 `Product` 用的；`RentCategory`（`Rent/GetAllCategories` 那一套，两位数字前缀拼接的层级树 + 押金/价格矩阵）是 `RentProduct`（物理租赁装备目录，`pages/admin/rent/settings/rent_product*`）专用，两者字段/语义互不相通。
- **没有可用的「分类管理」页面**能让管理员自己建 `category` 行——`CategoryController.AddNewCategory` 对非「餐饮」类目永远把 `code` 写 `null`，前端也没有页面调用它。
- 图片上传 + 富文本简介编辑的现成交互模式在 `pages/admin/rent/settings/rent_product.wxml`/`.js`：`<multi-uploader>` 组件 + 原生 `<editor>` 组件（虽然挂在 `RentProduct` 模型上，跟我们要用的 `Product` 不是一回事，但 UI 交互可以照搬）。
- `Category/AddProduct`、`Category/ModProduct`、`Category/GetProduct/{id}`（`CategoryController.cs`）已是通用 Product CRUD，可直接复用；`ProductImage.image_url` 可以直接存 `UploadFile/Upload/{sessionKey}` 返回的完整 URL，不需要走 `upload_id` 关联。

## 2. 方案设计与用户确认

用两轮 `AskUserQuestion` 确认了两个关键分歧点：
1. 是否整合旧的 `punchcard_products` 页面？→ 用户选整合，并追加要求：**图片上传 + 简介富文本编辑**是硬需求。
2. 新功能在 admin 菜单放哪？→ 用户要求**完全不改动菜单**，沿用现有单一入口。

据此写了 plan（`.claude/plans/admin-product-ticklish-meerkat.md`，本机路径，不在 doc 仓同步范围），核心设计：
- 没有分类管理页面这个缺口，用**后端自动建分类兜底**解决：管理员首次为某个 业务类型+卡类型 组合建商品时，找不到对应 `category` 行就自动创建（避免要求用户先手工跑 SQL）。
- 顾客侧购买流程（`Rent/GetPunchCardProducts`、`pages/mine/punchcard/*`）明确排除在改动范围外，行为保持不变（仍只认 租赁+次卡）。

用户批准后进入实现。

## 3. 实现

### 3.1 后端（`SnowmeetApi/Controllers/RentController.cs`）

- `ResolveNextCardCategoryCode(bizType)` 重构为通用 `ResolveCardCategoryCode(bizType, cardType, createIfMissing, staffId)`：先按 `biz_type+name+valid==1` 查找；找不到且 `createIfMissing` 才自动建（写 `CoreDataModLog`）；顾客侧只读路径 `createIfMissing=false`，行为不变。
- `GetAllPunchCardProducts` 加 `bizType`/`cardType` 可选参数：都不传时遍历 养护/租赁 × 次卡/季卡 4 种组合合并返回，每行带 `bizType`/`cardType`/`imageUrl`。
- `GetPunchCardCategoryCode` 加同样两个参数，`createIfMissing=true`——这是唯一允许自动建分类的入口。
- 两轮 `dotnet build` 均 0 错误。

### 3.2 前端（`snowmeet_wechat_mini`）

- `components/uploader/multi-uploader.wxml`：修了一个潜伏 bug——`image_count` prop 声明了但 `max-count` 硬编码 `"3"` 从没绑定过，改成 `max-count="{{image_count}}"`。
- `utils/data.js`：`getAllPunchCardProductsPromise`/`getPunchCardCategoryCodePromise` 加可选 `bizType`/`cardType`；新增 `getProductPromise`（`Category/GetProduct/{id}`，之前没有 wrapper）。
- `pages/admin/rent/punchcard_products/punchcard_products.{js,wxml,wxss}`：列表页原地改造，去掉弹层，加筛选 chip（业务类型×卡类型）、缩略图、"不限次数"文案，新增/编辑改为跳转详情页；新增入口做成 4 个「+ 养护次卡/养护季卡/租赁次卡/租赁季卡」按钮。
- 新增 `pages/admin/rent/punchcard_products/punchcard_product_detail/`：双模式（新建/编辑）详情页，图片走 `multi-uploader`（单图），简介走原生 `<editor>` + 简易工具栏。
- `app.json` 加新页面路由；admin 菜单（`admin.wxml`/`.js`）按用户要求**完全没碰**。
- 所有新建/改动的 `.js` 用微信开发者工具自带 node `--check` 过了语法；JSON 用 PowerShell `ConvertFrom-Json` 校验（第一次因为没加 `-Encoding UTF8` 读中文乱码导致 `app.json` 假报错，加上编码参数后确认真的没问题）。

## 4. 用户反馈修正一：生产库分类编码规则

用户直接给出生产库事实：`category` 表 id 15/17/18 无效；租赁次卡 code=`0101`、养护次卡 code=`0201`、养护季卡 code=`0202`。

- 复盘判断：15/17/18 应该就是本功能开发早期版本用英文 token（`RENT_PUNCH`/`CARE_PUNCH`/`CARE_SEASON`）自动建出来的坏数据，用户手工建好数字编码版本后把旧的作废。
- 查找逻辑本身不用改（按 `biz_type+name+valid` 匹配，不关心 code 具体值，自动会捡到用户手建的 `0101` 等）。
- 改的是自动建分类的兜底逻辑：编码规则从英文 token 换成两位数字对——租赁=`01`/养护=`02`，次卡=`01`/季卡=`02`，拼接后与用户已建的三条完全对齐。未建的「租赁季卡」以后自动创建会得到 `0102`，同规则续号。
- 重新 build 通过。

## 5. 用户反馈修正二：详情页 UI 问题（DevTools 截图）

用户截图反馈两个问题：
1. 顶部「类型」字段显示 `%E7%A7%9F%E8%B5%81...` 原始 URL 编码乱码。
2. 页面整体风格是"旧的"，跟项目里"目前新设计的页面风格"不一致。

排查与修复：
- **乱码根因**：`wx.navigateTo` 的 query 不会自动 `decodeURIComponent`。列表页拼 URL 时对业务类型/卡类型做了 `encodeURIComponent`，详情页 `onLoad` 却没有对应解码，导致原样展示。补上 `decodeURIComponent`。
- **风格问题**：详情页最初照抄 `rent_product.wxml` 用的 WeUI `mp-cells`/`mp-cell` 老式列表样式。改成参照 `pages/admin/fnb/mat_expire_detail` 的现代卡片式设计（`.header`/`.section`/`.fgroup`/`.finput` + 底部固定"取消/保存"按钮条，配色 `#006495` 主色/`#f8f9ff` 背景），彻底去掉 `mp-cells` 依赖。
- 重新语法检查 + JSON 校验通过。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `SnowmeetApi/Controllers/RentController.cs` | `ResolveCardCategoryCode` 泛化（含数字编码兜底）、`GetAllPunchCardProducts`/`GetPunchCardCategoryCode` 加参数 |
| `snowmeet_wechat_mini/pages/admin/rent/punchcard_products/punchcard_products.{js,wxml,wxss}` | 列表页原地改造：筛选、缩略图、跳转详情页 |
| `snowmeet_wechat_mini/pages/admin/rent/punchcard_products/punchcard_product_detail/*` | 新增详情维护页（新建/编辑双模式），现代卡片式样式 |
| `snowmeet_wechat_mini/components/uploader/multi-uploader.wxml` | 修 `max-count` 未绑定 `image_count` 的 bug |
| `snowmeet_wechat_mini/utils/data.js` | 3 处 wrapper 改动/新增 |
| `snowmeet_wechat_mini/app.json` | 新页面路由注册 |

## 学到的小知识

1. **`Category` vs `RentCategory` 是两套完全独立的分类体系**：前者扁平表给通用商品目录用，后者是带押金/价格矩阵的层级树给物理租赁装备用，字段名都不一样，千万别搭错。
2. **没有分类管理页面时，"首次使用时自动建分类"是比"要求用户先手工建"更好的兜底策略**——但生成的 code 格式最好提前跟用户对齐既有规则，否则会像本次一样先建出一批格式不对的脏数据，用户还得手工清理。
3. **`wx.navigateTo` 的 query 不会自动解码**，`encodeURIComponent` 过的中文参数必须在 `onLoad` 里手动 `decodeURIComponent`，否则页面上直接显示乱码。
4. **PowerShell `Get-Content -Raw` 默认编码在这台机器上会把中文读成乱码**，验证含中文的 JSON 文件务必加 `-Encoding UTF8`，否则会得到误报的"JSON 语法错误"。
5. **生产库直连（pyodbc）这次被 auto-mode 权限分类器直接拦了**，即使是只读 SELECT。以后要确认生产库实际状态，直接问用户比较可靠。
