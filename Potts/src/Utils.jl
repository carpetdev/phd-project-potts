module Utils
    export SymmetryData

    struct SymmetryData{q, n}
        classes::Vector{Vector{Tuple{NTuple{q, Int}, Tuple{Int, Int}}}}
        reps::Vector{NTuple{n, Int}} # Can also just find this from ordered_configs and classes together
        ordered_configs::Vector{NTuple{n, Int}}
    end

    function data_pather(rel_path::String)
        return abspath(something(Base.active_project()), "..", "..", "data", rel_path)
    end
end

module Load
    using ..Utils

    using JSON
    using Polynomials

    function part(q::Int, n::Int)
        return JSON.parsefile(Utils.data_pather("parts/$(q)_$(n).json"), Polynomial{BigInt})
    end

    function part′(q::Int, n::Int)
        return JSON.parsefile(Utils.data_pather("parts/$(q)_$(n)'.json"), Polynomial{BigInt})
    end

    function symmetry_class(q::Int, n::Int)
        return JSON.parsefile(Utils.data_pather("symmetry/$(q)_$(n).json"), SymmetryData{q, n})
    end
end
