<#
 Runs the official SuPreM container once (same flags as HF model card).

 Prerequisites:
 - Docker Desktop (Linux engine) running, NVIDIA GPU + WSL2 Linux backend configured
 - inputs layout: InputsRoot\{caseFolder}\ct.nii.gz

 Example (after unzip BodyMaps BDMAP ZIP so ct.nii.gz lives under InputsRoot):
   .\scripts\suprem-docker-once.ps1 `
       -InputsRoot "C:\work\bdmap-demo\inputs" `
       -OutputsRoot "C:\work\bdmap-demo\outputs"
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $InputsRoot,
    [Parameter(Mandatory = $true)]
    [string] $OutputsRoot,
    [string] $DockerImage = "qchen99/suprem:v1",
    [string] $GpuDevice = "0",
    [string] $DockerMemoryLimit = "128G",
    [switch] $SkipPull
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $InputsRoot)) {
    throw "InputsRoot not found or empty path: '$InputsRoot' (needs {case}\ct.nii.gz layout)."
}
$inp = (Resolve-Path -LiteralPath $InputsRoot).ProviderPath
$out = Resolve-Path -LiteralPath $OutputsRoot -ErrorAction SilentlyContinue
if (-not $out) {
    New-Item -ItemType Directory -Path $OutputsRoot | Out-Null
    $out = (Resolve-Path -LiteralPath $OutputsRoot).ProviderPath
}

Write-Host "Image: $DockerImage"
if (-not $SkipPull) {
    docker pull $DockerImage | Out-Host
}

docker run `
    --gpus "device=$GpuDevice" `
    -m $DockerMemoryLimit `
    --rm `
    -v "${inp}:/workspace/inputs" `
    -v "${out}:/workspace/outputs" `
    $DockerImage `
    /bin/bash -c "sh predict.sh"

Write-Host "`nOutputs should appear under:`n${out}"
