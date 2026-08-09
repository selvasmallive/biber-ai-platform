[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param()

$ErrorActionPreference = 'Stop'
$Project = 'xriq-project-dev'
$Region = 'northamerica-northeast2'
$Zone = 'northamerica-northeast2-a'
$Instance = 'xriq-staging-devnet-postgres'
$Vm = 'xriq-staging-devnet-node'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Snapshot = "xriq-staging-devnet-node-$Stamp"
$Gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source

$ConfiguredProject = & $Gcloud config get-value project 2>$null
if ($ConfiguredProject.Trim() -ne $Project) {
    throw "Refusing to continue: active project is '$ConfiguredProject', expected '$Project'."
}

& $Gcloud projects describe $Project --format='value(projectId)' | Out-Null

$Disk = & $Gcloud compute instances describe $Vm --project=$Project --zone=$Zone --format='value(disks[0].source.basename())'
if ([string]::IsNullOrWhiteSpace($Disk)) {
    throw "Could not resolve the boot disk for VM '$Vm'."
}

if ($PSCmdlet.ShouldProcess("Cloud SQL $Instance", 'Create on-demand backup')) {
    & $Gcloud sql backups create --instance=$Instance --project=$Project --description="Pre-shutdown backup $Stamp" --quiet
}

if ($PSCmdlet.ShouldProcess("disk $Disk", "Create snapshot $Snapshot")) {
    & $Gcloud compute disks snapshot $Disk --project=$Project --zone=$Zone --snapshot-names=$Snapshot --quiet
}

if ($PSCmdlet.ShouldProcess("VM $Vm", 'Stop')) {
    & $Gcloud compute instances stop $Vm --project=$Project --zone=$Zone --quiet
}

if ($PSCmdlet.ShouldProcess("Cloud SQL $Instance", 'Set activation policy to never')) {
    & $Gcloud sql instances patch $Instance --project=$Project --activation-policy=never --quiet
}

Write-Host "Shutdown completed. VM disk snapshot: $Snapshot"
& $Gcloud sql backups list --instance=$Instance --project=$Project --limit=3
& $Gcloud compute instances describe $Vm --project=$Project --zone=$Zone --format='table(name,status)'
& $Gcloud sql instances describe $Instance --project=$Project --format='table(name,state,settings.activationPolicy)'
