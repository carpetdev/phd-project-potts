import csv, collections, math
from pathlib import Path
coeffs=collections.defaultdict(list); roots=collections.defaultdict(list)
with open('outputs/square_potts_3state_coefficients.csv', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f): coeffs[int(r['N'])].append(int(r['exact_coefficient']))
with open('outputs/square_potts_3state_zeros.csv', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f): roots[int(r['N'])].append(complex(float(r['real_x']),float(r['imag_x'])))
for n in (8,9,10,11):
    c=coeffs[n]; d=len(c)-1; r=math.exp((math.log(c[0])-math.log(c[-1]))/d)
    a=[0. if v==0 else math.exp(math.log(v)+k*math.log(r)-max(math.log(u)+j*math.log(r) for j,u in enumerate(c) if u)) for k,v in enumerate(c)]
    za=[z/r for z in roots[n]]
    dc=[k*a[k] for k in range(1,len(a))]
    cond=[]; sep=[]
    for i,z in enumerate(za):
        p=sum(abs(v)*abs(z)**k for k,v in enumerate(a))
        der=abs(sum(v*z**k for k,v in enumerate(dc)))
        cond.append(p/(der*max(abs(z),1e-300)))
        sep.append(min(abs(z-w) for j,w in enumerate(za) if j!=i))
    print(n, 'max rel cond', max(cond), 'median', sorted(cond)[len(cond)//2], 'min separation',min(sep), 'median sep', sorted(sep)[len(sep)//2])
