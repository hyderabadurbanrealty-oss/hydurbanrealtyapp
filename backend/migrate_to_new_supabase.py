"""
Migrate all data from current Supabase to new Supabase database.

This script:
1. Exports all tables from source database
2. Creates tables in target database (if needed)
3. Migrates all data
4. Optionally migrates storage files

Usage:
    python migrate_to_new_supabase.py [--skip-storage] [--tables-only]
"""

import psycopg2
import psycopg2.extras
import psycopg2.extensions
import sys
import argparse
import json
from datetime import datetime
from typing import List, Dict, Any

# Register JSON adapter
psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
psycopg2.extensions.register_adapter(list, psycopg2.extras.Json)

# ═══════════════════════════════════════════════════════════════════════════
# SOURCE DATABASE (Current Supabase)
# ═══════════════════════════════════════════════════════════════════════════
SOURCE_DB = {
    'host': 'aws-0-ap-northeast-1.pooler.supabase.com',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres.qjgwnbszmojzgwmafvuc',
    'password': 'LZGJwY0ryKkFKH5P',
    'sslmode': 'require'
}

# ═══════════════════════════════════════════════════════════════════════════
# TARGET DATABASE (New Supabase)
# ═══════════════════════════════════════════════════════════════════════════
TARGET_DB = {
    'host': 'aws-0-ap-south-1.pooler.supabase.com',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres.rhcepzstokcjuccxhfmm',
    'password': 'HyduUban@!986',
    'sslmode': 'require'
}

# Tables to migrate (in order - respecting foreign key dependencies)
TABLES_TO_MIGRATE = [
    'users',
    'projects',
    'media',
    'reviews',
    'favorites',
    'saved_properties',
    'saved_searches',
    'email_verification_tokens',
    'password_reset_tokens',
    'refresh_tokens',
    'comparison_results'
]


def connect_source():
    """Connect to source database."""
    print("🔌 Connecting to SOURCE database...")
    return psycopg2.connect(**SOURCE_DB)


def connect_target():
    """Connect to target database."""
    print("🔌 Connecting to TARGET database...")
    return psycopg2.connect(**TARGET_DB)


def get_table_schema(conn, table_name: str) -> str:
    """Get CREATE TABLE statement for a table."""
    cur = conn.cursor()
    
    # Get table columns with data types
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            column_default,
            is_nullable,
            udt_name
        FROM information_schema.columns
        WHERE table_name = %s
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns = cur.fetchall()
    
    if not columns:
        return None
    
    # Build CREATE TABLE statement
    col_defs = []
    sequences_to_create = []
    
    for col in columns:
        col_name = col[0]
        data_type = col[1]
        max_length = col[2]
        default = col[3]
        nullable = col[4]
        udt_name = col[5]
        
        # Handle specific types
        if data_type == 'character varying' and max_length:
            type_str = f'VARCHAR({max_length})'
        elif data_type == 'ARRAY':
            type_str = udt_name.replace('_', '') + '[]'
        elif data_type == 'USER-DEFINED' or udt_name in ('json', 'jsonb'):
            type_str = 'JSONB'
        else:
            type_str = data_type.upper()
        
        col_def = f'"{col_name}" {type_str}'
        
        # Handle defaults - create sequences if needed
        if default:
            if 'nextval' in default:
                # Extract sequence name
                seq_name = default.split("'")[1] if "'" in default else f'{table_name}_{col_name}_seq'
                sequences_to_create.append(seq_name)
                col_def += f' DEFAULT nextval(\'{seq_name}\'::regclass)'
            else:
                col_def += f' DEFAULT {default}'
        
        if nullable == 'NO':
            col_def += ' NOT NULL'
        
        col_defs.append(col_def)
    
    # Get primary key
    cur.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
    """, (f'public.{table_name}',))
    
    pk_cols = [row[0] for row in cur.fetchall()]
    if pk_cols:
        pk_cols_str = ', '.join([f'"{col}"' for col in pk_cols])
        col_defs.append(f'PRIMARY KEY ({pk_cols_str})')
    
    # Build complete SQL with sequences
    sql_statements = []
    
    # Create sequences first
    for seq_name in sequences_to_create:
        sql_statements.append(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")
    
    # Create table
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n  '
    create_sql += ',\n  '.join(col_defs)
    create_sql += '\n)'
    sql_statements.append(create_sql)
    
    cur.close()
    return sql_statements


def table_exists(conn, table_name: str) -> bool:
    """Check if table exists in target database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def get_row_count(conn, table_name: str) -> int:
    """Get row count for a table."""
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count = cur.fetchone()[0]
        cur.close()
        return count
    except:
        cur.close()
        return 0


def migrate_table(source_conn, target_conn, table_name: str) -> tuple[int, int]:
    """
    Migrate a single table from source to target.
    Returns (rows_exported, rows_imported)
    """
    print(f"\n📦 Migrating table: {table_name}")
    
    # Check if table exists in source
    if not table_exists(source_conn, table_name):
        print(f"  ⚠️  Table '{table_name}' not found in source - skipping")
        return (0, 0)
    
    # Get row count from source
    source_count = get_row_count(source_conn, table_name)
    print(f"  📊 Source rows: {source_count}")
    
    if source_count == 0:
        print(f"  ⏭️  Empty table - skipping")
        return (0, 0)
    
    # Create table in target if it doesn't exist
    if not table_exists(target_conn, table_name):
        print(f"  🏗️  Creating table in target database...")
        sql_statements = get_table_schema(source_conn, table_name)
        if sql_statements:
            target_cur = target_conn.cursor()
            for sql in sql_statements:
                try:
                    target_cur.execute(sql)
                except Exception as e:
                    print(f"  ⚠️  {e}")
            target_conn.commit()
            target_cur.close()
            print(f"  ✅ Table created")
        else:
            print(f"  ❌ Could not get table schema")
            return (0, 0)
    
    # Get all data from source
    source_cur = source_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    source_cur.execute(f'SELECT * FROM "{table_name}"')
    rows = source_cur.fetchall()
    source_cur.close()
    
    if not rows:
        return (0, 0)
    
    # Get column names
    columns = list(rows[0].keys())
    
    # Truncate target table (optional - comment out if you want to append)
    target_cur = target_conn.cursor()
    target_cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')
    target_conn.commit()
    
    # Insert data into target
    print(f"  💾 Inserting {len(rows)} rows...")
    
    placeholders = ', '.join(['%s'] * len(columns))
    cols_str = ', '.join([f'"{col}"' for col in columns])
    insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'
    
    inserted = 0
    batch_size = 1000
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        values = [[row[col] for col in columns] for row in batch]
        
        try:
            psycopg2.extras.execute_batch(target_cur, insert_sql, values, page_size=batch_size)
            target_conn.commit()
            inserted += len(batch)
            print(f"  ⏳ Progress: {inserted}/{len(rows)} rows", end='\r')
        except Exception as e:
            print(f"\n  ❌ Error inserting batch: {e}")
            target_conn.rollback()
            # Try inserting one by one for this batch
            for row_values in values:
                try:
                    target_cur.execute(insert_sql, row_values)
                    target_conn.commit()
                    inserted += 1
                except Exception as e2:
                    print(f"  ❌ Error inserting row: {e2}")
                    target_conn.rollback()
    
    target_cur.close()
    
    print(f"\n  ✅ Migrated {inserted}/{len(rows)} rows")
    
    return (len(rows), inserted)


def migrate_all_tables():
    """Migrate all tables from source to target."""
    print("=" * 70)
    print("🚀 SUPABASE DATABASE MIGRATION")
    print("=" * 70)
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    source_conn = None
    target_conn = None
    
    try:
        # Connect to databases
        source_conn = connect_source()
        target_conn = connect_target()
        
        print("✅ Connected to both databases\n")
        
        # Migration summary
        total_exported = 0
        total_imported = 0
        results = []
        
        # Migrate each table
        for table_name in TABLES_TO_MIGRATE:
            exported, imported = migrate_table(source_conn, target_conn, table_name)
            total_exported += exported
            total_imported += imported
            results.append({
                'table': table_name,
                'exported': exported,
                'imported': imported,
                'success': exported == imported
            })
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 MIGRATION SUMMARY")
        print("=" * 70)
        
        for result in results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['table']:<30} {result['exported']:>6} → {result['imported']:>6}")
        
        print("-" * 70)
        print(f"{'TOTAL':<32} {total_exported:>6} → {total_imported:>6}")
        print("=" * 70)
        
        success_rate = (total_imported / total_exported * 100) if total_exported > 0 else 0
        print(f"\n✨ Migration completed: {success_rate:.1f}% success rate")
        print(f"📅 Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if source_conn:
            source_conn.close()
            print("\n🔌 Disconnected from source database")
        if target_conn:
            target_conn.close()
            print("🔌 Disconnected from target database")


def list_tables_info():
    """List all tables with row counts from both databases."""
    print("\n" + "=" * 70)
    print("📋 DATABASE COMPARISON")
    print("=" * 70)
    
    source_conn = connect_source()
    target_conn = connect_target()
    
    print(f"\n{'Table':<30} {'Source':<15} {'Target':<15}")
    print("-" * 70)
    
    for table in TABLES_TO_MIGRATE:
        source_count = get_row_count(source_conn, table)
        target_count = get_row_count(target_conn, table)
        status = "✅" if source_count == target_count else "⚠️"
        print(f"{status} {table:<28} {source_count:>13,} {target_count:>13,}")
    
    source_conn.close()
    target_conn.close()
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate Supabase database')
    parser.add_argument('--info', action='store_true', help='Show table info only')
    parser.add_argument('--table', type=str, help='Migrate specific table only')
    
    args = parser.parse_args()
    
    if args.info:
        list_tables_info()
    elif args.table:
        source_conn = connect_source()
        target_conn = connect_target()
        migrate_table(source_conn, target_conn, args.table)
        source_conn.close()
        target_conn.close()
    else:
        migrate_all_tables()
