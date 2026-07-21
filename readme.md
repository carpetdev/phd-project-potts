# Installing Julia
See https://julialang.org/downloads/

# Running this code
First, clone this repo.
Start a Julia REPL with this project activated:
```shell
julia --project="/path/to/repo/Potts"
```
Press `]` to switch to the `pkg>` prompt and run
```julia
pkg> instantiate
```
to install all dependencies (first time only). Press Backspace to return to the `julia>` prompt and run
```julia
julia> using Potts
```
to import the package. This automatically runs `Potts.menu()`, but the modules defined in `Potts/src` are also available to the REPL. Note the menu's options perform calculations with periodic-open boundary conditions.