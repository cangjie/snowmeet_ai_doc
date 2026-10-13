# 2026-10-13 食材 v4 清理与状态分离：停用可恢复，删除后界面不再显示

本次从 start-work 开始，接续 10-12 的 v4 测试数据逻辑删除。改动落在 SnowmeetApi 后端及企业微信 H5；文档仓同步维护清理 skill、增量 SQL、接口契约与部署记录。用户最终要求部署，并以 end-work 收尾。

## 1. 清理范围核对与执行

用户先问：“清除食材管理 v4 版本的测试数据的 skill，他会清除哪些表？”随后要求执行，并明确连接来源为“使用 SnowmeetApi/config.sqlServer（仅本次）”。

- 使用 [fnb-clear-test-data](../.claude/skills/fnb-clear-test-data/SKILL.md)。
- 范围为 dbo 下 31 张 fnb_v4_ 表。
- 只将未删除行的 valid 置为 0。
- 同步现有更新时间列，写 UTC。
- 不物理删行，不改单位或共享业务表。
- 不删除上传记录、磁盘文件或 S3 文件。

08:22 北京时间执行时，31 张表共 23 行已全部为 valid=0，因此实际更新 0 行；fnb_unit 的 5 行单位保持原样。这是重复清理的正常结果，不表示命令没有执行。连接信息仅在进程内使用，未写入公开文档。

执行与核验清单保存在文档仓忽略目录 `.local/fnb-clear-executed-20261013-c.json` 等文件中，不随 Git 跨机同步。清理的 testing 生命周期保持不变；本次发布仍属测试阶段，正式业务启用前须永久 retire skill。

## 2. 为什么清理后区域仍显示

用户提供区域管理截图：二楼教室、吧台、冷藏柜仍在，均标为“停用”。生产数据确已 valid=0，界面现象来自状态语义和查询规则混用。

原版本 fe4eb6c2 给后补 valid 的 20 张表设置全局过滤，原有 10 张主数据仍由各查询处理；区域管理请求 includeDisabled=true，会把 valid=0 当作可逆停用数据返回。因此再次运行相同清理不能解决界面问题。

用户明确：“停用和删除是两回事。停用了未来可以启用，删除了……界面操作不可逆只能通过手动修改数据库来恢复。”按这个决策实现以下规则：

| 数据状态 | 界面含义 | 界面操作 |
|---|---|---|
| valid=true，enabled=true | 正常启用 | 可停用或按业务约束删除 |
| valid=true，enabled=false | 停用 | 可重新启用 |
| valid=false | 逻辑删除 | 不显示，不提供恢复入口 |

includeDisabled 只扩展到未删除的停用主数据，不能绕过删除过滤。删除仍保留数据库行；手动数据库恢复不作为界面功能实现，也未在本次执行。

## 3. 实现与验证

### 后端与数据库

SnowmeetApi 提交 `76246c612eb6e63ed7c49bcba314693f8e383d52`，共 28 个文件。30 张 v4 表统一按 valid 全局过滤；fnb_v4_request 为幂等例外，保留删除请求键，重试必须拒绝而非返回旧响应。

10 张主数据增加 enabled：category、item、item_form、purchase_spec、shelf_life_rule、dish_spec、area、supply、tool、check_item，均为 fnb_v4_ 前缀。增量 [SQL](../sql/2026-10-13_fnb_v4_enabled.sql) 仅新增 `enabled bit NOT NULL DEFAULT 1`，可重复执行，不改原 valid、业务字段或时间戳。

主数据编辑只改 enabled；旧请求中的 valid 字段保留为启停兼容输入。保存前按删除过滤查找 ID，已删除区域等不能通过 enabled=true 或旧 valid=true 保存恢复。区域删除改为 valid=false，保留数据库行；库存、作业、条码等业务入口同时检查所需主数据及上级是否启用。

### H5

- 分类启停与删除使用独立操作。
- 区域启停可往返，删除后刷新消失。
- 物资、工具管理可包含停用记录。
- 停用记录的业务操作按钮禁用。
- DeleteSpec 文案明确为“删除规格”。

入口引用的脚本版本改为 `20261013-enabled-delete`，地址及企业微信主页配置保持原设置。

### 本机验证

- 服务端回归 475 通过。
- 22 项 Windows LocalDB 集成测试跳过。
- 12 项 H5 Node 测试通过。
- 完整离线浏览器页面与业务流程通过。
- 新增分类、区域启停与删除流程覆盖。
- EF 新增列恰好 10 个。
- 原两份 10-06 建表 SQL 未修改。

新增 SQLite 回归覆盖删除过滤、停用可启用、旧请求不恢复删除 ID 及删除幂等请求拒绝重试。清理 skill 与接口契约同步更新，skill 校验通过；Windows 验证运行器接入 enabled 增量 SQL 并要求重复执行。

## 4. 用户授权部署与生产结果

用户要求“继续”后完成本地实现和验证，审阅新增字段与部署范围后明确“对，部署吧”。完整时间、哈希及回滚文件见 [生产部署记录](2026-10-13_fnb-v4-enabled-deletion-production-deploy.md)。

09:33:37–09:33:41 在 snowmeet_new 执行 enabled 增量 SQL，随后重复执行核对。31 张 v4 表的 23 行数据、既有 valid 与时间戳以及 fnb_unit 的 5 行均保持原值；原 valid=0 数据继续为删除状态。部署阶段没有再次清理数据。

服务器工作目录为 `/home/ubuntu/webs/SnowmeetApi`，服务 `mini.snowmeet.top.service`。发布始终使用原 republish.sh，没有修改脚本或另传 DLL。

首次发布因 SnowmeetApi.Tests/H5 目录及文件归 root，Git 无法完成 checkout；脚本仍继续构建启动并退出 0，源码 HEAD 未推进。捕获错误后，逐文件核对部分拉取内容与目标提交，保留无关文件，只修正 H5 测试目录所有者并恢复部分拉取内容，再 fast-forward 到目标提交。

第二次发布于 09:40:51 完成，HEAD 为 76246c61，构建日志无错误。随后验证：

- 服务 active/running，NRestarts=0。
- Swagger 原 587 条路由全部保留。
- 9 个 HTTPS 资源与提交逐字节一致。
- 445 个其他跟踪静态文件哈希未变。
- 含停用及不含停用的区域列表均为空。
- 其他清理主数据、库存无删除数据返回。
- 今日检查为 none，检查项为空。
- 5 个单位正常，失效会话返回 code 2。

使用已有店长会话向一个删除区域分别提交 enabled=true 和旧 valid=true，均返回 code 1 / “本店区域不存在”；数据库快照复核无业务写入。会话只经私有临时文件传递，验证后临时文件已删除。验收时段运行日志无错误。

回滚备份及两次发布日志保留在服务器私有目录 `/home/ubuntu/fnb-v4-enabled-deploy-20261013`。只清除本次生成的 bin/obj 缓存，最后可用空间约 1.9 GiB。未回滚、未恢复删除测试数据。

## 5. 收尾与下一步

end-work 先对文档仓 pull --ff-only，结果已最新；更新 CLAUDE.md 当前状态日期、显示规则、关键文件、遗留与下一步，追加开发日志，并提交推送本记录。收尾开始时 API 与文档仓干净，API 为 ai@76246c61；小程序、公众号与 reqai 未在本次改动，未自动合并或提交业务仓。

下次先关闭企业微信旧页面重进，重新配置分类、区域、检查项及工具，再做真实登录、OCR、蓝牙出纸和出餐扣减验收。单位保留，不需要补种子。

仍待完成：Windows 上 22 项 LocalDB 集成测试及清理 skill 隔离验证；先清除 tools/windows_test/ef_create.sql 缓存以重建当前模型。“新建食材后列表未刷新”是已有独立问题，本次未修复。正式业务启用前永久 retire 清理 skill。

## 关键改动文件

| 文件 | 改动 |
|---|---|
| [FnbSchemaConfiguration.cs](../../SnowmeetApi/Data/FnbSchemaConfiguration.cs) | 30 张表删除过滤、enabled 默认值 |
| [FnbV4CatalogService.cs](../../SnowmeetApi/Services/Fnb/FnbV4CatalogService.cs) | 主数据启停与旧请求兼容 |
| [FnbV4FacilitiesService.cs](../../SnowmeetApi/Services/Fnb/FnbV4FacilitiesService.cs) | 区域等启停与逻辑删除 |
| [FnbV4Service.cs](../../SnowmeetApi/Services/Fnb/FnbV4Service.cs) | 业务启用校验 |
| [FnbV4ControllerBase.cs](../../SnowmeetApi/Controllers/Fnb/FnbV4ControllerBase.cs) | 保留幂等键，拒绝删除请求重试 |
| [app.js](../../SnowmeetApi/wwwroot/fnb/v4/app.js)、[operations.js](../../SnowmeetApi/wwwroot/fnb/v4/operations.js) | H5 状态与操作分离 |
| [FnbV4DeletionAndSuspensionTests.cs](../../SnowmeetApi/SnowmeetApi.Tests/FnbV4DeletionAndSuspensionTests.cs) | 服务层状态回归 |
| [fnb-v4.state-flows.cjs](../../SnowmeetApi/SnowmeetApi.Tests/H5/fnb-v4.state-flows.cjs) | 浏览器启停、删除刷新流程 |
| [enabled SQL](../sql/2026-10-13_fnb_v4_enabled.sql) | 只新增 10 个 enabled 列 |
| [清理 skill](../.claude/skills/fnb-clear-test-data/SKILL.md)、[操作参考](../.claude/skills/fnb-clear-test-data/references/operations.md) | 纠正停用/删除语义与清理前提 |
| [接口契约](../docs/fnb/2026-10-06-fnb-v4-operations-api.md) | enabled 输入及删除语义 |

## 学到的小知识

1. **删除标记与启停状态要分开**：逻辑删除保留数据库行，但所有界面查询仍需排除；“包含停用”不能顺带返回删除行。
2. **清理后先核对状态与查询**：本次重复清理写入 0 行，因为数据库已删；界面可见来自接口状态混用，继续清理无法修好。
3. **发布退出 0 不等于目标版本在运行**：原脚本会在 pull 失败后继续构建，必须联合核对 HEAD、日志、服务、资源和接口。
4. **生产验证不替代隔离集成测试**：线上删除过滤验收通过，仍不能把 Windows LocalDB 的 22 项跳过记成通过。
