import csv, collections
for fn in ['outputs/square_potts_3state_large_coefficients.csv','outputs/square_potts_3state_large_zeros.csv']:
    counts=collections.Counter()
    with open(fn,newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f): counts[int(row['N'])]+=1
    print(fn,dict(counts))
with open('outputs/square_potts_3state_large_zeros.csv',newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
for n in (12,13,14):
    rs=[float(r['relative_residual']) for r in rows if int(r['N'])==n]
    print(n,'max logged scaled residual',max(rs))
