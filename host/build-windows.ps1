# Builds ixion.exe and ixion_fiber_smoke.exe with the llvm-mingw toolchain from a Kazarov deps
# root, then copies the runtime DLLs they need beside them.
#
#   powershell -File build-windows.ps1 -Deps <deps root> -Build <build dir> [-Cmake <cmake.exe>]
param(
    [Parameter(Mandatory)][string]$Deps,
    [Parameter(Mandatory)][string]$Build,
    [string]$Cmake
)

$ErrorActionPreference = 'Stop'

if (!$Cmake) {
    $found = Get-Command cmake -ErrorAction SilentlyContinue
    if (!$found) { throw 'cmake not found on PATH; pass -Cmake <path to cmake.exe>' }
    $Cmake = $found.Source
}

$deps = (Resolve-Path -LiteralPath $Deps).Path.Replace('\', '/')
$build = [IO.Path]::GetFullPath($Build).Replace('\', '/')
$source = [IO.Path]::GetFullPath($PSScriptRoot).Replace('\', '/')

$llvm = "$deps/llvm/llvm-mingw-20260922-ucrt-x86_64/bin"
$mingwBin = "$deps/llvm/llvm-mingw-20260922-ucrt-x86_64/x86_64-w64-mingw32/bin"
$ninja = "$deps/ninja/ninja.exe"
$sdlDir = "$deps/sdl/SDL3-3.4.18/x86_64-w64-mingw32/lib/cmake/SDL3"
$sdlBin = "$deps/sdl/SDL3-3.4.18/x86_64-w64-mingw32/bin"

foreach ($path in @("$llvm/clang++.exe", $ninja, "$sdlDir/SDL3Config.cmake", "$sdlBin/SDL3.dll", $Cmake)) {
    if (!(Test-Path -LiteralPath $path)) { throw "missing: $path" }
}

$env:PATH = "$llvm;$env:PATH"

& $Cmake -S $source -B $build -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_CXX_COMPILER=$llvm/clang++.exe" `
    "-DCMAKE_MAKE_PROGRAM=$ninja" `
    "-DSDL3_DIR=$sdlDir"
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed ($LASTEXITCODE)" }

& $Cmake --build $build --target ixion ixion_fiber_smoke
if ($LASTEXITCODE -ne 0) { throw "cmake build failed ($LASTEXITCODE)" }

# Stage SDL3 and the llvm-mingw runtime next to the executables. Both game modules must load this
# same SDL3.dll, so it lives in the one folder with ixion.exe.
$runtime = @("$sdlBin/SDL3.dll", "$mingwBin/libc++.dll", "$mingwBin/libunwind.dll", "$mingwBin/libwinpthread-1.dll")
foreach ($file in $runtime) {
    if (!(Test-Path -LiteralPath $file)) { throw "missing runtime file: $file" }
    Copy-Item -LiteralPath $file -Destination $build -Force
}

Write-Output "built: $build/ixion.exe, $build/ixion_fiber_smoke.exe"
