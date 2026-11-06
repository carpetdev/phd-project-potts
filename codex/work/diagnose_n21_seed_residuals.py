import csv
import math
from decimal import Decimal, localcontext
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with (root / "outputs/ising_2state_21x21_coefficients.csv").open() as f:
    coeffs = [int(row["exact_coefficient"]) for row in csv.DictReader(f)]
reduced = coeffs[21:]
def divide_x_plus_one(values):
    q = [0] * (len(values) - 1)
    q[-1] = values[-1]
    for k in range(len(q)-1, 0, -1):
        q[k-1] = values[k] - q[k]
    return q
for _ in range(40):
    reduced = divide_x_plus_one(reduced)
with (root / "work/ising_q2_n21_aberth3000_seeds.csv").open() as f:
    seeds = [tuple(map(float, line.split(","))) for line in f if line.strip()]

with localcontext() as ctx:
    ctx.prec = 70
    exact = [Decimal(c) for c in reduced]
    zero = Decimal(0)
    errors = []
    for index, (re, im) in enumerate(seeds):
        z = Decimal(repr(re)), Decimal(repr(im))
        p = (exact[-1], zero)
        for c in reversed(exact[:-1]):
            p = (p[0]*z[0] - p[1]*z[1] + c,
                 p[0]*z[1] + p[1]*z[0])
        radius = (z[0]*z[0] + z[1]*z[1]).sqrt()
        denom, power = zero, Decimal(1)
        for c in exact:
            denom += abs(c)*power
            power *= radius
        residual = (p[0]*p[0] + p[1]*p[1]).sqrt()/denom
        errors.append((residual, index, re, im))
    errors.sort(reverse=True)
    print("seed residual quantiles:", *(f"{errors[int(q*len(errors))][0]:.3g}" for q in (.5, .9, .99)))
    print("worst 12:")
    for e in errors[:12]:
        print(e[1]+1, e[2], e[3], f"{e[0]:.3g}")
