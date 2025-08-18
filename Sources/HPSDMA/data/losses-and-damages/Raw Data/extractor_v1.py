# save as load_sqlserver_go_split.py  ->  python load_sqlserver_go_split.py
import pyodbc, os, sys, pathlib, re

SQL_FILE   = r"D:\CivicDataLab_IDS-DRR\IDS-DRR_Github\Deployment\flood-data-ecosystem-Himachal-Pradesh\Sources\HPSDMA\data\losses-and-damages\Raw Data\losses_export_script.sql"  # <— your .sql
SOURCE_DB  = "HPSDMA"        # <— the DB name referenced IN the dump
TARGET_DB  = "HPSDMA_local"  # <— your local DB name

# Use the driver you actually have (check:  import pyodbc; print(pyodbc.drivers()))
CONN_STR_MASTER = r"DRIVER={ODBC Driver 18 for SQL Server};SERVER=(localdb)\MSSQLLocalDB;DATABASE=master;Trusted_Connection=Yes;TrustServerCertificate=Yes"
CONN_STR_DB     = CONN_STR_MASTER.replace("DATABASE=master", f"DATABASE={TARGET_DB}")
GO_LINE = re.compile(r'^\s*GO(?:\s+--.*)?\s*$', re.IGNORECASE)

def strip_bom_open_text(path):
    b = pathlib.Path(path).read_bytes()
    # Drop UTF-8 BOM at file start if present
    if b.startswith(b'\xef\xbb\xbf'):
        b = b[3:]
    text = b.decode("utf-16", errors="ignore")
    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove hidden zero-width chars that break GO detection
    ZW = "\ufeff\u200b\u200c\u200d\u2060"
    for ch in ZW:
        text = text.replace(ch, "")
    return text

def transform_line(line: str) -> str:
    # Drop any USE [HPSDMA] lines entirely
    s = line.strip().upper()
    if s.startswith("USE ") and SOURCE_DB.upper() in s:
        return ""  # skip this line
    # Remove [HPSDMA]. qualifiers (e.g., [HPSDMA].[dbo] -> [dbo])
    # Do it case-insensitively without regex
    return line.replace(f"[{SOURCE_DB}].", "").replace(f"[{SOURCE_DB.lower()}].", "").replace(f"[{SOURCE_DB.upper()}].", "")

def main():
    # 1) Ensure target DB exists
    with pyodbc.connect(CONN_STR_MASTER, autocommit=True) as cn:
        cn.execute(f"IF DB_ID('{TARGET_DB}') IS NULL CREATE DATABASE {TARGET_DB};")

    text = strip_bom_open_text(SQL_FILE)
    lines = text.split("\n")

    fail_path = pathlib.Path("loader_fail_batch.sql")
    if fail_path.exists():
        fail_path.unlink()

    go_count = 0
    batch_num = 0
    batch_buf = []

    def exec_batch(cur, sql_text: str, num: int):
        sql_text = sql_text.strip()
        if not sql_text:
            return
        try:
            cur.execute(sql_text)
        except Exception as e:
            fail_path.write_text(sql_text, encoding="utf-16")
            print(f"\n[ERROR] Batch #{num} failed. First 400 chars:\n{sql_text[:400]}\n")
            print(f"Saved full failing batch to: {fail_path.resolve()}")
            raise

    # 2) Connect and stream-execute per batch
    with pyodbc.connect(CONN_STR_DB, autocommit=True) as cn:
        cur = cn.cursor()
        for ln in lines:
            if GO_LINE.match(ln):
                go_count += 1
                batch_num += 1
                exec_batch(cur, "".join(batch_buf), batch_num)
                batch_buf = []
                continue
            tl = transform_line(ln)
            if tl:
                batch_buf.append(tl + "\n")

        # last (tail) batch
        if batch_buf:
            batch_num += 1
            exec_batch(cur, "".join(batch_buf), batch_num)

    print(f"Loaded script into {TARGET_DB}. Detected GO separators: {go_count}, executed batches: {batch_num}")

if __name__ == "__main__":
    main()
