# 七色米抓取工具跨电脑同步

用户要求把已有抓取程序放入 `snowmeet_ai_doc/tools`，通过 GitHub 在 Windows 和 macOS 间同步。

入口为 [tools/qisemiyun/run.py](../tools/qisemiyun/run.py)，完整安装、登录、输出与定时调用说明在 [README](../tools/qisemiyun/README.md)。使用 Python 3.11+ 与标准 pip 依赖，已去除本机 Codex 运行时路径、Node 工作簿依赖、真实用户和账套标识。

每台电脑独立安装并登录。业务数据默认保存在仓库外的应用数据目录，每轮新建快照；仅成功完成校验后更新最近成功指针。跨进程文件锁阻止同一数据目录的并发任务。Windows 使用 DPAPI 保存会话，macOS 使用系统钥匙串；密码不保存，会话不经 Git 同步。

库存模式重新查询商品、仓库、门店、总库存和各仓库存，校验汇总并导出 Excel、JSONL、SQLite 和 ZIP。全量模式补充全部时间范围的单据、明细、库存流水、关联历史版本、图片附件及索引。收付款采用 Excel 可打开的 UTF-8 BOM CSV，保留 JSONL / SQLite 中的原始字段。

程序选择物理网卡直连，保留 TLS 证书验证，不修改 VPN 和系统路由。Windows 使用源 IPv4，macOS 同时使用接口绑定。网络环境变化后先执行 `doctor --network`。

本机已通过合成数据测试、跨进程锁、Windows 原生 DPAPI 和公共站点网络检查。GitHub Actions 配置 Windows / macOS 与 Python 3.11 / 3.13 的矩阵检查；不在 CI 中使用真实业务账号。真实账号登录、VPN 环境及全量采集需要在运行电脑检查。本次迁移未重新抓取业务数据，既有本机导出保留。

定时执行可由任务计划程序或用户 LaunchAgent 调用，加 `--non-interactive`；未创建定时任务或指定执行周期。
