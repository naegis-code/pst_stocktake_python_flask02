from decimal import Decimal
import pandas as pd

chg_no_zero_count_dtype_decimal_map = {'Cnt': Decimal, 'Variance': Decimal, 'Total': Decimal}
    
dtype_decimal = chg_no_zero_count_dtype_decimal_map.keys()

path = r'D:\Users\prthanap\Documents\chg\NoCount.xls'

df = pd.read_excel(path, sheet_name='Sheet1',engine='xlrd',dtype=str)

for col in dtype_decimal:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).round(3)

df.columns = df.columns.str.strip().str.lower()

df['bu'] = 'CHG'
df['stcode'] = '60964'
df['skutype'] = 'Credit'
df['rpname'] = 'NOC2'
df['cntdate'] = '20240630'



df = df.groupby(['bu', 'stcode', 'cntdate', 'skutype', 'rpname'], as_index=False).agg(
    sku=('sku', 'count')
)


print(df.head())
