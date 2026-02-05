import pandas as pd



path = r'D:\Users\prthanap\Documents\chg\STK2_Credit_CHG_TW RA2_60964_29012026_Sutichot Vongkamchai 1.xls'


df = pd.read_excel(path, sheet_name='Sheet1',engine='xlrd',dtype=str)

df.columns = df.columns.str.strip().str.lower()

dtype_decimal = ['soh','cntqnt','varianceqnt','varianceperc',
                 'extphycnt_retail','extphycnt_cost','extphy_retailvar',
                 'extphy_costvar','extphycnt_retail_exvat','gmperc']
for col in dtype_decimal:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).round(3)


df['bu'] = 'CHG'
df['stcode'] = df['stmerch']
df['skutype'] = 'Credit'
df['rpname'] = 'STK2'
df['soh_amount'] = df['extphycnt_cost'] - df['extphy_costvar']

df = df.groupby(['bu', 'stcode', 'cntdate', 'skutype', 'rpname'], as_index=False).agg(
    sku=('sku', 'count'),
    # นับจำนวน x:(condition)
    sgain=('varianceqnt',lambda x: (x > 0).sum()),
    sloss=('varianceqnt', lambda x: (x < 0).sum()),
    psoh=('soh', 'sum'),
    pqty=('cntqnt', 'sum'),
    # รวมจำนวนมูลค่า ต้องมีค่า X: x[condition]
    pgain=('varianceqnt', lambda x: x[x > 0].sum()),
    ploss=('varianceqnt', lambda x: x[x < 0].sum()),
    vsoh=('soh_amount', 'sum'),
    vqty=('extphycnt_cost', 'sum'),
    vgain=('extphy_costvar', lambda x: x[x > 0].sum()),
    vloss=('extphy_costvar', lambda x: x[x < 0].sum())
)


print(df.head())

'''Index(['RESULT', 'DOCNAME', 'BUNAME', 'PRNDATE', 'CNTNUM', 'CNTNAME',
       'STMERCH', 'STNAME', 'POSTDATE', 'FREEZEDATE', 'CNTDATE', 'DEPTCODE',
       'DEPTNAME', 'SUBDEPTCODE', 'SUBDEPTNAME', 'SKU', 'SBC', 'IBC',
       'BNDCODE', 'BNDNAME', 'PRNAME', 'PRMODEL', 'SOH', 'CNTQNT',
       'VARIANCEQNT', 'VARIANCEPERC', 'EXTPHYCNT_RETAIL', 'EXTPHYCNT_COST',
       'EXTPHY_RETAILVAR', 'EXTPHY_COSTVAR', 'EXTPHYCNT_RETAIL_EXVAT',
       'GMPERC'],
      dtype='str')
      
_chg_stk_report.py
Index(['result', 'docname', 'buname', 'prndate', 'cntnum', 'cntname',
       'stmerch', 'stname', 'postdate', 'freezedate', 'cntdate', 'deptcode',
       'deptname', 'subdeptcode', 'subdeptname', 'sku', 'sbc', 'ibc',
       'bndcode', 'bndname', 'prname', 'prmodel', 'soh', 'cntqnt',
       'varianceqnt', 'varianceperc', 'extphycnt_retail', 'extphycnt_cost',
       'extphy_retailvar', 'extphy_costvar', 'extphycnt_retail_exvat',
       'gmperc'],
      dtype='str')'''