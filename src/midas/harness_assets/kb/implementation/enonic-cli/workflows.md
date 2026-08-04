# Enonic CLI Workflows

> Multi-step recipes for common operations. All commands use `-f` for non-interactive execution.

> **XP 7 note:** CLI 4.x defaults to the XP 8 API format. When the target instance runs XP 7, add `--compat 7` to the `snapshot
> create/restore` and `dump create/load` commands below (and `--archive` only works alongside `--compat 7`).

## New Project Setup

Create a project, link it to a sandbox, and start development:

```bash
enonic sandbox create my-sandbox -v 7.14.4 -f
enonic project create my-app -s my-sandbox -f
cd my-app
enonic dev
```

## Content Export and Import

Export content from one instance and import to another:

```bash
# Export from source (local sandbox or remote instance)
enonic export -t my-export --path cms-repo:draft:/content/my-site -a su:password -f

# Import to target instance
enonic import -t my-export --path cms-repo:draft:/content/my-site \
  -a su:password -f
```

Export files are stored in `$XP_HOME/data/export/<export-name>/`.

## Backup and Restore (Dump)

Full system backup and restore:

```bash
# Create dump (all repos)
enonic dump create -d pre-upgrade-backup --skip-versions -a su:password -f

# Restore from dump (replaces all existing repos)
enonic dump load -d pre-upgrade-backup -a su:password -f
```

## Snapshot Workflow

Create a snapshot before risky operations, restore if something goes wrong:

```bash
# Snapshot before changes
enonic snapshot create -a su:password -f

# ... perform risky operations ...

# If something went wrong, list snapshots and restore
enonic snapshot ls -a su:password -f
enonic snapshot restore --snap <snapshot-name> -a su:password -f
```

## Version Upgrade

Upgrade XP version using dump/load:

```bash
# 1. Dump from current version
enonic dump create -d upgrade-dump --skip-versions -a su:password -f

# 2. Upgrade sandbox to new version
enonic sandbox upgrade my-sandbox -v 7.15.0 -f

# 3. Start upgraded sandbox and load dump with --upgrade flag
enonic sandbox start my-sandbox -d -f
enonic dump load -d upgrade-dump --upgrade -a su:password -f
```

## CI/CD Deployment

Build and deploy to a remote XP instance in a pipeline:

```bash
export ENONIC_CLI_REMOTE_URL="production.example.com:4848"
export ENONIC_CLI_CRED_FILE="/secrets/sa-key.json"

enonic project build -f
enonic project install -f
```

## Cloud Deployment

Build locally and deploy to Enonic Cloud:

```bash
# Login (interactive — opens browser)
enonic cloud login

# Build and install to cloud
enonic project build -f
enonic cloud app install -y
```

**Note:** `enonic cloud login` is the only command that requires user interaction (browser-based OAuth). It cannot be automated with `-f`.

## Reindex After Schema Changes

After modifying content types or index configurations:

```bash
enonic repo reindex -r cms-repo -b draft,master -i -a su:password -f
```

The `-i` flag recreates index data from scratch (delete + reindex).

## Maintenance

Vacuum old versions and clean up audit logs:

```bash
# Vacuum versions older than 30 days and unused blobs
enonic vacuum -b -t P30D -a su:password -f

# Clean audit log entries older than 90 days
enonic auditlog cleanup --age P90D -a su:password -f
```
