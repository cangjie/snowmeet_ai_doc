"""Actual LocalDB checks for the v4 soft-delete utility; never opens another database."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / ".claude" / "skills" / "fnb-clear-test-data" / "scripts" / "clear_test_data.py"
spec = importlib.util.spec_from_file_location("food_clear", SCRIPT)
clear = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = clear
spec.loader.exec_module(clear)


def verify_lifecycle():
    # Use an isolated skill copy: never retire the real installed skill.
    class UnreachableConnection:
        def cursor(self):
            raise AssertionError("Retired skill accessed database")
    original = clear.LIFECYCLE_PATH
    with tempfile.TemporaryDirectory(prefix="fnb-skill-lifecycle-") as folder:
        root = Path(folder)
        script = root / "scripts" / SCRIPT.name
        script.parent.mkdir()
        shutil.copyfile(SCRIPT, script)
        clear.LIFECYCLE_PATH = root / "lifecycle.json"
        try:
            for state in (None, {"version": 1, "status": "unexpected"}, {"version": 1, "status": "retired"}):
                if state is None:
                    clear.LIFECYCLE_PATH.unlink(missing_ok=True)
                else:
                    clear.save_manifest(clear.LIFECYCLE_PATH, state)
                try:
                    clear.run(UnreachableConnection(), "never-connect", root / "manifest.json", True)
                except ValueError as error:
                    assert "lifecycle" in str(error) or "retired" in str(error)
                else:
                    raise AssertionError("Disabled skill accepted cleanup")
            clear.save_manifest(clear.LIFECYCLE_PATH, {"version": 1, "status": "testing", "retired_at": None, "reason": None})
            clear.require_testing()
            def cli(*args):
                return subprocess.run([sys.executable, "-X", "utf8", str(script), *args], capture_output=True, text=True, encoding="utf-8", timeout=30)
            assert json.loads(cli("--status").stdout)["status"] == "testing"
            retired = cli("--retire")
            assert retired.returncode == 0, retired.stderr
            first = clear.lifecycle()
            assert first["status"] == "retired" and first["retired_at"]
            assert cli("--retire").returncode == 0
            assert clear.lifecycle() == first
            for mode in ([], ["--execute"]):
                result = cli(*mode, "--manifest", str(root / "must-not-exist.json"))
                assert result.returncode == 1 and "retired" in result.stderr, result
                assert not (root / "must-not-exist.json").exists()
        finally:
            clear.LIFECYCLE_PATH = original
    print("临时 skill：缺失/无效/作废状态在连接数据库前拒绝；正式上线退役可重复，预览/执行全部禁用")


def snapshot(cur, names):
    return {name: sorted([tuple(str(v) for v in row) for row in cur.execute("SELECT * FROM dbo." + clear.quote(name))]) for name in names}


def columns(cur, table):
    return {r[0] for r in cur.execute("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(?)", "dbo." + table)}


def insert(cur, table, values):
    # Fill required non-default columns from the real EF DDL, keeping fixture ids isolated.
    required = list(cur.execute("SELECT c.name,t.name,c.max_length FROM sys.columns c JOIN sys.types t ON t.user_type_id=c.user_type_id WHERE c.object_id=OBJECT_ID(?) AND c.is_nullable=0 AND c.is_identity=0 AND c.is_computed=0 AND c.default_object_id=0 AND t.name NOT IN ('timestamp','rowversion')", "dbo." + table))
    for name, kind, length in required:
        if name not in values:
            if kind in ("varchar", "nvarchar", "char", "nchar", "text", "ntext"):
                values[name] = "proof"[:max(1, length // (2 if kind.startswith("n") else 1))]
            elif kind in ("binary", "varbinary"):
                values[name] = bytes(32)
            elif kind in ("datetime", "datetime2", "date", "smalldatetime"):
                values[name] = "2026-10-06"
            elif kind == "uniqueidentifier":
                values[name] = "10000000-0000-0000-0000-000000000001"
            else:
                values[name] = 1
    if "valid" in columns(cur, table):
        values.setdefault("valid", 1)
    names = ",".join(map(clear.quote, values))
    key = "session_key" if table == "mini_session" else "id"
    cur.execute(f"INSERT INTO dbo.{clear.quote(table)} ({names}) OUTPUT INSERTED.{clear.quote(key)} VALUES ({','.join('?' for _ in values)})", *values.values())
    return cur.fetchone()[0]


def expect_failure(connection, database, manifest, message):
    try:
        clear.run(connection, database, manifest, execute=True)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("Expected refusal: " + message)


def verify(connection, ef):
    verify_lifecycle()
    cur = connection.cursor()
    database = cur.execute("SELECT DB_NAME()").fetchval()
    assert database.startswith("snowmeet_fnb_test_")
    # Production got valid on every v4 table on 2026-10-12; apply the same additive script (twice: it must be repeatable).
    add_valid = (HERE.parent.parent / "sql" / "2026-10-12_fnb_v4_add_valid.sql").read_text(encoding="utf-8")
    for _ in range(2):
        cur.execute(add_valid)
        while cur.nextset():
            pass
    # The runner already seeded a category to verify that repeated DDL preserves data.
    existing_categories = list(cur.execute("SELECT id,valid FROM dbo.fnb_v4_category"))
    existing_live_categories = [key for key, valid in existing_categories if valid is None or valid]

    # Real personal and other-business rows: none of them may change.
    staff = insert(cur, "staff", {"name": "real-staff", "gender": "male"})
    shop = insert(cur, "shop_list", {"name": "real-shop"})
    member = insert(cur, "member", {})
    social = insert(cur, "social_account_for_job", {"member_id": member, "cell": "13900000001", "wechat_mini_openid": "real-openid"})
    insert(cur, "staff_social_account", {"staff_id": staff, "social_account_id": social})
    insert(cur, "member_social_account", {"member_id": member, "type": "wecom", "num": "real-wecom"})
    insert(cur, "mini_session", {"session_key": "real-session", "session_type": "wecom_userid"})
    food_category = insert(cur, "category", {"name": "test-food", "biz_type": "餐饮"})
    food_product = insert(cur, "product", {"name": "food", "type": "餐饮", "category_id": food_category})
    food_order = insert(cur, "order", {"type": "餐饮", "staff_id": staff, "member_id": member})
    food_upload = insert(cur, "mini_upload", {"file_path_name": "/upload/20261006/food.jpg", "purpose": "食材批次", "staff_id": staff, "thumb": "/upload/20261006/food_thumb.jpg", "is_web": 1})

    # Real v4 schema with all 18 first-phase tables populated, including self-referencing chains.
    parent = insert(cur, "fnb_v4_category", {"level": 1, "name": "raw", "is_prepared": 0, "sort": 0})
    child = insert(cur, "fnb_v4_category", {"parent_id": parent, "level": 2, "name": "milk", "batch_code": "M", "measure_type": "volume", "default_storage": "chilled", "is_prepared": 0, "sort": 0})
    # Already disabled before the run: must keep its own timestamp.
    disabled = insert(cur, "fnb_v4_category", {"level": 1, "name": "already-off", "is_prepared": 0, "sort": 0, "valid": 0, "updated_at": "2026-01-01"})
    item = insert(cur, "fnb_v4_item", {"category_id": child, "name": "milk", "item_type": "raw", "base_unit_code": "ml", "image_id": food_upload})
    form = insert(cur, "fnb_v4_item_form", {"item_id": item, "seq": 0, "name": "final", "unit_name": "ml", "per_base": 1, "storage_type": "chilled", "form_code": "F"})
    upper = insert(cur, "fnb_v4_item_form", {"item_id": item, "seq": 1, "name": "upper", "unit_name": "bottle", "per_base": 1000, "storage_type": "chilled", "form_code": "U", "in_op_name": "open", "in_op_ratio": 1000, "in_op_yield": 1, "in_op_hours": 0})
    purchase = insert(cur, "fnb_v4_purchase_spec", {"item_id": item, "entry_form_id": upper, "name": "bottle", "sort": 0})
    batch_values = {"shop_id": shop, "item_id": item, "form_id": form, "state": "final", "quantity": 100, "amount": 1, "storage_type": "chilled", "expire_date": "2026-10-10", "expiry_source": "manual", "spec_id": purchase}
    batch = insert(cur, "fnb_v4_batch", {**batch_values, "batch_no": "M-F-1"})
    batch2 = insert(cur, "fnb_v4_batch", {**batch_values, "batch_no": "M-F-2", "parent_batch_id": batch})
    cur.execute("INSERT INTO fnb_v4_batch_image(batch_id,upload_id) VALUES (?,?)", batch, food_upload)
    insert(cur, "fnb_v4_shelf_life_rule", {"item_id": item, "storage_type": "chilled", "season": "all", "days": 3})
    dish = insert(cur, "fnb_v4_dish_spec", {"shop_id": shop, "product_id": food_product, "spec_code": "default", "name": "dish", "is_default": 1})
    recipe = insert(cur, "fnb_v4_recipe", {"shop_id": shop, "recipe_type": "dish", "dish_spec_id": dish, "output_qty": 1, "version_no": 1, "status": "draft", "created_by_staff_id": staff})
    insert(cur, "fnb_v4_recipe_line", {"recipe_id": recipe, "item_id": item, "quantity": 1, "sort": 0})
    kitchen = insert(cur, "fnb_v4_order", {"shop_id": shop, "source_type": "manual", "sales_order_id": food_order, "display_no": "K1", "order_status": "pending", "refund_status": "none", "review_status": "pending"})
    insert(cur, "fnb_v4_order_line", {"order_id": kitchen, "dish_spec_id": dish, "recipe_id": recipe, "line_key": "1", "option_key": "", "item_name": "dish", "quantity": 1, "cancelled_qty": 0, "is_inventory_line": 1})
    insert(cur, "fnb_v4_order_import", {"shop_id": shop, "source_method": "internal", "dedupe_key": "1", "order_id": kitchen, "process_status": "pending"})
    doc = insert(cur, "fnb_v4_stock_document", {"shop_id": shop, "document_no": "D1", "document_type": "op", "status": "draft", "source_client": "wecom", "created_by_staff_id": staff, "order_id": kitchen, "recipe_id": recipe})
    line = insert(cur, "fnb_v4_stock_document_line", {"document_id": doc, "shop_id": shop, "line_no": 1, "item_id": item, "item_name": "milk", "direction": 1, "input_qty": 1, "input_unit_name": "ml", "input_to_base": 1, "actual_qty": 1, "actual_amount": 1, "specified_batch_id": batch, "spec_id": purchase, "form_id": form})
    insert(cur, "fnb_v4_stock_movement", {"document_line_id": line, "shop_id": shop, "item_id": item, "batch_id": batch, "direction": 1, "quantity": 1, "amount": 1, "balance_qty": 1, "balance_amount": 1})
    insert(cur, "fnb_v4_stock_operation", {"document_id": doc, "item_id": item, "from_form_id": upper, "to_form_id": form, "source_batch_id": batch, "output_batch_id": batch2, "op_name": "open", "input_qty": 1, "std_ratio": 1, "std_yield": 1, "expected_qty": 1, "actual_qty": 1, "loss_base_qty": 0, "duration_hours": 0, "status": "done", "staff_id": staff})
    insert(cur, "fnb_v4_stocktake_line", {"document_id": doc, "shop_id": shop, "item_id": item, "system_qty": 1, "snapshot_fingerprint": bytes(32)})

    # Full backend extension: all thirteen operation tables.
    area = insert(cur, "fnb_v4_area", {"shop_id": shop, "name": "warehouse", "area_type": "warehouse", "sort": 0})
    leaf = insert(cur, "fnb_v4_area", {"shop_id": shop, "parent_id": area, "name": "shelf", "area_type": "warehouse", "sort": 0})
    cur.execute("INSERT INTO fnb_v4_area_image(area_id,upload_id,staff_id,created_at) VALUES (?,?,?,SYSUTCDATETIME())", area, food_upload, staff)
    cur.execute("INSERT INTO fnb_v4_batch_detail(batch_id,area_id) VALUES (?,?)", batch, leaf)
    cur.execute("INSERT INTO fnb_v4_request(shop_id,action,request_id,payload_hash,response_json,staff_id,created_at) VALUES (?,'test',NEWID(),REPLICATE('0',64),'{}',?,SYSUTCDATETIME())", shop, staff)
    supply = insert(cur, "fnb_v4_supply", {"shop_id": shop, "name": "cup", "supply_type": "disposable", "pack_label": "pack", "pack_size": 50, "area_id": leaf, "quantity": 100, "last_receipt_qty": 100})
    insert(cur, "fnb_v4_supply_movement", {"supply_id": supply, "movement_type": "in", "input_qty": 2, "quantity": 100, "balance_qty": 100, "cancelled": 0, "staff_id": staff})
    tool = insert(cur, "fnb_v4_tool", {"shop_id": shop, "name": "grinder", "asset_no": "K1", "quantity": 1, "area_id": leaf, "status": "normal", "daily_check": 1, "owner_staff_id": staff})
    insert(cur, "fnb_v4_tool_log", {"tool_id": tool, "from_status": "normal", "to_status": "normal", "to_area_id": leaf, "staff_id": staff})
    ci = insert(cur, "fnb_v4_check_item", {"area_id": leaf, "name": "temperature", "kind": "environment", "method": "number", "required": 1, "photo_suggested": 1})
    sheet = insert(cur, "fnb_v4_check_sheet", {"shop_id": shop, "status": "submitted", "fingerprint": "0" * 64, "started_by": staff})
    cl = insert(cur, "fnb_v4_check_line", {"sheet_id": sheet, "item_id": ci, "snapshot_json": "{}", "active": 1, "result": "abnormal", "reason": "test", "upload_id": food_upload, "bulk": 0, "staff_id": staff})
    insert(cur, "fnb_v4_check_handling", {"line_id": cl, "remark": "fixed", "staff_id": staff})
    cur.execute("INSERT INTO fnb_v4_alert_delivery(batch_id,business_date,status,attempted_at,receivers) VALUES (?,CONVERT(date,SYSUTCDATETIME()),'success',SYSUTCDATETIME(),'test')", batch)

    all_tables = sorted(r[0] for r in cur.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')"))
    v4 = [name for name in all_tables if name.startswith(clear.PREFIX)]
    with_valid = [name for name in v4 if "valid" in columns(cur, name)]
    without_valid = [name for name in v4 if name not in with_valid]
    assert len(v4) == 31 and with_valid == v4 and not without_valid, (len(v4), without_valid)
    before = snapshot(cur, all_tables)
    assert all(before[name] for name in v4), [name for name in v4 if not before[name]]
    with tempfile.TemporaryDirectory(prefix="food-clear-test-") as folder:
        root = Path(folder)
        preview = clear.run(connection, database, root / "preview.json")
        assert snapshot(cur, all_tables) == before
        assert preview["database_state"] == "preview"
        assert sorted(preview["tables"]) == with_valid and sorted(preview["skipped_no_valid"]) == without_valid
        assert all(preview["tables"][name]["to_invalidate"] > 0 for name in with_valid)
        assert preview["tables"]["fnb_v4_category"] == {"rows": len(existing_categories) + 3, "to_invalidate": len(existing_live_categories) + 2, "stamp_columns": ["updated_at"]}
        assert preview["tables"]["fnb_v4_tool"]["stamp_columns"] == [] and preview["tables"]["fnb_v4_supply"]["stamp_columns"] == []
        assert sorted(name for name in with_valid if preview["tables"][name]["stamp_columns"]) == sorted(name for name in v4 if "updated_at" in columns(cur, name))
        assert preview["skipped_no_valid"] == {}
        print(f"逻辑删除脚本：预览只读，{len(with_valid)} 张 v4 表全部列入处理")

        expect_failure(connection, "wrong-database", root / "wrong.json", "Unexpected database")
        cur.execute("CREATE TRIGGER dbo.reset_guard ON dbo.fnb_v4_item AFTER UPDATE AS THROW 51099, 'should not run', 1")
        expect_failure(connection, database, root / "trigger.json", "Enabled DML trigger")
        cur.execute("DROP TRIGGER dbo.reset_guard")
        cur.execute("CREATE SCHEMA food_side")
        cur.execute("CREATE TABLE food_side.fnb_v4_shadow(id int PRIMARY KEY, valid bit NOT NULL)")
        expect_failure(connection, database, root / "schema.json", "outside dbo")
        cur.execute("DROP TABLE food_side.fnb_v4_shadow")
        cur.execute("DROP SCHEMA food_side")
        cur.execute("CREATE TABLE dbo.fnb_v4_odd(id int PRIMARY KEY, valid varchar(5) NOT NULL)")
        expect_failure(connection, database, root / "type.json", "Unexpected valid column type")
        cur.execute("DROP TABLE dbo.fnb_v4_odd")
        # A future v4 table without valid is reported and left alone, not refused.
        cur.execute("CREATE TABLE dbo.fnb_v4_plain(id int PRIMARY KEY)")
        cur.execute("INSERT INTO dbo.fnb_v4_plain VALUES (1)")
        assert clear.run(connection, database, root / "plain.json")["skipped_no_valid"] == {"fnb_v4_plain": 1}
        cur.execute("DROP TABLE dbo.fnb_v4_plain")
        assert snapshot(cur, all_tables) == before
        print("逻辑删除脚本：错库、触发器、非 dbo 的 v4 表、valid 类型异常均拒绝，没有 valid 的 v4 表只报告，全部数据保留")

        # Tables are updated in name order; a constraint on fnb_v4_tool fails after all the earlier ones were changed.
        cur.execute("ALTER TABLE dbo.fnb_v4_tool ADD CONSTRAINT reset_block CHECK (valid=1)")
        try:
            clear.run(connection, database, root / "rollback.json", True)
        except ValueError as error:
            raise AssertionError("Expected a database error, got refusal: " + str(error))
        except Exception:
            pass
        else:
            raise AssertionError("Expected constraint failure")
        cur.execute("ALTER TABLE dbo.fnb_v4_tool DROP CONSTRAINT reset_block")
        assert snapshot(cur, all_tables) == before
        assert json.loads((root / "rollback.json").read_text(encoding="utf-8"))["database_state"] == "prepared"
        print("逻辑删除脚本：按表名顺序更新到 fnb_v4_tool 时注入失败，此前各表的更新全部回滚")

        identities = {r[0]: str(r[1]) for r in cur.execute("SELECT OBJECT_NAME(object_id),CONVERT(nvarchar(50),last_value) FROM sys.identity_columns")}
        result = clear.run(connection, database, root / "clear.json", True)
        after = snapshot(cur, all_tables)
        assert result["database_state"] == "committed"
        stamp = result["stamp_utc"]
        for name in with_valid:
            done = result["invalidated"][name]
            assert done["count"] == preview["tables"][name]["to_invalidate"] == len(done["keys"]), name
            assert len(after[name]) == len(before[name]), name
            assert cur.execute(f"SELECT COUNT(*) FROM dbo.{clear.quote(name)} WHERE valid<>0").fetchval() == 0, name
            if "updated_at" in columns(cur, name):
                assert cur.execute(f"SELECT COUNT(*) FROM dbo.{clear.quote(name)} WHERE updated_at=CONVERT(datetime2(3),?,121)", stamp).fetchval() == done["count"], name
        assert sorted(result["invalidated"]["fnb_v4_category"]["keys"]) == sorted(existing_live_categories + [parent, child])
        assert tuple(cur.execute("SELECT valid,CONVERT(varchar(10),updated_at,120) FROM dbo.fnb_v4_category WHERE id=?", disabled).fetchone()) == (False, "2026-01-01")
        for name in all_tables:
            if name not in with_valid:
                assert after[name] == before[name], name
        assert {r[0]: str(r[1]) for r in cur.execute("SELECT OBJECT_NAME(object_id),CONVERT(nvarchar(50),last_value) FROM sys.identity_columns")} == identities
        repeat = clear.run(connection, database, root / "repeat.json", True)
        assert all(t["to_invalidate"] == 0 for t in repeat["tables"].values())
        assert all(t["count"] == 0 for t in repeat["invalidated"].values())
        assert snapshot(cur, all_tables) == after
        print("逻辑删除脚本：31 张 v4 表全部置 0，有更新时间列的同时刷新，原本无效的行不变；单位和其它业务逐行未变；无行被删除、ID 未重置，重复执行为 0 行")
