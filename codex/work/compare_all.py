import csv
for n in range(6,12):
  old=[]; new=[]
  with open('outputs/square_potts_3state_zeros.csv',newline='',encoding='utf-8') as f:
    old=[complex(float(x['real_x']),float(x['imag_x'])) for x in csv.DictReader(f) if int(x['N'])==n]
  with open(f'work/refined_decimal_{n}.csv',newline='',encoding='utf-8') as f:
    new=[complex(float(x['real_x']),float(x['imag_x'])) for x in csv.DictReader(f)]
  shifts=[min(abs(z-w) for w in new) for z in old]
  print(n,'median matched shift',sorted(shifts)[len(shifts)//2],'p95',sorted(shifts)[int(.95*len(shifts))],'max',max(shifts))
