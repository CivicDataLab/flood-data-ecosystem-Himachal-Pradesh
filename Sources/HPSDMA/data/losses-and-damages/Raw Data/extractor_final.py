# extractor.py — fresh-load and export every table to CSV
# Run:  python extractor.py

import os, sys, re, pathlib, pyodbc, pandas as pd

# ------------------- CONFIG -------------------
SQL_FILE   = r"D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\Deployment\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\losses-and-damages\Raw Data\losses_export_script.sql"
SOURCE_DB  = "HPSDMA"        # the DB name referenced inside the .sql
TARGET_DB  = "HPSDMA_local"  # local DB to create/refresh
OUTPUT_DIR = r"D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\Deployment\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\losses-and-damages\Raw Data\extracted_tables"

# Drop DB first so re-runs don't collide with existing objects
DROP_DB_FIRST = True

# ODBC driver & server (adjust DRIVER if you only have 17)

DRIVER = "ODBC Driver 18 for SQL Server"   # or "ODBC Driver 17 for SQL Server"
SERVER = r"(localdb)\MSSQLLocalDB"         # or your named pipe/host,port
TRUSTED_CONNECTION = True                     # True for Windows auth to LocalDB

# Exports
EXPORT_CSV = True
EXPORT_PARQUET = False   # needs pyarrow

# ------------------- INTERNALS -------------------
GO_LINE = re.compile(r'^\s*GO(?:\s+--.*)?\s*$', re.IGNORECASE)
USE_SRC = re.compile(rf'^\s*USE\s+\[?{re.escape(SOURCE_DB)}\]?\s*;?\s*$', re.IGNORECASE)
DB_QUAL = re.compile(rf'\[\s*{re.escape(SOURCE_DB)}\s*\]\s*\.\s*', re.IGNORECASE)  # [HPSDMA].

# Some scripted filegroup clauses to strip (don’t matter for LocalDB)
ON_PRIMARY = re.compile(r'\bON\s+\[?PRIMARY\]?\b.*?(?=(,|;|\n|$))', re.IGNORECASE | re.DOTALL)
TEXTIMAGE  = re.compile(r'\bTEXTIMAGE_ON\s+\[?PRIMARY\]?\b.*?(?=(,|;|\n|$))', re.IGNORECASE | re.DOTALL)

SKIP_BATCH_PREFIXES = (
    "CREATE DATABASE",
    "ALTER DATABASE",
    "ALTER AUTHORIZATION",
    "EXEC sys.sp_db_vardecimal_storage_format",
)

def make_conn_str(database: str) -> str:
    parts = [
        "DRIVER={" + DRIVER + "}",          # <-- build braces explicitly
        "SERVER=" + SERVER,
        "DATABASE=" + database,
        "TrustServerCertificate=Yes",
    ]
    if TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=Yes")
    return ";".join(parts)

def read_sql_text(path: str) -> str:
    b = pathlib.Path(path).read_bytes()
    # Prefer utf-16 (SSMS often saves as UTF-16 LE). Fallback to utf-8.
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        text = b.decode("utf-16")
    else:
        # strip UTF-8 BOM if any
        if b.startswith(b"\xef\xbb\xbf"):
            b = b[3:]
        text = b.decode("utf-8", errors="ignore")
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove zero-width chars that can break GO detection
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060"):
        text = text.replace(ch, "")
    return text

def transform_line(line: str) -> str:
    # drop "USE [HPSDMA]" lines
    if USE_SRC.match(line):
        return ""
    # remove [HPSDMA]. qualifiers so objects resolve in TARGET_DB
    return DB_QUAL.sub("", line)

def transform_batch_sql(sql: str) -> str:
    # strip filegroup noise that’s irrelevant in LocalDB
    sql = ON_PRIMARY.sub("", sql)
    sql = TEXTIMAGE.sub("", sql)
    return sql.strip()

def should_skip_batch(sql: str) -> bool:
    s = sql.lstrip().upper()
    return any(s.startswith(p) for p in SKIP_BATCH_PREFIXES)

def drop_db_if_exists():
    if not DROP_DB_FIRST:
        return
    with pyodbc.connect(make_conn_str("master"), autocommit=True) as cn:
        # kick users and drop if present
        cn.execute(f"""
        IF DB_ID(N'{TARGET_DB}') IS NOT NULL
        BEGIN
            ALTER DATABASE [{TARGET_DB}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
            DROP DATABASE [{TARGET_DB}];
        END
        """)

def ensure_db():
    with pyodbc.connect(make_conn_str("master"), autocommit=True) as cn:
        cn.execute(f"IF DB_ID('{TARGET_DB}') IS NULL CREATE DATABASE [{TARGET_DB}];")

def load_dump():
    text = read_sql_text(SQL_FILE)
    lines = text.split("\n")

    fail_path = pathlib.Path("loader_fail_batch.sql")
    if fail_path.exists():
        fail_path.unlink()

    go_count = 0
    batch_num = 0
    batch_buf = []

    def exec_batch(cur, sql_text: str, num: int):
        sql_text = transform_batch_sql(sql_text)
        if not sql_text or should_skip_batch(sql_text):
            return
        try:
            cur.execute(sql_text)
        except Exception as e:
            # Save failing batch for inspection
            # Save as UTF-16 so you can re-open in Notepad if needed
            try:
                fail_path.write_text(sql_text, encoding="utf-16")
            except Exception:
                fail_path.write_text(sql_text, encoding="utf-8", errors="ignore")
            print(f"\n[ERROR] Batch #{num} failed. First 400 chars:\n{sql_text[:400]}\n", file=sys.stderr)
            print(f"Saved full failing batch to: {fail_path.resolve()}", file=sys.stderr)
            raise

    with pyodbc.connect(make_conn_str(TARGET_DB), autocommit=True) as cn:
        cur = cn.cursor()
        for ln in lines:
            if GO_LINE.match(ln):
                go_count += 1
                batch_num += 1
                exec_batch(cur, "".join(batch_buf), batch_num)
                batch_buf = []
            else:
                tl = transform_line(ln)
                if tl:
                    batch_buf.append(tl + "\n")

        if batch_buf:
            batch_num += 1
            exec_batch(cur, "".join(batch_buf), batch_num)

    print(f"Loaded script into {TARGET_DB}. Detected GO lines: {go_count}, executed batches: {batch_num}")

def export_all_tables():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with pyodbc.connect(make_conn_str(TARGET_DB)) as conn:
        tables = pd.read_sql("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """, conn)

        # quick profile
        prof = []
        for _, r in tables.iterrows():
            schema, table = r.TABLE_SCHEMA, r.TABLE_NAME
            fq = f"[{schema}].[{table}]"
            n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {fq}", conn).iloc[0,0]
            cols = pd.read_sql(f"""
                SELECT c.name AS col, t.name AS typ
                FROM sys.columns c JOIN sys.types t ON c.user_type_id=t.user_type_id
                WHERE c.[object_id]=OBJECT_ID('{schema}.{table}')
            """, conn)
            prof.append({"table": f"{schema}.{table}", "rows": n, "columns": len(cols)})
        pd.DataFrame(prof).to_csv(os.path.join(OUTPUT_DIR, "_profile_summary.csv"), index=False)
        print("Wrote:", os.path.join(OUTPUT_DIR, "_profile_summary.csv"))

        # export CSVs (chunked)
        for _, r in tables.iterrows():
            schema, table = r.TABLE_SCHEMA, r.TABLE_NAME
            fq = f"[{schema}].[{table}]"
            csv_path = os.path.join(OUTPUT_DIR, f"{schema}.{table}.csv")
            print("Exporting", csv_path)
            first = True
            for chunk in pd.read_sql(f"SELECT * FROM {fq}", conn, chunksize=100_000):
                if EXPORT_CSV:
                    chunk.to_csv(csv_path, index=False, header=first, mode='w' if first else 'a')
                first = False
            if EXPORT_PARQUET:
                try:
                    df = pd.read_sql(f"SELECT * FROM {fq}", conn)  # caution for very large tables
                    df.to_parquet(os.path.join(OUTPUT_DIR, f"{schema}.{table}.parquet"), index=False)
                except Exception as e:
                    print(f"Parquet skipped for {schema}.{table}: {e}")

def main():
    print("Drivers:", pyodbc.drivers())
    test_conn = pyodbc.connect(make_conn_str("master"), autocommit=True)
    print("✅ Smoke test OK: connected to master")
    test_conn.close()
    if not pathlib.Path(SQL_FILE).exists():
        print(f"ERROR: SQL file not found: {SQL_FILE}")
        sys.exit(1)
    conn = pyodbc.connect(make_conn_str("master"), autocommit=True)
    print("Connected to master OK")
    # If LocalDB isn’t running or driver differs, adjust DRIVER or SERVER accordingly.
    # print(pyodbc.drivers())

    drop_db_if_exists()
    ensure_db()
    load_dump()
    export_all_tables()
    print("Done.")

if __name__ == "__main__":
    main()
