#include <boost/multiprecision/cpp_dec_float.hpp>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using Real = boost::multiprecision::number<boost::multiprecision::cpp_dec_float<80>>;

struct C {
    Real re, im;
    C() : re(0), im(0) {}
    C(Real r, Real i = 0) : re(r), im(i) {}
};

static C operator+(const C& a, const C& b) { return C(a.re + b.re, a.im + b.im); }
static C operator-(const C& a, const C& b) { return C(a.re - b.re, a.im - b.im); }
static C operator*(const C& a, const C& b) {
    return C(a.re*b.re - a.im*b.im, a.re*b.im + a.im*b.re);
}
static C operator/(const C& a, const C& b) {
    Real d = b.re*b.re + b.im*b.im;
    return C((a.re*b.re + a.im*b.im)/d, (a.im*b.re - a.re*b.im)/d);
}
static Real norm2(const C& a) { return a.re*a.re + a.im*a.im; }
static Real magnitude(const C& a) { return sqrt(norm2(a)); }

static bool next_csv_line(std::ifstream& f, std::string& line) {
    return static_cast<bool>(std::getline(f, line));
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: refine_aberth N coefficients.csv roots.csv\n";
        return 2;
    }
    const int target_n = std::stoi(argv[1]);
    std::vector<Real> coeffs;
    {
        std::ifstream in(argv[2]);
        std::string line;
        std::getline(in, line);
        while (std::getline(in, line)) {
            std::stringstream ss(line);
            std::string n_s, k_s, c_s;
            std::getline(ss, n_s, ','); std::getline(ss, k_s, ','); std::getline(ss, c_s, ',');
            if (std::stoi(n_s) == target_n) {
                const int k = std::stoi(k_s);
                if (static_cast<int>(coeffs.size()) <= k) coeffs.resize(k + 1);
                coeffs[k] = Real(c_s);
            }
        }
    }
    if (coeffs.size() < 2) throw std::runtime_error("No polynomial coefficients loaded");
    const int degree = static_cast<int>(coeffs.size()) - 1;

    std::vector<C> roots;
    {
        std::ifstream in(argv[3]);
        std::string line;
        std::getline(in, line);
        while (std::getline(in, line)) {
            std::stringstream ss(line);
            std::string n_s, idx_s, re_s, im_s, err_s;
            std::getline(ss, n_s, ','); std::getline(ss, idx_s, ',');
            std::getline(ss, re_s, ','); std::getline(ss, im_s, ',');
            if (std::stoi(n_s) == target_n) roots.emplace_back(Real(re_s), Real(im_s));
        }
    }
    if (static_cast<int>(roots.size()) != degree) throw std::runtime_error("Root seed count does not equal degree");

    const C one(Real(1));
    int iteration = 0;
    Real last_step = 0;
    for (; iteration < 500; ++iteration) {
        std::vector<C> next(roots.size());
        last_step = 0;
        for (size_t i = 0; i < roots.size(); ++i) {
            C p(coeffs.back()), dp;
            for (int k = degree - 1; k >= 0; --k) {
                dp = dp*roots[i] + p;
                p = p*roots[i] + C(coeffs[k]);
            }
            if (norm2(dp) == 0) { next[i] = roots[i]; continue; }
            const C newton = p / dp;
            C repulsion;
            for (size_t j = 0; j < roots.size(); ++j) {
                if (j == i) continue;
                const C diff = roots[i] - roots[j];
                if (norm2(diff) != 0) repulsion = repulsion + one / diff;
            }
            const C denominator = one - newton*repulsion;
            C correction = (norm2(denominator) == 0) ? newton : newton / denominator;
            next[i] = roots[i] - correction;
            Real step = magnitude(correction);
            if (step > last_step) last_step = step;
        }
        roots.swap(next);
        if (last_step < Real("1e-55")) break;
    }

    std::cerr << "N=" << target_n << " Aberth iterations=" << iteration
              << " max_step=" << std::scientific << std::setprecision(4) << last_step << '\n';
    std::cout << std::scientific << std::setprecision(55);
    for (size_t i = 0; i < roots.size(); ++i) {
        C p(coeffs.back());
        for (int k = degree - 1; k >= 0; --k) p = p*roots[i] + C(coeffs[k]);
        Real denom = 0;
        const Real r = magnitude(roots[i]);
        Real rpow = 1;
        for (const Real& c : coeffs) { denom += abs(c)*rpow; rpow *= r; }
        const Real residual = denom == 0 ? Real(0) : magnitude(p)/denom;
        std::cout << i+1 << ',' << roots[i].re << ',' << roots[i].im << ',' << residual << '\n';
    }
}
