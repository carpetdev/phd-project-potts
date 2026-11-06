import math

def is_prime(n):
    if n < 2:
        return False
    small = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for a in [2, 325, 9375, 28178, 450775, 9780504, 1795265022]:
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True

primes = []
for offset in range(0, 100000000, 1000000):
    n = (2**61 - 1) - offset
    while not is_prime(n):
        n -= 2
    primes.append(n)
    if len(primes) == 4:
        break
print(primes)
print('product bits', math.prod(primes).bit_length())
print('bound bits', (3**121).bit_length())
