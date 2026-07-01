module Save

using FromFile
@from "Partition.jl" using Partition
@from "Load.jl" using Load

using JSON

function part(q::Int, n::Int)
    part = Partition.spart(q, n)
    JSON.json(Load.data_pather("parts/$(q)_$(n).json"), part)
    return
end

function classes(q::Int, n::Int)
    symmetry = SymmetryData{q,n}(Partition.symmetry_classes(q, n)...)
    JSON.json(Load.data_pather("symmetry/$(q)_$(n).json"), symmetry)
    return
end

end