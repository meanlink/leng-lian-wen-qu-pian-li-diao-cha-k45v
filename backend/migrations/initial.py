from sqlalchemy import text
from src.config.database import Base, engine
from src import models
EXTRA_COLUMNS={
    'jobs':[('version_id','INT'),('version_no','INT')],
    'deliveries':[('version_id','INT'),('version_no','INT'),('superseded_by','INT')],
}
def _existing_columns(conn,table):
    if engine.dialect.name=='sqlite':
        return {r[1] for r in conn.execute(text(f'PRAGMA table_info({table})'))}
    return {r[0] for r in conn.execute(text('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t'),{'t':table})}
def migrate():
    Base.metadata.create_all(engine)
    # 老库就地补列；新建库由 create_all 一次到位，下述检查自动跳过
    with engine.begin() as conn:
        for table,columns in EXTRA_COLUMNS.items():
            have=_existing_columns(conn,table)
            for name,ddl in columns:
                if name not in have:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
if __name__=='__main__':migrate()
