import csv
from collections import defaultdict
old=defaultdict(list); new=defaultdict(list)
for path, target in [('outputs/square_potts_3state_zeros.csv',old),('work/refined_decimal_10.csv',new)]:
    with open(path,newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if 'N' in row and int(row['N']) != 10: continue
            if 'real_x' in row: target[10].append(complex(float(row['real_x']),float(row['imag_x'])))
            else: target[10].append(complex(float(row['real_x']),float(row['imag_x'])))
a,b=old[10],new[10]
for arr in (a,b):
    pass
changes=[min(abs(z-w) for w in b) for z in a]
print('max nearest displacement',max(changes),'median',sorted(changes)[len(changes)//2],'p95',sorted(changes)[int(.95*len(changes))])
print('matched above 1e-6',sum(c>1e-6 for c in changes),'above 1e-3',sum(c>1e-3 for c in changes))
