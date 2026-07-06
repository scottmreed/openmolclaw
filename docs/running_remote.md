# Running OpenMolClaw Remotely

OpenMolClaw stays local-first in remote environments: choose the model provider
explicitly, keep provider keys in environment variables or platform secrets, and
prefer SSH tunnels over public network exposure.

## Cloud VM Over SSH

On the VM:

```bash
git clone https://github.com/scottmreed/openmolclaw.git
cd openmolclaw
export OPENROUTER_API_KEY=...
scripts/run_vm.sh
```

From your laptop:

```bash
ssh -N -L 5000:127.0.0.1:5000 user@vm.example.edu
```

Then open `http://127.0.0.1:5000`.

Override defaults with environment variables:

```bash
OPENMOLCLAW_PORT=5050 \
OPENMOLCLAW_CONFIG=examples/config.remote.local.yaml \
OPENMOLCLAW_WORKSPACE_ID=vm-demo \
scripts/run_vm.sh
```

## HPC Login Nodes

Login nodes are appropriate for diagnostics, demos, and tunnel setup:

```bash
python -m openmolclaw doctor
python -m openmolclaw run-contracts
python -m openmolclaw serve --host 127.0.0.1 --port 5000 --workspace-id login-demo
```

Do not run long-lived servers, heavy local inference, or batch workloads on a
shared login node unless your cluster policy explicitly allows it. Use a Slurm
allocation for heavier work.

## Slurm Server Job

From a checkout on the cluster:

```bash
mkdir -p logs
sbatch scripts/slurm/openmolclaw-server.sbatch
tail -f logs/openmolclaw-<jobid>.out
```

The job prints values like:

```text
OPENMOLCLAW_JOB_ID=123456
OPENMOLCLAW_NODE=compute-12.cluster.edu
OPENMOLCLAW_HOST=127.0.0.1
OPENMOLCLAW_PORT=5000
OPENMOLCLAW_WORKSPACE_ID=slurm-123456
```

If direct SSH to compute nodes is allowed:

```bash
ssh -N -J user@login.cluster.edu -L 5000:127.0.0.1:5000 user@compute-12.cluster.edu
```

If the login node can route to the compute node:

```bash
scripts/slurm/tunnel_from_job.sh \
  --login user@login.cluster.edu \
  --node compute-12.cluster.edu \
  --port 5000
```

That prints:

```bash
ssh -N -L 5000:compute-12.cluster.edu:5000 user@login.cluster.edu
```

The login-node routing form may require `OPENMOLCLAW_HOST=0.0.0.0` in the Slurm
job. Use that only when your cluster firewall is trusted, and set
`OPENMOLCLAW_REMOTE_TOKEN` for lightweight API protection.

## Modal

Create the OpenRouter secret, then serve or deploy the WSGI template:

```bash
modal secret create openmolclaw-openrouter OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
modal serve deploy/modal_app.py
modal deploy deploy/modal_app.py
```

The default Modal template uses `workspace.save_mode: memory_only` and does not
mount a persistent volume for user structures.

## Remote Token

Set `OPENMOLCLAW_REMOTE_TOKEN` when you expose the API beyond an SSH tunnel:

```bash
export OPENMOLCLAW_REMOTE_TOKEN="$(openssl rand -hex 24)"
python -m openmolclaw serve --host 0.0.0.0 --config examples/config.remote.openrouter.zdr.yaml
```

When the token is set, `/api/*` routes require one of:

```bash
curl -H "Authorization: Bearer $OPENMOLCLAW_REMOTE_TOKEN" http://127.0.0.1:5000/api/health
curl -H "X-OpenMolClaw-Token: $OPENMOLCLAW_REMOTE_TOKEN" http://127.0.0.1:5000/api/health
```

The current browser UI does not yet include a token prompt, so this guard is
best for API use, curl smoke tests, or deployments that inject the header before
requests reach OpenMolClaw. For browser use, prefer the SSH tunnel workflow.

This is lightweight protection, not multi-user authentication. Keep the default
`--host 127.0.0.1` and SSH tunnel workflow unless you have a specific reason to
bind the app to a remote network interface.
