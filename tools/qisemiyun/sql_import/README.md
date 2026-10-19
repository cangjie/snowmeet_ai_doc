# 七色米 SQL Server 初次迁移

对应 [已确认的表结构](../../../docs/qisemi/database-design.md)。这是初次完整快照的建表与导入工具，操作范围限 `dbo.qsm_*`。不启动抓取、不改已有零售记录、不发布 H5。

需要 Python 3.11+、本机 SQL Server ODBC 驱动，以及现有配置文件的读取权限。导入输出目录必须位于 Git 仓库外或 workspace 的 `.local/`；其中包含真实业务数据，不得提交到 Git。

```text
python -m pip install -r requirements.txt
```

按顺序运行，路径替换成当前电脑的实际位置：

```text
python prepare.py --data-dir <完整采集的data目录> --output-dir <新的本机暂存目录>
python sync_s3.py --prepared <本机暂存目录> --ssh-host ubuntu@<已配置的转发服务器> --ssh-port 2222 --report <本机文件迁移报告.json>
python load.py --config <SnowmeetApi/config.sqlServer> --expected-database snowmeet_new --stage <暂存目录/staged.sqlite3> --asset-receipt <本机文件迁移报告.json> --apply-schema --report <本机数据库迁移报告.json>
```

`prepare.py` 仅读取已有完整数据，核对数量、媒体校验值、基础单位、逐商品库存合计，保留业务原始行、原表和元数据。新暂存目录避免覆盖上次结果。自动归组只对有独立数字鞋码属性、明确鞋类名称、名称末尾精确尺码及完整款式属性佐证的商品启用；其余单列，均待人工确认，不把所有 `Property3` 都当尺码。

`sync_s3.py` 使用项目现有 S3 私有桶的 `private/qisemi/datasets/<数据指纹>/`。IAM 凭据留在服务器，短时上传授权仅在进程内存中使用；本机绑定物理网卡上传，不打印或保存签名 URL。上传前探测匿名访问受限，每个对象使用 Content-MD5 校验，再由服务器核对长度与 SHA-256 元数据。数据库 `storage_provider='s3'`、`object_key` 为完整私有对象键。读取需复用现有文件服务的私有读取或鉴权接口，不能直接拼公开图片域名。

可选的 `sync_files.py` 则通过 SSH 流式写 `/home/ubuntu/data/qisemi/datasets/<数据指纹>/`，权限 700/600，用于空间充足时的私有磁盘部署；两种方式都避免生成第二份远端大包。原始 JSONL 完整存数据库，SQLite 和 ZIP 是重复载体，保留本机备份，不在服务器再复制整包。

`load.py --apply-schema` 执行生成的 [建表脚本](../../../sql/2026-10-19_qisemi_schema.sql)，核对表/列集合后导入。原始 JSON 以 `payload_gzip varbinary(max)` 无损保存，通过 `payload_json` 计算列读取，约束检查解压后的 JSON，发布前逐条检查 UTF-8 SHA-256。查询用字段仍为普通列，避免库存搜索解压全表。

首次导入使用会话锁、分批暂存和检查点控制日志占用，表及索引使用 PAGE 压缩。暂存期间批次是 `staging`，当前全业务/库存指针均为 NULL；核对通过后在一个事务内设置单据版本指针、批次发布状态和两个当前指针。业务读取必须通过已发布指针，不能把暂存记录当当前数据。异常回滚当前事务，已提交的暂存前缀保持未发布；同一快照可继续，校验连续 ID 前缀且不重复插入。

相同数据指纹与解析器版本已发布时，复核后直接返回。已有其他快照则拒绝覆盖；**这个版本尚不支持新快照的日常增量更新或历史批次回退**，不能把初次迁移命令当作已完成的定时导入。

大批数据建议在已核实身份的服务器本机导入，避免经 SSH/TDS 逐包传输，也避免服务器落地巨大的暂存 SQLite：

```text
python stream_package.py --stage <暂存目录/staged.sqlite3> --output-dir <新的压缩导入包目录>
python sync_s3.py --prepared <压缩导入包目录> --ssh-host ubuntu@<转发服务器> --report <本机导入包上传报告.json>
```

把本目录的 Python 源码、`stream-manifest.json` 和文件迁移报告复制到服务器的私有作业目录。使用服务器既有 `pymssql`、`botocore` 与实例角色，执行：

```text
python3 remote_load.py --manifest <stream-manifest.json> --asset-receipt <文件迁移报告.json> --config /home/ubuntu/webs/SnowmeetApi/config.sqlServer --expected-database snowmeet_new --expected-identity <已核对的数据库GUID> --report <数据库迁移报告.json>
```

数据库 GUID 从配置所指的数据库只读取得：`SELECT CONVERT(varchar(50),service_broker_guid) FROM sys.databases WHERE name=DB_NAME()`。服务器本机目标必须与之相同，才允许建表/导入。压缩包逐表从 S3 流式读取，SQL 凭据从服务器同一应用配置取得，不复制到工作目录或命令行。当前服务器已验证 `pymssql 2.4.3`；运行环境可通过 `PYTHONPATH` 复用已安装的依赖。

默认使用 ODBC TLS。Windows 只有旧 `SQL Server` 驱动且不能协商 TLS 时，可使用已经建立、绑定本机回环地址的 SSH 隧道；账号和库名仍从同一配置文件读取，不另选凭据：

```text
ssh -N -o ExitOnForwardFailure=yes -p 2222 -L 127.0.0.1:41433:127.0.0.1:1433 ubuntu@<已配置的转发服务器>
python load.py --config <SnowmeetApi/config.sqlServer> --expected-database snowmeet_new --tunnel-server 127.0.0.1,41433 --stage <暂存目录/staged.sqlite3> --apply-schema --report <本机数据库迁移报告.json>
```

隧道目标必须经过只读核对，确认与配置所指应用数据库一致；`--tunnel-server` 仅接受 `127.0.0.1,端口`。不得把此选项用于未加密的外网连接。配置、账号、密码和 SSH 私钥不进入命令参数、输出或 Git。

维护 DDL / 检查通用转换：

```text
python schema.py
python -m unittest discover -s tests -v
```

数据库结构变化需同步设计文档。临时 SQL Server 已验证真实快照导入、逐条原始哈希、外键与逻辑删除、重复导入；另外用合成数据注入中断，验证分批暂存、继续导入、发布指针、PAGE 压缩及负库存。Python 单元检查不能替代这些数据库验证。`prepare.py --resume-raw` 只重建未完成的本机派生暂存，不修改已抓取文件或生产库。
