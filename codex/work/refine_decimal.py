from __future__ import annotations

import csv
import sys
from collections import defaultdict
from decimal import Decimal, getcontext

getcontext().prec = 75
D = Decimal
ONE = D(1)
ZERO = D(0)

def add(a, b): return (a[0] + b[0], a[1] + b[1])
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def mul(a, b): return (a[0]*b[0] - a[1]*b[1], a[0]*b[1] + a[1]*b[0])
def div(a, b):
    den = b[0]*b[0] + b[1]*b[1]
    return ((a[0]*b[0] + a[1]*b[1])/den, (a[1]*b[0] - a[0]*b[1])/den)

n = int(sys.argv[1])
coeffs = []
with open('outputs/square_potts_3state_coefficients.csv', newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if int(row['N']) == n: coeffs.append(D(row['exact_coefficient']))
roots = []
with open('outputs/square_potts_3state_zeros.csv', newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if int(row['N']) == n: roots.append((D(row['real_x']), D(row['imag_x'])))
degree = len(coeffs)-1
threshold2 = D('1e-90')
for iteration in range(250):
    updated = []
    max_step2 = ZERO
    for i, z in enumerate(roots):
        p, dp = ((coeffs[-1], ZERO), (ZERO, ZERO))
        for c in reversed(coeffs[:-1]):
            dp = add(mul(dp, z), p)
            p = add(mul(p, z), (c, ZERO))
        newton = div(p, dp)
        sigma = (ZERO, ZERO)
        for j, w in enumerate(roots):
            if i != j: sigma = add(sigma, div((ONE, ZERO), sub(z, w)))
        den = sub((ONE, ZERO), mul(newton, sigma))
        correction = div(newton, den)
        updated.append(sub(z, correction))
        step2 = correction[0]*correction[0] + correction[1]*correction[1]
        if step2 > max_step2: max_step2 = step2
    roots = updated
    if iteration % 10 == 0:
        print(f'N={n} iter={iteration} max_step={max_step2.sqrt():.3E}', flush=True)
    if max_step2 < threshold2: break

print(f'FINISHED N={n} iter={iteration} max_step={max_step2.sqrt():.3E}')
out = f'work/refined_decimal_{n}.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['root_index','real_x','imag_x'])
    for i,z in enumerate(roots,1): w.writerow([i, str(z[0]), str(z[1])])
