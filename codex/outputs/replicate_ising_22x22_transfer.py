#!/usr/bin/env python3
"""Compute the exact Q=2 square-lattice polynomial and complex roots for 22x22'.

Run: python replicate_ising_22x22_transfer.py
Requires Python 3, NumPy, Pillow, and g++ with OpenMP support. Modular passes
are cached in ../work and reused after interruptions.
"""

from __future__ import annotations

import csv
import ctypes
import math
import os
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
WORK = HERE.parent / "work"
SOURCE = HERE / "ising_square_transfer_n22.cpp"
ENGINE = WORK / "ising_square_transfer_n22.exe"
N = 22
THREADS = min(12, os.cpu_count() or 4)


def primes_below_2_31(count: int) -> tuple[int, ...]:
    """Generate distinct primes deterministically for the 32-bit residue engine."""
    def is_prime(value: int) -> bool:
        if value < 2:
            return False
        for small in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if value % small == 0:
                return value == small
        d, shifts = value - 1, 0
        while d % 2 == 0:
            d //= 2
            shifts += 1
        # These bases are deterministic for the sub-2^32 range.
        for base_value in (2, 3, 5, 7, 11):
            if base_value >= value:
                continue
            x = pow(base_value, d, value)
            if x in (1, value - 1):
                continue
            for _ in range(shifts - 1):
                x = x * x % value
                if x == value - 1:
                    break
            else:
                return False
        return True

    found = []
    candidate = (1 << 31) - 1
    if candidate % 2 == 0:
        candidate -= 1
    while len(found) < count:
        if is_prime(candidate):
            found.append(candidate)
        candidate -= 2
    return tuple(found)


PRIMES = primes_below_2_31(16)

sys.path.insert(0, str(HERE))
import replicate_square_potts as base  # noqa: E402


def available_memory_bytes() -> int | None:
    if sys.platform != "win32":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.ullAvailPhys)
    return None


def compile_engine() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    if ENGINE.exists() and ENGINE.stat().st_mtime >= SOURCE.stat().st_mtime:
        return
    print("Compiling the parallel 22-row Q=2 transfer engine...", flush=True)
    subprocess.run(
        ["g++", "-O3", "-std=c++17", "-DNDEBUG", "-fopenmp", str(SOURCE), "-o", str(ENGINE)],
        check=True,
    )


def modular_rows() -> list[list[int]]:
    compile_engine()
    degree_expected = 2 * N * N - N
    rows: list[list[int]] = []
    for index, prime in enumerate(PRIMES, 1):
        cache = WORK / f"ising_q2_n{N}_mod{index}.csv"
        if cache.exists():
            try:
                fields = [int(v) for v in cache.read_text(encoding="utf-8").strip().split(",")]
                if fields[:2] == [N, degree_expected] and len(fields) == degree_expected + 3:
                    rows.append(fields[2:])
                    print(f"N={N}: reusing modular pass {index}/{len(PRIMES)}", flush=True)
                    continue
            except (ValueError, OSError):
                pass
        print(f"N={N}: exact modular pass {index}/{len(PRIMES)} (prime {prime})", flush=True)
        run = subprocess.run(
            [str(ENGINE), str(prime), str(N), str(THREADS)], check=True,
            text=True, stdout=subprocess.PIPE,
        )
        fields = [int(v) for v in run.stdout.strip().split(",")]
        if fields[:2] != [N, degree_expected] or len(fields) != degree_expected + 3:
            raise RuntimeError("Bad modular coefficient output")
        cache.write_text(",".join(map(str, fields)), encoding="utf-8")
        rows.append(fields[2:])
    return rows


def recover_coefficients(rows: list[list[int]]) -> list[int]:
    bound = 1 << (N * N)
    if math.prod(PRIMES) <= bound:
        raise RuntimeError("CRT modulus product is below the coefficient bound")
    if len(rows) != len(PRIMES) or any(len(r) != len(rows[0]) for r in rows):
        raise RuntimeError("Missing or inconsistent modular passes")
    coeffs = [base.crt([row[k] for row in rows], PRIMES) for k in range(len(rows[0]))]
    if any(c < 0 or c > bound for c in coeffs):
        raise RuntimeError("A reconstructed coefficient is outside its counting bound")
    if sum(coeffs) != bound or len(coeffs) != 2*N*N-N+1 or coeffs[-1] != 2:
        raise RuntimeError("Exact polynomial checks failed (degree, leading term, or Z(1))")
    return coeffs


def divide_by_x_plus_one(coeffs: list[int]) -> list[int]:
    reduced = [0] * (len(coeffs) - 1)
    reduced[-1] = coeffs[-1]
    for power in range(len(reduced) - 1, 0, -1):
        reduced[power - 1] = coeffs[power] - reduced[power]
    if coeffs[0] - reduced[0] != 0:
        raise ValueError("Not divisible by x+1")
    return reduced


def extract_known_roots(coeffs: list[int]) -> tuple[list[int], list[complex], list[int], int]:
    """Remove exact x=0 and x=-1 roots, retaining their multiplicities."""
    first_nonzero = next((k for k, c in enumerate(coeffs) if c), None)
    if first_nonzero is None:
        raise RuntimeError("Zero partition polynomial")
    reduced = coeffs[first_nonzero:]
    seed_polynomial = reduced[:]
    exact_roots = [0j] * first_nonzero
    minus_one_count = 0
    while sum(c if k % 2 == 0 else -c for k, c in enumerate(reduced)) == 0:
        reduced = divide_by_x_plus_one(reduced)
        exact_roots.append(-1 + 0j)
        minus_one_count += 1
    print(f"N={N}: exact factors x^{first_nonzero} and (x+1)^{minus_one_count}", flush=True)
    return reduced, exact_roots, seed_polynomial, minus_one_count


def modular_gcd_degree(coeffs: list[int], prime: int) -> int:
    def trim(values: list[int]) -> list[int]:
        while values and values[-1] == 0:
            values.pop()
        return values

    def remainder(a: list[int], b: list[int]) -> list[int]:
        a = trim(a[:])
        inv = pow(b[-1], -1, prime)
        while len(a) >= len(b):
            offset = len(a) - len(b)
            factor = a[-1] * inv % prime
            for j, value in enumerate(b):
                a[offset + j] = (a[offset + j] - factor * value) % prime
            trim(a)
        return a

    a = trim([c % prime for c in coeffs])
    b = trim([(k * coeffs[k]) % prime for k in range(1, len(coeffs))])
    while b:
        a, b = b, remainder(a, b)
    return len(a) - 1


def vectorized_aberth_seeds(coeffs: list[int], fixed_root: complex | None = None,
                            fixed_multiplicity: int = 0):
    degree = len(coeffs) - 1
    if coeffs[0] == 0 or coeffs[-1] == 0:
        raise ValueError("Remove exact zero roots before forming seeds")
    radius = math.exp((math.log(abs(coeffs[0])) - math.log(abs(coeffs[-1]))) / degree)
    log_radius = math.log(radius)
    scale_log = max(math.log(abs(c)) + k * log_radius for k, c in enumerate(coeffs) if c)
    scaled = base.np.asarray(
        [0.0 if c == 0 else math.copysign(math.exp(math.log(abs(c)) + k * log_radius - scale_log), c)
         for k, c in enumerate(coeffs)], dtype=base.np.float64,
    )
    roots = base.np.roots(scaled[::-1]).astype(base.np.complex128)
    active_mask = base.np.ones(roots.size, dtype=bool)
    if fixed_multiplicity:
        fixed = base.np.argsort(base.np.abs(roots - fixed_root))[:fixed_multiplicity]
        active_mask[fixed] = False
        roots[fixed] = fixed_root
    root_cap = max(8.0, 1.5 * float(base.np.max(base.np.abs(roots))))
    for iteration in range(1, 3001):
        value = base.np.full(roots.shape, scaled[-1], dtype=base.np.complex128)
        derivative = base.np.zeros(roots.shape, dtype=base.np.complex128)
        log_scale = base.np.zeros(roots.shape, dtype=base.np.float64)
        for c in scaled[-2::-1]:
            derivative = derivative * roots + value
            if c == 0:
                scaled_c = 0.0
            else:
                with base.np.errstate(under="ignore"):
                    scaled_c = base.np.sign(c) * base.np.exp(math.log(abs(c)) - log_scale)
            value = value * roots + scaled_c
            magnitude = base.np.maximum(base.np.abs(value), base.np.abs(derivative))
            rescale = magnitude > 1e100
            value[rescale] *= 1e-100
            derivative[rescale] *= 1e-100
            log_scale[rescale] += math.log(1e100)
        differences = roots[:, None] - roots[None, :]
        base.np.fill_diagonal(differences, base.np.inf + 0j)
        with base.np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            repulsion = base.np.sum(1.0 / differences, axis=1)
            newton = value[active_mask] / derivative[active_mask]
            correction = base.np.zeros(roots.shape, dtype=base.np.complex128)
            correction[active_mask] = newton / (1.0 - newton * repulsion[active_mask])
        if not base.np.all(base.np.isfinite(correction)):
            raise RuntimeError("Aberth seeding became non-finite")
        step_limit = 0.25 * base.np.maximum(1.0, base.np.abs(roots))
        step_size = base.np.abs(correction)
        too_large = active_mask & (step_size > step_limit)
        correction[too_large] *= step_limit[too_large] / step_size[too_large]
        relative_step = base.np.max(
            base.np.abs(correction[active_mask])
            / base.np.maximum(1.0, base.np.abs(roots[active_mask]))
        )
        roots -= correction
        roots[active_mask] = base.np.clip(roots[active_mask].real, -root_cap, root_cap) + 1j * base.np.clip(
            roots[active_mask].imag, -root_cap, root_cap
        )
        if iteration % 500 == 0:
            print(f"Aberth seeding {iteration}/3000: max relative step {relative_step:.2g}", flush=True)
        if relative_step < 2e-13:
            break
    return [(float(z.real * radius), float(z.imag * radius)) for z in roots[active_mask]]


def companion_seeds(coeffs: list[int]):
    """Return scaled companion-matrix seeds without unstable global Aberth updates."""
    degree = len(coeffs) - 1
    if coeffs[0] == 0 or coeffs[-1] == 0:
        raise ValueError("Remove exact zero roots before forming seeds")
    radius = math.exp((math.log(abs(coeffs[0])) - math.log(abs(coeffs[-1]))) / degree)
    log_radius = math.log(radius)
    scale_log = max(math.log(abs(c)) + k * log_radius for k, c in enumerate(coeffs) if c)
    scaled = base.np.asarray(
        [0.0 if c == 0 else math.copysign(math.exp(math.log(abs(c)) + k * log_radius - scale_log), c)
         for k, c in enumerate(coeffs)], dtype=base.np.float64,
    )
    roots = base.np.roots(scaled[::-1]).astype(base.np.complex128)
    if not base.np.all(base.np.isfinite(roots)):
        raise RuntimeError("Companion-matrix root seeds became non-finite")
    return [(float(z.real * radius), float(z.imag * radius)) for z in roots]


def polish_roots(coeffs: list[int], seeds):
    with localcontext() as context:
        context.prec = 85
        zero, one = Decimal(0), Decimal(1)
        exact = [Decimal(c) for c in coeffs]

        def add(a, b): return a[0] + b[0], a[1] + b[1]
        def sub(a, b): return a[0] - b[0], a[1] - b[1]
        def mul(a, b): return a[0]*b[0] - a[1]*b[1], a[0]*b[1] + a[1]*b[0]
        def div(a, b):
            den = b[0]*b[0] + b[1]*b[1]
            return ((a[0]*b[0] + a[1]*b[1])/den,
                    (a[1]*b[0] - a[0]*b[1])/den)

        def eval_pd(z):
            p, dp = (exact[-1], zero), (zero, zero)
            for c in reversed(exact[:-1]):
                dp = add(mul(dp, z), p)
                p = add(mul(p, z), (c, zero))
            return p, dp

        roots, errors = [], []
        for index, (re, im) in enumerate(seeds, 1):
            z = Decimal(repr(re)), Decimal(repr(im))
            for _ in range(100):
                p, dp = eval_pd(z)
                if dp == (zero, zero):
                    break
                step = div(p, dp)
                z = sub(z, step)
                step2 = step[0]*step[0] + step[1]*step[1]
                scale2 = max(one, z[0]*z[0] + z[1]*z[1])
                if step2 < Decimal("1e-70") * scale2:
                    break
            p, _ = eval_pd(z)
            radius = (z[0]*z[0] + z[1]*z[1]).sqrt()
            denom, power = zero, one
            for c in exact:
                denom += abs(c) * power
                power *= radius
            residual = (p[0]*p[0] + p[1]*p[1]).sqrt() / denom if denom else zero
            roots.append(z)
            errors.append(residual)
            if index % 100 == 0:
                print(f"N={N}: high-precision Newton {index}/{len(seeds)} roots", flush=True)
        if max(errors) > Decimal("1e-10"):
            raise RuntimeError(f"Root residual target failed: {max(errors):.2g}")
        return roots, errors


def write_data(coeffs, roots, errors) -> None:
    with (HERE / "ising_2state_22x22_coefficients.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["N", "power_of_x", "exact_coefficient"])
        w.writerows((N, k, c) for k, c in enumerate(coeffs))
    with (HERE / "ising_2state_22x22_zeros.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["N", "root_index", "real_x", "imag_x", "relative_residual"])
        for i, (z, err) in enumerate(zip(roots, errors, strict=True), 1):
            w.writerow([N, i, format(z[0], ".80g"), format(z[1], ".80g"), format(err, ".3g")])


def draw_plot(roots) -> None:
    width, height = 1200, 1100
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((width//2, 25), "2-state Potts (Ising) model: all 22 × 22′ zeros",
              font=base.font(35, True), fill="#172033", anchor="mt")
    draw.text((width//2, 78), "Periodic vertical · open horizontal   |   complex coupling x = exp(βJ)",
              font=base.font(21), fill="#46536a", anchor="mt")
    bound = max(max(abs(float(z[0])), abs(float(z[1]))) for z in roots)
    limit = math.ceil(bound * 2) / 2 + 0.1
    px0, py0, px1, py1 = 175, 145, 1025, 995
    xmin, xmax, ymin, ymax = -limit, limit, -limit, limit
    span = xmax - xmin
    draw.rectangle((px0, py0, px1, py1), outline="#9aa5b5", width=2)
    nticks = int(math.floor(limit))
    for tick in range(-nticks, nticks + 1):
        x = px0 + (tick - xmin) / span * (px1-px0)
        y = py1 - (tick - ymin) / span * (py1-py0)
        if tick:
            draw.line((x, py0, x, py1), fill="#e8edf3", width=1)
            draw.line((px0, y, px1, y), fill="#e8edf3", width=1)
        draw.line((x, py1, x, py1+7), fill="#596579", width=1)
        draw.line((px0-7, y, px0, y), fill="#596579", width=1)
        draw.text((x, py1+12), str(tick), font=base.font(18), fill="#46536a", anchor="mt")
        draw.text((px0-14, y), str(tick), font=base.font(18), fill="#46536a", anchor="rm")
    xzero = px0 + (0-xmin)/span*(px1-px0)
    yzero = py1 - (0-ymin)/span*(py1-py0)
    draw.line((xzero, py0, xzero, py1), fill="#a9b4c2", width=1)
    draw.line((px0, yzero, px1, yzero), fill="#a9b4c2", width=1)
    for z in roots:
        xval, yval = float(z[0]), float(z[1])
        x = px0 + (xval-xmin)/span*(px1-px0)
        y = py1 - (yval-ymin)/span*(py1-py0)
        draw.ellipse((x-3, y-3, x+3, y+3), fill="#2563eb", outline="white", width=1)
    draw.text((width/2, height-22), "Re(x)", font=base.font(19), fill="#344054", anchor="ms")
    draw.text((26, height/2), "Im(x)", font=base.font(19), fill="#344054", anchor="mm")
    image.save(HERE / "ising_2state_22x22_transfer_roots.png", dpi=(180,180), optimize=True)


def main() -> None:
    degree = 2*N*N-N
    estimated = (1 << N) * (degree + 1) * 4
    available = available_memory_bytes()
    print(f"N={N}: one modular pass needs about {estimated/1e9:.2f} GB; available RAM "
          f"{available/1e9:.2f} GB; using {THREADS} threads", flush=True)
    if available is not None and estimated * 1.15 > available:
        raise MemoryError("Not enough available RAM for one 22x22 coefficient pass with headroom")
    coeffs = recover_coefficients(modular_rows())
    with (HERE / "ising_2state_22x22_coefficients.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["N", "power_of_x", "exact_coefficient"])
        w.writerows((N, k, c) for k, c in enumerate(coeffs))
    print(f"N={N}: exact degree-{len(coeffs)-1} polynomial; factoring exact real roots", flush=True)
    reduced, exact_roots, seed_polynomial, minus_one_count = extract_known_roots(coeffs)
    gcd_degree = modular_gcd_degree(reduced, PRIMES[0])
    print(f"N={N}: reduced degree {len(reduced)-1}; repeated-factor gcd degree modulo prime = {gcd_degree}", flush=True)
    if gcd_degree:
        raise RuntimeError("Unexpected repeated factor remains after extracting x=0 and x=-1 roots")
    # Damped Aberth seeding improves the raw companion roots collectively;
    # cache the resulting guesses so polishing can be retried independently.
    seed_cache = WORK / "ising_q2_n22_aberth3000_seeds.csv"
    if seed_cache.exists():
        seed_rows = [line.split(",") for line in seed_cache.read_text(encoding="utf-8").splitlines()]
        seeds = [(float(row[0]), float(row[1])) for row in seed_rows if len(row) == 2]
        if len(seeds) != len(reduced) - 1:
            seeds = []
    else:
        seeds = []
    if not seeds:
        seeds = vectorized_aberth_seeds(reduced)
        seed_cache.write_text("\n".join(f"{re:.17g},{im:.17g}" for re, im in seeds), encoding="utf-8")
    roots, errors = polish_roots(reduced, seeds)
    roots.extend((Decimal(repr(z.real)), Decimal(repr(z.imag))) for z in exact_roots)
    errors.extend([Decimal(0)] * len(exact_roots))
    ordered = sorted(zip(roots, errors, strict=True), key=lambda item: (item[0][0], item[0][1]))
    roots = [item[0] for item in ordered]
    errors = [item[1] for item in ordered]
    if len(roots) != degree:
        raise RuntimeError(f"Expected {degree} roots, found {len(roots)}")
    simple = [z for z in roots if z != (Decimal(0), Decimal(0))
              and z != (Decimal(-1), Decimal(0))]
    serialized = [(format(z[0], ".80g"), format(z[1], ".80g")) for z in simple]
    duplicates = len(serialized) - len(set(serialized))
    if duplicates:
        raise RuntimeError(f"{duplicates} simple roots collide at the 80-digit output precision")
    print(f"N={N}: {len(roots)} roots; maximum scaled residual {max(errors):.2g}", flush=True)
    write_data(coeffs, roots, errors)
    draw_plot(roots)
    print(f"Wrote exact coefficients, roots, and plot to {HERE}", flush=True)


if __name__ == "__main__":
    main()
