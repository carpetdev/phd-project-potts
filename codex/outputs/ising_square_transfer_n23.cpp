#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

// Exact-coefficient transfer engine for the 23 x 23 Ising/Potts (Q=2)
// square lattice with periodic vertical and open horizontal boundaries.
// Each run computes one coefficient vector modulo a prime below 2^16.
// Values are stored in uint16_t; the intermediate sum is safe in uint32_t.
static inline uint16_t add_mod(uint16_t a, uint16_t b, uint16_t p) {
    const uint32_t sum = static_cast<uint32_t>(a) + b;
    return static_cast<uint16_t>(sum >= p ? sum - p : sum);
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: ising_square_transfer_n23 MODULUS N THREADS\n";
        return 2;
    }
    const uint32_t parsed_p = static_cast<uint32_t>(std::stoul(argv[1]));
    if (parsed_p >= (1u << 16)) throw std::runtime_error("Modulus must be below 2^16");
    const uint16_t p = static_cast<uint16_t>(parsed_p);
    const int n = std::stoi(argv[2]);
    const int threads = std::stoi(argv[3]);
#ifdef _OPENMP
    omp_set_num_threads(threads);
#else
    (void)threads;
#endif
    if (n != 23) throw std::runtime_error("This engine is configured for N=23");

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

    std::vector<uint16_t> values(static_cast<size_t>(states) * coeff_stride, 0);
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
                    uint16_t* a0 = values.data() + static_cast<size_t>(s0) * coeff_stride;
                    uint16_t* a1 = values.data() + static_cast<size_t>(s1) * coeff_stride;
                    uint16_t prev0 = 0, prev1 = 0;
                    for (int k = 0; k <= expanded_degree; ++k) {
                        const uint16_t old0 = (k <= degree) ? a0[k] : 0;
                        const uint16_t old1 = (k <= degree) ? a1[k] : 0;
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
            uint16_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = degree; k >= 0; --k) a[k + shift] = a[k];
            for (int k = 0; k < shift; ++k) a[k] = 0;
        }
        degree += n;
        std::cerr << "N=" << n << " column " << column + 1 << "/" << m << '\n';
    }

    std::vector<uint16_t> partition_coeffs(degree + 1, 0);
#pragma omp parallel
    {
        std::vector<uint16_t> local(degree + 1, 0);
#pragma omp for schedule(static)
        for (int state = 0; state < states; ++state) {
            const uint16_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = 0; k <= degree; ++k) local[k] = add_mod(local[k], a[k], p);
        }
#pragma omp critical
        {
            for (int k = 0; k <= degree; ++k) partition_coeffs[k] = add_mod(partition_coeffs[k], local[k], p);
        }
    }

    std::cout << n << ',' << degree;
    for (uint16_t c : partition_coeffs) std::cout << ',' << c;
    std::cout << '\n';
    return 0;
}
