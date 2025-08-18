import pyodbc

DRIVER = "ODBC Driver 18 for SQL Server"   # or "ODBC Driver 17 for SQL Server"
SERVER = r"(localdb)\MSSQLLocalDB"
TRUSTED_CONNECTION = True

def make_conn_str(database: str) -> str:
    parts = [
        "DRIVER={" + DRIVER + "}",
        "SERVER=" + SERVER,
        "DATABASE=" + database,
        "TrustServerCertificate=Yes",
    ]
    if TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=Yes")
    return ";".join(parts)

if __name__ == "__main__":
    print("Available drivers:", pyodbc.drivers())
    conn_str = make_conn_str("master")
    print("Connection string:", conn_str)
    conn = pyodbc.connect(conn_str, autocommit=True)
    print("✅ Connected successfully to master DB")
    conn.close()
