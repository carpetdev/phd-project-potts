module Save
using ..Utils
using ..Partition

using JSON

function part(q::Int, n::Int)
    part = Partition.part(q, n)
    JSON.json(Utils.data_pather("parts/$(q)_$(n).json"), part)
    return
end

function part′(q::Int, n::Int)
    part = Partition.spart′(q, n)
    JSON.json(Utils.data_pather("parts/$(q)_$(n)'.json"), part)
    return
end

function classes(q::Int, n::Int)
    symmetry = SymmetryData{q, n}(Partition.symmetry_classes(q, n)...)
    JSON.json(Utils.data_pather("symmetry/$(q)_$(n).json"), symmetry)
    return
end
end
