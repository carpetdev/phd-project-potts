#!/usr/bin/env python3
"""Recreate the Q=3 square-lattice zero plots (thesis Figure 5.10).

The partition-function coefficients are computed exactly by a transfer
recurrence, using four modular passes and the Chinese remainder theorem. The
roots are then found numerically. Requires Python 3, NumPy, Pillow, and g++.
Run: python replicate_square_potts.py
"""

from __future__ import annotations

import csv
import math
import subprocess
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
WORK = HERE.parent / "work"
ENGINE_SOURCE = HERE / "square_potts_transfer.cpp"
ENGINE = WORK / "square_potts_transfer.exe"
SIZES = range(6, 12)
PRIMES = (
    2305843009213693951,
    2305843009212693901,
    2305843009211693951,
    2305843009210693903,
)


def compile_engine() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    if ENGINE.exists() and ENGINE.stat().st_mtime >= ENGINE_SOURCE.stat().st_mtime:
        return
    print("Compiling the exact transfer-matrix engine...", flush=True)
    subprocess.run(
        ["g++", "-O3", "-std=c++17", "-DNDEBUG", str(ENGINE_SOURCE), "-o", str(ENGINE)],
        check=True,
    )


def calculate_modular_coefficients() -> dict[int, list[list[int]]]:
    """Return coefficients by N, with one row of residues per prime."""
    compile_engine()
    result: dict[int, list[list[int]]] = {n: [] for n in SIZES}
    for pass_number, prime in enumerate(PRIMES, 1):
        print(f"Exact coefficient pass {pass_number}/{len(PRIMES)}...", flush=True)
        run = subprocess.run(
            [str(ENGINE), str(prime)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        for line in run.stdout.splitlines():
            fields = [int(part) for part in line.split(",")]
            n, degree, *coeffs = fields
            if len(coeffs) != degree + 1:
                raise RuntimeError(f"Bad coefficient row for N={n}")
            result[n].append(coeffs)
    return result


def crt(residues: list[int], moduli: tuple[int, ...]) -> int:
    value = 0
    product = 1
    for residue, modulus in zip(residues, moduli, strict=True):
        multiplier = ((residue - value) * pow(product, -1, modulus)) % modulus
        value += product * multiplier
        product *= modulus
    return value


def recover_coefficients(rows: dict[int, list[list[int]]]) -> dict[int, list[int]]:
    product = math.prod(PRIMES)
    bound = 3 ** (11 * 11)  # Every coefficient counts a subset of all 3^(11*11) spins.
    if product <= bound:
        raise RuntimeError("CRT modulus product is too small for the coefficient bound")

    exact: dict[int, list[int]] = {}
    for n, pass_rows in rows.items():
        if len(pass_rows) != len(PRIMES):
            raise RuntimeError(f"Missing modular passes for N={n}")
        if any(len(row) != len(pass_rows[0]) for row in pass_rows):
            raise RuntimeError(f"Inconsistent residue lengths for N={n}")
        exact[n] = [
            crt([pass_rows[j][k] for j in range(len(PRIMES))], PRIMES)
            for k in range(len(pass_rows[0]))
        ]
        if any(c < 0 or c > 3 ** (n * n) for c in exact[n]):
            raise RuntimeError(f"CRT reconstruction failed a coefficient bound for N={n}")
        if sum(exact[n]) != 3 ** (n * n):
            raise RuntimeError(f"Partition function check Z(1)=3^(N^2) failed for N={n}")
        if exact[n][-1] != 3:
            raise RuntimeError(f"Leading coefficient check failed for N={n}")
    return exact


def evaluate_with_derivative(z: complex, coefficients: list[float]) -> tuple[complex, complex]:
    p = complex(coefficients[-1])
    dp = 0j
    for coefficient in reversed(coefficients[:-1]):
        dp = dp * z + p
        p = p * z + coefficient
    return p, dp


def double_precision_seeds(exact_coeffs: list[int]) -> list[complex]:
    degree = len(exact_coeffs) - 1
    if degree <= 0 or exact_coeffs[0] == 0 or exact_coeffs[-1] == 0:
        raise ValueError("The partition polynomial must have nonzero constant and leading terms")

    # Balance the constant and leading terms before forming the companion matrix.
    radius = math.exp((math.log(exact_coeffs[0]) - math.log(exact_coeffs[-1])) / degree)
    log_radius = math.log(radius)
    log_coeffs = [math.log(c) + k * log_radius for k, c in enumerate(exact_coeffs) if c]
    scale_log = max(log_coeffs)
    scaled = np.array(
        [0.0 if c == 0 else math.exp(math.log(c) + k * log_radius - scale_log)
         for k, c in enumerate(exact_coeffs)],
        dtype=np.float64,
    )
    roots_z = np.roots(scaled[::-1])
    derivative_coeffs = np.arange(1, len(scaled), dtype=np.float64) * scaled[1:]

    # A few Newton steps improve the companion-matrix roots without changing
    # their ordering or trying to merge the deliberately dense root clouds.
    refined: list[complex] = []
    for z0 in roots_z:
        z = complex(z0)
        for _ in range(12):
            p, dp = evaluate_with_derivative(z, scaled.tolist())
            if dp == 0:
                break
            step = p / dp
            if not (math.isfinite(step.real) and math.isfinite(step.imag)):
                break
            z -= step
            if abs(step) <= 2e-14 * max(1.0, abs(z)):
                break
        refined.append(radius * z)
    return refined


def refine_roots_high_precision(exact_coeffs: list[int], seeds: list[complex]
                                ) -> tuple[list[tuple[Decimal, Decimal]], list[Decimal]]:
    """Refine the roots with a 75-digit Aberth iteration.

    The companion-matrix roots are only starting guesses. High-degree Potts
    polynomials become badly conditioned, so double precision can place roots
    visibly off their true loci even when its backward residual is small.
    """
    with localcontext() as context:
        context.prec = 75
        zero, one = Decimal(0), Decimal(1)
        coeffs = [Decimal(c) for c in exact_coeffs]
        roots = [(Decimal(repr(z.real)), Decimal(repr(z.imag))) for z in seeds]

        def add(a, b):
            return (a[0] + b[0], a[1] + b[1])

        def sub(a, b):
            return (a[0] - b[0], a[1] - b[1])

        def mul(a, b):
            return (a[0]*b[0] - a[1]*b[1], a[0]*b[1] + a[1]*b[0])

        def div(a, b):
            denominator = b[0]*b[0] + b[1]*b[1]
            return ((a[0]*b[0] + a[1]*b[1])/denominator,
                    (a[1]*b[0] - a[0]*b[1])/denominator)

        def evaluate(z):
            p, derivative = (coeffs[-1], zero), (zero, zero)
            for coefficient in reversed(coeffs[:-1]):
                derivative = add(mul(derivative, z), p)
                p = add(mul(p, z), (coefficient, zero))
            return p, derivative

        tolerance_squared = Decimal("1e-36")
        max_step_squared = Decimal("Infinity")
        for _ in range(500):
            next_roots = []
            max_step_squared = zero
            for i, z in enumerate(roots):
                p, derivative = evaluate(z)
                if derivative == (zero, zero):
                    next_roots.append(z)
                    continue
                newton = div(p, derivative)
                repulsion = (zero, zero)
                for j, other in enumerate(roots):
                    if j != i:
                        difference = sub(z, other)
                        repulsion = add(repulsion, div((one, zero), difference))
                denominator = sub((one, zero), mul(newton, repulsion))
                correction = (newton if denominator == (zero, zero)
                              else div(newton, denominator))
                next_roots.append(sub(z, correction))
                step_squared = correction[0]*correction[0] + correction[1]*correction[1]
                if step_squared > max_step_squared:
                    max_step_squared = step_squared
            roots = next_roots
            if max_step_squared < tolerance_squared:
                break

        errors: list[Decimal] = []
        for z in roots:
            p, _ = evaluate(z)
            radius = (z[0]*z[0] + z[1]*z[1]).sqrt()
            denominator = zero
            radius_power = one
            for coefficient in coeffs:
                denominator += abs(coefficient) * radius_power
                radius_power *= radius
            residual = ((p[0]*p[0] + p[1]*p[1]).sqrt() / denominator
                        if denominator else zero)
            errors.append(residual)
        if max(errors) > Decimal("1e-20"):
            raise RuntimeError("High-precision root refinement did not reach the residual target")
        return roots, errors


def write_data(exact: dict[int, list[int]], roots: dict[int, list[tuple[Decimal, Decimal]]],
               errors: dict[int, list[Decimal]]) -> None:
    with (HERE / "square_potts_3state_coefficients.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "power_of_x", "exact_coefficient"])
        for n, coeffs in exact.items():
            writer.writerows((n, k, c) for k, c in enumerate(coeffs))

    with (HERE / "square_potts_3state_zeros.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "root_index", "real_x", "imag_x", "relative_residual"])
        for n, values in roots.items():
            for index, (z, error) in enumerate(zip(values, errors[n], strict=True), 1):
                writer.writerow([n, index, format(z[0], ".40g"), format(z[1], ".40g"), format(error, ".3g")])


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]
        if bold else [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_plot(roots: dict[int, list[tuple[Decimal, Decimal]]]) -> None:
    width, height = 1920, 1280
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = font(36, bold=True)
    subtitle_font = font(21)
    panel_font = font(25, bold=True)
    tick_font = font(16)
    axis_font = font(18)
    draw.text((width // 2, 28), "3-state Potts model on square lattices", font=title_font,
              fill="#172033", anchor="mt")
    draw.text((width // 2, 78), "Periodic vertical · open horizontal   |   complex coupling x = exp(βJ)",
              font=subtitle_font, fill="#46536a", anchor="mt")

    left, right = 86, width - 48
    top, bottom = 142, height - 92
    gap_x, gap_y = 42, 62
    panel_w = (right - left - 2 * gap_x) / 3
    panel_h = (bottom - top - gap_y) / 2
    xmin, xmax, ymin, ymax = -3.15, 3.15, -2.2, 2.2
    colors = {6: "#2563eb", 7: "#7c3aed", 8: "#0891b2", 9: "#d97706", 10: "#059669", 11: "#db2777"}

    for panel, n in enumerate(SIZES):
        row, col = divmod(panel, 3)
        x0 = left + col * (panel_w + gap_x)
        y0 = top + row * (panel_h + gap_y)
        px0, py0 = x0 + 42, y0 + 42
        pw, ph = panel_w - 64, panel_h - 91
        px1, py1 = px0 + pw, py0 + ph

        draw.text((x0 + panel_w / 2, y0), f"{n} × {n}′", font=panel_font,
                  fill="#172033", anchor="mt")
        draw.rectangle((px0, py0, px1, py1), outline="#9aa5b5", width=2)
        for xtick in range(-3, 4):
            x = px0 + (xtick - xmin) / (xmax - xmin) * pw
            if xtick != 0:
                draw.line((x, py0, x, py1), fill="#e8edf3", width=1)
            draw.line((x, py1, x, py1 + 6), fill="#596579", width=1)
            draw.text((x, py1 + 10), str(xtick), font=tick_font, fill="#46536a", anchor="mt")
        for ytick in range(-2, 3):
            y = py1 - (ytick - ymin) / (ymax - ymin) * ph
            if ytick != 0:
                draw.line((px0, y, px1, y), fill="#e8edf3", width=1)
            draw.line((px0 - 6, y, px0, y), fill="#596579", width=1)
            draw.text((px0 - 11, y), str(ytick), font=tick_font, fill="#46536a", anchor="rm")
        xzero = px0 + (0 - xmin) / (xmax - xmin) * pw
        yzero = py1 - (0 - ymin) / (ymax - ymin) * ph
        draw.line((xzero, py0, xzero, py1), fill="#a9b4c2", width=1)
        draw.line((px0, yzero, px1, yzero), fill="#a9b4c2", width=1)

        radius = 3.0
        for z in roots[n]:
            real_x, imag_x = float(z[0]), float(z[1])
            if xmin <= real_x <= xmax and ymin <= imag_x <= ymax:
                x = px0 + (real_x - xmin) / (xmax - xmin) * pw
                y = py1 - (imag_x - ymin) / (ymax - ymin) * ph
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=colors[n], outline="white", width=1)

    draw.text((width / 2, height - 25), "Re(x)", font=axis_font, fill="#344054", anchor="ms")
    draw.text((22, height / 2), "Im(x)", font=axis_font, fill="#344054", anchor="mm")
    image.save(HERE / "square_potts_3state_figure_5_10.png", dpi=(180, 180), optimize=True)


def main() -> None:
    rows = calculate_modular_coefficients()
    exact = recover_coefficients(rows)
    roots: dict[int, list[complex]] = {}
    errors: dict[int, list[Decimal]] = {}
    for n, coeffs in exact.items():
        seeds = double_precision_seeds(coeffs)
        roots[n], errors[n] = refine_roots_high_precision(coeffs, seeds)
        print(f"N={n}: degree {len(coeffs)-1}, roots {len(roots[n])}, "
              f"max scaled residual {max(errors[n]):.2g}", flush=True)
    write_data(exact, roots, errors)
    draw_plot(roots)
    print(f"Wrote figure and data to {HERE}", flush=True)


if __name__ == "__main__":
    main()
