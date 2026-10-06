"""Actual LocalDB checks for the destructive utility; never opens another database."""
import importlib.util
import json
from pathlib import Path
import re
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
                for operation in (lambda: clear.run(UnreachableConnection(), "never-connect", root / "manifest.json", True),
                                  lambda: clear.remove_files({}, root / "files.json")):
                    try:
                        operation()
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
            for mode in ([], ["--execute"], ["--resume-files"]):
                result = cli(*mode, "--manifest", str(root / "must-not-exist.json"))
                assert result.returncode == 1 and "retired" in result.stderr, result
                assert not (root / "must-not-exist.json").exists()
        finally:
            clear.LIFECYCLE_PATH = original
    print("临时 skill：缺失/无效/作废状态在连接或文件删除前拒绝；正式上线退役可重复，预览/清理/文件重试全部禁用")


def snapshot(cur, names):
    return {name: sorted([tuple(str(v) for v in row) for row in cur.execute("SELECT * FROM dbo." + clear.quote(name))]) for name in names}


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
    if "valid" in {r[0] for r in cur.execute("SELECT name FROM sys.columns WHERE object_id=OBJECT_ID(?)", table)}:
        values.setdefault("valid", 1)
    columns = ",".join(map(clear.quote, values))
    key = "session_key" if table == "mini_session" else "id"
    cur.execute(f"INSERT INTO dbo.{clear.quote(table)} ({columns}) OUTPUT INSERTED.{clear.quote(key)} VALUES ({','.join('?' for _ in values)})", *values.values())
    return cur.fetchone()[0]


def expect_failure(connection, database, manifest, message):
    try:
        clear.run(connection, database, manifest, execute=True, file_remover=lambda *_: None)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("Expected refusal: " + message)


def verify(connection, ef):
    verify_lifecycle()
    cur = connection.cursor()
    database = cur.execute("SELECT DB_NAME()").fetchval()
    assert database.startswith("snowmeet_fnb_test_")
    # Reuse this random test database only; add real EF definitions for shared children.
    blocks = {m.group(1): m.group(0) for m in re.finditer(r"CREATE TABLE \[(\w+)\] \(.*?^\);", ef, re.S | re.M)}
    for name in ("product_image", "fd_order", "order_payment", "payment_refund", "product_stock", "order_online", "order_online_detail", "payment_share", "order_share_relation"):
        if not cur.execute("SELECT OBJECT_ID(?, 'U')", "dbo." + name).fetchval():
            lines = [line for line in blocks[name].splitlines() if "FOREIGN KEY" not in line]
            cur.execute(re.sub(r",\s*\n\);", "\n);", "\n".join(lines)))
    cur.execute("ALTER TABLE dbo.fd_order ADD CONSTRAINT reset_fd_product FOREIGN KEY(product_id) REFERENCES dbo.product(id), CONSTRAINT reset_fd_order FOREIGN KEY(order_id) REFERENCES dbo.[order](id)")
    cur.execute("ALTER TABLE dbo.product_image ADD CONSTRAINT reset_img_product FOREIGN KEY(product_id) REFERENCES dbo.product(id), CONSTRAINT reset_img_upload FOREIGN KEY(upload_id) REFERENCES dbo.mini_upload(id)")
    cur.execute("ALTER TABLE dbo.order_payment ADD CONSTRAINT reset_payment_order FOREIGN KEY(order_id) REFERENCES dbo.[order](id)")
    cur.execute("ALTER TABLE dbo.order_payment ADD CONSTRAINT reset_payment_online FOREIGN KEY(order_id) REFERENCES dbo.order_online(id)")
    cur.execute("ALTER TABLE dbo.payment_share ADD CONSTRAINT reset_share_payment FOREIGN KEY(payment_id) REFERENCES dbo.order_payment(id)")
    cur.execute("ALTER TABLE dbo.payment_refund ADD CONSTRAINT reset_refund_order FOREIGN KEY(order_id) REFERENCES dbo.[order](id)")
    cur.execute("ALTER TABLE dbo.product ADD CONSTRAINT reset_product_category FOREIGN KEY(category_id) REFERENCES dbo.category(id)")

    staff = insert(cur, "staff", {"name": "real-staff", "gender": "male"})
    shop = insert(cur, "shop_list", {"name": "real-shop"})
    member = insert(cur, "member", {})
    social = insert(cur, "social_account_for_job", {"member_id": member, "cell": "13900000001", "wechat_mini_openid": "real-openid"})
    insert(cur, "staff_social_account", {"staff_id": staff, "social_account_id": social})
    insert(cur, "member_social_account", {"member_id": member, "type": "wecom", "num": "real-wecom"})
    insert(cur, "mini_session", {"session_key": "real-session", "session_type": "wecom_userid"})
    food_category = insert(cur, "category", {"name": "test-food", "biz_type": "餐饮"})
    other_category = insert(cur, "category", {"name": "real-ski", "biz_type": "租赁"})
    food_product = insert(cur, "product", {"name": "food", "type": "餐饮", "category_id": food_category})
    other_product = insert(cur, "product", {"name": "ski", "type": "租赁", "category_id": other_category})
    food_order = insert(cur, "order", {"type": "餐饮", "staff_id": staff, "member_id": member})
    other_order = insert(cur, "order", {"type": "租赁", "staff_id": staff, "member_id": member})
    food_online = insert(cur, "order_online", {"type": "餐饮"})
    other_online = insert(cur, "order_online", {"type": "租赁"})
    insert(cur, "order_online_detail", {"order_online_id": food_online, "product_id": food_product})
    insert(cur, "order_online_detail", {"order_online_id": other_online, "product_id": other_product})
    insert(cur, "order_share_relation", {"staff_id": staff, "name": "real-payment-account", "type": "staff"})
    food_upload = insert(cur, "mini_upload", {"file_path_name": "/upload/20261006/food.jpg", "purpose": "食材批次", "staff_id": staff, "thumb": "/upload/20261006/food_thumb.jpg", "is_web": 1})
    other_upload = insert(cur, "mini_upload", {"file_path_name": "/upload/20261006/staff.jpg", "purpose": "员工个人资料", "staff_id": staff, "is_web": 1})
    insert(cur, "product_image", {"product_id": food_product, "upload_id": food_upload})
    insert(cur, "product_image", {"product_id": other_product, "upload_id": other_upload})
    insert(cur, "fd_order", {"order_id": food_order, "product_id": food_product})
    insert(cur, "fd_order", {"order_id": other_order, "product_id": other_product})
    food_payment = insert(cur, "order_payment", {"order_id": food_order, "staff_id": staff})
    other_payment = insert(cur, "order_payment", {"order_id": other_order, "staff_id": staff})
    insert(cur, "payment_share", {"payment_id": food_payment})
    insert(cur, "payment_share", {"payment_id": other_payment})
    insert(cur, "payment_refund", {"order_id": food_order})
    insert(cur, "payment_refund", {"order_id": other_order})

    # Real v4 schema with all 18 tables populated, including self-referencing chains.
    parent = insert(cur, "fnb_v4_category", {"level": 1, "name": "raw", "is_prepared": 0, "sort": 0})
    child = insert(cur, "fnb_v4_category", {"parent_id": parent, "level": 2, "name": "milk", "batch_code": "M", "measure_type": "volume", "default_storage": "chilled", "is_prepared": 0, "sort": 0})
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

    # Full backend extension: all thirteen new tables and their protected staff references.
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

    existing = {r[0] for r in cur.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')")}
    # Add missing legacy business tables with real FK edges to exercise ordering as well.
    for name in sorted(clear.FOOD_TABLES - existing):
        cur.execute(f"CREATE TABLE dbo.{clear.quote(name)} (id int IDENTITY PRIMARY KEY, staff_id int NULL, proof varchar(40) NOT NULL)")
        cur.execute(f"INSERT INTO dbo.{clear.quote(name)} (staff_id,proof) VALUES (?, 'food-test')", staff)
    cur.execute("ALTER TABLE dbo.fnb_stock_movement ADD legacy_item int NULL")
    cur.execute("ALTER TABLE dbo.fnb_stock_movement ADD CONSTRAINT reset_legacy_item FOREIGN KEY(legacy_item) REFERENCES dbo.fnb_material_item(id)")
    cur.execute("ALTER TABLE dbo.fnb_stocktake_line ADD movement_id int NULL")
    cur.execute("ALTER TABLE dbo.fnb_stocktake_line ADD CONSTRAINT reset_legacy_count FOREIGN KEY(movement_id) REFERENCES dbo.fnb_stock_movement(id)")
    cur.execute("UPDATE dbo.fnb_stock_movement SET legacy_item=1; UPDATE dbo.fnb_stocktake_line SET movement_id=1")
    all_tables = sorted(r[0] for r in cur.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')"))
    before = snapshot(cur, all_tables)
    with tempfile.TemporaryDirectory(prefix="food-clear-test-") as folder:
        root = Path(folder)
        preview = clear.run(connection, database, root / "preview.json")
        assert snapshot(cur, all_tables) == before
        assert all(preview["counts"][name] > 0 for name in clear.FOOD_TABLES)
        assert preview["file_keys"] == ["upload/20261006/food.jpg", "upload/20261006/food_thumb.jpg"]
        print(f"清理脚本：全部 {len(clear.FOOD_TABLES)} 张食材表 + 餐饮商品/订单/上传预览，只读且个人数据未变")
        expect_failure(connection, "wrong-database", root / "wrong.json", "Unexpected database")
        cur.execute("CREATE TABLE dbo.staff_private_file(id int PRIMARY KEY, upload_id int REFERENCES dbo.mini_upload(id))")
        cur.execute("INSERT INTO dbo.staff_private_file VALUES (1,?)", food_upload)
        expect_failure(connection, database, root / "shared.json", "Unscoped reference")
        cur.execute("DROP TABLE dbo.staff_private_file")
        assert snapshot(cur, all_tables) == before
        shared_img = insert(cur, "product_image", {"product_id": other_product, "upload_id": food_upload})
        expect_failure(connection, database, root / "shared-image.json", "Unscoped reference")
        cur.execute("DELETE FROM dbo.product_image WHERE id=?", shared_img)
        mixed_line = insert(cur, "fd_order", {"order_id": food_order, "product_id": other_product})
        expect_failure(connection, database, root / "mixed.json", "Mixed food/non-food")
        cur.execute("DELETE FROM dbo.fd_order WHERE id=?", mixed_line)
        # Food offline payment must not silently resolve to a different online business.
        cur.execute("UPDATE dbo.order_online SET type=? WHERE id=?", "租赁", food_online)
        cur.execute("UPDATE dbo.order_online_detail SET product_id=? WHERE order_online_id=?", other_product, food_online)
        expect_failure(connection, database, root / "payment-namespace.json", "Ambiguous payment")
        cur.execute("UPDATE dbo.order_online SET type=? WHERE id=?", "餐饮", food_online)
        cur.execute("UPDATE dbo.order_online_detail SET product_id=? WHERE order_online_id=?", food_product, food_online)
        cur.execute("UPDATE dbo.mini_upload SET thumb='/upload/20261006/food.jpg' WHERE id=?", other_upload)
        expect_failure(connection, database, root / "path.json", "File also used outside")
        cur.execute("UPDATE dbo.mini_upload SET thumb=NULL WHERE id=?", other_upload)
        cur.execute("CREATE TRIGGER dbo.reset_guard ON dbo.fnb_v4_item AFTER DELETE AS THROW 51099, 'should not run', 1")
        expect_failure(connection, database, root / "trigger.json", "Enabled DML trigger")
        cur.execute("DROP TRIGGER dbo.reset_guard")
        cur.execute("CREATE TABLE dbo.fnb_future(id int PRIMARY KEY)")
        expect_failure(connection, database, root / "future.json", "Unreviewed food tables")
        cur.execute("DROP TABLE dbo.fnb_future")
        assert snapshot(cur, all_tables) == before
        print("清理脚本：错库、员工文件引用、共用路径、触发器、未知食材表均拒绝，全部数据保留")

        original = clear.Scope.clear
        def fail_midway(self, order):
            for t in order[:3]:
                self.cur.execute(f"DELETE a FROM {t.sql} a JOIN {t.temp} s ON {clear.key_join(t,'a','s')}")
            raise ValueError("injected-failure")
        clear.Scope.clear = fail_midway
        try:
            expect_failure(connection, database, root / "rollback.json", "injected-failure")
        finally:
            clear.Scope.clear = original
        assert snapshot(cur, all_tables) == before
        print("清理脚本：实际删除前三表后注入失败，事务全部回滚")

        calls = []
        identities = {r[0]: str(r[1]) for r in cur.execute("SELECT OBJECT_NAME(object_id),CONVERT(nvarchar(50),last_value) FROM sys.identity_columns")}
        result = clear.run(connection, database, root / "clear.json", True, file_remover=lambda m, p: calls.append(m["database_state"]))
        assert calls == ["committed"]
        for name in clear.FOOD_TABLES:
            assert cur.execute("SELECT COUNT(*) FROM dbo." + clear.quote(name)).fetchval() == 0, name
        for name, ident in (("product", other_product), ("order", other_order), ("order_online", other_online), ("mini_upload", other_upload), ("category", other_category)):
            assert cur.execute("SELECT COUNT(*) FROM dbo." + clear.quote(name)).fetchval() == 1, name
            assert cur.execute("SELECT id FROM dbo." + clear.quote(name)).fetchval() == ident
        for name in all_tables:
            if name not in clear.ALLOWED:
                assert snapshot(cur, [name])[name] == before[name], name
        assert {r[0]: str(r[1]) for r in cur.execute("SELECT OBJECT_NAME(object_id),CONVERT(nvarchar(50),last_value) FROM sys.identity_columns")} == identities
        # A fresh connection avoids transaction-scoped temp names surviving a commit.
        for t in clear.catalog(cur)[0].values():
            if t.name in clear.ALLOWED:
                cur.execute(f"IF OBJECT_ID('tempdb..{t.temp}') IS NOT NULL DROP TABLE {t.temp}")
        repeat = clear.run(connection, database, root / "repeat.json", True, file_remover=lambda *_: None)
        assert sum(repeat["counts"].values()) == 0
        print("清理脚本：食材新旧表/单位/关联商品订单上传全空，其它业务与真实个人信息逐行未变；重复执行成功、ID 未重置")
        verify_files(root)


def verify_files(root):
    class FakeS3:
        def __init__(self): self.deleted = []; self.fail = True
        def get_paginator(self, name): assert name == "list_object_versions"; return self
        def paginate(self, **kwargs):
            key = kwargs["Prefix"]
            yield {"Versions": [{"Key": key, "VersionId": "v1"}, {"Key": key + ".other", "VersionId": "keep"}], "DeleteMarkers": [{"Key": key, "VersionId": "d1"}]}
        def delete_object(self, **kwargs):
            if self.fail: self.fail = False; raise RuntimeError("S3 failure")
            self.deleted.append((kwargs["Key"], kwargs.get("VersionId")))
    from hashlib import sha256
    key = "upload/20261006/food.jpg"
    webroot = root / "wwwroot"
    target = webroot / key
    target.parent.mkdir(parents=True)
    target.write_bytes(b"food")
    keep = target.with_name("staff.jpg")
    keep.write_bytes(b"personal")
    manifest = {"database_state": "committed", "file_keys": [key], "file_keys_sha256": sha256(key.encode()).hexdigest(), "bucket": clear.BUCKET, "local_app_root": str(root), "files_done": []}
    path = root / "files.json"
    clear.save_manifest(path, manifest)
    s3 = FakeS3()
    try: clear.remove_files(manifest, path, s3=s3)
    except RuntimeError: pass
    else: raise AssertionError("Expected file failure")
    assert target.exists() and not manifest["files_done"]
    clear.remove_files(manifest, path, s3=s3)
    assert not target.exists() and keep.read_bytes() == b"personal"
    assert s3.deleted == [(key, "v1"), (key, "d1")]
    assert clear.local_target(str(root), "private/upload/20261006/private.jpg") == root / "upload/20261006/private.jpg"
    for bad in ("/upload/../staff.jpg", "/upload//staff.jpg", "https://evil.example/upload/20261006/x.jpg", "/upload/20261006/x%2f.jpg", "C:\\personal.jpg"):
        try: clear.normalize_path(bad, True)
        except ValueError: pass
        else: raise AssertionError("Unsafe file accepted: " + bad)
    print("文件清理：仅模拟 S3；精确对象及全部版本删除、失败重试、本地副本清理通过，个人文件/邻近对象保留，非法路径拒绝")
