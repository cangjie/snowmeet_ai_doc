"""Export only reviewed legacy food objects; connection is supplied by caller.

Produces a SQL restore script and JSON catalog/data archive. No connection/config
loading, no writes to the database, no staff/shared table export.
"""
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import json
from pathlib import Path

TABLES = frozenset('''fnb_material_category fnb_material_item fnb_shelf_life_rule
fnb_material_batch fnb_material_batch_stock fnb_material_alert_log fnb_dish_spec
fnb_recipe fnb_recipe_line fnb_stock_document fnb_stock_document_line
fnb_stock_movement fnb_stocktake_line fnb_order fnb_order_line fnb_order_import
fnb_channel_shop fnb_channel_dish_map'''.split())
VIEWS = frozenset(('vw_fnb_material_stock', 'vw_fnb_material_loss'))


def quote(value):
    return '[' + value.replace(']', ']]') + ']'


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return '1' if value else '0'
    if isinstance(value, (int, Decimal)): return str(value)
    if isinstance(value, float):
        import math
        if not math.isfinite(value): raise ValueError('Nonfinite SQL value')
        return repr(value)
    if isinstance(value, (bytes, bytearray, memoryview)): return '0x' + bytes(value).hex()
    if isinstance(value, (datetime, date, time)): value = value.isoformat()
    return "N'" + str(value).replace("'", "''") + "'"


def export(connection, folder):
    folder = Path(folder)
    if folder.exists(): raise ValueError('Backup destination already exists')
    cur = connection.cursor()
    def rows(sql):
        cur.execute(sql)
        names = [c[0] for c in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]
    objects = rows("SELECT o.object_id,o.name,RTRIM(o.type) AS type FROM sys.objects o WHERE o.schema_id=SCHEMA_ID('dbo') AND o.type IN ('U','V')")
    objects = [o for o in objects if o['name'] in TABLES | VIEWS]
    ids = ','.join(str(int(o['object_id'])) for o in objects) or '0'
    catalog = {'objects': objects}
    catalog['columns'] = rows(f"""SELECT c.object_id,c.column_id,c.name,t.name AS type_name,t.is_user_defined,c.max_length,c.precision,c.scale,
     c.is_nullable,c.is_identity,c.collation_name,c.is_computed,cc.definition AS computed_definition,cc.is_persisted,
     CONVERT(decimal(38,0),ic.seed_value) AS seed_value,CONVERT(decimal(38,0),ic.increment_value) AS increment_value,
     CONVERT(decimal(38,0),ic.last_value) AS last_value,dc.name AS default_name,dc.definition AS default_definition
     FROM sys.columns c JOIN sys.types t ON t.user_type_id=c.user_type_id
     LEFT JOIN sys.computed_columns cc ON cc.object_id=c.object_id AND cc.column_id=c.column_id
     LEFT JOIN sys.identity_columns ic ON ic.object_id=c.object_id AND ic.column_id=c.column_id
     LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id WHERE c.object_id IN ({ids}) ORDER BY c.object_id,c.column_id""")
    catalog['indexes'] = rows(f"SELECT i.object_id,i.index_id,i.name,i.type,i.is_unique,i.is_primary_key,i.is_unique_constraint,i.filter_definition,i.is_disabled FROM sys.indexes i WHERE i.object_id IN ({ids}) AND i.index_id>0 AND i.is_hypothetical=0 ORDER BY i.object_id,i.index_id")
    catalog['index_columns'] = rows(f"SELECT ic.object_id,ic.index_id,ic.key_ordinal,ic.index_column_id,ic.is_descending_key,ic.is_included_column,c.name FROM sys.index_columns ic JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE ic.object_id IN ({ids}) ORDER BY ic.object_id,ic.index_id,ic.key_ordinal,ic.index_column_id")
    catalog['checks'] = rows(f"SELECT parent_object_id,name,definition,is_disabled,is_not_trusted,is_not_for_replication FROM sys.check_constraints WHERE parent_object_id IN ({ids})")
    catalog['foreign_keys'] = rows(f"""SELECT fk.object_id,fk.name,fk.parent_object_id,fk.referenced_object_id,
     OBJECT_SCHEMA_NAME(fk.parent_object_id) AS child_schema,OBJECT_NAME(fk.parent_object_id) AS child,
     OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS parent_schema,OBJECT_NAME(fk.referenced_object_id) AS parent,
     fk.delete_referential_action_desc,fk.update_referential_action_desc,fk.is_disabled,fk.is_not_trusted,fk.is_not_for_replication
     FROM sys.foreign_keys fk WHERE fk.parent_object_id IN ({ids})""")
    catalog['fk_columns'] = rows(f"SELECT f.constraint_object_id,f.constraint_column_id,c.name AS child,p.name AS parent FROM sys.foreign_key_columns f JOIN sys.columns c ON c.object_id=f.parent_object_id AND c.column_id=f.parent_column_id JOIN sys.columns p ON p.object_id=f.referenced_object_id AND p.column_id=f.referenced_column_id WHERE f.parent_object_id IN ({ids}) ORDER BY f.constraint_object_id,f.constraint_column_id")
    catalog['modules'] = rows(f"SELECT object_id,definition,uses_ansi_nulls,uses_quoted_identifier FROM sys.sql_modules WHERE object_id IN ({ids})")
    catalog['properties'] = rows(f"SELECT class,major_id,minor_id,name,CONVERT(nvarchar(max),value) AS value,CONVERT(nvarchar(128),SQL_VARIANT_PROPERTY(value,'BaseType')) AS value_type FROM sys.extended_properties WHERE class=1 AND major_id IN ({ids})")
    catalog['permissions'] = rows(f"SELECT class,major_id,minor_id,permission_name,state_desc,USER_NAME(grantee_principal_id) AS grantee FROM sys.database_permissions WHERE class=1 AND major_id IN ({ids})")
    catalog['data'] = {}
    sql = ['-- Legacy food objects only. Restore into an isolated recovery database first.',
           '-- Shared parent rows must already exist. Never execute over existing objects.',
           '-- ROWVERSION values regenerate on restore; original binary values remain in catalog.json.',
           'SET XACT_ABORT ON; SET NOCOUNT ON;', 'BEGIN TRANSACTION;']
    for obj in objects:
        sql.append(f"IF OBJECT_ID(N'dbo.{obj['name']}') IS NOT NULL THROW 51090, N'Restore target already exists', 1;")
    for obj in sorted(objects, key=lambda o: o['name']):
        if obj['type'] != 'U': continue
        columns = [c for c in catalog['columns'] if c['object_id'] == obj['object_id']]
        definitions = []
        for c in columns:
            if c['is_user_defined']: raise ValueError('User-defined column type requires separate review')
            definition = quote(c['name']) + ' '
            if c['is_computed']:
                definition += 'AS ' + c['computed_definition'] + (' PERSISTED' if c['is_persisted'] else '')
            else:
                kind = c['type_name']
                definition += kind
                if kind in ('varchar','nvarchar','char','nchar','varbinary','binary'):
                    definition += '(' + ('max' if c['max_length'] == -1 else str(c['max_length'] // (2 if kind in ('nvarchar','nchar') else 1))) + ')'
                elif kind in ('decimal','numeric'): definition += f"({c['precision']},{c['scale']})"
                elif kind in ('datetime2','datetimeoffset','time'): definition += f"({c['scale']})"
                if c['collation_name']: definition += ' COLLATE ' + c['collation_name']
                if c['is_identity']: definition += f" IDENTITY({c['seed_value']},{c['increment_value']})"
                definition += ' NULL' if c['is_nullable'] else ' NOT NULL'
                if c['default_name']: definition += ' CONSTRAINT ' + quote(c['default_name']) + ' DEFAULT ' + c['default_definition']
            definitions.append(definition)
        table = 'dbo.' + quote(obj['name'])
        sql.append('CREATE TABLE ' + table + ' (\n  ' + ',\n  '.join(definitions) + '\n);')
        data = rows('SELECT * FROM ' + table)
        catalog['data'][obj['name']] = [{k: literal(v) for k,v in row.items()} for row in data]
        writable = [c for c in columns if not c['is_computed'] and c['type_name'] not in ('timestamp','rowversion')]
        identity = next((c for c in writable if c['is_identity']), None)
        if identity: sql.append('SET IDENTITY_INSERT ' + table + ' ON;')
        for row in data:
            sql.append('INSERT INTO ' + table + ' (' + ','.join(quote(c['name']) for c in writable) + ') VALUES (' + ','.join(literal(row[c['name']]) for c in writable) + ');')
        if identity:
            sql.append('SET IDENTITY_INSERT ' + table + ' OFF;')
            if identity['last_value'] is not None: sql.append(f"DBCC CHECKIDENT ({literal(table)}, RESEED, {identity['last_value']}) WITH NO_INFOMSGS;")
    names = {o['object_id']: 'dbo.' + quote(o['name']) for o in objects}
    for index in catalog['indexes']:
        if index['type'] not in (1,2): raise ValueError('Unsupported legacy index type')
        cols = [c for c in catalog['index_columns'] if c['object_id']==index['object_id'] and c['index_id']==index['index_id']]
        keys = ','.join(quote(c['name']) + (' DESC' if c['is_descending_key'] else ' ASC') for c in cols if c['key_ordinal']>0)
        clustered = 'CLUSTERED' if index['type']==1 else 'NONCLUSTERED'
        table = names[index['object_id']]
        if index['is_primary_key'] or index['is_unique_constraint']:
            sql.append('ALTER TABLE ' + table + ' ADD CONSTRAINT ' + quote(index['name']) + (' PRIMARY KEY ' if index['is_primary_key'] else ' UNIQUE ') + clustered + ' (' + keys + ');')
        else:
            line = 'CREATE ' + ('UNIQUE ' if index['is_unique'] else '') + clustered + ' INDEX ' + quote(index['name']) + ' ON ' + table + ' (' + keys + ')'
            included = ','.join(quote(c['name']) for c in cols if c['is_included_column'])
            if included: line += ' INCLUDE (' + included + ')'
            if index['filter_definition']: line += ' WHERE ' + index['filter_definition']
            sql.append(line + ';')
        if index['is_disabled']: sql.append('ALTER INDEX ' + quote(index['name']) + ' ON ' + table + ' DISABLE;')
    for check in catalog['checks']:
        table = names[check['parent_object_id']]
        sql.append('ALTER TABLE ' + table + (' WITH NOCHECK' if check['is_not_trusted'] else ' WITH CHECK') + ' ADD CONSTRAINT ' + quote(check['name']) + ' CHECK ' + ('NOT FOR REPLICATION ' if check['is_not_for_replication'] else '') + check['definition'] + ';')
        if check['is_disabled']: sql.append('ALTER TABLE ' + table + ' NOCHECK CONSTRAINT ' + quote(check['name']) + ';')
    for fk in catalog['foreign_keys']:
        cols = [c for c in catalog['fk_columns'] if c['constraint_object_id']==fk['object_id']]
        table = names[fk['parent_object_id']]
        line = 'ALTER TABLE ' + table + (' WITH NOCHECK' if fk['is_not_trusted'] else ' WITH CHECK') + ' ADD CONSTRAINT ' + quote(fk['name']) + ' FOREIGN KEY (' + ','.join(quote(c['child']) for c in cols) + ') REFERENCES ' + quote(fk['parent_schema']) + '.' + quote(fk['parent']) + ' (' + ','.join(quote(c['parent']) for c in cols) + ')'
        for action in ('delete','update'): line += ' ON ' + action.upper() + ' ' + fk[action+'_referential_action_desc'].replace('_',' ')
        if fk['is_not_for_replication']: line += ' NOT FOR REPLICATION'
        sql.append(line + ';')
        if fk['is_disabled']: sql.append('ALTER TABLE ' + table + ' NOCHECK CONSTRAINT ' + quote(fk['name']) + ';')
    # Views use CREATE in their own dynamic batches, preserving ANSI/identifier settings.
    for mod in sorted(catalog['modules'], key=lambda m: next(o['name'] for o in objects if o['object_id']==m['object_id']), reverse=True):
        if not mod['definition']: raise ValueError('Encrypted legacy module cannot be exported')
        sql.append('SET ANSI_NULLS ' + ('ON' if mod['uses_ansi_nulls'] else 'OFF') + '; SET QUOTED_IDENTIFIER ' + ('ON' if mod['uses_quoted_identifier'] else 'OFF') + ';')
        definition = mod['definition'].lstrip()
        import re
        definition = re.sub(r'^ALTER\s+VIEW\b', 'CREATE VIEW', definition, count=1, flags=re.I)
        sql.append('EXEC sys.sp_executesql ' + literal(definition) + ';')
    sql.append('COMMIT TRANSACTION;')
    folder.mkdir(parents=True, mode=0o700)
    (folder / 'restore.sql').write_text('\n'.join(sql)+'\n', encoding='utf-8')
    (folder / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    hashes = {name:hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in ('restore.sql','catalog.json')}
    result = {'objects':sorted(o['name'] for o in objects),'row_counts':{k:len(v) for k,v in catalog['data'].items()},'sha256':hashes}
    (folder / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for name,digest in hashes.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest()!=digest: raise ValueError('Backup verification failed')
    return result
