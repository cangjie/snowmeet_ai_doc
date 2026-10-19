import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import run as runner

class RunnerTests(unittest.TestCase):
    def test_public_asset_with_unquoted_attributes(self):
        for html in ['<script src=https://cdn-web.qisemiyun.com/js/app.123.js></script>',
                     '<script src="//cdn-web.qisemiyun.com/js/app.123.js"></script>']:
            self.assertEqual(runner.application_asset(html),'https://cdn-web.qisemiyun.com/js/app.123.js')

    def test_effective_config_keeps_full_history_and_new_identity(self):
        modules,jobs=runner.configured({'UserId':'test-user','ContactId':'test-contact','SOBId':'test-sob'})
        by_name={m['name']:m for m in modules}
        for name in ['sales','purchases','loans_out','stocktaking','other_inbound']:
            self.assertEqual(by_name[name]['payload']['IsShowWriteBack'],1)
        self.assertEqual(by_name['stock']['payload']['UserId'],'test-user')
        self.assertEqual(by_name['employees_all']['payload']['SOBId'],'test-sob')
        self.assertIsNone(by_name['employees_all']['payload']['UserType'])
        self.assertEqual(next(j for j in jobs if j['name']=='stock')['payload']['UserId'],'test-user')

    def test_dry_run_has_no_network_or_snapshot_writes(self):
        output=io.StringIO()
        with patch.object(runner,'network',side_effect=AssertionError('network called')),patch.object(runner,'authenticated',side_effect=AssertionError('login called')),contextlib.redirect_stdout(output):
            runner.collect(SimpleNamespace(scope='full',dry_run=True))
        plan=json.loads(output.getvalue())
        self.assertFalse(plan['network_requests'])
        self.assertFalse(Path(plan['fresh_snapshot']).exists())
        commands=[x['command'][1] for x in plan['steps']]
        self.assertLess(next(i for i,c in enumerate(commands) if c.endswith('stock_movements.py')),next(i for i,c in enumerate(commands) if c.endswith('augment.py')))
        self.assertIn('--verify-only',next(x['command'] for x in plan['steps'] if x['command'][1].endswith('finalize.py')))

    def test_child_scripts_use_isolated_data_root_and_shared_encrypted_session(self):
        with tempfile.TemporaryDirectory() as temp:
            env=os.environ.copy();env.update(QISE_OUTPUT_ROOT=temp,QISE_SOURCE_IP='192.0.2.10')
            code="import json,sys;sys.path.insert(0,sys.argv[1]);from client import ROOT;from platform_support import data_home;print(json.dumps([str(ROOT),str(data_home())]))"
            result=subprocess.run([sys.executable,'-c',code,str(BASE)],env=env,capture_output=True,text=True,check=True)
            root,home=json.loads(result.stdout)
            self.assertEqual(Path(root),Path(temp));self.assertFalse(Path(home).is_relative_to(BASE.parents[1]))
            self.assertFalse((Path(root)/'data').exists())

    def test_second_process_cannot_enter_run_lock(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(runner,'HOME',Path(temp)):
            script="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import run;run.HOME=Path(sys.argv[2]);\ntry:\n with run.run_lock():sys.exit(9)\nexcept RuntimeError:sys.exit(0)"
            with runner.run_lock():
                result=subprocess.run([sys.executable,'-c',script,str(BASE),temp])
                self.assertEqual(result.returncode,0)
            with runner.run_lock():pass

    def test_inventory_packaging_uses_snapshot_and_omits_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'new-run';data=root/'data';(data/'status').mkdir(parents=True)
            (data/'pages').mkdir();(data/'pages/old-cache.json').write_text('{"obsolete":true}')
            (root/'session.dpapi').write_bytes(b'fake-session-not-for-export')
            db=sqlite3.connect(data/'qisemiyun.sqlite3')
            db.execute('CREATE TABLE records (module TEXT,record_id TEXT,data TEXT,PRIMARY KEY(module,record_id))')
            for module in ['products_all','warehouses','stock','stock_by_warehouse']:
                (data/(module+'.jsonl')).write_text('{"id":"new"}\n',encoding='utf-8')
                db.execute('INSERT INTO records VALUES (?,?,?)',(module,'new','{"id":"new"}'))
            db.commit();db.close()
            (data/'status/stock_by_warehouse.json').write_text(json.dumps({'state':'complete','warehouses':1,'reconciliation_differences':[]}))
            runner.finish_inventory(root)
            result=json.loads((root/'package-verification.json').read_text(encoding='utf-8'))
            self.assertTrue(result['verified'])
            with zipfile.ZipFile(result['archive']) as z:
                self.assertIsNone(z.testzip())
                self.assertNotIn('pages/old-cache.json',z.namelist())
                self.assertFalse(any('session.dpapi' in x for x in z.namelist()))
                self.assertEqual(json.loads(z.read('stock.jsonl')),{'id':'new'})

if __name__=='__main__':unittest.main()
