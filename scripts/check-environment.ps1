<#
 Smoke-check host tooling for demos + real inference.
#>
Write-Host "--- Python ---"
try {
    python --version
}
catch {
    Write-Host "(python not on PATH)"
}

Write-Host "`n--- Docker ---"
try {
    docker version
}
catch {
    Write-Host "Docker client error (is Docker Desktop started?)"
}

Write-Host "`n--- NVIDIA (Linux containers use WSL/driver stack) ---"
Write-Host "On Windows ensure WSL2 + Docker Desktop NVIDIA Container Toolkit docs are satisfied for GPU binds."
