#!/usr/bin/env python3
"""Recreate the thesis's 20 x 20' Q=2 square-lattice zero plot.

The polynomial coefficients are exact: seven modular transfer passes are
combined with the Chinese remainder theorem. Roots are seeded numerically,
then polished with the 75-digit Aberth solver shared with the Q=3 work.

Run from this directory with: python replicate_ising_20x20_transfer.py
Requires NumPy, Pillow, and g++ with OpenMP support. Modular passes are cached
under ../work, so an interrupted run resumes from the last completed pass.
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
SOURCE = HERE / "ising_square_transfer.cpp"
ENGINE = WORK / "ising_square_transfer.exe"
N = 20
THREADS = min(12, os.cpu_count() or 4)

# Seven distinct 61-bit primes. Their product is > 2^400, a bound on every
# coefficient because the polynomial counts at most all 2^(20*20) spin states.
PRIMES = (
    2305843009213693951,
    2305843009212693901,
    2305843009211693951,
    2305843009210693903,
    2305843009209693869,
    2305843009208693881,
    2305843009207693933,
)

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
    print("Compiling the parallel Q=2 transfer engine...", flush=True)
    subprocess.run(
        ["g++", "-O3", "-std=c++17", "-DNDEBUG", "-fopenmp", str(SOURCE), "-o", str(ENGINE)],
        check=True,
    )


def modular_coefficients() -> list[list[int]]:
    compile_engine()
    rows: list[list[int]] = []
    degree_expected = 2 * N * N - N
    for index, prime in enumerate(PRIMES, 1):
        cache = WORK / f"ising_q2_n{N}_mod{index}.csv"
        if cache.exists():
            try:
                fields = [int(part) for part in cache.read_text(encoding="utf-8").strip().split(",")]
                if fields[:2] == [N, degree_expected] and len(fields) == degree_expected + 3:
                    rows.append(fields[2:])
                    print(f"N={N}: reusing modular pass {index}/{len(PRIMES)}", flush=True)
                    continue
            except (ValueError, OSError):
                pass
        print(f"N={N}: exact modular pass {index}/{len(PRIMES)} (prime {prime})", flush=True)
        run = subprocess.run(
            [str(ENGINE), str(prime), str(N), str(THREADS)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        fields = [int(part) for part in run.stdout.strip().split(",")]
        degree, coeffs = fields[1], fields[2:]
        if fields[0] != N or degree != degree_expected or len(coeffs) != degree + 1:
            raise RuntimeError("Bad modular coefficient output")
        cache.write_text(",".join(map(str, fields)), encoding="utf-8")
        rows.append(coeffs)
    return rows


def recover_exact_coefficients(rows: list[list[int]]) -> list[int]:
    if len(rows) != len(PRIMES):
        raise RuntimeError("Missing modular coefficient passes")
    modulus_product = math.prod(PRIMES)
    bound = 1 << (N * N)
    if modulus_product <= bound:
        raise RuntimeError("CRT modulus product does not cover the coefficient bound")
    if any(len(row) != len(rows[0]) for row in rows):
        raise RuntimeError("Inconsistent modular coefficient vector lengths")
    coeffs = [
        base.crt([row[k] for row in rows], PRIMES)
        for k in range(len(rows[0]))
    ]
    if any(c < 0 or c > bound for c in coeffs):
        raise RuntimeError("CRT reconstruction failed a coefficient bound")
    if sum(coeffs) != bound:
        raise RuntimeError("Z(1)=2^400 check failed")
    if len(coeffs) != 781 or coeffs[-1] != 2 or coeffs[0] != 2:
        raise RuntimeError("Expected degree 780 and the two uniform/checkerboard configurations")
    return coeffs


def remove_exact_antiferromagnetic_root(coeffs: list[int], multiplicity: int = 20) -> list[int]:
    """Divide out the exact (x+1)^20 factor before locating simple roots."""
    quotient = coeffs[:]
    for _ in range(multiplicity):
        if len(quotient) < 2:
            raise RuntimeError("Polynomial degree is too small for the exact x=-1 factor")
        reduced = [0] * (len(quotient) - 1)
        reduced[-1] = quotient[-1]
        for power in range(len(reduced) - 1, 0, -1):
            reduced[power - 1] = quotient[power] - reduced[power]
        if quotient[0] - reduced[0] != 0:
            raise RuntimeError("Exact division by (x+1) failed")
        quotient = reduced
    if len(quotient) != 761 or quotient[0] != 2 or quotient[-1] != 2:
        raise RuntimeError("Unexpected quotient after extracting the twentyfold x=-1 root")
    if modular_gcd_degree(quotient, PRIMES[0]) != 0:
        raise RuntimeError("The remaining polynomial was not square-free modulo the verification prime")
    return quotient


def modular_gcd_degree(coeffs: list[int], prime: int) -> int:
    """Degree of gcd(P,P') over one finite field; zero certifies square-freeness here."""
    def trim(values: list[int]) -> list[int]:
        while values and values[-1] == 0:
            values.pop()
        return values

    def remainder(a: list[int], b: list[int]) -> list[int]:
        a = trim(a[:])
        inverse = pow(b[-1], -1, prime)
        while len(a) >= len(b):
            offset = len(a) - len(b)
            factor = a[-1] * inverse % prime
            for index, value in enumerate(b):
                a[offset + index] = (a[offset + index] - factor * value) % prime
            trim(a)
        return a

    a = trim([value % prime for value in coeffs])
    b = trim([(power * coeffs[power]) % prime for power in range(1, len(coeffs))])
    while b:
        a, b = b, remainder(a, b)
    return len(a) - 1


def vectorized_aberth_seeds(coeffs: list[int]):
    """Use NumPy for the all-roots Aberth stage, avoiding slow Decimal pairs."""
    degree = len(coeffs) - 1
    radius = math.exp((math.log(coeffs[0]) - math.log(coeffs[-1])) / degree)
    log_radius = math.log(radius)
    log_terms = [math.log(abs(c)) + k * log_radius for k, c in enumerate(coeffs) if c]
    scale_log = max(log_terms)
    scaled = base.np.asarray(
        [0.0 if c == 0 else math.copysign(math.exp(math.log(abs(c)) + k * log_radius - scale_log), c)
         for k, c in enumerate(coeffs)], dtype=base.np.float64,
    )
    roots = base.np.roots(scaled[::-1]).astype(base.np.complex128)
    fixed = base.np.argsort(base.np.abs(roots + 1.0))[:20]
    active_mask = base.np.ones(roots.size, dtype=bool)
    active_mask[fixed] = False
    roots[fixed] = -1.0 + 0j
    for iteration in range(1, 301):
        value = base.np.full(roots.shape, scaled[-1], dtype=base.np.complex128)
        derivative = base.np.zeros(roots.shape, dtype=base.np.complex128)
        for coefficient in scaled[-2::-1]:
            derivative = derivative * roots + value
            value = value * roots + coefficient
        differences = roots[:, None] - roots[None, :]
        base.np.fill_diagonal(differences, base.np.inf + 0j)
        with base.np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            repulsion = base.np.sum(1.0 / differences, axis=1)
            newton = value[active_mask] / derivative[active_mask]
            correction = base.np.zeros(roots.shape, dtype=base.np.complex128)
            correction[active_mask] = newton / (1.0 - newton * repulsion[active_mask])
        if not base.np.all(base.np.isfinite(correction)):
            raise RuntimeError("Vectorized Aberth iteration became non-finite")
        relative_step = base.np.max(
            base.np.abs(correction[active_mask])
            / base.np.maximum(1.0, base.np.abs(roots[active_mask]))
        )
        roots -= correction
        if iteration % 20 == 0:
            print(f"Aberth iteration {iteration}: maximum relative step {relative_step:.2g}", flush=True)
        if relative_step < 2e-13:
            print(f"Aberth converged after {iteration} iterations", flush=True)
            break
    else:
        print(f"Aberth reached 300 iterations; final relative step {relative_step:.2g}", flush=True)
    return [(float(z.real * radius), float(z.imag * radius)) for z in roots[active_mask]]


def polish_roots_newton(coeffs: list[int], seeds):
    """Polish each Aberth root independently using high-precision Decimal Newton steps."""
    with localcontext() as context:
        context.prec = 85
        zero, one = Decimal(0), Decimal(1)
        exact = [Decimal(c) for c in coeffs]

        def add(a, b):
            return a[0] + b[0], a[1] + b[1]

        def sub(a, b):
            return a[0] - b[0], a[1] - b[1]

        def mul(a, b):
            return a[0]*b[0] - a[1]*b[1], a[0]*b[1] + a[1]*b[0]

        def div(a, b):
            denominator = b[0]*b[0] + b[1]*b[1]
            return ((a[0]*b[0] + a[1]*b[1]) / denominator,
                    (a[1]*b[0] - a[0]*b[1]) / denominator)

        def evaluate(z):
            p, derivative = (exact[-1], zero), (zero, zero)
            for coefficient in reversed(exact[:-1]):
                derivative = add(mul(derivative, z), p)
                p = add(mul(p, z), (coefficient, zero))
            return p, derivative

        roots = []
        errors = []
        for index, (real_part, imag_part) in enumerate(seeds, 1):
            z = Decimal(repr(real_part)), Decimal(repr(imag_part))
            for _ in range(800):
                p, derivative = evaluate(z)
                if derivative == (zero, zero):
                    break
                correction = div(p, derivative)
                z = sub(z, correction)
                step_sq = correction[0]*correction[0] + correction[1]*correction[1]
                scale_sq = max(one, z[0]*z[0] + z[1]*z[1])
                if step_sq < Decimal("1e-70") * scale_sq:
                    break

            p, _ = evaluate(z)
            abs_z = (z[0]*z[0] + z[1]*z[1]).sqrt()
            denom, power = zero, one
            for coefficient in exact:
                denom += abs(coefficient) * power
                power *= abs_z
            residual = ((p[0]*p[0] + p[1]*p[1]).sqrt() / denom) if denom else zero
            roots.append(z)
            errors.append(residual)
            if index % 100 == 0:
                print(f"High-precision Newton polishing: {index}/{len(seeds)} roots", flush=True)

        worst = sorted(range(len(errors)), key=lambda i: errors[i], reverse=True)[:8]
        print("Largest scaled root residuals:", flush=True)
        for i in worst:
            print(f"  root {i+1}: residual={errors[i]:.3g}, x=({roots[i][0]:.12g},{roots[i][1]:.12g})", flush=True)
        if max(errors) > Decimal("1e-20"):
            with (WORK / "ising_q2_n20_root_debug.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["root_index", "real_x", "imag_x", "relative_residual"])
                for i, (z, error) in enumerate(zip(roots, errors, strict=True), 1):
                    writer.writerow([i, str(z[0]), str(z[1]), str(error)])
            raise RuntimeError(f"High-precision root residual target failed: {max(errors):.2g}")
        return roots, errors


def write_data(coeffs, roots, errors) -> None:
    with (HERE / "ising_2state_20x20_coefficients.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "power_of_x", "exact_coefficient"])
        writer.writerows((N, power, value) for power, value in enumerate(coeffs))
    with (HERE / "ising_2state_20x20_zeros.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "root_index", "real_x", "imag_x", "relative_residual"])
        for index, (z, error) in enumerate(zip(roots, errors, strict=True), 1):
            writer.writerow([N, index, format(z[0], ".40g"), format(z[1], ".40g"), format(error, ".3g")])


def draw_plot(roots) -> None:
    width, height = 1200, 1100
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((width // 2, 25), "2-state Potts (Ising) model: all 20 × 20′ zeros",
              font=base.font(35, True), fill="#172033", anchor="mt")
    draw.text((width // 2, 78), "Periodic vertical · open horizontal   |   complex coupling x = exp(βJ)",
              font=base.font(21), fill="#46536a", anchor="mt")
    xmin, xmax, ymin, ymax = -2.55, 2.55, -2.55, 2.55
    px0, py0, px1, py1 = 175, 145, 1025, 995
    pw, ph = px1 - px0, py1 - py0
    draw.rectangle((px0, py0, px1, py1), outline="#9aa5b5", width=2)
    for tick in range(-2, 3):
        x = px0 + (tick - xmin) / (xmax - xmin) * pw
        y = py1 - (tick - ymin) / (ymax - ymin) * ph
        if tick:
            draw.line((x, py0, x, py1), fill="#e8edf3", width=1)
            draw.line((px0, y, px1, y), fill="#e8edf3", width=1)
        draw.line((x, py1, x, py1 + 7), fill="#596579", width=1)
        draw.line((px0 - 7, y, px0, y), fill="#596579", width=1)
        draw.text((x, py1 + 12), str(tick), font=base.font(18), fill="#46536a", anchor="mt")
        draw.text((px0 - 14, y), str(tick), font=base.font(18), fill="#46536a", anchor="rm")
    xzero = px0 + (0 - xmin) / (xmax - xmin) * pw
    yzero = py1 - (0 - ymin) / (ymax - ymin) * ph
    draw.line((xzero, py0, xzero, py1), fill="#a9b4c2", width=1)
    draw.line((px0, yzero, px1, yzero), fill="#a9b4c2", width=1)
    for z in roots:
        real_x, imag_x = float(z[0]), float(z[1])
        if xmin <= real_x <= xmax and ymin <= imag_x <= ymax:
            x = px0 + (real_x - xmin) / (xmax - xmin) * pw
            y = py1 - (imag_x - ymin) / (ymax - ymin) * ph
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#2563eb", outline="white", width=1)
    draw.text((width / 2, height - 22), "Re(x)", font=base.font(19), fill="#344054", anchor="ms")
    draw.text((26, height / 2), "Im(x)", font=base.font(19), fill="#344054", anchor="mm")
    image.save(HERE / "ising_2state_20x20_transfer_roots.png", dpi=(180, 180), optimize=True)


def main() -> None:
    estimated_bytes = (1 << N) * (2 * N * N - N + 1) * 8
    available = available_memory_bytes()
    print(f"N={N}: one modular pass needs about {estimated_bytes / 1e9:.2f} GB; "
          f"using {THREADS} CPU threads", flush=True)
    if available is not None and estimated_bytes * 1.15 > available:
        raise MemoryError(f"Need about {estimated_bytes / 1e9:.1f} GB; only {available / 1e9:.1f} GB is available")

    residues = modular_coefficients()
    coeffs = recover_exact_coefficients(residues)
    print(f"N={N}: exact degree-{len(coeffs)-1} polynomial recovered; extracting the exact 20-fold root at x=-1", flush=True)
    squarefree = remove_exact_antiferromagnetic_root(coeffs)
    print(f"N={N}: locating the {len(squarefree)-1} remaining simple roots with x=-1 fixed", flush=True)
    seeds = vectorized_aberth_seeds(coeffs)
    print(f"N={N}: polishing {len(seeds)} roots individually at 85 digits", flush=True)
    roots, errors = polish_roots_newton(squarefree, seeds)
    roots.extend([(Decimal(-1), Decimal(0))] * 20)
    errors.extend([Decimal(0)] * 20)
    ordered = sorted(zip(roots, errors, strict=True), key=lambda item: (item[0][0], item[0][1]))
    roots = [item[0] for item in ordered]
    errors = [item[1] for item in ordered]
    print(f"N={N}: {len(roots)} roots; maximum scaled residual {max(errors):.2g}", flush=True)
    write_data(coeffs, roots, errors)
    draw_plot(roots)
    print(f"Wrote the exact coefficients, zeros, and plot to {HERE}", flush=True)


if __name__ == "__main__":
    main()
