module Potts

export Partition, Roots, Utils, Save, Load

include("Utils.jl")
include("Partition.jl")
include("Roots.jl")
include("Save.jl")

using PrecompileTools
using REPL.TerminalMenus

@compile_workload begin
    Save.classes(2, 1)
    Save.part′(2, 1)
    Roots.plot′(2, 1)
end

# struct TransferMatrix <: AbstractMatrix{Tuple{Int}}
#     matrix::Matrix{Tuple{Int}}

#     Base.zero(::Type{Tuple{Int}}) = (0,)

#     function TransferMatrix(n::Int)
#         new(zeros(Tuple{Int}, n, n))
#     end

#     Base.size(T::TransferMatrix) = 2
# end

function __init__()
    menu()
    return
end

function menu()
    isinteractive() || return
    task_menu = RadioMenu(["Plot roots of partition function", "Calculate partition function", "Calculate symmetry classes"], ctrl_c_interrupt = false)
    println("Choose an option (press ^C or q to cancel):")
    choice = request(task_menu)

    if choice == -1
        return
    end

    println("Please input q and n (e.g. \'3 5\'):")
    q::Int, n::Int = parse.(Int, split(readline()))

    if !isfile("data/symmetry/$(q)_$(n).json")
        println("Calculating symmetry classes for q=$(q), n=$(n) and saving to \'data/symmetry/$(q)_$(n).json\'")
        Save.classes(q, n)
    else
        println("Symmetry classes for q=$(q), n=$(n) exist at \'data/symmetry/$(q)_$(n).json\'")
    end

    if choice == 1 || choice == 2
        if !isfile("data/parts/$(q)_$(n)'.json")
            println("Calculating partition function for q=$(q), n=$(n) and saving to \'data/parts/$(q)_$(n).json\'")
            Save.part′(q, n)
        else
            println("Partition function for q=$(q), n=$(n) exists at \'data/symmetry/$(q)_$(n)'.json\'")
        end
    end

    if choice == 1
        println("Plotting roots for for q=$(q), n=$(n)")
        Roots.plot′(q, n)
    end

    println("Done!")
    println()
    menu()
    return
end

end
