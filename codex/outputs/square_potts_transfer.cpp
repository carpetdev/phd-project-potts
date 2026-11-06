#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

// Exact coefficient engine for the square-lattice Potts partition function.
// Coefficients are calculated modulo a large prime; the Python driver combines
// four residues with CRT to recover the exact integer coefficients.

static inline uint64_t add3_mod(uint64_t a, uint64_t b, uint64_t c, uint64_t p) {
    uint64_t s = a + b;
    if (s >= p) s -= p;
    s += c;
    if (s >= p) s -= p;
    return s;
}

static inline uint64_t sum_prev_minus(uint64_t s, uint64_t prev,
                                      uint64_t current, uint64_t p) {
    const uint64_t u = s + prev;
    if (u >= current) {
        uint64_t result = u - current;
        if (result >= p) result -= p;
        return result;
    }
    return u + p - current;
}

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: square_potts_transfer MODULUS\n";
        return 2;
    }
    const uint64_t p = std::stoull(argv[1]);

    for (int n = 6; n <= 11; ++n) {
        const int m = n;
        std::vector<int> pow3(n + 1, 1);
        for (int i = 1; i <= n; ++i) pow3[i] = pow3[i - 1] * 3;
        const int states = pow3[n];
        const int max_degree = 2 * n * m - n;
        const int coeff_stride = max_degree + 1;

        std::vector<uint8_t> vertical_matches(states, 0);
        for (int state = 0; state < states; ++state) {
            int matches = 0;
            for (int i = 0; i < n; ++i) {
                const int here = (state / pow3[i]) % 3;
                const int next = (state / pow3[(i + 1) % n]) % 3;
                matches += (here == next);
            }
            vertical_matches[state] = static_cast<uint8_t>(matches);
        }

        std::vector<uint64_t> values(static_cast<size_t>(states) * coeff_stride, 0);
        int degree = n;
        for (int state = 0; state < states; ++state) {
            values[static_cast<size_t>(state) * coeff_stride + vertical_matches[state]] = 1;
        }

        // Add columns one at a time. For one row site the horizontal-bond
        // kernel is J + (x-1)I, so the tensor contraction is exact and costs
        // O(n * 3^n) polynomial coefficient updates per new column.
        for (int column = 1; column < m; ++column) {
            for (int dim = 0; dim < n; ++dim) {
                const int stride = pow3[dim];
                const int block = 3 * stride;
                const int expanded_degree = degree + 1;
                for (int base = 0; base < states; base += block) {
                    for (int offset = 0; offset < stride; ++offset) {
                        const int s0 = base + offset;
                        const int s1 = s0 + stride;
                        const int s2 = s1 + stride;
                        uint64_t* a0 = values.data() + static_cast<size_t>(s0) * coeff_stride;
                        uint64_t* a1 = values.data() + static_cast<size_t>(s1) * coeff_stride;
                        uint64_t* a2 = values.data() + static_cast<size_t>(s2) * coeff_stride;
                        uint64_t prev0 = 0, prev1 = 0, prev2 = 0;
                        for (int k = 0; k <= expanded_degree; ++k) {
                            const uint64_t old0 = (k <= degree) ? a0[k] : 0;
                            const uint64_t old1 = (k <= degree) ? a1[k] : 0;
                            const uint64_t old2 = (k <= degree) ? a2[k] : 0;
                            const uint64_t s = add3_mod(old0, old1, old2, p);
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

            // Internal periodic bonds within the new column contribute x^v.
            for (int state = 0; state < states; ++state) {
                const int shift = vertical_matches[state];
                if (shift == 0) continue;
                uint64_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
                for (int k = degree; k >= 0; --k) a[k + shift] = a[k];
                for (int k = 0; k < shift; ++k) a[k] = 0;
            }
            degree += n;
        }

        std::vector<uint64_t> partition_coeffs(degree + 1, 0);
        for (int state = 0; state < states; ++state) {
            const uint64_t* a = values.data() + static_cast<size_t>(state) * coeff_stride;
            for (int k = 0; k <= degree; ++k) {
                partition_coeffs[k] = add3_mod(partition_coeffs[k], a[k], 0, p);
            }
        }

        std::cout << n << ',' << degree;
        for (uint64_t c : partition_coeffs) std::cout << ',' << c;
        std::cout << '\n';
        std::cerr << "finished N=" << n << " degree=" << degree << '\n';
    }
    return 0;
}
