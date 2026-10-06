# 食材测试数据清理操作参考

用户最新定义：目前全部食材相关数据都是测试数据，包括旧版食材、餐饮商品及销售订单、`fnb_unit`、食材上传记录与文件；员工个人资料是真实数据。此授权用于编写清理工具，**本轮没有执行生产清理**。

工具：[clear_test_data.py](../scripts/clear_test_data.py)。默认只预览；加 `--execute` 后，一条命令完成数据库事务清理及对应 S3 / 本机文件清理。运行过程中不询问第二次确认，也不自动读取 `config.sqlServer`。此工具仅用于正式上线前，所有清理入口受同目录生命周期状态约束。

## 实际清理范围

| 数据 | 选择规则 |
|---|---|
| 新旧食材业务、单位 | 脚本内 `FOOD_TABLES` 列出的 37 张表，存在的表全部清空，涵盖全部门店及已停用记录 |
| 餐饮商品与商品分类 | `product.type='餐饮'`、所属 `category.biz_type='餐饮'`，及新旧菜品规格指向的 product / legacy_product_id |
| 餐饮销售订单 | `order.type='餐饮'`、新旧厨房单 sales_order_id、食物商品对应的 fd_order；在线餐饮订单通过 type 及餐饮明细定位 |
| 商品、订单附属记录 | 依据白名单及真实外键 / 已审阅的列关联，清除对应商品图片、属性、商品库存流水、菜品明细、支付/退款/分账、优惠等测试记录；不调用支付或退款接口 |
| 食材上传 | 食材/餐饮/fnb 用途，以及食材图片、旧批次 image_ids、商品图片关联的 mini_upload；包括主文件与缩略图 |
| 实际文件 | 仅删除上述记录确定的 `upload/...` / `private/upload/...` 精确对象键；删除指定 S3 对象的全部版本及删除标记；指定本机 API 项目目录时也删除相应历史文件副本 |

保留真实员工、员工绑定、社交账号、会员、登录会话、门店及员工收款账户配置。其它业务的商品、订单、上传记录和文件也保留。脚本不会全表删除 `product`、`order`、`mini_upload`，不会按员工 id 删除个人数据或整个上传目录。

表结构、索引、约束和视图保留，ID 序号不重置。**fnb_unit 按要求全部清空，不保留旧单位，也不自动插入种子。**重新开始配置食材前，可执行原 [增量建表脚本](../../../../sql/2026-10-06_fnb_v4_rebuild.sql) 补回 g/kg/ml/l/piece 五种标准单位；它只新增缺失种子，不恢复测试食材。

## 一条命令执行

需要 Python 3.10+、pyodbc、机器上的 SQL Server ODBC 驱动；实际删除 S3 时需要 boto3 与 AWS 中国区凭据。S3 身份须具备目标桶的 `s3:ListBucketVersions`、`s3:DeleteObject`、`s3:DeleteObjectVersion`。现有服务 IAM 角色原本只有读写上传权限，不能假定它已有删除历史版本的权限；本轮没有修改 IAM。

先在运行环境中配置 `SNOWMEET_FNB_CLEAR_DSN`（完整 ODBC 连接串，数据库 snowmeet_new）。脚本只读取显式指定的环境变量，不读仓库配置文件；连接串不要提交到 Git。默认库名必须与真实连接库名一致。

在 snowmeet_ai_doc 目录执行预览：

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --manifest .local/fnb-clear-preview.json
```

清理命令：

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --execute --manifest .local/fnb-clear-executed.json
```

若在 mini 服务器运行，并需要删除历史本机副本，追加 `--local-app-root /home/ubuntu/webs/SnowmeetApi`，对应公开文件 wwwroot/upload 和私有文件项目根目录 upload。运行清理时应暂停食材操作；脚本会在 Serializable 事务中锁定已审阅的业务表，防止并发写入漏清。不会自动停止整个 API 服务。

每次使用一个新的清单文件，旧清单不会被覆盖。清单包含具体删除计数、删除顺序、文件键和完成状态，没有数据库凭据。预览文件不能用于实际文件删除。

## 失败与重新执行

- 数据库阶段：全部目标记录在同一事务中删除，错误会回滚。发现未审阅的食材表、未知外部引用、触发器、混合业务订单或食材文件同时被员工/其它业务使用时，停止，不扩大删除范围。
- 文件阶段：只在数据库已经提交并写入清单后开始。数据库和 S3 不能共用事务；若 S3 权限/网络或本机文件失败，数据库清理已经完成，文件清单保留待处理对象。只重试文件即可：

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --resume-files --manifest .local/fnb-clear-executed.json
```

- 清单状态为 `prepared` 表示提交结果尚未可靠记录（如提交边界发生断电/连接故障），不能直接用于文件删除，须先核对数据库结果。不要手工猜测为已成功。
- 已提交删除不能通过重新运行恢复。对象历史版本也会删除；需要保留恢复能力时，应先自行做数据库/文件备份。
- 清空数据库后重新运行会得到零条食材业务记录，仍保留其它业务。旧二维码不会因 ID 重置而指向新批次。已缓存的 CDN 图片可能短时仍可显示；本脚本不修改 CDN 配置或清缓存。

## 正式上线作废

先完成待重试文件清单，再执行以下命令并提交 `lifecycle.json` 到文档仓库 main。状态只有 testing → retired，没有重新启用参数；退役后预览、数据库清理和文件重试均会在连接/删除前拒绝。

```powershell
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --status
py .claude/skills/fnb-clear-test-data/scripts/clear_test_data.py --retire
```

本机 Codex 安装入口链接到仓库内此 skill，不复制独立状态。其他机器使用前同步 main；正式上线后不能恢复 testing 或运行旧版本。

## 验证

```powershell
py tools/windows_test/run_integration_localdb.py --verify-clear-test-data
```

只创建随机 `snowmeet_fnb_test_*` LocalDB 临时库；采用真实 v4 DDL，18 张表全部有夹具。旧版 19 张表（含 fnb_unit）使用简化夹具，并加入外键验证删除顺序；未读取生产结构。另有餐饮与非餐饮商品/线下及在线订单/支付/分账/图片、真实员工及认证/收款账户配置。检查预览、错库/外部引用/共用文件/混合订单/支付命名空间/触发器/未知表拒绝、中途实际删除后回滚、完整清空、非餐饮及个人数据逐行不变、重复执行和 ID 不重置。S3 仅模拟，检查精确键、全部历史版本、失败重试及非法路径；从未对真实 S3 执行删除。
