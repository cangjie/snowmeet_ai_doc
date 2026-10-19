"""Approved Qisemi schema; SQL generation never connects to a database."""
from pathlib import Path

C = {
    'id':'bigint IDENTITY(1,1) NOT NULL', 'valid':'bit NOT NULL DEFAULT 1',
    'created_at':'datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()',
    'updated_at':'datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()',
    'created_by':'nvarchar(128) NULL','updated_by':'nvarchar(128) NULL',
    'deleted_at':'datetime2(3) NULL','deleted_by':'nvarchar(128) NULL',
    'delete_reason':'nvarchar(500) NULL','row_version':'rowversion NOT NULL',
}
M = dict(source_id='bigint',source_key='nvarchar(128)',last_seen_batch_id='bigint?',last_raw_record_id='bigint?',source_deleted='bit?',source_enabled='bit?',source_state='nvarchar(100)?',source_missing='bit=0',is_stub='bit=0',source_created_at='datetime2(3)?',source_updated_at='datetime2(3)?')
P = dict(source_id='bigint',batch_id='bigint',raw_record_id='bigint',json_path="nvarchar(512)=N'$'")
TABLES={}
KINDS={}

def table(table_name,kind='C',**cols):
    name='qsm_'+table_name
    d=dict(C)
    for k,v in ({'C':{},'M':M,'P':P}[kind]|cols).items():
        nullable=v.endswith('?');v=v.removesuffix('?')
        typ,sep,default=v.partition('=')
        collation=''
        if typ.startswith(('nvarchar','varchar')):
            collation=' COLLATE '+('Latin1_General_100_BIN2' if k in ('source_key','source_entity_key','parent_source_key','source_detail_key','source_business_key','target_source_key','company_key','book_key','module_key','attribute_key') else 'Chinese_PRC_CI_AS')
        d[k]=typ+collation+(' NULL' if nullable else ' NOT NULL')+(' DEFAULT '+default if sep else '')
    TABLES[name]=d;KINDS[name]=kind

table('source',platform_code="varchar(32)='qisemi'",company_key='nvarchar(128)',book_key='nvarchar(128)',display_name='nvarchar(200)',source_timezone="nvarchar(64)=N'Asia/Shanghai'",current_full_batch_id='bigint?',current_inventory_batch_id='bigint?')
table('import_batch',source_id='bigint',batch_key='uniqueidentifier',scope='varchar(16)',dataset_hash='binary(32)',parser_version='nvarchar(64)',capture_started_at='datetime2(3)',capture_finished_at='datetime2(3)',import_started_at='datetime2(3)?',import_finished_at='datetime2(3)?',published_at='datetime2(3)?',state='varchar(20)',verification_passed='bit=0',package_file_id='bigint?',manifest_json='nvarchar(max)',verification_json='nvarchar(max)',error_summary='nvarchar(2000)?')
table('import_module',source_id='bigint',batch_id='bigint',module_key='nvarchar(128)',carrier='varchar(24)',state='varchar(20)',expected_count='bigint?',actual_count='bigint?',file_hash='binary(32)?',capture_started_at='datetime2(3)?',capture_finished_at='datetime2(3)?',coverage_json='nvarchar(max)',error_summary='nvarchar(2000)?')
table('raw_record',source_id='bigint',batch_id='bigint',module_id='bigint',row_ordinal='bigint',source_entity_key='nvarchar(200)?',parent_source_key='nvarchar(200)?',payload_json='nvarchar(max)',payload_hash='binary(32)',duplicate_ordinal='int=1',sheet_id='bigint?')
table('category','M',category_kind='varchar(24)',parent_id='bigint?',branch_id='bigint?',name='nvarchar(300)',sort='int=100',path_text='nvarchar(2000)?')
table('unit','M',name='nvarchar(100)',allows_decimal='bit?',remark='nvarchar(1000)?')
table('branch','M',parent_id='bigint?',code='nvarchar(100)?',name='nvarchar(200)',address='nvarchar(1000)?',telephone='nvarchar(100)?',branch_type='nvarchar(40)?')
table('warehouse','M',branch_id='bigint?',code='nvarchar(100)?',name='nvarchar(200)',source_warehouse_type='nvarchar(40)?',warehouse_purpose="varchar(24)='unreviewed'",retail_use="varchar(16)='unreviewed'",sort='int=100')
table('warehouse_position','M',warehouse_id='bigint',code='nvarchar(100)?',name='nvarchar(200)')
table('product_style',source_id='bigint',style_key='uniqueidentifier',display_name='nvarchar(300)',brand='nvarchar(100)?',model='nvarchar(300)?',style_code='nvarchar(100)?',season='nvarchar(100)?',color='nvarchar(100)?',gender='nvarchar(100)?',flex_label='nvarchar(100)?',category_id='bigint?',base_unit_id='bigint?',group_signature='binary(32)?',group_method='varchar(16)',rule_version='nvarchar(64)?',review_state="varchar(16)='pending'",search_text='nvarchar(2000)')
table('product_sku','M',record_kind="varchar(24)='product'",code='nvarchar(200)?',barcode='nvarchar(200)?',name='nvarchar(300)',category_id='bigint?',base_unit_id='bigint?',source_main_product_key='nvarchar(128)?',season='nvarchar(100)?',size_label='nvarchar(100)?',size_sort='decimal(9,3)?',shelf_state='nvarchar(40)?',remark='nvarchar(2000)?',search_text='nvarchar(2000)')
table('style_sku',source_id='bigint',style_id='bigint',sku_id='bigint',assignment_method='varchar(16)',rule_version='nvarchar(64)?',confirmed_by='nvarchar(128)?',confirmed_at='datetime2(3)?',locked='bit=0',evidence_json='nvarchar(max)')
table('sku_attribute',source_id='bigint',sku_id='bigint',attribute_key='nvarchar(128)',source_label='nvarchar(200)?',semantic_key='varchar(32)?',value_text='nvarchar(2000)?',value_json='nvarchar(max)?',sort='int=100',last_seen_batch_id='bigint',last_raw_record_id='bigint',json_path='nvarchar(512)')
table('sku_unit',source_id='bigint',sku_id='bigint',unit_id='bigint',source_unit_row_key='nvarchar(128)?',ratio_to_base='decimal(19,9)',is_base='bit',allows_decimal='bit?',barcode='nvarchar(200)?',sale_price='decimal(19,6)?',buy_price='decimal(19,6)?',lower_price='decimal(19,6)?',price_tiers_json='nvarchar(max)?',last_seen_batch_id='bigint',last_raw_record_id='bigint',json_path='nvarchar(512)')
table('partner','M',partner_kind='varchar(16)',code='nvarchar(100)?',name='nvarchar(300)',category_id='bigint?',branch_id='bigint?',contact_name='nvarchar(200)?',telephone='nvarchar(100)?',address='nvarchar(1000)?',email='nvarchar(200)?',remark='nvarchar(2000)?',receivable='decimal(19,6)?',payable='decimal(19,6)?',stored_amount='decimal(19,6)?',points='decimal(19,6)?')
table('account','M',branch_id='bigint?',name='nvarchar(200)',short_name='nvarchar(100)?',account_type='nvarchar(100)?',account_number='nvarchar(200)?',bank_account_name='nvarchar(200)?',initial_amount='decimal(19,6)?',current_amount='decimal(19,6)?',remark='nvarchar(2000)?')
table('employee','M',branch_id='bigint?',name='nvarchar(200)',login_name='nvarchar(200)?',telephone='nvarchar(100)?',user_type='nvarchar(40)?',user_status='nvarchar(40)?',is_root='bit?')
table('role','M',name='nvarchar(200)',permission_json='nvarchar(max)?',remark='nvarchar(2000)?')
table('project','M',parent_id='bigint?',name='nvarchar(200)',direction='varchar(16)?',remark='nvarchar(2000)?')
table('document','M',document_type='varchar(40)',document_no='nvarchar(200)?',current_version_id='bigint?',listing_state='varchar(24)')
table('document_version','P',document_id='bigint',revision_key='binary(32)',version_kind='varchar(16)',document_no='nvarchar(200)?',business_at='datetime2(3)?',business_time_precision="varchar(16)='unknown'",branch_id='bigint?',partner_id='bigint?',warehouse_id='bigint?',from_warehouse_id='bigint?',to_warehouse_id='bigint?',business_employee_id='bigint?',creator_employee_id='bigint?',branch_name='nvarchar(300)?',partner_name='nvarchar(300)?',warehouse_name='nvarchar(300)?',business_employee_name='nvarchar(200)?',creator_name='nvarchar(200)?',amount='decimal(19,6)?',discount_amount='decimal(19,6)?',tax_amount='decimal(19,6)?',other_fee='decimal(19,6)?',settled_amount='decimal(19,6)?',unsettled_amount='decimal(19,6)?',currency_code='nvarchar(16)?',exchange_rate='decimal(19,9)?',source_bill_state='nvarchar(100)?',source_io_state='nvarchar(100)?',source_payment_state='nvarchar(100)?',source_audit_state='nvarchar(100)?',write_back='bit?',is_multi_warehouse='bit?',is_multi_account='bit?',is_locked='bit?',source_created_at='datetime2(3)?',source_updated_at='datetime2(3)?',source_update_count='int?',remark='nvarchar(max)?',inside_remark='nvarchar(max)?',detail_coverage_json='nvarchar(max)')
table('document_line','P',document_version_id='bigint',line_key='nvarchar(200)',source_detail_key='nvarchar(128)?',line_no='int',line_kind='varchar(24)',sku_id='bigint?',unit_id='bigint?',warehouse_id='bigint?',from_warehouse_id='bigint?',to_warehouse_id='bigint?',position_id='bigint?',product_code='nvarchar(200)?',barcode='nvarchar(200)?',product_name='nvarchar(300)?',size_label='nvarchar(100)?',unit_name='nvarchar(100)?',properties_text='nvarchar(2000)?',quantity='decimal(19,6)?',quantity_base='decimal(19,6)?',return_quantity='decimal(19,6)?',unit_price='decimal(19,6)?',discount_rate='decimal(19,6)?',discounted_price='decimal(19,6)?',amount='decimal(19,6)?',cost_price='decimal(19,6)?',cost_amount='decimal(19,6)?',tax_rate='decimal(19,6)?',tax_amount='decimal(19,6)?',ratio_to_base='decimal(19,9)?',book_quantity='decimal(19,6)?',counted_quantity='decimal(19,6)?',difference_quantity='decimal(19,6)?',overage_amount='decimal(19,6)?',shortage_amount='decimal(19,6)?',is_gift='bit?',remark='nvarchar(max)?',match_state='varchar(20)')
table('document_relation','P',from_document_id='bigint',from_version_id='bigint',to_document_id='bigint?',to_line_id='bigint?',relation_type='varchar(32)',target_document_type='varchar(40)?',target_source_key='nvarchar(128)?',target_document_no='nvarchar(200)?',relation_key='nvarchar(200)',quantity='decimal(19,6)?',amount='decimal(19,6)?',match_state='varchar(20)')
table('settlement_line','P',document_version_id='bigint',line_key='nvarchar(200)',account_id='bigint?',account_name='nvarchar(200)?',direction='varchar(16)',amount='decimal(19,6)?',currency_code='nvarchar(16)?',exchange_rate='decimal(19,9)?',payment_type='nvarchar(100)?',business_at='datetime2(3)?',remark='nvarchar(2000)?')
table('writeoff_line','P',document_version_id='bigint',line_key='nvarchar(200)',target_document_id='bigint?',target_document_type='varchar(40)?',target_source_key='nvarchar(128)?',target_document_no='nvarchar(200)?',allocated_amount='decimal(19,6)?',discount_amount='decimal(19,6)?',remaining_amount='decimal(19,6)?',business_at='datetime2(3)?',match_state='varchar(20)',remark='nvarchar(2000)?')
table('stock_total','P',sku_id='bigint',base_unit_id='bigint?',quantity_main='decimal(19,6)',source_available_quantity='decimal(19,6)?',order_quantity='decimal(19,6)?',on_in_quantity='decimal(19,6)?',on_out_quantity='decimal(19,6)?',in_quantity='decimal(19,6)?',out_quantity='decimal(19,6)?',initial_quantity='decimal(19,6)?',stock_amount='decimal(19,6)?',estimated_cost_amount='decimal(19,6)?')
table('stock_snapshot','P',sku_id='bigint',warehouse_id='bigint',base_unit_id='bigint?',quantity_main='decimal(19,6)',source_available_quantity='decimal(19,6)?',order_quantity='decimal(19,6)?',on_in_quantity='decimal(19,6)?',on_out_quantity='decimal(19,6)?',stock_amount='decimal(19,6)?',estimated_cost_amount='decimal(19,6)?')
table('stock_movement','P',row_ordinal='bigint',row_hash='binary(32)',duplicate_ordinal='int=1',sku_id='bigint?',warehouse_id='bigint?',branch_id='bigint?',document_id='bigint?',document_version_id='bigint?',source_business_type='nvarchar(40)?',source_business_key='nvarchar(128)?',source_io_key='nvarchar(128)?',document_no='nvarchar(200)?',business_at='datetime2(3)?',unit_id='bigint?',unit_name='nvarchar(100)?',ratio_to_base='decimal(19,9)?',in_quantity='decimal(19,6)?',out_quantity='decimal(19,6)?',balance_quantity='decimal(19,6)?',cost_amount='decimal(19,6)?',sale_amount='decimal(19,6)?',write_back='bit?',match_state='varchar(20)')
table('sales_report_line','P',source_detail_key='nvarchar(128)',source_business_type='nvarchar(40)',source_business_key='nvarchar(128)?',document_id='bigint?',document_version_id='bigint?',document_line_id='bigint?',sku_id='bigint?',product_code='nvarchar(200)?',product_name='nvarchar(300)?',unit_name='nvarchar(100)?',warehouse_name='nvarchar(200)?',document_no='nvarchar(200)?',business_at='datetime2(3)?',quantity='decimal(19,6)?',unit_price='decimal(19,6)?',amount='decimal(19,6)?',deduct_amount='decimal(19,6)?',write_back='bit?',match_state='varchar(20)')
table('file',source_id='bigint',content_sha256='binary(32)',byte_length='bigint',mime_type='nvarchar(128)?',extension='nvarchar(32)?',storage_provider='varchar(32)',object_key='nvarchar(1024)',first_seen_batch_id='bigint',availability_state='varchar(20)')
table('file_ref','P',reference_key='nvarchar(200)',file_id='bigint?',sku_id='bigint?',document_version_id='bigint?',partner_id='bigint?',reference_kind='varchar(24)',source_attachment_key='nvarchar(128)?',original_name='nvarchar(500)?',source_url_sanitized='nvarchar(2048)?',is_primary='bit=0',sort='int=100',download_state='varchar(20)',error_summary='nvarchar(1000)?')
table('export_sheet',source_id='bigint',batch_id='bigint',module_id='bigint',file_id='bigint',export_key='nvarchar(128)',sheet_index='int',sheet_name='nvarchar(200)',sheet_role='varchar(24)',headers_json='nvarchar(max)',row_count='bigint',binding_state='varchar(20)')
table('retail_sku_map',source_id='bigint',sku_id='bigint',retail_product_id='int',mapping_state='varchar(16)',quantity_ratio='decimal(19,9)',confirmed_by='nvarchar(128)?',confirmed_at='datetime2(3)?',remark='nvarchar(1000)?')
table('retail_warehouse_map',source_id='bigint',warehouse_id='bigint',shop_id='int',mapping_state='varchar(16)',is_primary='bit=0',confirmed_by='nvarchar(128)?',confirmed_at='datetime2(3)?',remark='nvarchar(1000)?')
table('retail_sale_link',source_id='bigint',retail_id='int',document_id='bigint',document_line_id='bigint?',source_detail_key='nvarchar(128)?',relation_type='varchar(16)',link_key='binary(32)',matched_quantity='decimal(19,6)?',matched_amount='decimal(19,6)?',match_state='varchar(16)',matched_by='nvarchar(128)?',matched_at='datetime2(3)?')
table('data_issue',source_id='bigint',batch_id='bigint',raw_record_id='bigint?',issue_key='binary(32)',issue_code='varchar(64)',severity='varchar(16)',entity_table='nvarchar(64)?',entity_id='bigint?',state="varchar(16)='open'",summary='nvarchar(1000)',details_json='nvarchar(max)',resolved_by='nvarchar(128)?',resolved_at='datetime2(3)?',resolution_note='nvarchar(2000)?')
table('change_log',source_id='bigint',batch_id='bigint?',entity_table='nvarchar(64)',entity_id='bigint',action='varchar(32)',actor='nvarchar(128)',correlation_id='uniqueidentifier',before_json='nvarchar(max)?',after_json='nvarchar(max)?',reason='nvarchar(2000)?')
# Physical storage refinement: the original JSON remains queryable, without storing
# a second uncompressed copy on the small production volume.
TABLES['qsm_raw_record']['payload_gzip']='varbinary(max) NOT NULL'

UNIQUE={
 'source':[('platform_code','company_key','book_key')], 'import_batch':[('batch_key',),('source_id','dataset_hash','parser_version')],
 'import_module':[('batch_id','module_key','carrier')], 'raw_record':[('module_id','row_ordinal')],
 'category':[('source_id','category_kind','source_key')], 'product_style':[('source_id','style_key')],
 'sku_attribute':[('sku_id','attribute_key')], 'sku_unit':[('sku_id','unit_id')],
 'partner':[('source_id','partner_kind','source_key')], 'document':[('source_id','document_type','source_key')],
 'document_version':[('document_id','batch_id','revision_key')], 'document_line':[('document_version_id','line_key')],
 'document_relation':[('from_version_id','relation_type','relation_key')], 'settlement_line':[('document_version_id','line_key')],
 'writeoff_line':[('document_version_id','line_key')], 'stock_total':[('batch_id','sku_id')],
 'stock_snapshot':[('batch_id','warehouse_id','sku_id')], 'stock_movement':[('batch_id','row_ordinal')],
 'sales_report_line':[('batch_id','source_business_type','source_detail_key')], 'file':[('source_id','content_sha256')],
 'file_ref':[('batch_id','reference_key')], 'export_sheet':[('batch_id','export_key','sheet_index')], 'data_issue':[('batch_id','issue_key')],
}
for t in TABLES:
    short=t[4:]
    if KINDS[t]=='M' and short not in UNIQUE: UNIQUE[short]=[('source_id','source_key')]

FILTERED={
 'style_sku':[(('source_id','sku_id'),'[valid]=1')],
 'sku_unit':[(('sku_id',),'[valid]=1 AND [is_base]=1')],
 'retail_sku_map':[(('source_id','retail_product_id'),'[valid]=1')],
 'retail_warehouse_map':[(('source_id','warehouse_id','shop_id'),'[valid]=1'),(('source_id','shop_id'),'[valid]=1 AND [is_primary]=1')],
 'retail_sale_link':[(('source_id','retail_id','link_key'),'[valid]=1')],
}
INDEXES={
 'raw_record':[('module_id','source_entity_key'),('module_id','payload_hash','duplicate_ordinal')],
 'category':[('source_id','category_kind','parent_id','valid','sort')], 'branch':[('source_id','parent_id','valid'),('source_id','code')],
 'warehouse':[('source_id','branch_id','valid','sort')], 'warehouse_position':[('source_id','warehouse_id','valid')],
 'product_style':[('source_id','group_signature')], 'product_sku':[('source_id','code'),('source_id','barcode')],
 'style_sku':[('source_id','style_id','valid')], 'unit':[('source_id','name')],
 'document':[('source_id','document_type','document_no')], 'document_version':[('source_id','batch_id','business_at','id'),('document_id','version_kind','batch_id')],
 'document_line':[('document_version_id','line_no'),('source_id','sku_id','batch_id')],
 'document_relation':[('source_id','to_document_id','valid')],
 'stock_snapshot':[('source_id','batch_id','sku_id','warehouse_id')], 'stock_movement':[('source_id','batch_id','sku_id','warehouse_id','business_at','id'),('source_id','batch_id','document_id')],
 'file_ref':[('source_id','sku_id','batch_id'),('source_id','document_version_id')],
 'data_issue':[('source_id','batch_id','state','severity')], 'change_log':[('source_id','entity_table','entity_id','id'),('source_id','correlation_id')],
 'retail_sale_link':[('source_id','document_id','valid')], 'account':[('source_id','branch_id','valid')],
 'project':[('source_id','parent_id','valid')], 'import_module':[('source_id','batch_id','state')],
}
CHECKS={
 'source':["[platform_code]='qisemi'"], 'import_batch':["[scope] IN ('full','inventory')","[state] IN ('staging','validated','published','failed','revoked')","[capture_finished_at]>=[capture_started_at]"],
 'import_module':["[state] IN ('complete','empty','failed','omitted')","[carrier] IN ('api','native_sheet','media','metadata')"],
 'style_sku':["[assignment_method] IN ('rule','manual','singleton')"],
 'sku_attribute':["[value_text] IS NOT NULL OR [value_json] IS NOT NULL"],
 'sku_unit':["[ratio_to_base]>0 AND ([is_base]=0 OR [ratio_to_base]=1)"],
 'document':["[listing_state] IN ('current','history_only','missing_source')"],
 'document_version':["[version_kind] IN ('current','historical')"],
 'retail_sku_map':["[quantity_ratio]>0","[mapping_state] IN ('pending','confirmed')"],
 'retail_warehouse_map':["[mapping_state] IN ('pending','confirmed')","[is_primary]=0 OR [mapping_state]='confirmed'"],
 'file':["[byte_length]>=0"], 'raw_record':["[row_ordinal]>0 AND [duplicate_ordinal]>0"],
 'file_ref':["(CASE WHEN [sku_id] IS NULL THEN 0 ELSE 1 END+CASE WHEN [document_version_id] IS NULL THEN 0 ELSE 1 END+CASE WHEN [partner_id] IS NULL THEN 0 ELSE 1 END)<=1"],
}

REFS={'batch_id':'import_batch','last_seen_batch_id':'import_batch','first_seen_batch_id':'import_batch','current_full_batch_id':'import_batch','current_inventory_batch_id':'import_batch','raw_record_id':'raw_record','last_raw_record_id':'raw_record','module_id':'import_module','sheet_id':'export_sheet','package_file_id':'file','file_id':'file','branch_id':'branch','warehouse_id':'warehouse','from_warehouse_id':'warehouse','to_warehouse_id':'warehouse','category_id':'category','unit_id':'unit','base_unit_id':'unit','sku_id':'product_sku','style_id':'product_style','partner_id':'partner','account_id':'account','business_employee_id':'employee','creator_employee_id':'employee','document_id':'document','from_document_id':'document','to_document_id':'document','target_document_id':'document','document_version_id':'document_version','current_version_id':'document_version','from_version_id':'document_version','document_line_id':'document_line','to_line_id':'document_line','position_id':'warehouse_position'}

def ddl():
    out=['-- Generated by tools/qisemiyun/sql_import/schema.py; approved 2026-10-19.', '-- Additive only: creates dbo.qsm_* objects, never rewrites existing business tables.', 'SET NOCOUNT ON; SET XACT_ABORT ON; SET ANSI_NULLS ON; SET QUOTED_IDENTIFIER ON;', 'BEGIN TRY', 'BEGIN TRANSACTION;', "IF DB_NAME() IN ('master','model','msdb','tempdb') THROW 51000,'Application database required',1;"]
    for t,cols in TABLES.items():
        checks=["([valid]=1 AND [deleted_at] IS NULL AND [deleted_by] IS NULL AND [delete_reason] IS NULL) OR ([valid]=0 AND [deleted_at] IS NOT NULL AND [deleted_by] IS NOT NULL AND [delete_reason] IS NOT NULL AND LEN(LTRIM(RTRIM([delete_reason])))>0)"]
        checks += [f'[{c}] IS NULL OR ISJSON([{c}])=1' for c in cols if c.endswith('_json') and not(t=='qsm_raw_record' and c=='payload_json')]
        if t=='qsm_raw_record':checks += ['CONVERT(nvarchar(max),DECOMPRESS([payload_gzip])) IS NOT NULL AND ISJSON(CONVERT(nvarchar(max),DECOMPRESS([payload_gzip])))=1']
        checks += CHECKS.get(t[4:],[])
        lines=[f'    [{k}] '+('AS CONVERT(nvarchar(max),DECOMPRESS([payload_gzip]))' if t=='qsm_raw_record' and k=='payload_json' else v) for k,v in cols.items()]+[f'    CONSTRAINT [PK_{t}] PRIMARY KEY ([id]) WITH (DATA_COMPRESSION=PAGE)']
        if 'source_id' in cols:lines += [f'    CONSTRAINT [AK_{t}_source] UNIQUE ([source_id],[id]) WITH (DATA_COMPRESSION=PAGE)']
        if 'batch_id' in cols:lines += [f'    CONSTRAINT [AK_{t}_batch] UNIQUE ([source_id],[batch_id],[id]) WITH (DATA_COMPRESSION=PAGE)']
        if t=='qsm_document_version':lines += [f'    CONSTRAINT [AK_{t}_document] UNIQUE ([source_id],[document_id],[id]) WITH (DATA_COMPRESSION=PAGE)']
        lines += [f'    CONSTRAINT [CK_{t}_{i}] CHECK ({ch})' for i,ch in enumerate(checks)]
        out += [f"IF OBJECT_ID(N'dbo.{t}',N'U') IS NULL",'BEGIN',f'CREATE TABLE [dbo].[{t}] (',',\n'.join(lines),' );','END;']
    for t,cols in TABLES.items():
        short=t[4:]
        for c in cols:
            if c=='source_id':parent='qsm_source';lc=[c];rc=['id']
            elif c in ('retail_product_id','retail_id','shop_id'):
                parent={'retail_product_id':'product','retail_id':'retail','shop_id':'shop_list'}[c];lc=[c];rc=['id']
            elif c=='parent_id':parent=t;lc=['source_id',c];rc=['source_id','id']
            elif c in REFS:
                parent='qsm_'+REFS[c];lc=['source_id',c] if 'source_id' in cols else ['id',c];rc=['source_id','id']
                if c=='raw_record_id' and 'batch_id' in cols:lc=['source_id','batch_id',c];rc=['source_id','batch_id','id']
                if c=='module_id' and 'batch_id' in cols:lc=['source_id','batch_id',c];rc=['source_id','batch_id','id']
                if c=='sheet_id':lc=['source_id','batch_id',c];rc=['source_id','batch_id','id']
                if c=='current_version_id':lc=['source_id','id',c];rc=['source_id','document_id','id']
            else:continue
            fk=f'FK_{t}_{c}'
            out += [f"IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'{fk}' AND parent_object_id=OBJECT_ID(N'dbo.{t}'))",f"ALTER TABLE [dbo].[{t}] WITH CHECK ADD CONSTRAINT [{fk}] FOREIGN KEY ({','.join('['+x+']' for x in lc)}) REFERENCES [dbo].[{parent}] ({','.join('['+x+']' for x in rc)}) ON DELETE NO ACTION;"]
        for unique,prefix,sets in [(True,'UQ',[(x,None) for x in UNIQUE.get(short,[])]),(True,'UX',FILTERED.get(short,[])),(False,'IX',[(x,None) for x in INDEXES.get(short,[])])]:
            for i,(keys,where) in enumerate(sets):
                name=f'{prefix}_{t}_{i}'
                include=' INCLUDE ([quantity_main])' if short=='stock_snapshot' and not unique else ''
                out += [f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'{name}' AND object_id=OBJECT_ID(N'dbo.{t}'))",f"CREATE {'UNIQUE ' if unique else ''}INDEX [{name}] ON [dbo].[{t}] ({','.join('['+k+']' for k in keys)}){include}{' WHERE '+where if where else ''} WITH (DATA_COMPRESSION=PAGE);"]
    out+=['COMMIT TRANSACTION;','END TRY','BEGIN CATCH','IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;','THROW;','END CATCH;','']
    return '\n'.join(out)

if __name__=='__main__':
    target=Path(__file__).resolve().parents[3]/'sql'/'2026-10-19_qisemi_schema.sql'
    target.write_text(ddl(),encoding='utf-8')
    print(f'{len(TABLES)} tables: {target}')
