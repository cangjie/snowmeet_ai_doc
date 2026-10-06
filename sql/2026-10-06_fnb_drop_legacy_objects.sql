/*
2026-10-06：用户明确要求 DROP v4 不再使用的旧食材表和视图。
仅删除下列 18 张 dbo 旧表、2 个 dbo 旧视图；保留 fnb_unit、所有 fnb_v4_* 和共享表。
生产执行前须导出并校验目标结构/数据备份，然后在本连接设置：
 EXEC sys.sp_set_session_context @key=N'fnb_legacy_backup_verified', @value=1;
默认只允许 snowmeet_new；LocalDB 验证仅允许 snowmeet_fnb_test_* 随机库。
不读取任何配置，不删除上传文件，不清除共享表记录，不禁用外部约束。
可重复执行；全部 DDL 在同一事务中，依赖检查失败时回滚。
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET LOCK_TIMEOUT 15000;

IF DB_NAME() <> N'snowmeet_new' AND DB_NAME() NOT LIKE N'snowmeet[_]fnb[_]test[_]%'
    THROW 51040, N'目标库不在允许范围，禁止删除旧食材对象。', 1;
IF @@TRANCOUNT <> 0
    THROW 51041, N'禁止在已有外层事务中执行。', 1;
IF DB_NAME() = N'snowmeet_new' AND ISNULL(TRY_CONVERT(int, SESSION_CONTEXT(N'fnb_legacy_backup_verified')), 0) <> 1
    THROW 51042, N'尚未确认目标对象的已校验备份，禁止删除。', 1;

DECLARE @targets TABLE (name sysname COLLATE DATABASE_DEFAULT PRIMARY KEY, kind char(2) COLLATE DATABASE_DEFAULT NOT NULL);
INSERT INTO @targets(name, kind) VALUES
 (N'fnb_material_category','U'), (N'fnb_material_item','U'),
 (N'fnb_shelf_life_rule','U'), (N'fnb_material_batch','U'),
 (N'fnb_material_batch_stock','U'), (N'fnb_material_alert_log','U'),
 (N'fnb_dish_spec','U'), (N'fnb_recipe','U'), (N'fnb_recipe_line','U'),
 (N'fnb_stock_document','U'), (N'fnb_stock_document_line','U'),
 (N'fnb_stock_movement','U'), (N'fnb_stocktake_line','U'),
 (N'fnb_order','U'), (N'fnb_order_line','U'), (N'fnb_order_import','U'),
 (N'fnb_channel_shop','U'), (N'fnb_channel_dish_map','U'),
 (N'vw_fnb_material_stock','V'), (N'vw_fnb_material_loss','V');

BEGIN TRY
    BEGIN TRANSACTION;
    IF OBJECT_ID(N'dbo.fnb_unit', 'U') IS NULL
       OR OBJECT_ID(N'dbo.fnb_v4_item', 'U') IS NULL
       OR OBJECT_ID(N'dbo.fnb_v4_batch', 'U') IS NULL
       OR OBJECT_ID(N'dbo.vw_fnb_v4_stock', 'V') IS NULL
       OR OBJECT_ID(N'dbo.vw_fnb_v4_loss', 'V') IS NULL
        THROW 51043, N'v4 基础结构不完整，禁止删除旧食材对象。', 1;

    IF EXISTS (SELECT 1 FROM @targets t JOIN sys.objects o
               ON o.schema_id=SCHEMA_ID(N'dbo') AND o.name COLLATE DATABASE_DEFAULT=t.name WHERE o.type COLLATE DATABASE_DEFAULT<>t.kind)
        THROW 51044, N'目标对象类型与清单不一致。', 1;

    DECLARE @existing TABLE (object_id int PRIMARY KEY, name sysname COLLATE DATABASE_DEFAULT, kind char(2) COLLATE DATABASE_DEFAULT);
    INSERT INTO @existing SELECT o.object_id,t.name,t.kind FROM @targets t
      JOIN sys.objects o ON o.schema_id=SCHEMA_ID(N'dbo') AND o.name COLLATE DATABASE_DEFAULT=t.name AND o.type COLLATE DATABASE_DEFAULT=t.kind;

    -- 外部表引用任一旧表时拒绝；不允许顺带修改其它表的外键。
    IF EXISTS (SELECT 1 FROM sys.foreign_keys f JOIN @existing p ON p.object_id=f.referenced_object_id
               WHERE NOT EXISTS (SELECT 1 FROM @existing c WHERE c.object_id=f.parent_object_id))
    BEGIN
        SELECT f.name AS foreign_key, OBJECT_SCHEMA_NAME(f.parent_object_id) AS child_schema,
               OBJECT_NAME(f.parent_object_id) AS child_table, p.name AS referenced_old_table
        FROM sys.foreign_keys f JOIN @existing p ON p.object_id=f.referenced_object_id
        WHERE NOT EXISTS (SELECT 1 FROM @existing c WHERE c.object_id=f.parent_object_id);
        THROW 51045, N'发现清单外表的外键引用，停止，不扩大删除范围。', 1;
    END;

    -- 约束、触发器的 referencing_id 属于子对象；按 parent_object_id 归属表。
    IF EXISTS (
      SELECT 1 FROM sys.sql_expression_dependencies d JOIN sys.objects owner ON owner.object_id=d.referencing_id
      WHERE NOT EXISTS (SELECT 1 FROM @existing e WHERE e.object_id=COALESCE(NULLIF(owner.parent_object_id,0),owner.object_id))
        AND (EXISTS (SELECT 1 FROM @existing e WHERE e.object_id=d.referenced_id)
          OR (d.referenced_database_name IS NULL AND d.referenced_server_name IS NULL
              AND ISNULL(d.referenced_schema_name,N'dbo')=N'dbo'
              AND EXISTS (SELECT 1 FROM @targets t WHERE t.name=d.referenced_entity_name COLLATE DATABASE_DEFAULT))))
        THROW 51046, N'发现清单外视图、函数或存储过程引用，停止。', 1;

    -- 动态 SQL 文本引用也拒绝；已列入目标的视图及表内子对象不属于外部依赖。
    IF EXISTS (
      SELECT 1 FROM sys.sql_modules m JOIN sys.objects owner ON owner.object_id=m.object_id
      WHERE NOT EXISTS (SELECT 1 FROM @existing e WHERE e.object_id=COALESCE(NULLIF(owner.parent_object_id,0),owner.object_id))
        AND EXISTS (SELECT 1 FROM @targets t WHERE CHARINDEX(t.name,m.definition COLLATE DATABASE_DEFAULT)>0))
        THROW 51047, N'发现外部 SQL 模块文本引用，停止。', 1;
    IF EXISTS (SELECT 1 FROM sys.synonyms s WHERE EXISTS
               (SELECT 1 FROM @targets t WHERE PARSENAME(s.base_object_name,1) COLLATE DATABASE_DEFAULT=t.name
                  AND ISNULL(PARSENAME(s.base_object_name,2),N'dbo')=N'dbo'
                  AND ISNULL(PARSENAME(s.base_object_name,3),DB_NAME())=DB_NAME()))
        THROW 51048, N'发现外部同义词引用，停止。', 1;
    IF EXISTS (SELECT 1 FROM sys.triggers WHERE parent_class=0 AND is_disabled=0)
        THROW 51049, N'数据库有启用的 DDL 触发器，停止。', 1;

    DECLARE @sql nvarchar(max);
    -- 两个目标视图先删除；loss 在 stock 前，兼容旧视图间可能存在的依赖。
    SELECT @sql=STRING_AGG(CONVERT(nvarchar(max),N'DROP VIEW dbo.'+QUOTENAME(name)+N';'),CHAR(10))
       WITHIN GROUP (ORDER BY name) FROM @existing WHERE kind='V';
    IF @sql IS NOT NULL EXEC sys.sp_executesql @sql;

    -- 只拆除两端均属于旧表清单的内部外键，处理自引用和循环引用。
    SELECT @sql=STRING_AGG(CONVERT(nvarchar(max),N'ALTER TABLE dbo.'+QUOTENAME(c.name)
       +N' DROP CONSTRAINT '+QUOTENAME(f.name)+N';'),CHAR(10))
    FROM sys.foreign_keys f JOIN @existing c ON c.object_id=f.parent_object_id
      JOIN @existing p ON p.object_id=f.referenced_object_id;
    IF @sql IS NOT NULL EXEC sys.sp_executesql @sql;

    SELECT @sql=STRING_AGG(CONVERT(nvarchar(max),N'DROP TABLE dbo.'+QUOTENAME(name)+N';'),CHAR(10))
       WITHIN GROUP (ORDER BY name) FROM @existing WHERE kind='U';
    IF @sql IS NOT NULL EXEC sys.sp_executesql @sql;

    IF EXISTS (SELECT 1 FROM sys.objects o JOIN @targets t
               ON o.schema_id=SCHEMA_ID(N'dbo') AND o.name COLLATE DATABASE_DEFAULT=t.name)
        THROW 51050, N'仍有目标对象未删除，事务回滚。', 1;
    COMMIT TRANSACTION;
    SELECT name,kind AS object_type FROM @existing ORDER BY kind,name;
    SELECT SUM(CASE WHEN kind='U' THEN 1 ELSE 0 END) AS dropped_tables,
           SUM(CASE WHEN kind='V' THEN 1 ELSE 0 END) AS dropped_views FROM @existing;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
