import gzip,io,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from staging import key,number,scrub,dt
from schema import TABLES,ddl
from stream_package import StreamStage

class ValueTests(unittest.TestCase):
    def test_negative_decimal_and_fractional_stock(self):
        self.assertEqual(number('-2.125'),'-2.125000')
        self.assertEqual(number('1,234.05'),'1234.050000')
        with self.assertRaises(ValueError):number('0.1234567')
        with self.assertRaises(ValueError):number('10000000000000')

    def test_dates_preserve_business_and_creation_distinction(self):
        self.assertEqual(dt('2027-02-22'),'2027-02-22T00:00:00.000')
        self.assertEqual(dt('2026-10-19T08:00:00',utc=True),'2026-10-19T00:00:00.000')
        self.assertIsNone(dt('not-a-date'))

    def test_source_identity_is_not_document_number(self):
        self.assertIsNone(key('00000000-0000-0000-0000-000000000000'))
        self.assertEqual(key('ABC001'),'ABC001')
        self.assertEqual(key('AABBCCDD-0000-0000-0000-000000000001'),'aabbccdd-0000-0000-0000-000000000001')

    def test_scrub_secrets_without_dropping_business_properties(self):
        r=scrub({'Password':'example','SaleNo':'0001','Property3':'26.5','list':[{'AccessToken':'example','amount':-2}],'url':'https://example.test/a?token=example&size=26.5'})
        self.assertEqual(r,{'SaleNo':'0001','Property3':'26.5','list':[{'amount':-2}],'url':'https://example.test/a?size=26.5'})

    def test_schema_scope_and_delete_contract(self):
        self.assertEqual(len(TABLES),37)
        for table,cols in TABLES.items():
            self.assertTrue(table.startswith('qsm_'))
            self.assertTrue({'valid','deleted_at','deleted_by','delete_reason','row_version'}<=set(cols))
        generated=ddl()
        self.assertNotIn('DROP TABLE',generated)
        self.assertNotIn('DELETE FROM',generated)
        self.assertIn('ON DELETE NO ACTION',generated)

    def test_old_storage_sdk_body_without_context_manager(self):
        class Body:
            def __init__(self,data):self.buffer=io.BytesIO(data);self.closed=False
            def read(self,n=-1):return self.buffer.read(n)
            def close(self):self.closed=True;self.buffer.close()
        body=Body(gzip.compress(b'{"id":1}\n'))
        class Client:
            def get_object(self,**kwargs):return {'Body':body}
        stage=StreamStage({'bucket':'test','tables':{'qsm_source':{'object_key':'test.gz'}}},s3_client=Client())
        self.assertEqual([json.loads(s) for s in stage.lines('qsm_source')],[{'id':1}])
        self.assertTrue(body.closed)

if __name__=='__main__':unittest.main()
