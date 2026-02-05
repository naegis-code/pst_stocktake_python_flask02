import pandas as pd
from sqlalchemy import create_engine,text
import db_connect

username = '20020016'
bu = 'B2S'
stcode = '50019'
atype = '3F'
cntdate = '2025-12-11'
cntdate_plan = cntdate.replace('-','')
print( cntdate_plan )

cntnum = bu + stcode + atype[1:2] + cntdate[:4] + cntdate[5:7] + cntdate[8:10] + '001'
print( cntnum )

engine = db_connect.engine

df_plan = pd.read_sql(f"""
    SELECT bu,stcode,branch from planall2 where bu = '{bu}' and stcode = '{stcode}' and cntdate = '{cntdate_plan}'
""", engine)
print('length plan:', len(df_plan))

df_stocktakeid = pd.read_sql(f"""
    SELECT 1 from stocktakeid where cntnum = '{cntnum}'
""", engine)
print('length stocktakeid:', len(df_stocktakeid))


if not df_plan.empty and df_stocktakeid.empty:
    print('ข้อมูลถูกต้อง - สร้าง cntnum ใหม่')
    try:
        with engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO stocktakeid (cntnum, bu, stcode, atype, cntdate, username, count_step, status, branch)
                VALUES ('{cntnum}', '{bu}', '{stcode}', '{atype}', '{cntdate}', '{username}', 1, 'สร้าง CNTNUM', '{df_plan.iloc[0]["branch"]}')
            """))
            conn.commit()
            print('สร้าง cntnum สำเร็จ:', cntnum)
    except Exception as e:
        print('เกิดข้อผิดพลาดในการสร้าง cntnum:', e)
else:
    print('ข้อมูลไม่ถูกต้อง - ไม่สามารถสร้าง cntnum ใหม่ได้')
    


