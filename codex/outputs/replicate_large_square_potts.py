#!/usr/bin/env python3
"""Compute Q=3 square-lattice partition zeros for N=12,13,14.

Run: python replicate_large_square_potts.py
Requires Python 3, NumPy, Pillow, and g++ with OpenMP support.
The exact modular coefficient passes are cached under ../work so an interrupted
run can resume without repeating completed passes.
"""

from __future__ import annotations

import csv
import ctypes
import math
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
WORK = HERE.parent / "work"
SOURCE = HERE / "square_potts_transfer_large.cpp"
ENGINE = WORK / "square_potts_transfer_large.exe"
SIZES = (12, 13, 14)
THREADS = min(12, os.cpu_count() or 4)

# Distinct 31-bit primes. Eleven residues give a 341-bit CRT range, exceeding
# the largest coefficient bound 3^(14*14) < 2^311.
PRIMES = (
    2147483647, 2147383633, 2147283599, 2147183627, 2147083639,
    2146983637, 2146883623, 2146783633, 2146683611, 2146583639,
    2146483643,
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
    print("Compiling the parallel large-width coefficient engine...", flush=True)
    subprocess.run(
        ["g++", "-O3", "-std=c++17", "-DNDEBUG", "-fopenmp", str(SOURCE), "-o", str(ENGINE)],
        check=True,
    )


def prime_count_for(n: int) -> int:
    target = 3 ** (n * n)
    product, count = 1, 0
    while product <= target:
        product *= PRIMES[count]
        count += 1
    return count


def modular_rows(n: int) -> list[list[int]]:
    compile_engine()
    count = prime_count_for(n)
    rows: list[list[int]] = []
    for index, prime in enumerate(PRIMES[:count], 1):
        cache = WORK / f"potts_q3_n{n}_mod{index}.csv"
        if cache.exists():
            fields = [int(part) for part in cache.read_text(encoding="utf-8").strip().split(",")]
            if fields[:2] == [n, 2*n*n-n] and len(fields) == fields[1] + 3:
                rows.append(fields[2:])
                print(f"N={n}: reusing modular pass {index}/{count}", flush=True)
                continue
        print(f"N={n}: exact modular pass {index}/{count} (prime {prime})", flush=True)
        run = subprocess.run(
            [str(ENGINE), str(prime), str(n), str(THREADS)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        fields = [int(part) for part in run.stdout.strip().split(",")]
        degree, coeffs = fields[1], fields[2:]
        if fields[0] != n or degree != 2*n*n-n or len(coeffs) != degree+1:
            raise RuntimeError(f"Bad modular coefficient output for N={n}")
        cache.write_text(",".join(map(str, fields)), encoding="utf-8")
        rows.append(coeffs)
    return rows


def exact_coefficients(n: int, residues: list[list[int]]) -> list[int]:
    product = math.prod(PRIMES[:len(residues)])
    bound = 3 ** (n*n)
    if product <= bound:
        raise RuntimeError(f"CRT range does not cover coefficients for N={n}")
    coeffs = [
        base.crt([row[k] for row in residues], PRIMES[:len(residues)])
        for k in range(len(residues[0]))
    ]
    if any(c < 0 or c > bound for c in coeffs):
        raise RuntimeError(f"Coefficient bound check failed for N={n}")
    if sum(coeffs) != 3 ** (n*n) or coeffs[-1] != 3:
        raise RuntimeError(f"Partition polynomial checks failed for N={n}")
    return coeffs


def write_large_data(coefficients, roots, errors) -> None:
    with (HERE / "square_potts_3state_large_coefficients.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "power_of_x", "exact_coefficient"])
        for n, coeffs in coefficients.items():
            writer.writerows((n, k, c) for k, c in enumerate(coeffs))
    with (HERE / "square_potts_3state_large_zeros.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["N", "root_index", "real_x", "imag_x", "relative_residual"])
        for n, zs in roots.items():
            for index, (z, error) in enumerate(zip(zs, errors[n], strict=True), 1):
                writer.writerow([n, index, format(z[0], ".40g"), format(z[1], ".40g"), format(error, ".3g")])


def draw_large_plot(roots) -> None:
    width, height = 2400, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((width//2, 24), "3-state Potts model: larger square lattices",
              font=base.font(38, True), fill="#172033", anchor="mt")
    draw.text((width//2, 78), "Periodic vertical · open horizontal   |   complex coupling x = exp(βJ)",
              font=base.font(21), fill="#46536a", anchor="mt")
    left, right = 95, width-45
    top, bottom = 145, height-90
    gap = 48
    panel_w = (right-left-2*gap)/3
    panel_h = bottom-top
    xmin, xmax, ymin, ymax = -3.15, 3.15, -2.2, 2.2
    colors = {12: "#2563eb", 13: "#7c3aed", 14: "#059669"}
    for panel, n in enumerate(sorted(roots)):
        x0 = left + panel*(panel_w+gap)
        px0, py0 = x0+54, top+48
        pw, ph = panel_w-82, panel_h-106
        px1, py1 = px0+pw, py0+ph
        draw.text((x0+panel_w/2, top+2), f"{n} × {n}′", font=base.font(27, True),
                  fill="#172033", anchor="mt")
        draw.rectangle((px0,py0,px1,py1), outline="#9aa5b5", width=2)
        for tick in range(-3,4):
            x=px0+(tick-xmin)/(xmax-xmin)*pw
            if tick: draw.line((x,py0,x,py1),fill="#e8edf3",width=1)
            draw.line((x,py1,x,py1+6),fill="#596579",width=1)
            draw.text((x,py1+10),str(tick),font=base.font(16),fill="#46536a",anchor="mt")
        for tick in range(-2,3):
            y=py1-(tick-ymin)/(ymax-ymin)*ph
            if tick: draw.line((px0,y,px1,y),fill="#e8edf3",width=1)
            draw.line((px0-6,y,px0,y),fill="#596579",width=1)
            draw.text((px0-11,y),str(tick),font=base.font(16),fill="#46536a",anchor="rm")
        xzero=px0+(0-xmin)/(xmax-xmin)*pw
        yzero=py1-(0-ymin)/(ymax-ymin)*ph
        draw.line((xzero,py0,xzero,py1),fill="#a9b4c2",width=1)
        draw.line((px0,yzero,px1,yzero),fill="#a9b4c2",width=1)
        for z in roots[n]:
            real_x, imag_x = float(z[0]), float(z[1])
            if xmin <= real_x <= xmax and ymin <= imag_x <= ymax:
                x=px0+(real_x-xmin)/(xmax-xmin)*pw
                y=py1-(imag_x-ymin)/(ymax-ymin)*ph
                draw.ellipse((x-3,y-3,x+3,y+3),fill=colors[n],outline="white",width=1)
    draw.text((width/2,height-20),"Re(x)",font=base.font(18),fill="#344054",anchor="ms")
    draw.text((23,height/2),"Im(x)",font=base.font(18),fill="#344054",anchor="mm")
    image.save(HERE / "square_potts_3state_large_square_roots.png", dpi=(180,180), optimize=True)


def main() -> None:
    coefficients, roots, errors = {}, {}, {}
    available = available_memory_bytes()
    for n in SIZES:
        estimated = 3**n * (2*n*n-n+1) * 4
        if available is not None and estimated * 1.2 > available:
            raise MemoryError(f"N={n} needs about {estimated/1e9:.1f} GB for one exact pass; available memory is too low")
        print(f"\nStarting N={n}; one modular pass needs about {estimated/1e9:.2f} GB", flush=True)
        residues = modular_rows(n)
        coefficients[n] = exact_coefficients(n, residues)
        print(f"N={n}: exact polynomial degree {len(coefficients[n])-1}; finding seeds and refining at 75 digits", flush=True)
        seeds = base.double_precision_seeds(coefficients[n])
        roots[n], errors[n] = base.refine_roots_high_precision(coefficients[n], seeds)
        print(f"N={n}: {len(roots[n])} roots; max scaled residual {max(errors[n]):.2g}", flush=True)
        write_large_data(coefficients, roots, errors)
    draw_large_plot(roots)
    print(f"Wrote large-square plot and CSV data to {HERE}", flush=True)


if __name__ == "__main__":
    main()
