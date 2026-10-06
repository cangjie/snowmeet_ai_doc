# 2026-10-06 食材管理 v4 企业微信 H5 生产部署

H5 开发交付后，用户明确要求「好的，部署吧」。本次只发布已经验证并推送的 `SnowmeetApi ai@955188ab`，不继续服务端第 2、3 期。北京时间 **2026-10-06 15:04** 完成发布及只读检查。

## 发布版本与范围

- 服务器经既有 `44.207.251.65:2222` 转发连接；工作目录 `/home/ubuntu/webs/SnowmeetApi`，服务 `mini.snowmeet.top.service`。
- 发布前 `ai@ec7c25612590b31ce72af56b4a1f6774d85dbdef`，跟踪文件没有改动；已核对远端 ai 为本次固定目标。
- 发布后 **`ai@955188ab4143cd63c051105823b2b4446464bc6b`**，使用服务器现有 **`republish.sh`**，没有改脚本或上传另一套 DLL。
- 程序交付文件：`Controllers/Fnb/FnbPageController.cs`、`wwwroot/fnb/v4/` 的 7 个 HTML/CSS/JS 文件、共享 `wwwroot/wecom/ble_print_test/ble_print.js`；测试文件与具体实现详见 [H5 开发记录](2026-10-06_fnb-v4-h5.md)。本次部署没有新增代码提交。
- **没有 SQL**，没有读取本机或服务器 `config.sqlServer`，没有运行数据库脚本；没有业务过账、真实员工 OAuth、OCR 请求或实际打印。
- 新入口 [食材管理 v4](https://mini.snowmeet.top/fnb/v4/index.html)。企业微信应用主页配置本轮未修改；需要工作台入口切换时，由管理员将原餐饮应用主页设置为该地址，保留 mini.snowmeet.top 可信域名及原员工映射。

## 发布中处理

1. 已备份 **435 个运行文件**与原共享蓝牙脚本。第一次预检因本机 app.js 使用 CRLF、Git 与 Linux 使用 LF 导致字节哈希不一致，在执行发布脚本前停止；校验改为固定 Git 提交的原始内容后继续。
2. 首次 republish 完成程序集发布并启动服务，但新 H5 目录由 sudo Git 拉取后归 root 所有，发布用户 ubuntu 无权生成 14 个 `.gz` / `.br` 静态压缩资源，出现 MSB3021。原脚本最终返回 0，不能仅凭退出码判断成功；已检查完整日志并核对错误全部局限于新目录。
3. 只将 `/home/ubuntu/webs/SnowmeetApi/wwwroot/fnb/v4` 及其文件所有者改为既有发布用户 `ubuntu:ubuntu`；保留第一次日志，再次执行原 republish。没有改其它目录权限、脚本或业务源码。
4. 第二次 republish **退出 0**，日志没有构建错误，既有编译警告仍在。最终主程序集 SHA-256 `8c3eaae9a9b731509c2e2ec9c5ab7d1e654b6719d0bdf8721a7a64667e128650`；原脚本 SHA-256 始终为 `dc778ef5d85148c23d3e08c39e17822dc17f01a93d2b1ce46d10150955b4a007`。

## 线上检查

- 服务 **active/running**，MainPID **37224**，NRestarts **0**；发布后根盘剩约 **1.1 GB**，回滚备份保留。
- 公网新入口、6 个配套资源、共享蓝牙文件和 3 个原打印库：共 **11 个资源 HTTP 200**，响应字节 SHA-256 与固定 Git 提交一致。
- 公网 Swagger HTTP **200**，`FnbAuth` / `FnbCatalog` / `FnbRoute` 的 **17 个第一期接口**保留；发布前 **517 个路由**均保留，新增 `/fnb/b` 已注册。
- `/fnb/b?id=9223372036854775806&shopId=1` 返回 **302**，Location 为 `/fnb/v4/index.html?id=9223372036854775806&shopId=1`，长批次 ID 和 query 完整保留。
- 不存在的会话调用 `FnbAuth/GetMe` 返回 HTTP **200 / code 2**。这是只读身份检查，没有创建真实员工会话或修改业务数据。
- **462 个受保护文件哈希未变**，涵盖其它已跟踪静态页面、美团采集控制器及工具；共享蓝牙脚本属于本次明确修改范围，单独校验。小程序没有改动。
- 发布使用开发阶段已通过的 **构建 0 错误、467 项服务端单元/HTTP、12 项 LocalDB、9 项 H5 测试、22 页浏览器检查**结果，没有重复运行生产集成测试。

## 回滚与使用边界

- 程序备份 `/home/ubuntu/fnb-v4-h5-deploy-20261006/runtime-backup`，原主程序集 SHA-256 `334654396f3050eb884b0972cdecb6804c49b5937673ddae252da71cb7bc918f`；共享脚本备份在同目录 `static-backup`。
- 日志 `republish.log`、首次日志 `republish.log.attempt1`、诊断 `diagnosis.json`、权限修复 `permission-repair.json`、发布前状态 `publication-before.json`、最终验收 `verification.json` 位于该目录，目录权限 700。未触发回滚，上午部署备份也保留。
- 故障回滚时可恢复运行文件和原共享蓝牙脚本并重启服务；保留全部数据库表和数据，不执行数据库回滚。源码 HEAD 已推进到新提交，恢复运行文件后须记录源码与运行版本差异。
- 当前只开放第一期分类、食材、链路及进货规格等主数据。入库、库存、作业、出餐、盘点、报表等运营页面仍等待后两期接口，相关提交禁用；完整 32 步流程没有上线。
- 企业微信 iPhone/安卓的真实 OAuth、相机 OCR、扫码、蓝牙搜索/连接/重连、60×40mm 标签实际出纸仍待真机验收。线上资源与接口检查不替代这些验证。
