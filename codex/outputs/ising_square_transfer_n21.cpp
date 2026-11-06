#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

// Exact-coefficient transfer engine for the 21 x 21 Ising/Potts (Q=2)
// square lattice with periodic vertical and open horizontal boundaries.
// Each run computes one coefficient vector modulo a 61-bit prime. Only
// addition is used, so uint64_t arithmetic is sufficient for the residues.

static inline uint64_t add_mod(uint64_t a, uint64_t b, uint64_t p) {
    const uint64_t sum = a + b;  // a,b < p < 2^61, hence no overflow.
    return sum >= p ? sum - p : sum;
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: ising_square_transfer_n21 MODULUS N THREADS\n";
        return 2;
    }
    const uint64_t p = std::stoull(argv[1]);
    const int n = std::stoi(argv[2]);
    const int threads = std::stoi(argv[3]);
#ifdef _OPENMP
    omp_set_num_threads(threads);
#else
    (void)threads;
#endif
    if (n != 21) throw std::runtime_error("This engine is configured for N=21");

    const int m = n;
    const int states = 1 << n;
    const int max_degree = 2 * n * m - n;
    const int coeff_stride = max_degree + 1;

    std::vector<uint8_t> vertical_matches(states, 0);
#pragma omp parallel for schedule(static)
    for (int state = 0; state < states; ++state) {
        int matches = 0;
        for (int i = 0; i < n; ++i) {
            const int here = (state >> i) & 1;
            const int next = (state >> ((i + 1) % n)) & 1;
            matches += (here == next);
        }
        vertical_matches[state] = static_cast<uint8_t>(matches);
    }

    std::vector<uint64_t> values(static_cast<size_t>(states) * coeff_stride, 0);
    int degree = n;
#pragma omp parallel for schedule(static)
    for (int state = 0; state < states; ++state) {
        values[static_cast<size_t>(state) * coeff_stride + vertical_matches[state]] = 1;
    }

    for (int column = 1; column < m; ++column) {
        for (int dim = 0; dim < n; ++dim) {
            const int stride = 1 << dim;
            const int block = 2 * stride;
            const int expanded_degree = degree + 1;
#pragma omp parallel for schedule(static)
            for (int base = 0; base < states; base += block) {
                for (int offset = 0; offset < stride; ++offset) {
                    const int s0 = base + offset;
                    const int s1 = s0 + stride;
                    uint64_t* a0 = values.data() + static_cast<size_t>(s0) * coeff_stride;
                    uint64_t* a1 = values.data() + static_cast<size_t>(s1) * coeff_stride;
                    uint64_t prev0 = 0, prev1 = 0;
                    for (int k = 0; k <= expanded_degree; ++k) {
                        const uint64_t old0 = (k <= degree) ? a0[k] : 0;
                        const uint64_t old1 = (k <= degree) ? a1[k] : 0;
                        // K = [[x,1],[1,x]]. The two assignments are
                        // old0*x+old1 and old0+old1*x, written in place.
                        a0[k] = add_mod(old1, prev0, p);
                        a1[k] = add_mod(old0, prev1, p);
                        prev0 = old0;
                        prev1 = old1;
                    }
                }
            }
            degree = expanded_degree;
        }

        // Add the periodic vertical bonds for this column.
#pragma omp parallel for schedule(static)
        for (int state = 0; state < states; ++state) {
            const int shift = vertical_matches[state];
            if (shift == 0) continue;
            uint64_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = degree; k >= 0; --k) a[k + shift] = a[k];
            for (int k = 0; k < shift; ++k) a[k] = 0;
        }
        degree += n;
        std::cerr << "N=" << n << " column " << column + 1 << "/" << m << '\n';
    }

    std::vector<uint64_t> partition_coeffs(degree + 1, 0);
#pragma omp parallel
    {
        std::vector<uint64_t> local(degree + 1, 0);
#pragma omp for schedule(static)
        for (int state = 0; state < states; ++state) {
            const uint64_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = 0; k <= degree; ++k) local[k] = add_mod(local[k], a[k], p);
        }
#pragma omp critical
        {
            for (int k = 0; k <= degree; ++k) partition_coeffs[k] = add_mod(partition_coeffs[k], local[k], p);
        }
    }

    std::cout << n << ',' << degree;
    for (uint64_t c : partition_coeffs) std::cout << ',' << c;
    std::cout << '\n';
    return 0;
}
