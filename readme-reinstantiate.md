# Reinstantiate BIBER On A New Vast GPU/Volume

Use this guide when you have already downloaded the old Vast runtime artifacts
to your local workstation and want to make a brand-new Vast GPU/volume look like
the previous BIBER runtime.

This guide assumes your local backup includes:

```text
/workspace/adapters
/workspace/outputs
/workspace/.hf_home
/workspace/biber-logs
/workspace/biber-ai-platform/.env
```

Do not commit these artifacts or `.env` to GitHub. `.env` contains secrets, and
the adapter/model cache folders are large runtime artifacts.

## Resume Prompt For Future Codex

Copy this prompt into the next Codex session after the new GPU exists:

```text
Read readme-reinstantiate.md, readme-resume-biber.md, and docs/CODEX_HANDOFF.md.
Resume BIBER on a brand-new Vast GPU/volume from the current GitHub main branch.
I have a local backup of /workspace/adapters, /workspace/outputs,
/workspace/.hf_home, /workspace/biber-logs, and /workspace/biber-ai-platform/.env.
Help me restore those artifacts to /workspace, bootstrap BIBER, and verify the
runtime. Keep OpenAI/Codex usage minimal. Do not rotate credentials. Do not
start training unless I explicitly approve it.
```

## 1. Create The New Vast Instance

Create a new Vast GPU instance with enough disk/volume space for the restored
runtime. The old backup was roughly:

```text
adapters    about 8.6 GB
.hf_home    about 15 GB
outputs     about 31 MB
biber-logs  about 156 KB
```

Choose a volume with extra space for the Python venv, vLLM cache, future
outputs, and training artifacts.

For the lowest-cost BIBER MVP resume, see
`docs/BIBER_VAST_COST_SAVING_RESUME.md`. The minimum practical profile for the
current default 7B coding model is usually one 16 GB NVIDIA GPU, 80-120 GB
container disk, and a 250-500 GB `/workspace` volume. Use `500 GB` when
restoring `.hf_home`, adapters, outputs, or datasets; use `250-300 GB` only for
short live eval/inference sessions where redownloading model cache later is
acceptable.

After Vast shows the new SSH host and port, set these PowerShell variables on
your workstation. Adjust `$BackupRoot` to your actual backup folder:

```powershell
$NewHost = "<new-vast-host-or-ip>"
$NewPort = "<new-vast-ssh-port>"
$Key = "$env:USERPROFILE\.ssh\biber_vast_ed25519"
$BackupRoot = "C:\BiberVastBackup"

$Adapters = "$BackupRoot\adapters"
$Outputs = "$BackupRoot\outputs"
$HfHome = "$BackupRoot\.hf_home"
$Logs = "$BackupRoot\biber-logs"
$EnvFile = "$BackupRoot\.env"
```

If you saved Hugging Face cache as `hf_home` instead of `.hf_home`, set:

```powershell
$HfHome = "$BackupRoot\hf_home"
```

## 2. Prepare The New `/workspace`

SSH into the new instance and install the minimum tools needed to clone the
repo:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "mkdir -p /workspace && apt-get update && apt-get install -y git curl jq python3 python3-venv python3-pip"
```

Clone the repo:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace && git clone https://github.com/selvasmallive/biber-ai-platform.git && cd biber-ai-platform && git checkout main && git pull --ff-only origin main"
```

For the current BIBER MVP-only branch, prefer:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace && git clone https://github.com/selvasmallive/biber-ai-platform.git && cd biber-ai-platform && git checkout biber/mvp-resume-20260712 && git pull --ff-only origin biber/mvp-resume-20260712"
```

## 3. Upload The Local Backup

Upload the runtime folders back to the new volume:

```powershell
scp -r -P $NewPort -i $Key $Adapters root@${NewHost}:/workspace/
scp -r -P $NewPort -i $Key $Outputs root@${NewHost}:/workspace/
scp -r -P $NewPort -i $Key $Logs root@${NewHost}:/workspace/
```

Upload Hugging Face cache to `/workspace/.hf_home`. Use this command whether
your local folder is named `.hf_home` or `hf_home`:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "rm -rf /workspace/.hf_home"
scp -r -P $NewPort -i $Key $HfHome root@${NewHost}:/workspace/.hf_home
```

Restore `.env` after the repo clone:

```powershell
scp -P $NewPort -i $Key $EnvFile root@${NewHost}:/workspace/biber-ai-platform/.env
ssh -i $Key -p $NewPort root@$NewHost "chmod 600 /workspace/biber-ai-platform/.env"
```

If any upload is interrupted, rerun the same `scp` command. For very large or
unstable transfers, use Git Bash/WSL `rsync -avP` instead of PowerShell `scp`.

## 4. Bootstrap Without Starting Base vLLM

On the new Vast instance, install dependencies and create the venv without
starting the base model first:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && BIBER_START_AFTER_BOOTSTRAP=false bash scripts/vast_bootstrap_direct.sh"
```

This reuses:

```text
/workspace/.hf_home
/workspace/adapters
/workspace/outputs
/workspace/biber-logs
/workspace/biber-ai-platform/.env
```

## 5. Start With The Previously Served Adapter

The adapter last served by the old Vast API was:

```text
/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z
```

Start BIBER with that adapter:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && BIBER_LORA_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z bash scripts/vast_start_lora_direct.sh"
```

If that adapter folder is missing, start the base model instead:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && bash scripts/vast_start_direct.sh"
```

## 6. Verify The Reinstantiated Runtime

Run the standard checks:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && bash scripts/vast_status_direct.sh"
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && bash scripts/vast_test_direct.sh"
```

Run the XRIQ API/client smoke:

```powershell
ssh -i $Key -p $NewPort root@$NewHost "cd /workspace/biber-ai-platform && bash scripts/vast_xriq_api_smoke.sh"
```

Expected broad result:

- API health returns `ok`.
- `/v1/models` lists `biber-dev-core-base` and, if adapter start succeeded,
  `biber-dev-core`.
- `vast_test_direct.sh` completes.
- `vast_xriq_api_smoke.sh` writes artifacts under `/workspace/outputs`.

## 7. Open A Local SSH Tunnel

Use the new Vast host and port:

```powershell
ssh -i $Key -p $NewPort root@$NewHost -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
```

## 8. Continue Development

After verification, future Codex should read these files:

1. `readme-reinstantiate.md`
2. `readme-resume-biber.md`
3. `docs/CODEX_HANDOFF.md`
4. `xriq/README.md`
5. `docs/VAST_DIRECT_DEPLOY.md`

Current near-term priority remains XRIQ private-devnet prototype first. Do not
restart QLoRA/training unless the user explicitly approves it.
