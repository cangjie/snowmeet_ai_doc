# 食材测试数据清理（临时 skill）

已封装为 [fnb-clear-test-data](../../.claude/skills/fnb-clear-test-data/SKILL.md)，可通过 `$fnb-clear-test-data` 或“清理食材测试数据”调用。完整范围、运行方式与失败处理见 [操作参考](../../.claude/skills/fnb-clear-test-data/references/operations.md)。

仅食材系统正式上线前可用。正式上线时运行 skill 的 `--retire` 并提交状态，之后预览和执行均拒绝。当前为 testing 状态。

**2026-10-12 用户重新定义了范围**：只处理 `fnb_v4_` 开头的表，并且只做逻辑删除——把 `valid` 置 0、刷新 `updated_at`，不删除任何行。没有 `valid` 列的 v4 表原样保留。`fnb_unit`、餐饮商品与销售订单、上传记录及文件、员工和其他业务都不在范围内。

此前（2026-10-06）的定义是物理清空全部新旧食材、餐饮商品与销售订单、`fnb_unit`、相关上传记录及文件；这一版从未在生产执行，已被上面的定义取代。
