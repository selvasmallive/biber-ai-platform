[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param()

$ErrorActionPreference = 'Stop'
$Project = 'xriq-project-dev'
$Zone = 'northamerica-northeast2-a'
$Instance = 'xriq-staging-devnet-postgres'
$Vm = 'xriq-staging-devnet-node'
$Gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source

$ConfiguredProject = & $Gcloud config get-value project 2>$null
if ($ConfiguredProject.Trim() -ne $Project) {
    throw "Refusing to continue: active project is '$ConfiguredProject', expected '$Project'."
}

& $Gcloud projects describe $Project --format='value(projectId)' | Out-Null

if ($PSCmdlet.ShouldProcess("Cloud SQL $Instance", 'Set activation policy to always')) {
    & $Gcloud sql instances patch $Instance --project=$Project --activation-policy=always --quiet
}

if ($PSCmdlet.ShouldProcess("VM $Vm", 'Start')) {
    & $Gcloud compute instances start $Vm --project=$Project --zone=$Zone --quiet
}

& $Gcloud compute instances describe $Vm --project=$Project --zone=$Zone --format='table(name,status)'
& $Gcloud sql instances describe $Instance --project=$Project --format='table(name,state,settings.activationPolicy)'

Write-Host 'Resources started. Run docs/XRIQ_GCP_LIVE_CHAIN_SMOKE.md before declaring service restored.'
