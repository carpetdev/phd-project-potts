def is_prime(n):
    for p in (2,3,5,7,11,13,17,19,23,29,31,37):
        if n%p==0: return n==p
    d,s=n-1,0
    while d%2==0: d//=2; s+=1
    for a in (2,325,9375,28178,450775,9780504,1795265022):
        a%=n
        if not a: continue
        x=pow(a,d,n)
        if x in (1,n-1): continue
        for _ in range(s-1):
            x=x*x%n
            if x==n-1: break
        else: return False
    return True
ps=[]
for j in range(7):
    x=2**61-1-j*1000000
    while not is_prime(x): x-=2
    ps.append(x)
import math
print(ps,'product_bits',math.prod(ps).bit_length(),'bound_bits',(2**400).bit_length())
