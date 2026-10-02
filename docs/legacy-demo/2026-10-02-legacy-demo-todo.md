# 旧版演示（legacy 分包）待办清单

2026-10-02 整理。代码已由 Claude 生成，还没有提交。下面是剩下的工作，分两类：**【负责人】** 要人工在平台上操作；**【Copilot】** 交给 VS Code Copilot 执行。

## 交给 Copilot 的启动指令（复制下面整段）

> 请完成 Snowmeet 小程序「旧版演示」分包的验证与收尾。工作区是 `D:\source\snowmeet\ai`。先完整阅读本文件 `snowmeet_ai_doc/docs/legacy-demo/2026-10-02-legacy-demo-todo.md`，以及 `snowmeet_ai_doc/tools/legacy/` 下 4 个文件开头的说明。按本文件「Copilot 待办」逐项执行。每完成一项就在本文件里勾选，并在「执行记录」里写上结果、数字和截图路径。遇到【负责人】项还没完成而无法继续的，标记 BLOCKED，然后接着做能做的项。必须遵守「红线」；不确定的地方记录下来问负责人，不要自行改业务代码，也不要提交、推送或上传。

## 背景（Copilot 必读）

- **目标**：最新版小程序（`snowmeet_wechat_mini`，`ai` 分支）里加了「旧版演示」。旧版是 `origin/master` 的最后一次提交 `584b9466`（2026-03-30），用来对比新旧功能。
  - 旧版独立运行，接口、上传、WebSocket 都连 `mini.snowmeet.com`（演示服务器，负责人另行搭建）。
  - 图片显示地址 `snowmeet.wanlonghuaxue.com`、公众号二维码服务 `wxoa.snowmeet.top`、二维码内容里的 `mini.snowmeet.top/mapp/...` 按负责人的决定保持原样。
- **最高要求：现有新版不能受任何影响。**
  - 新版只有 3 处纯插入：
    - `app.json`：`subPackages` 末尾 `root` 为 `legacy` 的那一块；
    - `pages/admin/admin.wxml` 和 `pages/admin/admin.js`：`legacy-demo begin` 与 `legacy-demo end` 之间的内容。
  - 把这 3 处去掉后，新版和原来逐字节相同。
- **入口**：新版后台首页「【演示】进入旧版」，只有管理员可见（`title_level > 200`）。点击后 `wx.reLaunch('/legacy/pages/admin/admin')`。
  - 旧版后台首页和旧版首页顶部各有一条「【演示】当前为旧版，点此返回新版」，点击后释放旧版占用的资源，再 `reLaunch` 回新版后台首页。
- **`snowmeet_wechat_mini/legacy/` 是生成出来的（635 个文件、112 个页面），不要手改。**
  - 生成器：`snowmeet_ai_doc/tools/legacy/build_legacy.py`。
  - 旧版的「App」：`legacy/legacy_app.js`，模板是 `tools/legacy/legacy_app.template.js`。
  - 旧版有 74 个单元直接共用新版主包的文件（vant、部分 firstui、打印库、weui/common 样式等），只读引用。
- **检查器**：`snowmeet_ai_doc/tools/legacy/check_legacy.py`。检查新版零改动、`legacy/` 隔离、共用单元仍被新版使用，并输出估算体积。
- **2026-10-02 生成时的基线**：
  - 检查器全部通过；
  - 估算体积：主包 1808 KB → 1812 KB，`legacy` 约 1271 KB；
  - 旧版 164 个 JS/WXS 语法检查通过；
  - 新版测试 194/194。

## 本机命令（Windows）

| 用途 | 命令 |
|---|---|
| Python | 用 `py`，不要用 `python`（那是应用商店的占位程序） |
| 检查器 | `cd snowmeet_ai_doc/tools/legacy; py check_legacy.py`；删除旧版后用 `py check_legacy.py --removed` |
| 重新生成 | `cd snowmeet_ai_doc/tools/legacy; py build_legacy.py`（会删掉并重建 `legacy/`，`app.json` 里的 legacy 块会原样替换） |
| 小程序测试 | 在 `snowmeet_wechat_mini` 目录用开发者工具自带的 node（node 不在 PATH，路径是 `C:\Program Files (x86)\Tencent\微信web开发者工具\node.exe`）运行 `snowmeet_ai_doc/tools/windows_test/run_tests.js tests/*.test.js`，基线 194/194 |

## 红线

1. 新版的文件，除了上面 3 处插入，一个字都不能改。共用的文件也不能改，例如 `components/firstui/*`、`miniprogram_npm/@vant/*`、`utils/ble_label_printer/*`、`weui.wxss`、`common.wxss`。也不要动 `sitemap.json`、`project.config.json`、`app.json` 的其他部分。
2. 不要手改 `legacy/`。要修就改 `tools/legacy/` 下的生成器或模板，重新生成，再跑 `check_legacy.py`，必须「全部通过」。
3. 不提交、不推送、不上传，也不点开发者工具的「上传」「预览」。这些都由负责人决定。
4. 演示里不要发起真实支付或退款，不要下雪票订单。旧服务端可能连着真实商户和自我游，会真扣款、真扣预存款。除非负责人确认演示服务器用的是沙箱配置。
5. 不要让顾客账号扫演示里生成的二维码。二维码内容保持原样，扫码后会在新版里按演示数据的订单号打开生产数据。
6. 不访问生产数据库。

## 【负责人】前置

- [ ] P1 部署演示服务器 `https://mini.snowmeet.com`。建议用 SnowmeetApi 的 `migrate_to_new_season` 分支（`9b4d35f1`，04-14），这是和旧小程序同一时期的服务端；SnowmeetApi 的 master 停在 2025-10-21，更老。需要 HTTPS、已备案、支持 `wss://mini.snowmeet.com/ws`。
- [ ] P2 演示服务器的数据库要有管理员员工数据，否则进旧版后台首页会显示「您不是管理员」。支付、雪票接口请改用沙箱或关闭。
- [ ] P3 小程序后台 → 开发管理 → 服务器域名：
  - request 合法域名、uploadFile 合法域名加 `https://mini.snowmeet.com`；
  - socket 合法域名加 `wss://mini.snowmeet.com`；
  - 如需 downloadFile 也一并加上。
- [ ] P4 Copilot 的 C1 通过后，把小程序仓库（`legacy/` 和 3 个文件）、文档仓库（`tools/legacy/` 和本文件）提交。

## 【Copilot】待办

### C1 编译和实际体积（不需要服务器，先做）
- [ ] C1.1 在开发者工具里打开 `snowmeet_wechat_mini` 并编译。编译不能有报错，尤其是 `legacy/` 下的「找不到组件或模块」「wxml 编译错误」。
- [ ] C1.2 记录「详情 → 基本信息 → 本地代码」里主包、`legacy` 分包和总包的实际大小。主包和 `legacy` 都要小于 2048 KB；`legacy` 超过 1900 KB 就报告负责人，不要自己拆分。
- [ ] C1.3 记录 `legacy` 实际大小与估算值 1271 KB 的差距，供以后估算参考。
- [ ] C1.4 如果有编译错误：定位到生成规则（`build_legacy.py` 的路径改写、组件注入，或 `legacy_app.template.js`），修生成器，重新生成，再跑 `check_legacy.py` 和 C1.1。每处修改都写进执行记录。
- [ ] C1.5 跑小程序测试，要求 194/194。

### C2 新版回归（不进旧版，不需要演示服务器）
- [ ] C2.1 用管理员账号打开新版后台首页，底部「演示」分组里有「【演示】进入旧版」。用非管理员店员账号打开，看不到这一项。
- [ ] C2.2 在新版里随便操作几个主要页面（租赁列表、养护列表、会员、食材），确认行为和之前一样，Network 里的请求都发往 `mini.snowmeet.top`，没有任何请求发往 `mini.snowmeet.com`。

### C3 旧版演示点测（需要 P1～P3）
- [ ] C3.1 管理员点「进入旧版」：能进入旧版后台首页，顶部有返回条，导航栏没有「回首页」按钮。
- [ ] C3.2 Network 面板：旧版的接口、上传、WebSocket 都发往 `mini.snowmeet.com`。允许的例外只有：
  - 图片 `snowmeet.wanlonghuaxue.com`；
  - `wxoa.snowmeet.top` 的公众号二维码接口；
  - 第三方静态资源。
  
  其他发往 `mini.snowmeet.top` 的请求都算问题。
- [ ] C3.3 旧版登录成功（演示服务器的 `MiniAppHelper/MemberLogin`），旧版后台菜单显示正常。
- [ ] C3.4 逐个点旧版后台菜单：租赁（接待、开单、订单列表、报表、租赁物设置）、养护、零售、雪票、优惠券、储值、打印。再从旧版首页进「我的」。逐项记录能否打开、能否加载数据。每个问题要归类：
  - 演示服务器缺接口或缺数据；
  - 生成器改写错误（路径、组件、跳转）；
  - 旧版本来就有的问题。已知旧版菜单里有 31 处跳转指向本来就没注册的页面，点了会提示页面不存在，这和旧版一致，不算问题。
- [ ] C3.5 非管理员拦截：在开发者工具里用非管理员账号，把编译模式的启动页设为 `legacy/pages/admin/admin`，应当被送回新版首页 `/pages/index/index`。
- [ ] C3.6 返回新版：在旧版点返回条，回到新版后台首页；新版登录态正常，请求重新发往 `mini.snowmeet.top`。
- [ ] C3.7 资源释放：
  - 先在旧版里打开会连 WebSocket 的页面（如旧版接待 `recept_entry`、带支付二维码的页面），或用蓝牙打印一次标签；
  - 然后返回新版；
  - 确认 Network 的 WS 连接已关闭，控制台没有旧页面定时器继续触发的报错；
  - 新版里再打印一次标签，能正常打印。

### C4 删除演练（在临时分支上做，做完丢弃，不提交）
- [ ] C4.1 需要 P4 提交后再做。从当前提交建临时分支，然后：
  1. 删除 `legacy/`；
  2. 删掉 `app.json` 里 `root` 为 `legacy` 的那一块；
  3. 删掉两个 admin 文件里 `legacy-demo begin`～`end` 之间的内容，含这两行。
- [ ] C4.2 运行 `py check_legacy.py --removed`，要求「全部通过」。
- [ ] C4.3 用 `git diff <加入旧版之前的提交> -- app.json pages/admin/admin.wxml pages/admin/admin.js` 对比，结果应为空；小程序测试 194/194；开发者工具编译通过。
- [ ] C4.4 切回原分支，删掉临时分支。确认原分支上的旧版完好，`check_legacy.py` 仍然全部通过。

## 已知且可接受的差异（不用修）

- 新版 `app.js` 会对所有 POST 请求里的中文做解码，这对旧版请求同样生效（旧版原来没有）。
- 演示里新上传的图片可能显示不出来，因为显示地址仍是 `snowmeet.wanlonghuaxue.com`。
- 演示里生成的二维码被扫后会打开新版（见红线 5）。
- 共用件以后在新版里改了，旧版也会跟着变。这是共用的代价，新版开发不需要顾及旧版。

## 执行记录

| 项 | 结果 | 数字 / 说明 / 截图 |
|---|---|---|
| C1.1 |  |  |
| C1.2 |  | 主包 ___ KB，legacy ___ KB，总计 ___ KB |
| C1.5 |  | ___ / ___ |
|  |  |  |
