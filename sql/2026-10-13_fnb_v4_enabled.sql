-- Separate reversible suspension from logical deletion.
-- Apply before deploying the accompanying API/H5 changes.
-- valid=0 remains deleted. No existing valid values or business rows are changed.
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @tables TABLE (name sysname NOT NULL PRIMARY KEY);
    INSERT INTO @tables(name) VALUES
      (N'fnb_v4_category'), (N'fnb_v4_item'), (N'fnb_v4_item_form'),
      (N'fnb_v4_purchase_spec'), (N'fnb_v4_shelf_life_rule'), (N'fnb_v4_dish_spec'),
      (N'fnb_v4_area'), (N'fnb_v4_supply'), (N'fnb_v4_tool'), (N'fnb_v4_check_item');
    DECLARE @name sysname, @sql nvarchar(max);
    WHILE EXISTS (SELECT 1 FROM @tables)
    BEGIN
        SELECT TOP (1) @name = name FROM @tables ORDER BY name;
        IF OBJECT_ID(N'dbo.' + @name, N'U') IS NULL
            THROW 51000, N'Expected v4 master table is missing; migration rolled back.', 1;
        IF COL_LENGTH(N'dbo.' + @name, N'enabled') IS NULL
        BEGIN
            SET @sql = N'ALTER TABLE dbo.' + QUOTENAME(@name)
                + N' ADD [enabled] bit NOT NULL CONSTRAINT '
                + QUOTENAME(N'DF_' + @name + N'_enabled') + N' DEFAULT CAST(1 AS bit) WITH VALUES;';
            EXEC sys.sp_executesql @sql;
        END
        ELSE IF NOT EXISTS (
            SELECT 1 FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(N'dbo.' + @name) AND c.name = N'enabled'
              AND t.name = N'bit' AND c.is_nullable = 0
        )
            THROW 51001, N'Existing enabled column has an unexpected definition; migration rolled back.', 1;
        DELETE FROM @tables WHERE name = @name;
    END;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
