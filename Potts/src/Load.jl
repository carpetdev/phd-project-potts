module Load

export SymmetryData

using Polynomials
using JSON
using Bijections

struct SymmetryData{q,n}
    classes::Vector{Vector{Tuple{NTuple{q,Int},Tuple{Int,Int}}}}
    reps::Vector{NTuple{n,Int}} # Can also just find this from ordered_configs and classes together
    ordered_configs::Vector{NTuple{n,Int}}
end

function part(q::Int, n::Int)
    return JSON.parsefile("data/parts/$(q)_$(n).json", Polynomial{BigInt})
end

function part′(q::Int, n::Int)
    return JSON.parsefile("data/parts/$(q)_$(n)'.json", Polynomial{BigInt})
end

function symmetry_class(q::Int, n::Int)
    return JSON.parsefile("data/symmetry/$(q)_$(n).json", SymmetryData{q,n})
end

end