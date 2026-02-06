import pandas as pd



path = r'D:\Users\prthanap\Documents\chg\NoCount.xls'


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
    sku=('sku', 'count'))



print(df.head())