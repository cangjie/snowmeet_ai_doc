"""Verify guarded DROP and target-object backup/restore only in random LocalDB."""
import importlib.util
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('legacy_backup', HERE.parent / 'fnb' / 'backup_legacy_objects.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def verify(connection, sql):
    cur = connection.cursor()
    assert cur.execute('SELECT DB_NAME()').fetchval().startswith('snowmeet_fnb_test_')
    names = sorted(backup.TABLES)
    for name in names:
        if not cur.execute("SELECT OBJECT_ID(?, 'U')", 'dbo.'+name).fetchval():
            cur.execute('CREATE TABLE dbo.'+backup.quote(name)+' (id int IDENTITY PRIMARY KEY, proof nvarchar(40) NOT NULL, extra int NULL, changed rowversion)')
        if not cur.execute('SELECT COUNT(*) FROM dbo.'+backup.quote(name)).fetchval():
            cur.execute('INSERT INTO dbo.'+backup.quote(name)+" (proof) VALUES (N'餐饮测试')")
    cur.execute('ALTER TABLE dbo.fnb_recipe ADD CONSTRAINT CK_recipe_proof CHECK (extra IS NULL OR extra>=0)')
    cur.execute('CREATE INDEX IX_recipe_proof ON dbo.fnb_recipe(proof) INCLUDE(extra) WHERE extra IS NOT NULL')
    cur.execute('ALTER TABLE dbo.fnb_recipe ADD CONSTRAINT FK_recipe_self FOREIGN KEY(extra) REFERENCES dbo.fnb_recipe(id)')
    cur.execute('ALTER TABLE dbo.fnb_recipe_line ADD CONSTRAINT FK_recipe_line_cycle FOREIGN KEY(extra) REFERENCES dbo.fnb_recipe(id)')
    cur.execute('ALTER TABLE dbo.fnb_recipe ADD CONSTRAINT FK_recipe_cycle FOREIGN KEY(extra) REFERENCES dbo.fnb_recipe_line(id)')
    cur.execute('CREATE VIEW dbo.vw_fnb_material_stock WITH SCHEMABINDING AS SELECT id,proof FROM dbo.fnb_recipe')
    cur.execute('CREATE VIEW dbo.vw_fnb_material_loss AS SELECT id,proof FROM dbo.vw_fnb_material_stock')
    def object_names():
        return [tuple(r) for r in cur.execute("SELECT s.name,o.name,o.type FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE o.type IN ('U','V') ORDER BY s.name,o.name")]
    def data():
        # Restored rowversion values regenerate, so compare the original writable columns.
        return {n:[tuple(str(v) for v in r) for r in cur.execute('SELECT id,proof FROM dbo.'+backup.quote(n)+' ORDER BY id')] for n in names}
    def run(text):
        cur.execute(text)
        while cur.nextset(): pass
    before_objects = object_names()
    before_data = data()
    for guarded,code in (
        (sql.replace("DB_NAME() <> N'snowmeet_new' AND DB_NAME() NOT LIKE N'snowmeet[_]fnb[_]test[_]%'", '1=1'),'51040'),
        (sql.replace("DB_NAME() = N'snowmeet_new' AND ISNULL", '1=1 AND ISNULL'),'51042')):
        assert guarded!=sql
        try: run(guarded)
        except Exception as error: assert code in str(error), str(error)
        else: raise AssertionError('Expected database/backup guard refusal')
        assert object_names()==before_objects and data()==before_data
    cur.execute('BEGIN TRANSACTION')
    try:
        try: run(sql)
        except Exception as error: assert '51041' in str(error), str(error)
        else: raise AssertionError('Expected outer transaction refusal')
    finally:
        cur.execute('IF @@TRANCOUNT>0 ROLLBACK TRANSACTION')
    assert object_names()==before_objects and data()==before_data
    print('DROP：错库、未校验备份和已有外层事务在修改前拒绝')
    protected = {n:[tuple(str(v) for v in r) for r in cur.execute('SELECT * FROM dbo.'+backup.quote(n))] for n in ('fnb_unit','fnb_v4_category','staff','mini_upload','product','order')}
    def refuse(message):
        try: run(sql)
        except Exception as error:
            assert message in str(error), str(error)
        else: raise AssertionError('Expected DROP refusal')
        assert object_names()==before_objects or len(object_names())>len(before_objects)
        assert data()==before_data
    cur.execute('CREATE TABLE dbo.keep_reference(id int PRIMARY KEY, recipe_id int REFERENCES dbo.fnb_recipe(id))')
    refuse('51045')
    cur.execute('DROP TABLE dbo.keep_reference')
    cur.execute('CREATE VIEW dbo.keep_view AS SELECT id FROM dbo.fnb_recipe')
    refuse('51046')
    cur.execute('DROP VIEW dbo.keep_view')
    cur.execute("CREATE PROCEDURE dbo.keep_proc AS EXEC(N'SELECT * FROM dbo.fnb_recipe')")
    refuse('51047')
    cur.execute('DROP PROCEDURE dbo.keep_proc')
    cur.execute('CREATE SYNONYM dbo.keep_synonym FOR dbo.fnb_recipe')
    refuse('51048')
    cur.execute('DROP SYNONYM dbo.keep_synonym')
    cur.execute("CREATE TRIGGER drop_guard ON DATABASE FOR DROP_TABLE AS PRINT 'guard'")
    refuse('51049')
    cur.execute('DROP TRIGGER drop_guard ON DATABASE')
    assert object_names()==before_objects and data()==before_data
    print('DROP：外部外键、视图、动态 SQL、同义词、DDL 触发器均拒绝，旧对象与数据保留')
    injected = sql.replace('    IF EXISTS (SELECT 1 FROM sys.objects o JOIN @targets t', "    THROW 51991, N'Injected after DROP', 1;\n    IF EXISTS (SELECT 1 FROM sys.objects o JOIN @targets t")
    assert injected!=sql
    try: run(injected)
    except Exception as error: assert '51991' in str(error)
    else: raise AssertionError('Expected injected rollback')
    assert object_names()==before_objects and data()==before_data
    print('DROP：实际删除全部旧表及视图后注入异常，DDL 和数据全部回滚')
    with tempfile.TemporaryDirectory(prefix='fnb-drop-backup-') as folder:
        archive = Path(folder) / 'backup'
        result = backup.export(connection, archive)
        assert len(result['objects'])==20 and sum(result['row_counts'].values())>=18
        run(sql)
        after = object_names()
        assert len(before_objects)-len(after)==20
        assert all(n not in backup.TABLES|backup.VIEWS for s,n,t in after if s=='dbo')
        for n,values in protected.items():
            assert [tuple(str(v) for v in r) for r in cur.execute('SELECT * FROM dbo.'+backup.quote(n))]==values
        run(sql)
        assert object_names()==after
        print('DROP：仅删除 18 张旧表和 2 个视图；v4、单位、员工和共享表未变，重复执行成功')
        run((archive / 'restore.sql').read_text(encoding='utf-8'))
        assert object_names()==before_objects and data()==before_data
        assert cur.execute("SELECT COUNT(*) FROM sys.foreign_keys WHERE name IN ('FK_recipe_self','FK_recipe_cycle','FK_recipe_line_cycle')").fetchval()==3
        assert cur.execute("SELECT COUNT(*) FROM sys.indexes WHERE name='IX_recipe_proof'").fetchval()==1
        assert cur.execute("SELECT COUNT(*) FROM sys.check_constraints WHERE name='CK_recipe_proof'").fetchval()==1
        print('备份：结构、可写列数据、身份 ID、循环外键、CHECK、索引和视图在 LocalDB 恢复通过；rowversion 自动重建')
