# 2026-10-21 零售开单迁移 + iPhone 顶栏返回键修复：小程序两项改动，后端零改动（Windows 机）

本次会话先执行 start-work，然后做了两件事：把零售开单迁到新版接待流程，并修复 iPhone 上自定义顶栏的返回键被状态栏挡住的问题。改动都在 `snowmeet_wechat_mini`，用户已自己提交并推送（`be14ac8d retail`、`a2515491 safe area`）。另外改了文档仓的旧版演示生成器和检查器。

## 1. 零售开单迁移

### 1.1 用户决定

- 原话：「零售开单流程一直没有迁移过来，现在先迁移一下。」
- 订单类型保留原来的 6 项，其中「养护卡类」「租赁卡类」先置灰、不能选。
- 不存草稿：零售单在点「去结算」时才下单。
- 一单只有一件商品。
- 零售订单详情页一起重做。

### 1.2 实现

- 新增 [utils/retail.js](../../snowmeet_wechat_mini/utils/retail.js)，内容包括：
  - 6 种类型，其中两种卡类为禁用状态；
  - 七色米单号的处理：去掉首尾空格、转大写、校验。校验规则照抄后端 `Util.IsValidMi7Code`：以 XSD 开头，15 位且以 I/A 结尾，或 14 位且不以 I/A 结尾；
  - 卡类禁用时的提示文案。
- 新增组件 [retail_recept_form](../../snowmeet_wechat_mini/components/reception/retail_recept_form/retail_recept_form.js)：
  - 字段：金额、紧急开单、七色米单号（失焦时查重，也可以扫码）、订单类型、招待、放弃龙珠、备注、照片；
  - 只有会员并且已关注公众号时，才能积龙珠；
  - 「去结算」按钮不禁用。点击时如果有缺项，按缺项逐条提示。
- [recept_new](../../snowmeet_wechat_mini/pages/admin/reception/recept_new.js) 新增 `onRetailCheckout`：
  - 调 `Order/PlaceOrder` 下单，招待单的金额为 0；
  - 下单成功后跳到结算页，并重置表单；
  - 加了防止重复提交的保护。
- 结算页支付完成后，零售单跳到零售订单详情页。
- [order-summary-card](../../snowmeet_wechat_mini/components/order-summary-card/index.js) 新增零售内容展示：七色米单号、类型、是否招待。紧急开单还没有单号时，显示「紧急开单（待补单号）」。
- [retail_order_detail](../../snowmeet_wechat_mini/pages/admin/retail/retail_order_detail.js) 原地重写，页面分四块：
  - 订单信息；
  - 顾客信息：可以修改，走 `UpdateOrderByStaff`；
  - 零售内容：可以修改，走 `UpdateOrderWithDetailByStaff`。可以补填七色米单号，查重时排除本单自己；金额只有未支付、且不是招待单时才能改；
  - 支付信息：有「去收款 / 去确认生效」按钮。

### 1.3 后端

- 用户问：「服务器端，是否有改动？」回答：没有。复用的都是已有接口。

## 2. iPhone 顶栏返回键与状态栏时间重叠

### 2.1 原因

- 用户原话：「苹果手机，貌似所有的后退按钮和时间是重叠的，因此后退不生效。检查下目前小程序的所有页面，不能再发生此类问题！」
- 页面 json 设了 `navigationStyle: custom`，关掉了系统导航栏，页面自己画了一个固定在顶部的顶栏，但没有让出状态栏的高度。
- iPhone 上状态栏区域不响应点击，所以返回键点了没反应。

### 2.2 全量检查

- 检查了 app.json 注册的全部页面，包括主包、分包和 legacy。关掉系统导航栏的共 6 页：
  - 主包 4 页：开单入口、开单页、选择套餐、万龙雪票预定；
  - 旧版演示 2 页：`legacy/pages/ski_pass/skipass_detail_new`、`legacy/pages/claude/index`。
- app.json 的全局 window 没有关掉系统导航栏。

### 2.3 修复

- 新增 [utils/navbar.js](../../snowmeet_wechat_mini/utils/navbar.js) 的 `getNavMetrics()`：
  - 顶栏高度按胶囊按钮位置计算：`(menu.top - statusBarHeight) * 2 + menu.height`；
  - 取不到胶囊位置时用 44/95 兜底，这种结果不缓存。
- 新增组件 [safe_nav_bar](../../snowmeet_wechat_mini/components/safe_nav_bar/safe_nav_bar.js)：
  - 顶栏固定在顶部，先让出状态栏高度；
  - 左侧放 44px 宽的返回热区，右侧留出胶囊按钮的宽度；
  - 默认在原位放一个同高的占位块，页面内容自然排在顶栏下面。
- 返回逻辑：
  - 有上一页时 `navigateBack`；
  - 只有一页时（比如从分享或扫码直接打开）`reLaunch` 到 `homeUrl`；
  - `autoBack=false` 时只触发 `back` 事件，由页面自己处理。
- 4 个主包页面都换成这个组件，删掉原来自己画的顶栏和对应样式。
- 雪票预定页的内容在整页 scroll-view 里，所以关掉占位块，改为在 `onLoad` 里用 `getNavMetrics().totalHeight` 设置上边距。
- 删掉雪票预定页右上角的「⋯」占位按钮。它点了什么都不做，而且位置正好被胶囊按钮占着。
- 旧版页面是生成的代码，不能手改。处理方式：
  - 改生成器 [build_legacy.py](../tools/legacy/build_legacy.py) 的 `json_()`，以后生成时去掉页面 json 里的 `navigationStyle: custom`，用回系统导航栏；
  - 两个现有页面的 json 用生成器对这两个文件的输出写回。核对过，差异只有删掉的这一行；
  - [check_legacy.py](../tools/legacy/check_legacy.py) 加了一项检查：旧版页面不能用 `navigationStyle: custom`。

### 2.4 回归测试

- 新增 [tests/custom_nav_safe_area.test.js](../../snowmeet_wechat_mini/tests/custom_nav_safe_area.test.js)：
  - app.json 全局 window 不能关掉系统导航栏；
  - 每个关掉系统导航栏的注册页面，必须在 json 里注册 safe-nav-bar，wxml 里也要真的用到（去掉注释后再查）；
  - 测了顶栏高度的计算，以及取不到胶囊位置时的兜底；
  - 测了三种返回情况：有上一页、只有一页、`autoBack=false`。
- 反向验证：删掉一个页面的 `<safe-nav-bar>`，测试立即失败，并指出是哪个页面。
- 第一版测试里有一项专门检查 legacy。但 check_legacy.py 不允许新版代码出现带引号或斜杠的 `legacy/` 路径字样，所以删掉了这一项。旧版页面已经被通用检查覆盖。
- 全部测试 203/203 通过。

### 2.5 和本次无关的问题：旧版演示缺返回条

- `check_legacy.py` 报了 110 个旧版页面缺少「返回新版」横幅。
- 原因：现在的 `legacy/` 是 10-02 改生成器之前的产物。新生成器会给全部页面加横幅，但没有重新生成过。
- 重新生成会改动约 118 个文件，还会删掉用户后来加回的 8 个空 JSON/WXSS 文件，所以这次没有动。
- 检查器的「legacy/ 以外有其他改动」是因为当时工作区里有未提交的改动，不是问题。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| `snowmeet_wechat_mini/utils/retail.js` | 新建：零售类型、七色米单号校验 |
| `snowmeet_wechat_mini/components/reception/retail_recept_form/` | 新建：零售开单表单 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_new.*` | 接入零售表单与下单；改用 safe-nav-bar |
| `snowmeet_wechat_mini/pages/admin/retail/retail_order_detail.*` | 零售详情页重写 |
| `snowmeet_wechat_mini/components/order-summary-card/` | 加零售内容展示 |
| `snowmeet_wechat_mini/pages/payment/settle/index.js` | 零售单支付完成后跳零售详情 |
| `snowmeet_wechat_mini/utils/navbar.js` | 新建：状态栏与胶囊尺寸计算 |
| `snowmeet_wechat_mini/components/safe_nav_bar/` | 新建：带安全区的自定义顶栏 |
| `snowmeet_wechat_mini/pages/admin/reception/recept_entry.*`、`recept_package.*` | 改用 safe-nav-bar |
| `snowmeet_wechat_mini/pages/ski_pass/skipass_detail_new.*` | 改用 safe-nav-bar，删「⋯」 |
| `snowmeet_wechat_mini/legacy/pages/{ski_pass/skipass_detail_new,claude/index}.json` | 去掉 custom（按生成器输出写回） |
| `snowmeet_wechat_mini/tests/custom_nav_safe_area.test.js` | 新建：回归测试 |
| `snowmeet_ai_doc/tools/legacy/build_legacy.py` | 生成时去掉旧版页面的 custom |
| `snowmeet_ai_doc/tools/legacy/check_legacy.py` | 加旧版页面不能用 custom 的检查 |

## 学到的小知识

1. **只要关掉系统导航栏，页面就必须自己处理状态栏**：iPhone 状态栏区域不响应点击。高度要按胶囊按钮位置算，不能写死 rpx。
2. **从分享或扫码进入时，页面栈只有一页**：这时 `navigateBack` 会静默失败，返回键要改成 `reLaunch` 到首页。
3. **生成的代码不要手改**：要改生成器，再用生成器的输出写回需要改的文件，并核对差异只有预期的那一行。这样既不违反「不要手改」，也不会把旧版没提交的整批改动一起带出来。
4. **check_legacy.py 会扫描新版代码里带引号或斜杠的 `legacy/` 字样**：测试和工具文件也在扫描范围内，写新代码时不要出现这种路径字样。
5. **这台 Windows 机跑小程序测试的方法**：用 Codex 运行时自带的 node（`C:\Users\cangj\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`），在小程序目录下执行 `--test --test-isolation=none --test-reporter=tap tests/*.test.js`。不加 isolation 参数会报 IPC deserialize 错误。微信开发者工具自带的 node 在这台机器上不存在。
6. **用户会在会话中途自己提交**：收尾前要重新查一次 `git status` 和 `git log`，不要按会话开始时的状态汇报。
