# Local deployment

Run `./deploy.sh` from the Menú Familiar checkout on the Home Server as the repository owner. The command deploys the current committed branch. It pushes that exact commit to the branch's configured upstream after the local deployment succeeds.

## Owner setup

- Use the existing local Docker Engine and Compose installation and an account already authorized to use Docker through sudo. The command uses the local Unix socket and prompts for ordinary sudo authorization if needed.
- Keep the repository's `.venv` installed from `requirements.txt`. Use an attached local branch with a configured GitHub upstream and credentials that work without prompts. Commit the deployment workflow and your application changes through the normal Git workflow before the first run.
- Protect `.env` with mode `0600` and keep one unindented `MENU_IMAGE=` assignment. The existing Compose service must be running with the configured image, `/var/lib/menu-familiar/data`, LAN port `192.168.1.22:18766` and loopback backend `127.0.0.1:18768`. The configured Tailscale hostname must resolve from the host and serve valid HTTPS on port `8443`.
- Create a private, owner-controlled deployment directory. Allow disk space for an image archive and paired data snapshot per deployment, plus the Docker builds.

  ```sh
  install -d -m 0700 "$HOME/menu-familiar-deployments"
  ```

Before the first production execution, run the [isolated Docker verifier](../README.md#isolated-docker-verification) on the committed checkout and confirm LAN and HTTPS work from the deployment host and trusted devices. Use a maintenance window and pause household edits through verification or recovery. Keep other operators and maintenance jobs from running `start.sh`, `stop.sh`, importing data, modifying `.env`, or pruning Docker images during deployment. The deployment lock serializes invocations of `deploy.sh`.

## What to expect

The command tests committed source in a temporary directory, builds and smoke-tests it with the existing Docker verifier, and selects the verified local image by its full SHA-256 ID. It checks the running container, bind mount, port mappings and proxy gateway against the resolved configuration. Downtime starts when Menú Familiar stops for the paired SQLite/photo backup. After any approved migration, Compose recreates the single service with its existing volume, bridge and listeners. The host probes `/healthz`, the weekly menu, catalogue, shopping and CSS over LAN HTTP and certificate-validated Tailscale HTTPS. Once healthy, `MENU_IMAGE` is updated atomically so the existing start command uses the same image.

The unattended migration gate allows atomic migrations that only add nullable scalar columns without defaults, uniqueness or indexes. It rehearses a supported plan on a disposable copy of the verified snapshot, then checks the plan again during application. Pending data migrations, destructive schema changes, unknown history and other operations require a separate owner-approved update. In particular, if `0012_pizza_category` is pending, use the [Pizza migration procedure](../README.md#updates) before adopting this workflow.

`./deploy.sh --latest` prints the latest attempt's JSON Lines events. The run directory contains the test and Docker verification logs, timestamped events, previous image reference and content ID, previous image archive, saved Compose file and environment, and the verified paired data under `snapshot/data`. A run that stops early may contain only some of these files. Keep run directories private and retain good backups off-host. Review retention and available disk space as part of routine maintenance.

A failed GitHub push leaves a successful deployment running and logs `sync_pending` with the commit and destination. Once access is restored, the owner can retry `git push <remote> <commit>:<target>` from that log. If the upstream has diverged, reconcile it through the normal Git workflow. Deployments never fetch or merge incoming changes.

## Failure and recovery

- Before cutover, a failed gate leaves the running service in place. Read the last event and the relevant synthetic verification log.
- If cutover fails before a live migration attempt, the command restarts or recreates the previous container by image ID and checks both endpoints. It keeps production data in place.
- After a live migration attempt, a failed cutover stops the service for manual recovery. The command leaves the database and photographs in place. An interrupted cutover or unsuccessful rollback leaves `recovery-required` in the deployment directory and blocks subsequent deployments. Read the run named by that file and inspect the service before deciding what to recover. After an abrupt interruption, confirm no maintenance container with the label `menu-familiar.deployment=<run-directory-name>` is still running before working on the data.
- For database recovery, use the [paired-data restore procedure](V2.0.0-RELEASE.md#recovery) with the interrupted run's `snapshot/data`. That historical procedure expects a release tag and different filenames. Use `production.env`, `compose.yaml`, the second line of `image.txt` as the matching image ID, and `previous-image.tar` if the image must be loaded. Restore the snapshot to a new sibling directory, set ownership to UID/GID `10001`, and verify migration status and the paired media with that image before starting it. Preserve the displaced production directory and all SQLite sidecars together. After verifying the recovered image and both endpoints, the owner can archive the `recovery-required` marker.
- Recovery to a point-in-time backup excludes edits made after the snapshot. A failed migration may have committed changes even if a later migration failed. Restarting a previous image alone leaves those database changes in place.

The host probes confirm reachable endpoints from the Home Server. Keep the existing [trusted and untrusted device checks](V2.0.1-RELEASE.md) for LAN and tailnet access control. Full workflow tests use disposable repositories, synthetic SQLite data and failure injection for Docker operations. Run them with `.venv/bin/python -m unittest discover -s scripts/tests -v`.
