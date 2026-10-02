# COMMON-02 聚焦测试结果

- Run ID：`qa-20261001-common02-yesterday-113751-6bb721`
- 范围：仅 `COMMON-02 / yesterday-shortcut / C-M`；不是 170 条目录的完整执行，也不是 COMMON-02 全部日期边界矩阵。
- 状态：**PASS（attempt 2）**；attempt 1 因模拟器输入工具阻塞，原始记录保留为 `BLOCKED_TOOL`。

## 执行记录

1. 记录了文档仓 `main@0083352`、小程序仓 `ai@fed5a59f`；两仓起始工作区均干净。
2. 在 `/tmp/snowmeet-common02-qa-20261001` 创建仅有一个入口的隔离副本，直接复用正式 `date-range-picker`。源仓未修改。
3. App 启动前安装合成登录和 fail-closed 网络桩；未观察到业务请求，页面拦截计数为 0。
4. 微信开发者工具 `2.02.2607171` 编译并显示测试页；首屏日期为 `2026-10-01 ~ 2026-10-01`，“今天”高亮。
5. attempt 1 的 DevTools 自动化/系统点击没有将 tap 送入小程序，保留为 `BLOCKED_TOOL`。
6. attempt 2 由测试人员在前台 DevTools 模拟器点击“昨天”；日期组件与父页面均显示 `2026-09-30 ~ 2026-09-30`，“昨天”蓝色高亮，业务请求数仍为 0，判 PASS。

## 证据与结论

首屏截图：`screenshots/COMMON-02-before.png`。attempt 1 截图：`screenshots/COMMON-02-click-attempt.png`。attempt 2 通过截图：`screenshots/COMMON-02-after-pass.png`。DevTools 原始日志：`logs/devtools-project.log`。

未发现产品缺陷。原始 DevTools 日志记录了 `routeTo appLaunch timeout` 警告，但画面随后成功渲染测试页；该环境差异已保留。

该 PASS 仅覆盖 COMMON-02 的“昨天”单场景；本周/上周、跨月跨年、周一/周日和手选范围仍未执行。全量 170 条用例状态不受本次单例结果影响。
