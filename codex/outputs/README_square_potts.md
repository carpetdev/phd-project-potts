# Square-lattice Potts zeros: Figure 5.10

This folder contains a computed recreation of Figure 5.10 in the attached
thesis. It covers the three-state Potts model on N by N lattices for N=6,...,11.
Each lattice is periodic vertically and open horizontally, as in the thesis.

The plotted variable is x = exp(beta J). For a spin configuration s, the
partition function is

    Z_N(x) = sum_s x^(number of equal-spin nearest-neighbour bonds)

with the vertical wraparound bonds included and no horizontal wraparound bond.
The polynomial degree is 2*N*N-N (66, 91, 120, 153, 190, and 231).

## Recompute

Requires Python 3, NumPy, Pillow, and a C++17 compiler named `g++`. From this
folder, run:

    python replicate_square_potts.py

The script calculates the integer polynomial coefficients with a transfer
recurrence, reconstructs them exactly from modular passes, and rewrites the
plot and CSV files. NumPy companion-matrix roots provide initial guesses; a
75-digit Aberth iteration then refines their locations. The script checks the
coefficient bounds, leading coefficient, Z_N(1)=3^(N*N), and scaled root
residuals.

## Files

- `square_potts_3state_figure_5_10.png`: six-panel complex-root plot.
- `square_potts_3state_zeros.csv`: root coordinates and scaled residuals.
- `square_potts_3state_coefficients.csv`: exact polynomial coefficients.
- `replicate_square_potts.py` and `square_potts_transfer.cpp`: computation and
  plotting source.
- `square_potts_3state_large_square_roots.png`: comparison of the 12x12,
  13x13, and 14x14 square cases.
- `square_potts_3state_large_zeros.csv` and
  `square_potts_3state_large_coefficients.csv`: large-case roots and exact
  coefficients.
- `replicate_large_square_potts.py` and `square_potts_transfer_large.cpp`:
  source for the larger cases.

To recompute the 12x12, 13x13, and 14x14 cases, run:

    python replicate_large_square_potts.py

That run uses a parallel modular engine and needs about 7.25 GB for one
14x14 coefficient pass. Completed modular passes are cached in the sibling
`work` folder so the calculation can resume if interrupted. The root solve uses
the same 75-digit refinement as the smaller cases.

Roots are calculated from the partition polynomials; they are not digitized
from the thesis image. High precision is needed for the larger lattices because
their roots are tightly clustered and ill-conditioned.

## 20x20 Ising transfer-matrix case

The Ising benchmark in Figure 5.5 reaches 20x20' with the same periodic-vertical,
open-horizontal boundaries. Recompute it with:

    python replicate_ising_20x20_transfer.py

The Q=2 transfer engine uses seven 61-bit modular passes (about 6.55 GB per
pass) and CRT to recover the degree-780 polynomial exactly. Its known repeated
factor is `(x+1)^20`; the script removes that factor before solving the 760
remaining simple roots, verifies the quotient is square-free modulo a prime,
and restores the twentyfold root at x=-1 in the output. The largest scaled
residual in this run was about 3.3e-69.

- `ising_2state_20x20_transfer_roots.png`: complex-root plot with expanded
  symmetric limits so all 780 zeros are visible.
- `ising_2state_20x20_zeros.csv`: all 780 roots, including repeated rows for
  the multiplicity-20 root at -1.
- `ising_2state_20x20_coefficients.csv`: exact integer coefficients.
- `replicate_ising_20x20_transfer.py` and `ising_square_transfer.cpp`:
  coefficient, root, and plotting source. Modular passes are cached under
  `../work` for restartability.

## 21x21 Ising transfer-matrix case

Recompute it with:

    python replicate_ising_21x21_transfer.py

Eight 61-bit modular passes recover the degree-861 polynomial exactly. Its
known factors are `x^21 (x+1)^40`; the remaining degree-800 quotient is
square-free modulo a reconstruction prime. All 861 roots are saved, including
the repeated roots at zero and -1. The largest scaled residual is about
`1.1e-12`. The larger residual than in the 20x20 case reflects the severe
conditioning of the degree-800 factor; roots are retained to 80 significant
digits in the CSV.

- `ising_2state_21x21_transfer_roots.png`: plot of all 861 roots.
- `ising_2state_21x21_zeros.csv`: root coordinates and scaled residuals.
- `ising_2state_21x21_coefficients.csv`: exact integer coefficients.
- `replicate_ising_21x21_transfer.py` and `ising_square_transfer_n21.cpp`:
  coefficient, root, and plotting source. All eight modular passes are cached
  in `../work`.

## 22x22 Ising transfer-matrix case

The 22x22 engine uses 32-bit modular residues to fit a pass in about 15.9 GB
of RAM; 16 primes suffice for exact reconstruction. The degree-946 polynomial
has no root at zero and has a 22-fold root at -1. Its remaining degree-924
quotient is square-free modulo a reconstruction prime. All 946 roots are
saved, with a largest scaled residual of about `8.9e-13` and 80 significant
digits in the CSV.

- `ising_2state_22x22_transfer_roots.png`: plot of all 946 roots.
- `ising_2state_22x22_zeros.csv`: root coordinates and scaled residuals.
- `ising_2state_22x22_coefficients.csv`: exact integer coefficients.
- `replicate_ising_22x22_transfer.py` and `ising_square_transfer_n22.cpp`:
  coefficient, root, and plotting source. All 16 modular passes are cached in
  `../work`.

The exact polynomial can be recomputed with:

    python replicate_ising_22x22_transfer.py

One coefficient pass needs about 15.9 GB of RAM.
