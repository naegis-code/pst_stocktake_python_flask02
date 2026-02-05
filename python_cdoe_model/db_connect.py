from sqlalchemy import create_engine

postgsql = {
    'host': '157.85.98.51',
    'database': 'postgres',
    'user': 'postgres',
    'password': '20020015',
    'port': 5432
}

engine = create_engine(
    f"postgresql+psycopg2://{postgsql['user']}:{postgsql['password']}@{postgsql['host']}:{postgsql['port']}/{postgsql['database']}"
)