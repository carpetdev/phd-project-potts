import csv, collections, math
path = r'C:\Users\ibata\Documents\Codex\2026-09-25\im\outputs\square_potts_3state_zeros.csv'
by_n = collections.defaultdict(list)
with open(path, newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        z = complex(float(row['real_x']), float(row['imag_x']))
        by_n[int(row['N'])].append((z, float(row['relative_residual'])))
for n, vals in by_n.items():
    zs = [v[0] for v in vals]
    conjugacy = max(min(abs(w-z.conjugate()) for w in zs) for z in zs)
    print(n, len(zs), 'range', min(z.real for z in zs), max(z.real for z in zs), min(z.imag for z in zs), max(z.imag for z in zs), 'conj_error', conjugacy, 'resid', max(v[1] for v in vals))
