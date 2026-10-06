# 食材测试数据清理（临时 skill）

已封装为 [fnb-clear-test-data](../../.claude/skills/fnb-clear-test-data/SKILL.md)，可通过 `$fnb-clear-test-data` 或“清理食材测试数据”调用。完整范围、运行方式与失败处理见 [操作参考](../../.claude/skills/fnb-clear-test-data/references/operations.md)。

仅食材系统正式上线前可用。正式上线时运行 skill 的 `--retire` 并提交状态，之后预览、数据库清理及文件重试均拒绝。当前为 testing 状态，本轮只创建并验证工具，没有执行生产数据库或真实 S3 清理。

清理包含全部新旧食材、餐饮商品与销售订单、fnb_unit、相关上传记录及文件；保留员工个人资料、认证及其他业务数据。表结构和 ID 序号保留。
