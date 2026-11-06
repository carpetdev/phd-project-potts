import csv, sys
from decimal import Decimal as D, getcontext
getcontext().prec=80
n=int(sys.argv[1])
co=[]
with open('outputs/square_potts_3state_coefficients.csv',newline='',encoding='utf-8') as f:
    co=[D(r['exact_coefficient']) for r in csv.DictReader(f) if int(r['N'])==n]
zs=[]
with open(f'work/refined_decimal_{n}.csv',newline='',encoding='utf-8') as f:
    for row in csv.DictReader(f): zs.append((D(row['real_x']),D(row['imag_x'])))
errs=[]
for x,y in zs:
    pr,pi=co[-1],D(0)
    for c in reversed(co[:-1]): pr,pi=pr*x-pi*y+c,pr*y+pi*x
    r=(x*x+y*y).sqrt(); den=D(0); rp=D(1)
    for c in co: den+=c*rp; rp*=r
    errs.append(((pr*pr+pi*pi).sqrt()/den))
cs=[complex(float(x),float(y)) for x,y in zs]
conj=max(min(abs(w-z.conjugate()) for w in cs) for z in cs)
print(n,'roots',len(zs),'max residual',max(errs),'conjugacy',conj,'range',min(z.real for z in cs),max(z.real for z in cs),min(z.imag for z in cs),max(z.imag for z in cs))
