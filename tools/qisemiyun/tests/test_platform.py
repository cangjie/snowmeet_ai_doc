import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import platform_support as platform

class PlatformTests(unittest.TestCase):
    def test_default_data_home_outside_repository(self):
        for name in ['win32','darwin']:
            home=platform.data_home(platform=name,environ={})
            self.assertFalse(home.is_relative_to(platform.REPO_ROOT))
        with self.assertRaises(RuntimeError):platform.data_home(environ={'QISE_HOME':str(BASE/'data')})

    def test_macos_keychain_store_has_no_plaintext_file(self):
        values={};backend=Mock()
        backend.set_password.side_effect=lambda service,account,value:values.update({(service,account):value})
        backend.get_password.side_effect=lambda service,account:values.get((service,account))
        with tempfile.TemporaryDirectory() as temp:
            store=platform.SessionStore(temp,platform='darwin',backend=backend)
            with self.assertRaises(FileNotFoundError):store.load()
            value={'Token':'synthetic-session','UserId':'synthetic-user'}
            store.save(value);self.assertEqual(store.load(),value)
            self.assertEqual(list(Path(temp).iterdir()),[])

    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI')
    def test_windows_native_dpapi_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            store=platform.SessionStore(temp)
            value={'Token':'synthetic-session-not-a-real-token'}
            store.save(value)
            self.assertNotIn(value['Token'].encode(),store.path.read_bytes())
            self.assertEqual(store.load(),value)

    def test_macos_adapter_discovery_ignores_vpn(self):
        with patch.object(platform.sys,'platform','darwin'),patch.object(platform.socket,'if_nameindex',return_value=[(1,'lo0'),(2,'en0'),(3,'utun4')]),patch.object(platform.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'192.0.2.10\n','')) as call:
            self.assertEqual(platform.physical_adapters(),[{'address':'192.0.2.10','interface':'en0'}])
            self.assertEqual(call.call_args.args[0],['/usr/sbin/ipconfig','getifaddr','en0'])

    def test_interface_binding_preserves_tls_and_closes_failed_socket(self):
        failed=Mock();failed.connect.side_effect=OSError('unreachable');working=Mock()
        candidates=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('192.0.2.20',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('192.0.2.21',443))]
        with patch.object(platform.socket,'getaddrinfo',return_value=candidates),patch.object(platform.socket,'socket',side_effect=[failed,working]),patch.object(platform.socket,'if_nametoindex',return_value=7):
            result=platform.bound_socket(('example.invalid',443),12,('192.0.2.10',0),'en0')
            self.assertIs(result,working);failed.close.assert_called_once()
            working.setsockopt.assert_called_with(socket.IPPROTO_IP,25,7)
            working.bind.assert_called_with(('192.0.2.10',0))
        with patch.object(platform.sys,'platform','darwin'):
            connection=platform.http_connection('example.invalid',source_ip='192.0.2.10',interface='en0')
            self.assertTrue(connection._context.check_hostname)
            self.assertNotEqual(connection._context.verify_mode,0)
            connection.close()

    @unittest.skipUnless(sys.platform=='darwin','macOS native interface binding')
    def test_macos_native_bound_socket_on_loopback(self):
        server=socket.socket();server.settimeout(5);server.bind(('127.0.0.1',0));server.listen(1)
        thread=threading.Thread(target=lambda:server.accept()[0].close(),daemon=True);thread.start()
        try:
            client=platform.bound_socket(server.getsockname(),5,('127.0.0.1',0),'lo0');client.close();thread.join(5)
            self.assertFalse(thread.is_alive())
        finally:server.close()

class FinanceTests(unittest.TestCase):
    def test_csv_round_trip_empty_table_and_formula_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp)/'data';data.mkdir()
            row={'ReceiveId':'demo-receipt','AmtCurReceive':-7.5,'Remark':'=1+1','Items':[{'name':'demo'}]}
            (data/'receipts.jsonl').write_text(json.dumps(row)+'\n',encoding='utf-8');(data/'payments.jsonl').write_text('',encoding='utf-8')
            env=os.environ.copy();env['QISE_OUTPUT_ROOT']=temp
            result=subprocess.run([sys.executable,str(BASE/'write_finance.py')],env=env,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            import csv
            with (data/'native/receipts.csv').open(encoding='utf-8-sig',newline='') as stream:actual=list(csv.DictReader(stream))
            self.assertEqual(actual[0]['Remark'],"'=1+1");self.assertEqual(actual[0]['AmtCurReceive'],'-7.5')
            self.assertEqual(json.loads((data/'native_status/payments.json').read_text())['count'],0)

if __name__=='__main__':unittest.main()
