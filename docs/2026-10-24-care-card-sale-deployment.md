# 养护开单购卡与旧版兼容修复部署

2026-10-24，用户要求先修复两个兼容问题、实现小程序新需求、完成服务端并部署。

## 交付版本

- 服务端：`SnowmeetApi ai@542f7074`，已推送并部署至 `/home/ubuntu/webs/SnowmeetApi`，从原 `9f9f8217` 快进。
- 小程序：`snowmeet_wechat_mini ai@2279d68c`，已推送，实现添加卡类、试算、购卡零售结算、付款后发卡扣次、处理失败重试、两单互查与继续结算。尚未上传、提审或发布。
- 不新增表或列，无需 SQL，本轮未更改生产数据库结构或历史数据。原三表 SQL 已撤回为作废说明。

## 两项修复

1. 有限次卡在下单前按整单装备合并检查次数，核销时加锁再次校验。原核销接口遇到余额不足返回 ApiResult 业务错误，订单不会提前显示已支付；原先已提交的订单也可在修正余额后重试。
2. 旧零元核销与普通养护支付回调，把任务、权益消费和订单完成状态纳入同一业务事务；异常回滚清理变更跟踪，上层保存错误日志不会再写入回滚的任务/核销。已经收到的外部支付记录保留，业务可补处理，不重复收款。

付款前的安排复用原 retail.memo，发卡和养护生效成功后清空；实际发卡、核销、取消追溯继续使用原业务表。

## 本地验证

- 服务端 569 项通过，含 20 项本次购卡与旧版兼容用例；排除真实 SQL Server、七色米 SQL Server 和线上快照测试。
- 小程序 12 项购卡交互测试通过；排除既有 `fnbinv_pages.test.js` 后的回归 244 项通过。该既有测试存在用例结束后的 `wx.navigateBack is not a function`／子进程反序列化错误。
- JS 语法、JSON 与 WXML 标签结构检查通过。开发者工具界面控制未获授权，本轮没有通过其界面编译、生成真机预览或上传。
- 未触发真实微信/支付宝支付、退款，未创建生产测试订单；真实支付和手机布局仍需联调验收。

## 发布与生产验收

1. 发布前确认已跟踪工作区无改动、原服务 active，磁盘剩余约 7.4 GB。
2. 在 `/home/ubuntu/care-card-sale-deploy-20261024/` 保存原 HEAD、程序集、依赖/运行配置和 Swagger 清单备份。
3. 单独执行 `git pull --ff-only origin ai`，核对完整 HEAD 为 `542f70740845d160609cac011126de24f05efa27`，再运行原 `./republish.sh`，没有另建 DLL 上传发布流程。
4. 仓库开关默认关闭，生产通过 `/etc/systemd/system/mini.snowmeet.top.service.d/care-card-sale.conf` 设置 `CareCardSale__Enabled=true`，daemon-reload 后由原发布脚本启动服务生效。
5. 北京时间 19:47:00 停止服务，19:48:50 启动，停机约 1 分 50 秒。发布脚本退出 0，构建错误 0。
6. 验收时服务 active/running，MainPID 30109，NRestarts=0；本次启动后日志未发现 fail/未处理异常/SQL 异常。
7. Swagger 路径从 625 增至 631，原操作无删除，原接口无新增必填参数，原请求模型无新增必填字段。新增均为 CareCardSale 的 6 个动作。
8. 新 `CareCardSale/GetProducts`、旧 `Order/GetOrderByStaff` 的无效会话均返回 code=1、没有权限；公开旧接口 `https://mini.snowmeet.top/api/Order/GetUnCommonPayMethod` 返回正常 JSON，仍为 6 项。
9. 程序集 SHA256：`43d7b2c75046b0a28fde12125c16757d7e281652628f07795ee6752db35db4f6`。服务器证据保存于上述目录的 publish.log、swagger-before/after.json 与 verification.json。

## 后续边界

小程序代码已具备新流程，生产 API 已就绪。下一步需要在微信开发者工具编译，真机验证本人微信付款、核验后支付宝/代付、取消返次和断线续办，再按正常小程序发布节奏上传。旧版仍可使用原开单和付款接口；含卡禁退、取消返次按用户确认的新规则执行。

原有 `app.js`、`pages/index/index.js` 和未跟踪的 `tests/entry_navigation.test.js` 入口修复未纳入本次提交，原内容保留。服务端工作区干净。

业务及接口说明：[实施说明](2026-10-24-care-card-sale-implementation.md)。历史复现及修复：[兼容性检查](2026-10-24-care-card-sale-legacy-compatibility-review.md)。
