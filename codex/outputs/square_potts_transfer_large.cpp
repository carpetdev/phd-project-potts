#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

// Coefficient engine for the larger Q=3 square lattices. One 31-bit modular
// pass uses uint32_t storage, keeping the N=14 working vector below 7 GiB.

static inline uint32_t add3_mod(uint32_t a, uint32_t b, uint32_t c, uint32_t p) {
    uint64_t s = static_cast<uint64_t>(a) + b;
    if (s >= p) s -= p;
    s += c;
    if (s >= p) s -= p;
    return static_cast<uint32_t>(s);
}

static inline uint32_t sum_prev_minus(uint32_t s, uint32_t prev,
                                      uint32_t current, uint32_t p) {
    const uint64_t u = static_cast<uint64_t>(s) + prev;
    if (u >= current) {
        uint64_t result = u - current;
        if (result >= p) result -= p;
        return static_cast<uint32_t>(result);
    }
    return static_cast<uint32_t>(u + p - current);
}

static inline uint32_t add_mod(uint32_t a, uint32_t b, uint32_t p) {
    uint64_t s = static_cast<uint64_t>(a) + b;
    if (s >= p) s -= p;
    return static_cast<uint32_t>(s);
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: square_potts_transfer_large MODULUS N THREADS\n";
        return 2;
    }
    const uint32_t p = static_cast<uint32_t>(std::stoul(argv[1]));
    const int n = std::stoi(argv[2]);
    const int threads = std::stoi(argv[3]);
#ifdef _OPENMP
    omp_set_num_threads(threads);
#else
    (void)threads;
#endif
    if (n < 12 || n > 14) throw std::runtime_error("N must be 12, 13, or 14");

    const int m = n;
    std::vector<int> pow3(n + 1, 1);
    for (int i = 1; i <= n; ++i) pow3[i] = pow3[i - 1] * 3;
    const int states = pow3[n];
    const int max_degree = 2 * n * m - n;
    const int coeff_stride = max_degree + 1;

    std::vector<uint8_t> vertical_matches(states, 0);
#pragma omp parallel for schedule(static)
    for (int state = 0; state < states; ++state) {
        int matches = 0;
        for (int i = 0; i < n; ++i) {
            const int here = (state / pow3[i]) % 3;
            const int next = (state / pow3[(i + 1) % n]) % 3;
            matches += (here == next);
        }
        vertical_matches[state] = static_cast<uint8_t>(matches);
    }

    std::vector<uint32_t> values(static_cast<size_t>(states) * coeff_stride, 0);
    int degree = n;
#pragma omp parallel for schedule(static)
    for (int state = 0; state < states; ++state) {
        values[static_cast<size_t>(state) * coeff_stride + vertical_matches[state]] = 1;
    }

    for (int column = 1; column < m; ++column) {
        for (int dim = 0; dim < n; ++dim) {
            const int stride = pow3[dim];
            const int block = 3 * stride;
            const int expanded_degree = degree + 1;
#pragma omp parallel for schedule(static)
            for (int base = 0; base < states; base += block) {
                for (int offset = 0; offset < stride; ++offset) {
                    const int s0 = base + offset;
                    const int s1 = s0 + stride;
                    const int s2 = s1 + stride;
                    uint32_t* a0 = values.data() + static_cast<size_t>(s0) * coeff_stride;
                    uint32_t* a1 = values.data() + static_cast<size_t>(s1) * coeff_stride;
                    uint32_t* a2 = values.data() + static_cast<size_t>(s2) * coeff_stride;
                    uint32_t prev0 = 0, prev1 = 0, prev2 = 0;
                    for (int k = 0; k <= expanded_degree; ++k) {
                        const uint32_t old0 = (k <= degree) ? a0[k] : 0;
                        const uint32_t old1 = (k <= degree) ? a1[k] : 0;
                        const uint32_t old2 = (k <= degree) ? a2[k] : 0;
                        const uint32_t s = add3_mod(old0, old1, old2, p);
                        a0[k] = sum_prev_minus(s, prev0, old0, p);
                        a1[k] = sum_prev_minus(s, prev1, old1, p);
                        a2[k] = sum_prev_minus(s, prev2, old2, p);
                        prev0 = old0;
                        prev1 = old1;
                        prev2 = old2;
                    }
                }
            }
            degree = expanded_degree;
        }

#pragma omp parallel for schedule(static)
        for (int state = 0; state < states; ++state) {
            const int shift = vertical_matches[state];
            if (shift == 0) continue;
            uint32_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = degree; k >= 0; --k) a[k + shift] = a[k];
            for (int k = 0; k < shift; ++k) a[k] = 0;
        }
        degree += n;
        std::cerr << "N=" << n << " column " << column + 1 << "/" << m << '\n';
    }

    std::vector<uint32_t> partition_coeffs(degree + 1, 0);
#pragma omp parallel
    {
        std::vector<uint32_t> local(degree + 1, 0);
#pragma omp for schedule(static)
        for (int state = 0; state < states; ++state) {
            const uint32_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = 0; k <= degree; ++k) local[k] = add_mod(local[k], a[k], p);
        }
#pragma omp critical
        {
            for (int k = 0; k <= degree; ++k) partition_coeffs[k] = add_mod(partition_coeffs[k], local[k], p);
        }
    }

    std::cout << n << ',' << degree;
    for (uint32_t c : partition_coeffs) std::cout << ',' << c;
    std::cout << '\n';
    return 0;
}
