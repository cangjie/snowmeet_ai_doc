"""Build the initial full import privately. No database connections or live scraping."""
import collections,hashlib,json,mimetypes,re,uuid
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from staging import Stage,js,key,get,bit,number,dt,utcnow,sha_file

VERSION='qsm-initial-v1'
DOC_TYPES={'purchases':'purchase','purchase_returns':'purchase_return','purchase_orders':'purchase_order','sales':'sale','sales_returns':'sale_return','sales_orders':'sale_order','sales_drafts':'sale_draft','transfers':'transfer','stocktaking':'stocktake','loans_in':'loan_in','loans_out':'loan_out','inbound':'inbound','outbound':'outbound','other_inbound':'other_inbound','other_outbound':'other_outbound','assembly':'assembly','cost_adjustments':'cost_adjustment','receipts':'receipt','payments':'payment','daily_income_expenses':'income_expense','account_transfers':'account_transfer','writeoffs':'writeoff','client_stored_orders':'client_stored_order','client_stored_movements':'client_stored_movement','client_points':'client_points'}
BUSINESS_TYPES={'1':'purchase','2':'purchase_return','3':'sale','4':'sale_return','5':'stocktake','7':'transfer','8':'loan_in','9':'loan_out','10':'loan_in_return','11':'loan_out_return','14':'receipt','15':'payment'}
ID_FIELDS={'purchase':'BuyId','purchase_order':'BuyId','purchase_return':'ReturnId','sale':'SaleId','sale_return':'ReturnId','sale_order':'SaleId','sale_draft':'SaleId','transfer':'TranId','stocktake':'TakBillId','loan_in':'LendId','loan_out':'LendId','loan_in_return':'ReturnId','loan_out_return':'ReturnId','receipt':'ReceiveId','payment':'PaymentId','outbound':'IOId','inbound':'IOId'}
NO_FIELDS={'purchase':'BuyNo','purchase_order':'BuyNo','purchase_return':'ReturnNo','sale':'SaleNo','sale_return':'ReturnNo','sale_order':'SaleNo','sale_draft':'SaleNo','transfer':'TranNo','stocktake':'TakBillNo','loan_in':'LendNo','loan_out':'LendNo','loan_in_return':'ReturnNo','loan_out_return':'ReturnNo','receipt':'ReceiveNo','payment':'PaymentNo','outbound':'IONo','inbound':'IONo'}
DATE_FIELDS={'purchase':'BuyDate','purchase_order':'BuyDate','purchase_return':'ReturnDate','sale':'SaleDate','sale_return':'ReturnDate','sale_order':'SaleDate','sale_draft':'SaleDate','transfer':'TranDate','stocktake':'TakingDate','loan_in':'LendDate','loan_out':'LendDate','loan_in_return':'ReturnDate','loan_out_return':'ReturnDate','receipt':'BusiDate','payment':'BusiDate','outbound':'IODate','inbound':'IODate'}

def log(stage,**data):print(js({'stage':stage,**data}),flush=True)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def lines(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        for s in f:
            if s.strip():yield json.loads(s)

class Prepare:
    def __init__(self,data,out,resume_raw=False):
        self.data=Path(data).resolve();self.out=Path(out).resolve();self.out.mkdir(parents=True,exist_ok=True)
        self.s=Stage(self.out/'staged.sqlite3',resume_raw);self.modules={};self.files={};self.file_plan={};self.file_paths={};self.master={};self.documents={};self.versions={};self.details={};self.doc_rows={};self.sku_codes=collections.defaultdict(set);self.stock_meta={};self.doc_no=collections.defaultdict(list);self.source_keys={};self.line_keys={};self.issues=collections.Counter();self.unit_ratios={};self.name_cache={}
        self.registry=read(Path(__file__).resolve().parents[3]/'docs/qisemi/database-source-map.json')
        self.config={x['name']:x for x in read(Path(__file__).resolve().parents[1]/'config/modules.json')}

    def issue(self,code,summary,raw=None,entity=None,details=None,severity='warning'):
        fingerprint=hashlib.sha256(js([code,raw,entity,details]).encode()).hexdigest()
        if fingerprint in self.source_keys:return
        self.source_keys[fingerprint]=True;self.issues[code]+=1
        self.s.add('data_issue',batch_id=1,raw_record_id=raw,issue_key=fingerprint,issue_code=code,severity=severity,entity_table=entity[0] if entity else None,entity_id=entity[1] if entity else None,summary=summary,details_json=js(details or {}))

    def module(self,name,carrier,state='complete',count=None,coverage=None,file=None):
        mid=self.s.add('import_module',batch_id=1,module_key=name,carrier=carrier,state=state,expected_count=count,actual_count=count,file_hash=sha_file(file) if file else None,coverage_json=js(coverage or {}))
        self.modules[name]=mid;return mid

    def file(self,path):
        path=Path(path).resolve()
        if not path.is_relative_to(self.data):raise ValueError('File escapes snapshot directory')
        relative=path.relative_to(self.data).as_posix()
        if relative in self.file_paths:return self.file_paths[relative]
        digest=sha_file(path)
        if digest not in self.files:
            fid=self.s.add('file',content_sha256=digest,byte_length=path.stat().st_size,mime_type=mimetypes.guess_type(path.name)[0],extension=path.suffix.lower(),storage_provider='private_disk',object_key='datasets/'+self.fingerprint+'/'+relative,first_seen_batch_id=1,availability_state='ready')
            self.files[digest]=fid
            self.file_plan[digest]={'id':fid,'source':str(path),'relative_path':relative,'object_key':'datasets/'+self.fingerprint+'/'+relative,'sha256':digest,'bytes':path.stat().st_size}
        self.file_paths[relative]=self.files[digest]
        return self.files[digest]

    def initialize(self):
        verify=read(self.data/'verification.json');manifest=read(self.data/'manifest.json')
        if verify.get('sqlite_integrity')!='ok' or verify.get('movement_source_document_missing_ids'):raise ValueError('Source verification incomplete')
        paths=sorted(self.data.glob('*.jsonl'))+sorted((self.data/'native_rows').glob('*.jsonl'))+[self.data/'media/index.jsonl']
        fingerprint=[(p.relative_to(self.data).as_posix(),sha_file(p)) for p in paths]
        self.fingerprint=hashlib.sha256(js(fingerprint).encode()).hexdigest()
        history=next(lines(self.data/'sales_history_details.jsonl'))
        book=key(get(history,'SOBId'));company=key(get(history,'ContactId'))
        if not book or not company:raise ValueError('Source company/book not established')
        self.company,self.book=company,book
        self.s.add('source',company_key=company,book_key=book,display_name=verify.get('account') or manifest.get('account') or 'Qisemi')
        finish=dt(verify['completed_at'],utc=True)
        start=datetime.fromtimestamp(min(p.stat().st_mtime for p in paths),timezone.utc).replace(tzinfo=None).isoformat(timespec='milliseconds')
        self.s.add('import_batch',batch_key=str(uuid.uuid5(uuid.NAMESPACE_URL,self.fingerprint+VERSION)),scope='full',dataset_hash=self.fingerprint,parser_version=VERSION,capture_started_at=min(start,finish),capture_finished_at=finish,import_started_at=utcnow(),state='staging',manifest_json=js(manifest),verification_json=js(verify))
        self.s.info('source_fingerprint',self.fingerprint);self.s.info('data_dir',str(self.data));self.s.info('parser_version',VERSION)
        # Registered binary files are images/attachments and all original workbooks.
        for p in sorted((self.data/'media/files').glob('*')):
            if p.is_file():self.file(p)
        for p in sorted((self.data/'native').iterdir()):
            if p.suffix.lower() in ('.xls','.xlsx','.csv'):self.file(p)
        log('files_hashed',unique_contents=len(self.files))

    def raw_sources(self):
        for p in sorted(self.data.glob('*.jsonl')):
            name=p.stem;status_path=self.data/'status'/(name+'.json')
            status=read(status_path) if status_path.exists() else {}
            expected=read(self.data/'verification.json')['module_counts'].get(name)
            if status.get('state') not in (None,'complete'):raise ValueError('Incomplete API module '+name)
            count=sum(1 for _ in lines(p))
            if count!=expected:raise ValueError('Source row count mismatch '+name)
            mid=self.module(name,'api','complete' if count else 'empty',count,status,p)
            id_field=self.config.get(name,{}).get('id_field')
            hashes=collections.Counter()
            for i,row in enumerate(lines(p),1):
                src= get(row,id_field) if id_field else get(row,'SourceId','ProductId','productid')
                if name=='stock_by_warehouse':src=str(get(row,'WarehouseId'))+'|'+str(get(row,'productid'))
                h=hashlib.sha256(js(row).encode()).hexdigest();hashes[h]+=1
                self.s.add_raw(name,mid,1,i,row,src,duplicate=hashes[h])
            log('raw_module',module=name,rows=count)
        self.s.db.commit()
        for spec in self.registry['native_sheets']:
            name=spec['sheet_module'];p=self.data/'native_rows'/(name+'.jsonl');export,idx=name.rsplit('.',1)
            status=read(self.data/'native_status'/(export+'.json'));sheet=status['sheets'][int(idx)-1]
            actual_file=next(p for p in (self.data/'native').glob(export+'.*') if p.suffix in ('.xls','.xlsx','.csv'))
            count=sum(1 for _ in lines(p))
            if count!=sheet['rows']:raise ValueError('Native row count mismatch '+name)
            mid=self.module('native/'+name,'native_sheet','complete' if count else 'empty',count,sheet,p)
            sid=self.s.add('export_sheet',batch_id=1,module_id=mid,file_id=self.file(actual_file),export_key=export,sheet_index=int(idx),sheet_name=sheet['name'],sheet_role=spec['sheet_role'],headers_json=js(sheet['headers']),row_count=count,binding_state='unresolved')
            for i,row in enumerate(lines(p),1):self.s.add_raw('native/'+name,mid,1,i,row,get(row,'单据编号','商品编号','编号'),sheet_id=sid)
        p=self.data/'media/index.jsonl';count=sum(1 for _ in lines(p));mid=self.module('media/index.jsonl','media',count=count,file=p)
        for i,row in enumerate(lines(p),1):self.s.add_raw('media/index.jsonl',mid,1,i,row,get(row,'id'))
        metadata=[self.data/'manifest.json',self.data/'verification.json',self.data/'media/manifest.json',self.data/'media/documents.json']+sorted((self.data/'status').glob('*.json'))+sorted((self.data/'native_status').glob('*.json'))
        for p in metadata:
            name=p.relative_to(self.data).as_posix();value=read(p);mid=self.module(name,'metadata',count=1,file=p)
            self.s.add_raw(name,mid,1,1,value)
        mid=self.module('metadata/files','metadata',count=sum(1 for x in self.file_plan.values() if x['relative_path'].startswith('native/')))
        for i,entry in enumerate((x for x in self.file_plan.values() if x['relative_path'].startswith('native/')),1):
            rid=self.s.add_raw('metadata/files',mid,1,i,{k:v for k,v in entry.items() if k!='source'})
            self.s.add('file_ref',batch_id=1,raw_record_id=rid,reference_key='export:'+str(i),file_id=entry['id'],reference_kind='export',original_name=Path(entry['relative_path']).name,download_state='complete')
        self.s.db.commit();log('raw_complete',rows=self.s.seq['qsm_raw_record'],modules=len(self.modules))

    def ref(self,t,source_key,name=None,kind=None,raw=None,required=False):
        source_key=key(source_key)
        if not source_key:return None
        cache_key=(t,kind,source_key)
        if cache_key in self.master:return self.master[cache_key]
        values={'source_key':source_key,'name':name or '档案未取得','is_stub':1}
        if kind:values['category_kind' if t=='category' else 'partner_kind']=kind
        if raw:values.update(last_seen_batch_id=1,last_raw_record_id=raw)
        if t=='warehouse_position':return None
        id=self.s.add(t,**values);self.master[cache_key]=id
        self.issue('stub_'+t,'来源 ID 已取得，完整档案尚未取得',raw,('qsm_'+t,id),severity='blocker' if required else 'warning')
        return id

    def master_row(self,t,source_key,row,raw,kind=None,**fields):
        # A reserved all-zero GUID is a real source identity for the built-in role.
        original=source_key;source_key=key(source_key)
        if source_key is None and str(original)=='00000000-0000-0000-0000-000000000000':source_key=str(original)
        if not source_key:raise ValueError('Missing master source identity '+t)
        vals=dict(source_key=source_key,last_seen_batch_id=1,last_raw_record_id=raw,source_deleted=bit(get(row,'IsDel')),source_enabled=None if get(row,'IsStop') is None else 1-bit(get(row,'IsStop')) if bit(get(row,'IsStop')) is not None else None,source_state=str(get(row,'ProductState','UserStatus')) if get(row,'ProductState','UserStatus') is not None else None,source_created_at=dt(get(row,'CreateDate'),True),source_updated_at=dt(get(row,'UpdateDate'),True),is_stub=0,**fields)
        if kind:vals['category_kind' if t=='category' else 'partner_kind']=kind
        ck=(t,kind,source_key)
        if ck in self.master:
            id=self.master[ck];self.s.update(t,id,**vals)
        else:id=self.s.add(t,**vals);self.master[ck]=id
        return id

    def masters(self):
        for raw,_,r in self.s.raw('branches'):
            self.master_row('branch',get(r,'BranchId'),r,raw,name=get(r,'BranchName') or '未命名门店',code=get(r,'BranchCode'),address=get(r,'BranchAddress'),telephone=get(r,'BranchTel'),branch_type=str(get(r,'BranchType')) if get(r,'BranchType') is not None else None)
        for raw,_,r in self.s.raw('branches'):
            parent=key(get(r,'ParentBranch'))
            if parent and ('branch',None,parent) in self.master:self.s.update('branch',self.ref('branch',get(r,'BranchId')),parent_id=self.ref('branch',parent))
        for raw,_,r in self.s.raw('units'):
            self.master_row('unit',get(r,'UnitId'),r,raw,name=get(r,'UnitName') or '未命名单位',allows_decimal=bit(get(r,'IsDecimal')),remark=get(r,'UnitRemark'))
        for module,kind in [('product_classes_tree','product'),('client_classes','client'),('supplier_classes','supplier')]:
            for raw,_,r in self.s.raw(module):
                self.master_row('category',get(r,'ClassId','Id'),r,raw,kind=kind,name=get(r,'ClassName','title') or '未命名分类',sort=get(r,'ClassSort') or 100,branch_id=self.ref('branch',get(r,'BranchId'),raw=raw))
            for raw,_,r in self.s.raw(module):
                parent=key(get(r,'ParentClassId','ParentId'))
                if parent:
                    pid=self.ref('category',parent,kind=kind,raw=raw)
                    cid=self.ref('category',get(r,'ClassId','Id'),kind=kind)
                    if cid!=pid:self.s.update('category',cid,parent_id=pid)
        for raw,_,r in self.s.raw('warehouses'):
            self.master_row('warehouse',get(r,'WarehouseId'),r,raw,name=get(r,'WarehouseName') or '未命名仓库',code=get(r,'WarehouseCode'),branch_id=self.ref('branch',get(r,'BranchId'),get(r,'BranchName'),raw=raw),source_warehouse_type=str(get(r,'WarehouseType')) if get(r,'WarehouseType') is not None else None,sort=get(r,'ShowOrder') or 100)
        for module,kind in [('clients','client'),('suppliers','supplier')]:
            prefix='Client' if kind=='client' else 'Supplier'
            for raw,_,r in self.s.raw(module):
                self.master_row('partner',get(r,prefix+'Id'),r,raw,kind=kind,name=get(r,prefix+'Name') or '未命名往来单位',code=get(r,prefix+'Code'),category_id=self.ref('category',get(r,'ClassId'),get(r,'ClassName'),kind=kind,raw=raw),branch_id=self.ref('branch',get(r,'BranchId'),get(r,'BranchName'),raw=raw),contact_name=get(r,prefix+'Link'),telephone=get(r,prefix+'Tel'),address=get(r,prefix+'Address'),email=get(r,prefix+'Email'),remark=get(r,prefix+'Remark'),receivable=number(get(r,'ReceAmt')) if kind=='client' else None,payable=number(get(r,'PayAmt')) if kind=='supplier' else None,stored_amount=number(get(r,'TotalStoreAmt')),points=number(get(r,'TotalPoints')))
        for raw,_,r in self.s.raw('accounts_all'):
            self.master_row('account',get(r,'AccountId'),r,raw,name=get(r,'AccountName') or '未命名账户',branch_id=self.ref('branch',get(r,'BranchId'),raw=raw),short_name=get(r,'AccountSimpleName'),account_type=str(get(r,'AccountType')) if get(r,'AccountType') is not None else None,account_number=get(r,'AccountNumber'),bank_account_name=get(r,'BankAccountName'),initial_amount=number(get(r,'InitAmt')),current_amount=number(get(r,'TotalAmt')),remark=get(r,'AccountRemark'))
        for raw,_,r in self.s.raw('employees_all'):
            self.master_row('employee',get(r,'UserId'),r,raw,name=get(r,'UserName') or '未命名员工',branch_id=self.ref('branch',get(r,'BranchId'),raw=raw),login_name=get(r,'UserLoginName'),telephone=get(r,'UserPhone'),user_type=str(get(r,'UserType')) if get(r,'UserType') is not None else None,user_status=str(get(r,'UserStatus')) if get(r,'UserStatus') is not None else None,is_root=bit(get(r,'IsRoot')))
        for raw,_,r in self.s.raw('roles'):self.master_row('role',get(r,'RoleId'),r,raw,name=get(r,'RoleName') or '未命名角色',remark=get(r,'RoleDesc'))
        for raw,_,r in self.s.raw('projects'):self.master_row('project',get(r,'ProjectId'),r,raw,name=get(r,'ProjectName') or '未命名项目',remark=get(r,'ProjectRemark'))
        log('masters',registered=len(self.master))

    def products(self):
        for _,_,r in self.s.raw('stock'):self.stock_meta[key(get(r,'productid'))]=r
        group_cache={}
        for raw,_,r in self.s.raw('products_all'):
            units=r.get('UnitList') or [];basekey=key(get(r,'ProductUnit'));base_name=get(r,'ProductUnitName');product_key=key(r['ProductId'])
            if not basekey:raise ValueError('Product missing base unit')
            for u in units:
                uk=key(get(u,'UnitId'))
                if uk and ('unit',None,uk) not in self.master:
                    self.master_row('unit',uk,u,raw,name=get(u,'UnitName') or '单位未取得',allows_decimal=bit(get(u,'IsDecimal')))
            base=self.ref('unit',basekey,base_name,raw=raw,required=True)
            category=self.ref('category',get(r,'ClassId'),get(r,'ClassName'),kind='product',raw=raw)
            name=r.get('ProductName') or '未命名商品';size=None
            # Only classify a numeric boot size when corroborated by a separate
            # property, explicit boot name and exact trailing size token.
            candidate=str(r.get('Property3') or '').strip()
            boot='鞋' in name and r.get('Property1') and r.get('Property2')
            if boot and re.fullmatch(r'(?:[2-3]\d)(?:\.\d)?',candidate) and re.search(r'(?<![\d.])'+re.escape(candidate)+r'\s*$',name):size=candidate
            sku=self.master_row('product_sku',product_key,r,raw,name=name,code=get(r,'ProductCode'),barcode=get(r,'BarCode'),category_id=category,base_unit_id=base,source_main_product_key=key(get(r,'MainProductId')),season=get(r,'ProductForm'),size_label=size,size_sort=number(size,3) if size else None,shelf_state=str(get(r,'IsShelf')) if get(r,'IsShelf') is not None else None,remark=get(r,'ProductRemark'),search_text=' '.join(str(x) for x in [name,get(r,'ProductCode'),get(r,'BarCode'),get(r,'PropertyList'),get(r,'ProductForm')] if x))
            if get(r,'ProductCode'):self.sku_codes[str(get(r,'ProductCode'))].add(sku)
            for j in range(1,6):
                value=r.get('Property'+str(j))
                if value is not None:
                    semantic='size' if size and j==3 else None
                    self.s.add('sku_attribute',sku_id=sku,attribute_key='Property'+str(j),source_label=get(self.stock_meta.get(product_key,{}),'propertyname'+str(j)),semantic_key=semantic,value_text=str(value),sort=j,last_seen_batch_id=1,last_raw_record_id=raw,json_path='$.Property'+str(j))
            for j,f in enumerate(get(r,'FieldList') or []):
                self.s.add('sku_attribute',sku_id=sku,attribute_key='FieldList:'+str(j),value_json=js(f),sort=j+100,last_seen_batch_id=1,last_raw_record_id=raw,json_path=f'$.FieldList[{j}]')
            seen=set();has_base=False
            for j,u in enumerate(units):
                uk=key(get(u,'UnitId'));uid=self.ref('unit',uk,get(u,'UnitName'),raw=raw,required=True)
                if uid in seen:raise ValueError('Duplicate product unit')
                seen.add(uid);ratio=number(get(u,'UnitRatio'),9)
                if ratio is None or Decimal(ratio)<=0:raise ValueError('Missing/invalid unit conversion')
                is_base=1 if uk==basekey else 0
                if is_base and Decimal(ratio)!=1:raise ValueError('Base unit ratio is not one')
                has_base|=bool(is_base)
                self.s.add('sku_unit',sku_id=sku,unit_id=uid,ratio_to_base=ratio,is_base=is_base,allows_decimal=bit(get(u,'IsDecimal')),barcode=get(u,'BarCode'),sale_price=number(get(u,'SalePrice')),buy_price=number(get(u,'BuyPrice')),lower_price=number(get(u,'LowerPrice')),price_tiers_json=js({k:v for k,v in u.items() if k.startswith('PFPrice')}),last_seen_batch_id=1,last_raw_record_id=raw,json_path=f'$.UnitList[{j}]')
                self.unit_ratios[(sku,uid)]=ratio
            if not has_base:raise ValueError('Product base unit absent from UnitList')
            base_display=re.sub(re.escape(size)+r'\s*$','',name).rstrip() if size else name
            signature=[category,base,get(r,'ProductForm'),base_display,[(str(j),r.get('Property'+str(j))) for j in range(1,6) if j!=3 or not size]] if size else ['singleton',product_key]
            gh=hashlib.sha256(js(signature).encode()).hexdigest()
            if gh not in group_cache:
                style=self.s.add('product_style',style_key=str(uuid.uuid5(uuid.NAMESPACE_URL,gh)),display_name=base_display,brand=next((b for b in ['Fischer','Atomic','HEAD','Nordica','Salomon','Tecnica','Dalbello','Lange','Rossignol','K2','Burton'] if b.lower() in name.lower()),None),model=str(get(r,'Property1')) if size else None,style_code=str(get(r,'Property2')) if size else None,season=get(r,'ProductForm'),gender=str(get(r,'Property4')) if size and get(r,'Property4') else None,category_id=category,base_unit_id=base,group_signature=gh,group_method='rule' if size else 'singleton',rule_version='boot-size-conservative-v1',search_text=' '.join(str(x) for x in [base_display,get(r,'Property1'),get(r,'Property2'),get(r,'ProductForm')] if x))
                group_cache[gh]=style
            self.s.add('style_sku',style_id=group_cache[gh],sku_id=sku,assignment_method='rule' if size else 'singleton',rule_version='boot-size-conservative-v1',evidence_json=js({'rule':'separate_numeric_boot_size_and_exact_name_suffix' if size else 'insufficient_confirmed_variant_attributes','source_product_id':product_key,'raw_record_id':raw}))
        log('products',sku=self.s.seq['qsm_product_sku'],styles=self.s.seq['qsm_product_style'])

    def doc(self,typ,source_key,row,raw,historical=False):
        sk=key(source_key)
        if not sk:raise ValueError('Missing document identity '+typ)
        ck=(typ,sk)
        if ck not in self.documents:
            id=self.s.add('document',source_key=sk,last_seen_batch_id=1,last_raw_record_id=raw,document_type=typ,document_no=get(row,NO_FIELDS.get(typ,'BusinessNo')),listing_state='history_only' if historical else 'current',source_deleted=bit(get(row,'IsDel')),source_created_at=dt(get(row,'CreateDate'),True),source_updated_at=dt(get(row,'UpdateDate'),True))
            self.documents[ck]=id;self.doc_rows[ck]=(raw,row,historical)
        return self.documents[ck]

    def documents_prepare(self):
        capture_finished_at=self.s.get('import_batch',1)['capture_finished_at']
        supplements={'sales_multi_account_details':'sale','sales_order_details':'sale_order','sales_draft_details':'sale_draft','stocktaking_details':'stocktake','outbound_details':'outbound','receipts_details':'receipt','payments_details':'payment'}
        for module,typ in supplements.items():
            for raw,_,row in self.s.raw(module):
                body=row.get('Data',row)
                self.details[(typ,key(row.get('SourceId') or get(body,ID_FIELDS.get(typ,'Id'))))]=(raw,body,'$.Data' if 'Data' in row else '$')
        for module,typ in DOC_TYPES.items():
            for raw,_,row in self.s.raw(module):self.doc(typ,get(row,ID_FIELDS.get(typ,self.config.get(module,{}).get('id_field','Id'))),row,raw)
        for module,typ in [('sales_history_details','sale'),('purchases_history_details','purchase')]:
            for raw,_,r in self.s.raw(module):
                body=r.get('Data',r);sk=key(get(body,ID_FIELDS[typ]))
                self.doc(typ,sk,body,raw,True)
                self.details[(typ,sk)]=(raw,body,'$.Data' if 'Data' in r else '$')
        for module,typ in [('loans_in_return_details','loan_in_return'),('loans_out_return_details','loan_out_return')]:
            for raw,_,r in self.s.raw(module):
                body=r.get('Data',r);sk=key(get(body,'ReturnId'))
                self.doc(typ,sk,body,raw)
                self.details[(typ,sk)]=(raw,body,'$.Data')
        for ck,(raw,header,historical) in self.doc_rows.items():
            typ,sk=ck;did=self.documents[ck]
            supplement=self.details.get(ck)
            detail=supplement[1] if supplement else {}
            detail_header=detail.get('detail',detail)
            merged={**header,**detail_header}
            # Case-folded duplicate keys are not silently used to resolve identity.
            partner_kind='supplier' if typ.startswith('purchase') or typ=='payment' else 'client'
            partner_key=get(merged,'SupplierId') if partner_kind=='supplier' else get(merged,'ClientId')
            partner_name=get(merged,'SupplierName') if partner_kind=='supplier' else get(merged,'ClientName')
            if typ in ('loan_in','loan_out','loan_in_return','loan_out_return'):
                partner_key=get(merged,'CSId');partner_name=get(merged,'CSName')
                # Loan CSId may refer to either type; choose only an existing exact identity.
                hits=[(k,v) for k,v in self.master.items() if k[0]=='partner' and k[2]==key(partner_key)] if partner_key else []
                partner_id=hits[0][1] if len(hits)==1 else None
            else:partner_id=self.ref('partner',partner_key,partner_name,kind=partner_kind,raw=raw)
            amount_field={'purchase':'BuyAmt','purchase_order':'BuyAmt','purchase_return':'ReturnAmt','sale':'SaleAmt','sale_return':'ReturnAmt','sale_order':'SaleAmt','sale_draft':'SaleAmt','loan_in':'LendAmt','loan_out':'LendAmt','loan_in_return':'ReturnAmt','loan_out_return':'ReturnAmt','receipt':'AmtCurReceive','payment':'AmtCurPayment'}.get(typ)
            if amount_field=='SaleAmt' and get(merged,amount_field) is None:amount_field='ReceAmt'
            business=get(merged,DATE_FIELDS.get(typ,'BusiDate'),'businessdate')
            coverage={'product_lines':{'state':'not_acquired','count':0},'settlements':{'state':'not_provided','count':0},'writeoffs':{'state':'not_provided','count':0},'amount_source_field':amount_field,'header_raw_id':raw,'supplement_raw_id':supplement[0] if supplement else None}
            version=self.s.add('document_version',batch_id=1,raw_record_id=raw,document_id=did,revision_key=hashlib.sha256(js([typ,sk,header,detail]).encode()).hexdigest(),version_kind='historical' if historical else 'current',document_no=get(merged,NO_FIELDS.get(typ,'BusinessNo'),'businesscode'),business_at=dt(business),business_time_precision='date' if business and re.fullmatch(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',str(business)) else 'datetime' if dt(business) else 'unknown',branch_id=self.ref('branch',get(merged,'BranchId'),get(merged,'BranchName'),raw=raw),partner_id=partner_id,warehouse_id=self.ref('warehouse',get(merged,'WarehouseId'),get(merged,'WarehouseName'),raw=raw),from_warehouse_id=self.ref('warehouse',get(merged,'OutWarehouseId'),get(merged,'OutWarehouseName'),raw=raw),to_warehouse_id=self.ref('warehouse',get(merged,'InWarehouseId'),get(merged,'InWarehouseName'),raw=raw),business_employee_id=self.ref('employee',get(merged,'BusiUserId','SaleUser','BuyUser'),get(merged,'BusiUserName','SaleUserName','BuyUserName'),raw=raw),creator_employee_id=self.ref('employee',get(merged,'CreateUserId'),get(merged,'CreateUserName'),raw=raw),branch_name=get(merged,'BranchName'),partner_name=partner_name,warehouse_name=get(merged,'WarehouseName'),business_employee_name=get(merged,'BusiUserName','BusiUsername','SaleUserName','BuyUserName'),creator_name=get(merged,'CreateUserName','CreateUsername'),amount=number(get(merged,amount_field)) if amount_field else None,discount_amount=number(get(merged,'DiscountAmt')),tax_amount=number(get(merged,'TaxAmt')),other_fee=number(get(merged,'OtherFee')),settled_amount=number(get(merged,'RealPayAmt','TotalReceiveAmt')),unsettled_amount=number(get(merged,'NoWoAmt')),currency_code=get(merged,'Currency'),exchange_rate=number(get(merged,'ExchangeRate'),9),source_bill_state=str(get(merged,'BillState')) if get(merged,'BillState') is not None else None,source_io_state=str(get(merged,'IOState')) if get(merged,'IOState') is not None else None,source_payment_state=str(get(merged,'PayState','ReceState')) if get(merged,'PayState','ReceState') is not None else None,source_audit_state=str(get(merged,'AuditState')) if get(merged,'AuditState') is not None else None,write_back=bit(get(merged,'WriteBack')),is_multi_warehouse=bit(get(merged,'IsMultiWarehouse')),is_multi_account=bit(get(merged,'IsMultiAccount')),is_locked=bit(get(merged,'IsLocked')),source_created_at=dt(get(merged,'CreateDate'),True),source_updated_at=dt(get(merged,'UpdateDate'),True),source_update_count=get(merged,'UpdateTimes'),remark=get(merged,'SaleRemark','BuyRemark','ReturnRemark','TranRemark','BillRemark','ReceiveRemark','PaymentRemark','LendRemark','IORemark','detailremark'),inside_remark=get(merged,'InsideRemark'),detail_coverage_json=js(coverage))
            self.versions[ck]=version;self.s.update('document',did,current_version_id=version)
            no=get(merged,NO_FIELDS.get(typ,'BusinessNo'),'businesscode')
            if no:self.doc_no[(typ,str(no))].append(ck)
            if business and dt(business) and dt(business)>capture_finished_at[:10]+'T23:59:59.999':self.issue('future_business_date','来源业务日期晚于本次采集日期，原值保留',raw,('qsm_document_version',version))
            if supplement:
                arrays=[(k,v) for k,v in detail.items() if isinstance(v,list) and v and k in ['SaleDetails','BuyDetails','DetailList','BillDetailList','TakingDetails','ProductList','Details']]
                # Full details are authoritative for this version; never union them with native lines.
                if arrays:
                    field,items=arrays[0]
                    for j,item in enumerate(items,1):self.line(ck,supplement[0],item,j,supplement[2]+'.'+field+f'[{j-1}]','api')
                    self.cover(version,'product_lines','complete',len(items),'api')
                self.finances(ck,supplement[0],detail,supplement[2])
            if typ in ('loan_in_return','loan_out_return'):
                parent_type='loan_in' if typ=='loan_in_return' else 'loan_out';parent=key(get(merged,'LendId'))
                if parent:self.relation(ck,raw,parent_type,parent,'loan_return','$.LendId')
        self.s.db.commit();log('documents',identities=len(self.documents),versions=len(self.versions))

    def cover(self,version,section,state,count,carrier=None):
        r=self.s.get('document_version',version);coverage=json.loads(r['detail_coverage_json'])
        coverage[section]={'state':state,'count':count,'carrier':carrier}
        self.s.update('document_version',version,detail_coverage_json=js(coverage))

    def by_name(self,t,name):
        if not name:return None
        if t not in self.name_cache:
            index=collections.defaultdict(list)
            for r in self.s.rows(t):
                if not r.get('is_stub'):index[r.get('name')].append(r['id'])
            self.name_cache[t]=index
        hits=self.name_cache[t].get(name,[])
        return hits[0] if len(hits)==1 else None

    def line(self,ck,raw,item,no,path,carrier):
        version=self.versions[ck];typ=ck[0]
        product_key=key(get(item,'ProductId'));code=get(item,'ProductCode','商品编号');name=get(item,'ProductName','商品名称')
        sku=self.master.get(('product_sku',None,product_key)) if product_key else next(iter(self.sku_codes[str(code)])) if code is not None and len(self.sku_codes[str(code)])==1 else None
        unit_key=key(get(item,'ProductUnit','UnitId'))
        uid=self.master.get(('unit',None,unit_key)) if unit_key else self.by_name('unit',get(item,'UnitName','单位'))
        warehouse_key=key(get(item,'WarehouseId'));warehouse_name=get(item,'WarehouseName','出库仓库','入库仓库','进货仓库','仓库')
        wid=self.ref('warehouse',warehouse_key,warehouse_name,raw=raw) if warehouse_key else self.by_name('warehouse',warehouse_name)
        qty=get(item,'SaleCount','BuyCount','ReturnCount','TranCount','ProductCount','IOCount','LendCount','数量')
        ratio=number(get(item,'UnitRatio'),9)
        if ratio is None and sku and uid:
            ratio=self.unit_ratios.get((sku,uid))
        q=number(qty);base=number(Decimal(q)*Decimal(ratio)) if q is not None and ratio is not None else None
        source_detail=key(get(item,'Id','SaleDetailId','BuyDetailId','TakId','LendDetailId'))
        line_key=('source:'+source_detail) if source_detail else carrier+':'+str(raw)+':'+str(no)
        book=number(get(item,'TakSaveCount'));counted=number(get(item,'TakRealCount'))
        line_id=self.s.add('document_line',batch_id=1,raw_record_id=raw,json_path=path,document_version_id=version,line_key=line_key,source_detail_key=source_detail,line_no=no,line_kind='product',sku_id=sku,unit_id=uid,warehouse_id=wid,from_warehouse_id=self.by_name('warehouse',get(item,'调出仓库')),to_warehouse_id=self.by_name('warehouse',get(item,'调入仓库')),product_code=code,barcode=get(item,'BarCode','商品条码'),product_name=name,size_label=self.s.get('product_sku',sku)['size_label'] if sku else None,unit_name=get(item,'UnitName','ProductUnitName','单位'),properties_text=get(item,'PropertyList','Property','属性'),quantity=q,quantity_base=base,return_quantity=number(get(item,'ReturnCount','退货数量')) if typ not in ('purchase_return','sale_return','loan_in_return','loan_out_return') else None,unit_price=number(get(item,'SalePrice','BuyPrice','ReturnPrice','单价')),discount_rate=number(get(item,'DiscountRate','折扣')),discounted_price=number(get(item,'DiscountPrice','折后单价')),amount=number(get(item,'SaleAmt','BuyAmt','ReturnAmt','IOAmt','总额')),cost_price=number(get(item,'CostPrice','成本价')),cost_amount=number(get(item,'CostAmt','成本额')),tax_rate=number(get(item,'TaxRate')),tax_amount=number(get(item,'TaxAmt')),ratio_to_base=ratio,book_quantity=book,counted_quantity=counted,difference_quantity=number(Decimal(counted)-Decimal(book)) if book is not None and counted is not None else None,overage_amount=number(get(item,'OverageAmt')),shortage_amount=number(get(item,'ShortageAmt')),is_gift=bit(get(item,'IsGift')),remark=get(item,'SaleRemark','BuyRemark','ReturnRemark','IORemark','TakRemark','备注'),match_state='exact' if sku else 'ambiguous' if code and len(self.sku_codes[str(code)])>1 else 'unresolved')
        if source_detail:self.line_keys[(typ,ck[1],source_detail)]=line_id
        if not sku:self.issue('unmatched_line_sku','商品行无法唯一关联商品档案，原行完整保留',raw,('qsm_document_line',line_id))
        return line_id

    def relation(self,ck,raw,target_type,target_key,relation_type,path):
        target=self.documents.get((target_type,key(target_key)))
        self.s.add('document_relation',batch_id=1,raw_record_id=raw,json_path=path,from_document_id=self.documents[ck],from_version_id=self.versions[ck],to_document_id=target,relation_type=relation_type,target_document_type=target_type,target_source_key=key(target_key),relation_key=relation_type+':'+str(target_key),match_state='exact' if target else 'unresolved')

    def finances(self,ck,raw,body,prefix):
        # Source formats vary. Only explicitly identified account/allocation arrays are projected.
        version=self.versions[ck]
        def visit(node,path):
            if isinstance(node,dict):
                for k,v in node.items():
                    child=path+'.'+k
                    if isinstance(v,list) and k.lower() in ('accountlist','multiaccountlist','accountdetails','payaccountlist'):
                        count=0
                        for j,r in enumerate(v):
                            if not isinstance(r,dict):continue
                            account_key=get(r,'AccountId');amount=get(r,'Amount','Amt','PayAmt','ReceiveAmt','Payment')
                            if account_key is None and get(r,'AccountName') is None:continue
                            self.s.add('settlement_line',batch_id=1,raw_record_id=raw,json_path=child+f'[{j}]',document_version_id=version,line_key='account:'+child+':'+str(j),account_id=self.ref('account',account_key,get(r,'AccountName'),raw=raw),account_name=get(r,'AccountName'),direction='pay' if ck[0] in ('payment','purchase') else 'receive',amount=number(amount),payment_type=str(get(r,'PayType')) if get(r,'PayType') is not None else None)
                            count+=1
                        self.cover(version,'settlements','complete',count,'api')
                    elif isinstance(v,list) and k.lower() in ('hxlist','billdetail','writeofflist'):
                        count=0
                        for j,r in enumerate(v):
                            if not isinstance(r,dict):continue
                            target_key=key(get(r,'BusiId','BusinessId','SaleId','BuyId'));target_type=BUSINESS_TYPES.get(str(get(r,'BusiType','BusinessType')))
                            self.s.add('writeoff_line',batch_id=1,raw_record_id=raw,json_path=child+f'[{j}]',document_version_id=version,line_key='writeoff:'+child+':'+str(j),target_document_id=self.documents.get((target_type,target_key)),target_document_type=target_type,target_source_key=target_key,target_document_no=get(r,'BusiNo','BusinessCode','SaleNo','BuyNo'),allocated_amount=number(get(r,'WOAmt','WriteOffAmt','Amount','Amt')),discount_amount=number(get(r,'FavAmt')),remaining_amount=number(get(r,'RemainingAmt')),match_state='exact' if (target_type,target_key) in self.documents else 'unresolved')
                            count+=1
                        self.cover(version,'writeoffs','complete',count,'api')
                    visit(v,child)
            elif isinstance(node,list):
                for j,v in enumerate(node):visit(v,path+f'[{j}]')
        visit(body,prefix)

    def other_lines(self):
        counts=collections.Counter()
        for raw,_,r in self.s.raw('stocktaking_lines'):
            ck=('stocktake',key(get(r,'SourceTakBillId')))
            if ck not in self.versions:raise ValueError('Missing stocktake parent')
            if (ck[0],ck[1],key(get(r,'TakId'))) in self.line_keys:continue
            self.line(ck,raw,r,counts[ck]+1,'$','stocktaking_lines');counts[ck]+=1
        for ck,n in counts.items():self.cover(self.versions[ck],'product_lines','complete',n,'stocktaking_lines')
        for spec in self.registry['native_sheets']:
            if spec['sheet_role']!='product_line':continue
            typ=DOC_TYPES[spec['h5_module']];module='native/'+spec['sheet_module'];counts=collections.Counter();ambiguous=collections.Counter()
            for raw,ordinal,r in self.s.raw(module):
                no=get(r,'单据编号');matches=[ck for ck in self.doc_no.get((typ,str(no)),[]) if not self.doc_rows[ck][2]]
                # Refine duplicate numbers using independent header attributes. Never choose first.
                if len(matches)>1:
                    date=dt(get(r,'业务日期'));branch=get(r,'所属门店')
                    if date:matches=[ck for ck in matches if (self.s.get('document_version',self.versions[ck])['business_at'] or '')[:10]==date[:10]]
                    if branch:matches=[ck for ck in matches if self.s.get('document_version',self.versions[ck])['branch_name']==branch]
                if len(matches)!=1:
                    self.issue('native_ambiguous_document','原表行无法唯一关联单据，仍可在原表完整浏览',raw,details={'candidate_count':len(matches),'module':module});continue
                ck=matches[0];version=self.versions[ck];coverage=json.loads(self.s.get('document_version',version)['detail_coverage_json'])
                if coverage['product_lines']['state']=='complete':continue
                self.line(ck,raw,r,counts[ck]+1,'$','native');counts[ck]+=1
            for ck,n in counts.items():self.cover(self.versions[ck],'product_lines','complete',n,'native')
        log('document_lines',rows=self.s.seq['qsm_document_line'])

    def stock(self):
        totals={};sums=collections.defaultdict(Decimal)
        for module,t in [('stock','stock_total'),('stock_by_warehouse','stock_snapshot')]:
            seen=set()
            for raw,_,r in self.s.raw(module):
                sk=key(get(r,'productid'));sku=self.master.get(('product_sku',None,sk))
                if not sku:raise ValueError('Stock SKU missing from full product master')
                base=self.s.get('product_sku',sku)['base_unit_id'];source_unit=key(get(r,'mainunitid'))
                if source_unit and self.master.get(('unit',None,source_unit))!=base:raise ValueError('Stock base unit mismatch')
                row=dict(batch_id=1,raw_record_id=raw,sku_id=sku,base_unit_id=base,quantity_main=number(get(r,'currentstockcount')),source_available_quantity=number(get(r,'availablestock')),order_quantity=number(get(r,'orderstock')),on_in_quantity=number(get(r,'oninstock')),on_out_quantity=number(get(r,'onoutstock')),stock_amount=number(get(r,'productamt')),estimated_cost_amount=number(get(r,'estimatedcostamt')))
                if t=='stock_total':
                    if sku in seen:raise ValueError('Duplicate total-stock SKU')
                    seen.add(sku);totals[sku]=Decimal(row['quantity_main'])
                    row.update(in_quantity=number(get(r,'instockcount')),out_quantity=number(get(r,'outstockcount')),initial_quantity=number(get(r,'initstockcount')))
                else:
                    wid=self.ref('warehouse',get(r,'WarehouseId'),get(r,'WarehouseName'),raw=raw,required=True)
                    pair=(sku,wid)
                    if pair in seen:raise ValueError('Duplicate stock SKU/warehouse')
                    seen.add(pair);row['warehouse_id']=wid;sums[sku]+=Decimal(row['quantity_main'])
                self.s.add(t,**row)
        differences=[sku for sku,q in totals.items() if abs(q-sums[sku])>Decimal('0.000001')]
        if differences:raise ValueError('Stock reconciliation failed: '+str(len(differences)))
        self.s.info('stock_reconciliation',{'sku_count':len(totals),'differences':0})
        log('stock_verified',sku=len(totals),warehouse_rows=self.s.seq['qsm_stock_snapshot'],differences=0)
        duplicates=collections.Counter()
        for raw,ordinal,r in self.s.raw('stock_movements'):
            typ=BUSINESS_TYPES.get(str(get(r,'BuinessType')));doc_key=key(get(r,'BuinessId'));ck=(typ,doc_key)
            sku=self.master.get(('product_sku',None,key(get(r,'ProductId','SourceProductId'))));did=self.documents.get(ck)
            wid=self.ref('warehouse',get(r,'WarehouseId'),get(r,'WarehouseName'),raw=raw)
            h=hashlib.sha256(js(r).encode()).hexdigest();duplicates[h]+=1
            movement=self.s.add('stock_movement',batch_id=1,raw_record_id=raw,row_ordinal=ordinal,row_hash=h,duplicate_ordinal=duplicates[h],sku_id=sku,warehouse_id=wid,branch_id=self.ref('branch',get(r,'BranchId'),get(r,'BranchName'),raw=raw),document_id=did,document_version_id=self.versions.get(ck),source_business_type=str(get(r,'BuinessType')) if get(r,'BuinessType') is not None else None,source_business_key=doc_key,source_io_key=key(get(r,'IOId')),document_no=get(r,'BuinessCode'),business_at=dt(get(r,'BuinessDate')),unit_id=self.master.get(('unit',None,key(get(r,'ProductUnit')))),unit_name=get(r,'UnitName'),ratio_to_base=number(get(r,'UnitRatio'),9),in_quantity=number(get(r,'BuinessInCount')),out_quantity=number(get(r,'BuinessOutCount')),balance_quantity=number(get(r,'BalanceCount')),cost_amount=number(get(r,'TotalCost')),sale_amount=number(get(r,'SaleAmt')),write_back=bit(get(r,'WriteBack')),match_state='exact' if sku and did and wid else 'unresolved')
            if not did:self.issue('movement_missing_document','来源流水未匹配到单据身份',raw,('qsm_stock_movement',movement),severity='blocker' if typ else 'warning')
        self.s.info('movement_identical_duplicates',sum(x-1 for x in duplicates.values()))
        log('movements',rows=self.s.seq['qsm_stock_movement'],identical_duplicates=sum(x-1 for x in duplicates.values()))

    def report(self):
        for raw,_,r in self.s.raw('sales_line_items'):
            typ=BUSINESS_TYPES.get(str(get(r,'BusiType')));sk=key(get(r,'SaleId'));detail=key(get(r,'SaleDetailId'));ck=(typ,sk)
            did=self.documents.get(ck);line_id=self.line_keys.get((typ,sk,detail));code=get(r,'ProductCode')
            sku=self.s.get('document_line',line_id)['sku_id'] if line_id else next(iter(self.sku_codes[str(code)])) if code and len(self.sku_codes[str(code)])==1 else None
            rid=self.s.add('sales_report_line',batch_id=1,raw_record_id=raw,source_detail_key=detail,source_business_type=str(get(r,'BusiType')),source_business_key=sk,document_id=did,document_version_id=self.versions.get(ck),document_line_id=line_id,sku_id=sku,product_code=code,product_name=get(r,'ProductName'),unit_name=get(r,'UnitName'),warehouse_name=get(r,'WarehouseName'),document_no=get(r,'SaleNo'),business_at=dt(get(r,'SaleDate')),quantity=number(get(r,'SaleCount')),unit_price=number(get(r,'SalePrice')),amount=number(get(r,'SaleAmt')),deduct_amount=number(get(r,'DeductAmt')),write_back=bit(get(r,'WriteBack')),match_state='exact' if did and sku else 'unresolved')
            if not did:self.issue('report_missing_document','销售/退货报表行未匹配单据',raw,('qsm_sales_report_line',rid),severity='blocker')
        log('sales_report',rows=self.s.seq['qsm_sales_report_line'])

    def media(self):
        for raw,ordinal,r in self.s.raw('media/index.jsonl'):
            p=self.data/'media/files'/Path(str(r.get('file') or '').replace('\\','/')).name
            if not p.is_file():raise ValueError('Missing source media file')
            fid=self.file(p);file=self.s.get('file',fid)
            if file['content_sha256']!=r.get('sha256') or file['byte_length']!=r.get('bytes'):raise ValueError('Media checksum mismatch')
            module=r.get('module');source_key=key(r.get('id'));sku=self.master.get(('product_sku',None,source_key)) if module in ('products','products_all') else None
            typ=DOC_TYPES.get(module) or {'sales_history_details':'sale','purchases_history_details':'purchase'}.get(module)
            version=self.versions.get((typ,source_key))
            self.s.add('file_ref',batch_id=1,raw_record_id=raw,reference_key='media:'+str(ordinal),file_id=fid,sku_id=sku,document_version_id=version,reference_kind='product_image' if sku else 'document_file' if version else 'other',source_attachment_key=key(r.get('name')) if re.fullmatch(r'[0-9a-fA-F-]{36}',str(r.get('name',''))) else None,original_name=r.get('name'),source_url_sanitized=r.get('url'),is_primary=1 if r.get('name')=='main' else 0,sort=ordinal,download_state='complete')
            if not sku and not version:self.issue('media_missing_parent','媒体来源身份未唯一关联，文件和原始索引均已保留',raw)
        log('media',references=self.s.seq['qsm_file_ref'],contents=len(self.files))

    def finish(self):
        blockers=self.s.db.execute("SELECT COUNT(*) FROM staged WHERE table_name='qsm_data_issue' AND json_extract(payload,'$.severity')='blocker'").fetchone()[0]
        if blockers:raise ValueError('Blocking data issues: '+str(blockers))
        raw_summary=[{'module':r['module_key'],'carrier':r['carrier'],'rows':r['actual_count']} for r in self.s.rows('import_module')]
        self.s.update('import_batch',1,state='validated',verification_passed=1,import_finished_at=utcnow())
        self.s.add('change_log',batch_id=1,entity_table='qsm_import_batch',entity_id=1,action='create',actor='qisemi-import',correlation_id=str(uuid.uuid4()),after_json=js({'dataset_hash':self.fingerprint,'state':'validated'}),reason='User approved initial database migration')
        counts={t:n for t,n in self.s.seq.items()}
        self.s.info('counts',counts);self.s.info('modules',raw_summary)
        self.s.info('file_plan',list(self.file_plan.values()))
        self.s.info('issues',dict(self.issues))
        self.s.finish()
        summary={'dataset_hash':self.fingerprint,'parser_version':VERSION,'tables':counts,'issues':dict(self.issues),'modules':raw_summary,'files':len(self.file_plan),'file_bytes':sum(x['bytes'] for x in self.file_plan.values()),'stock_reconciliation_differences':0}
        (self.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        (self.out/'file-plan.json').write_text(json.dumps(list(self.file_plan.values()),ensure_ascii=False,indent=2),encoding='utf-8')
        log('prepared',**{k:v for k,v in summary.items() if k not in ('modules',)})
        return summary

def prepare(data,out,resume_raw=False):
    p=Prepare(data,out,resume_raw)
    if resume_raw:
        p.fingerprint=json.loads(p.s.db.execute("SELECT value FROM info WHERE key='source_fingerprint'").fetchone()[0])
        paths=sorted(p.data.glob('*.jsonl'))+sorted((p.data/'native_rows').glob('*.jsonl'))+[p.data/'media/index.jsonl']
        fingerprint=hashlib.sha256(js([(x.relative_to(p.data).as_posix(),sha_file(x)) for x in paths]).encode()).hexdigest()
        if fingerprint!=p.fingerprint:raise ValueError('Source snapshot changed; cannot resume')
        p.modules={r['module_key']:r['id'] for r in p.s.rows('import_module')}
        if sum(r['carrier']=='api' for r in p.s.rows('import_module'))!=len(p.registry['api_modules']):raise ValueError('Raw API stage incomplete')
        if sum(r['carrier']=='native_sheet' for r in p.s.rows('import_module'))!=len(p.registry['native_sheets']):raise ValueError('Raw native stage incomplete')
        for r in p.s.rows('file'):
            relative=r['object_key'].removeprefix('datasets/'+p.fingerprint+'/')
            p.files[r['content_sha256']]=r['id'];p.file_paths[relative]=r['id']
            p.file_plan[r['content_sha256']]={'id':r['id'],'source':str(p.data/relative),'relative_path':relative,'object_key':r['object_key'],'sha256':r['content_sha256'],'bytes':r['byte_length']}
        log('resumed_raw',raw_records=p.s.seq['qsm_raw_record'])
    else:p.initialize();p.raw_sources()
    p.masters();p.products();p.documents_prepare();p.other_lines();p.stock();p.report();p.media()
    return p.finish()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--output-dir',required=True);parser.add_argument('--resume-raw',action='store_true')
    args=parser.parse_args();prepare(args.data_dir,args.output_dir,args.resume_raw)
