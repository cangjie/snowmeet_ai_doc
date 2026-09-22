-- 在目标业务数据库执行；仅删除 dbo.[order] 上的 CK_order_source_pair。
IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.[order]', N'U')
      AND name = N'CK_order_source_pair'
)
BEGIN
    ALTER TABLE [dbo].[order] DROP CONSTRAINT [CK_order_source_pair];
END;
