import pyodbc
import pandas as pd

cn = pyodbc.connect(
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=localhost\\SQLEXPRESS;"      # double the backslash
    "Database=ParkingTickets;"
    "Trusted_Connection=yes;"            # Windows auth
)

df = pd.read_sql("SELECT TOP 5 * FROM sys.tables;", cn)
print(df)
