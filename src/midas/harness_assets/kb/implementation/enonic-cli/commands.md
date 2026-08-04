# Enonic CLI — Full Command Reference

> Exhaustive flag tables for every command. Loaded on demand from `SKILL.md`.

## Standard Auth Flags

These flags apply to all **remote** commands (commands that talk to a running XP instance).

| Flag            | Short | Description                                                 | Default |
|-----------------|-------|-------------------------------------------------------------|---------|
| `--auth`        | `-a`  | Basic auth `user:password` (deprecated for XP 7.15+)        | —       |
| `--cred-file`   | —     | Service account key file (JSON, XP 7.15+)                   | —       |
| `--client-key`  | —     | Private key for mTLS (must pair with `--client-cert`)       | —       |
| `--client-cert` | —     | Client certificate for mTLS (must pair with `--client-key`) | —       |

---

## Compatibility Mode (`--compat`)

CLI 4.x talks to the **XP 8** management API by default. Four data commands accept a `--compat` flag to target a legacy **XP 7** instance:
`snapshot create`, `snapshot restore`, `dump create`, `dump load`.

| Flag       | Values                          | Effect                                                            |
|------------|---------------------------------|-------------------------------------------------------------------|
| `--compat` | `7` (or any value starting `7`) | Use the legacy XP 7 API format. Omit for the default XP 8 format. |

The `--archive` flag on `dump create` / `dump load` is **only effective in compat mode** (XP 7).

---

## Project Commands

### enonic project create

Create a new Enonic project from a starter.

```
enonic project create [name] [flags]
```

| Flag            | Short            | Description                                            | Default                   |
|-----------------|------------------|--------------------------------------------------------|---------------------------|
| `--repository`  | `-r` OR `--repo` | Starter repo (`<enonic>`, `<org>/<repo>`, or full URL) | —                         |
| `--branch`      | `-b`             | Branch to checkout                                     | `master`                  |
| `--checkout`    | `-c`             | Commit hash to checkout (excludes `--branch`)          | —                         |
| `--destination` | `-d` OR `--dest` | Destination path                                       | last word of project name |
| `--version`     | `-v` OR `--ver`  | Version number                                         | `1.0.0-SNAPSHOT`          |
| `--name`        | `-n`             | Application name (overrides positional arg)            | —                         |
| `--sandbox`     | `-s` OR `--sb`   | Link to existing sandbox                               | —                         |
| `--prod`        | —                | Run XP in non-development mode                         | `false`                   |
| `--skip-start`  | —                | Don't start sandbox after creation                     | `false`                   |
| `--force`       | `-f`             | Non-interactive mode                                   | `false`                   |

### enonic project sandbox

Set or change the project's default sandbox. Aliases: `sbox`, `sb`.

```
enonic project sandbox [name] [-f]
```

| Flag      | Short | Description          | Default |
|-----------|-------|----------------------|---------|
| `--force` | `-f`  | Non-interactive mode | `false` |

### enonic project build

Build project via Gradle.

```
enonic project build [-f]
```

| Flag      | Short | Description                             | Default |
|-----------|-------|-----------------------------------------|---------|
| `--force` | `-f`  | Non-interactive mode (uses system Java) | `false` |

### enonic project clean

Clean build artifacts (alias for `gradlew clean`).

```
enonic project clean [-f]
```

| Flag      | Short | Description          | Default |
|-----------|-------|----------------------|---------|
| `--force` | `-f`  | Non-interactive mode | `false` |

### enonic project test

Run tests via Gradle.

```
enonic project test [-f]
```

| Flag      | Short | Description          | Default |
|-----------|-------|----------------------|---------|
| `--force` | `-f`  | Non-interactive mode | `false` |

### enonic project deploy

Build and deploy project to associated sandbox.

```
enonic project deploy [sandbox-name] [flags]
```

| Flag           | Short | Description                              | Default |
|----------------|-------|------------------------------------------|---------|
| `--prod`       | —     | Non-development mode                     | `false` |
| `--debug`      | —     | Enable debug on port 5005                | `false` |
| `--continuous` | `-c`  | Watch for changes, redeploy continuously | `false` |
| `--skip-start` | —     | Don't start sandbox                      | `false` |
| `--force`      | `-f`  | Non-interactive mode                     | `false` |

### enonic project install

Build and install project to a running XP instance via management API. Alias: `i`.

```
enonic project install [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

### enonic project shell

Open shell with project's `JAVA_HOME` and `XP_HOME` set.

```
enonic project shell
```

No additional flags. Exit with `quit`.

### enonic project gradle

Run arbitrary Gradle tasks with project context.

```
enonic project gradle [tasks / flags ...]
```

Everything after `gradle` is forwarded to `gradlew`.

### enonic project env

Export `JAVA_HOME` and `XP_HOME` for the current shell.

```
eval $(enonic project env)
```

Not available on Windows.

---

## Sandbox Commands

### enonic sandbox create

Create a new local XP sandbox.

```
enonic sandbox create [name] [flags]
```

| Flag              | Short | Description                                             | Default       |
|-------------------|-------|---------------------------------------------------------|---------------|
| `--template`      | `-t`  | Use specific template                                   | —             |
| `--skip-template` | —     | Don't use a template                                    | `false`       |
| `--version`       | `-v`  | XP distribution version                                 | latest stable |
| `--image`         | `-i`  | Use specific Docker image (e.g. `enonic/xp:7.13.4-sdk`) | —             |
| `--all`           | —     | List all distro versions                                | `false`       |
| `--prod`          | —     | Non-development mode                                    | `false`       |
| `--skip-start`    | —     | Don't start after creation                              | `false`       |
| `--force`         | `-f`  | Non-interactive mode                                    | `false`       |

### enonic sandbox list

List all sandboxes. Alias: `enonic sandbox ls`.

```
enonic sandbox list
```

No additional flags. Running sandbox is marked with `*`.

### enonic sandbox start

Start a sandbox (only one can run at a time).

```
enonic sandbox start [name] [flags]
```

| Flag          | Short | Description               | Default |
|---------------|-------|---------------------------|---------|
| `--prod`      | —     | Non-development mode      | `false` |
| `--debug`     | —     | Enable debug on port 5005 | `false` |
| `--detach`    | `-d`  | Run in background         | `false` |
| `--http.port` | —     | Custom HTTP port          | `8080`  |
| `--force`     | `-f`  | Non-interactive mode      | `false` |

### enonic sandbox stop

Stop the running sandbox.

```
enonic sandbox stop
```

No additional flags.

### enonic sandbox upgrade

Upgrade sandbox XP distribution version. Downgrades are not allowed. Alias: `up`.

```
enonic sandbox upgrade [name] [flags]
```

| Flag        | Short | Description                                           | Default |
|-------------|-------|-------------------------------------------------------|---------|
| `--version` | `-v`  | Target distribution version                           | —       |
| `--image`   | `-i`  | New Docker image to use (e.g. `enonic/xp:7.13.4-sdk`) | —       |
| `--all`     | `-a`  | List all distro versions                              | `false` |
| `--force`   | `-f`  | Non-interactive mode                                  | `false` |

### enonic sandbox delete

Delete sandbox and all its data. Aliases: `del`, `rm`.

```
enonic sandbox delete [name] [-f]
```

| Flag      | Short | Description          | Default |
|-----------|-------|----------------------|---------|
| `--force` | `-f`  | Non-interactive mode | `false` |

### enonic sandbox copy

Clone an existing sandbox to a new one. Alias: `cp`.

```
enonic sandbox copy [source] [target] [-f]
```

| Flag      | Short | Description          | Default |
|-----------|-------|----------------------|---------|
| `--force` | `-f`  | Non-interactive mode | `false` |

---

## Snapshot Commands

### enonic snapshot create

Create a snapshot of one or all repositories.

```
enonic snapshot create [flags]
```

| Flag                  | Short | Description                                    | Default |
|-----------------------|-------|------------------------------------------------|---------|
| `--repo`              | `-r`  | Repository name (omit for all)                 | —       |
| `--compat`            | —     | XP version compat mode (`7` = legacy XP 7 API) | XP 8    |
| + Standard auth flags |       |                                                |         |
| `--force`             | `-f`  | Non-interactive mode                           | `false` |

### enonic snapshot list

List all snapshots. Alias: `enonic snapshot ls`.

```
enonic snapshot ls [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

### enonic snapshot restore

Restore a snapshot.

```
enonic snapshot restore [flags]
```

| Flag                  | Short    | Description                                          | Default |
|-----------------------|----------|------------------------------------------------------|---------|
| `--snapshot`          | `--snap` | Snapshot name                                        | —       |
| `--repo`              | `-r`     | Target repository                                    | —       |
| `--latest`            | —        | Use latest snapshot (takes precedence over `--snap`) | `false` |
| `--clean`             | —        | Delete indices before restoring                      | `false` |
| `--compat`            | —        | XP version compat mode (`7` = legacy XP 7 API)       | XP 8    |
| + Standard auth flags |          |                                                      |         |
| `--force`             | `-f`     | Non-interactive mode                                 | `false` |

### enonic snapshot delete

Delete snapshots by name or date. Alias: `del`.

```
enonic snapshot delete [flags]
```

| Flag                  | Short    | Description                             | Default |
|-----------------------|----------|-----------------------------------------|---------|
| `--snapshot`          | `--snap` | Snapshot name                           | —       |
| `--before`            | `-b`     | Delete before date (format: `2 Jan 06`) | —       |
| + Standard auth flags |          |                                         |         |
| `--force`             | `-f`     | Non-interactive mode                    | `false` |

---

## Dump Commands

### enonic dump create

Export all repositories to a dump.

```
enonic dump create [flags]
```

| Flag                  | Short | Description                                      | Default |
|-----------------------|-------|--------------------------------------------------|---------|
| `-d`                  | —     | Dump name                                        | —       |
| `--skip-versions`     | —     | Don't include version history                    | `false` |
| `--max-version-age`   | —     | Max age of versions in days                      | —       |
| `--max-versions`      | —     | Max number of versions per node                  | —       |
| `--archive`           | —     | Create as ZIP archive (only in compat/XP 7 mode) | `false` |
| `--compat`            | —     | XP version compat mode (`7` = legacy XP 7 API)   | XP 8    |
| + Standard auth flags |       |                                                  |         |
| `--force`             | `-f`  | Non-interactive mode                             | `false` |

### enonic dump upgrade

Upgrade dump format for newer XP version. Alias: `up`.

```
enonic dump upgrade [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| `-d`                  | —     | Dump name            | —       |
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

Output name: `<dump-name>_upgraded_<version>`.

### enonic dump list

List all dumps. Alias: `enonic dump ls`.

```
enonic dump ls [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

### enonic dump load

Import a dump. Deletes existing repos before loading.

```
enonic dump load [flags]
```

| Flag                  | Short | Description                                      | Default |
|-----------------------|-------|--------------------------------------------------|---------|
| `-d`                  | —     | Dump name                                        | —       |
| `--upgrade`           | —     | Automatically upgrade dump before loading        | `false` |
| `--archive`           | —     | Load from ZIP archive (only in compat/XP 7 mode) | `false` |
| `--compat`            | —     | XP version compat mode (`7` = legacy XP 7 API)   | XP 8    |
| + Standard auth flags |       |                                                  |         |
| `--force`             | `-f`  | Non-interactive mode                             | `false` |

---

## Export / Import

### enonic export

Export repository branch data to the exports directory.

```
enonic export [flags]
```

| Flag                  | Short | Description                           | Default |
|-----------------------|-------|---------------------------------------|---------|
| `-t`                  | —     | Export name                           | —       |
| `--path`              | —     | Source path (`repo:branch:path`)      | —       |
| `--skip-ids`          | —     | Don't export node IDs                 | `false` |
| `--skip-versions`     | —     | Don't export version history          | `false` |
| `--dry`               | —     | Dry run — show what would be exported | `false` |
| + Standard auth flags |       |                                       |         |
| `--force`             | `-f`  | Non-interactive mode                  | `false` |

### enonic import

Import data from the exports directory.

```
enonic import [flags]
```

| Flag                  | Short | Description                      | Default |
|-----------------------|-------|----------------------------------|---------|
| `-t`                  | —     | Export name to import from       | —       |
| `--path`              | —     | Target path (`repo:branch:path`) | —       |
| `--xsl-source`        | —     | XSL transformation file          | —       |
| `--xsl-param`         | —     | XSL parameters (`key=value`)     | —       |
| `--skip-ids`          | —     | Generate new node IDs            | `false` |
| `--skip-permissions`  | —     | Use target node permissions      | `false` |
| `--dry`               | —     | Dry run                          | `false` |
| + Standard auth flags |       |                                  |         |
| `--force`             | `-f`  | Non-interactive mode             | `false` |

---

## App Commands

### enonic app install

Install an application on all cluster nodes. Alias: `i`.

```
enonic app install [flags]
```

| Flag                  | Short | Description                                       | Default |
|-----------------------|-------|---------------------------------------------------|---------|
| `--url`               | —     | URL to application JAR                            | —       |
| `--file`              | —     | Local path to JAR (takes precedence over `--url`) | —       |
| + Standard auth flags |       |                                                   |         |
| `--force`             | `-f`  | Non-interactive mode                              | `false` |

### enonic app start

Start an installed application.

```
enonic app start <app-key> [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

### enonic app stop

Stop a running application.

```
enonic app stop <app-key> [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

---

## Repository Commands

### enonic repo reindex

Rebuild search indices for a repository.

```
enonic repo reindex [flags]
```

| Flag                  | Short | Description                            | Default |
|-----------------------|-------|----------------------------------------|---------|
| `-b`                  | —     | Comma-separated branch list            | —       |
| `-r`                  | —     | Repository name                        | —       |
| `-i`                  | —     | Recreate index data (delete + reindex) | `false` |
| + Standard auth flags |       |                                        |         |
| `--force`             | `-f`  | Non-interactive mode                   | `false` |

### enonic repo readonly

Toggle read-only mode.

```
enonic repo readonly <true|false> [flags]
```

| Flag                  | Short | Description                            | Default |
|-----------------------|-------|----------------------------------------|---------|
| `-r`                  | —     | Single repository (omit for all repos) | —       |
| + Standard auth flags |       |                                        |         |
| `--force`             | `-f`  | Non-interactive mode                   | `false` |

### enonic repo replicas

Set number of replicas for the cluster.

```
enonic repo replicas <1-99> [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

### enonic repo list

List all repositories. Alias: `enonic repo ls`.

```
enonic repo list [flags]
```

| Flag                  | Short | Description          | Default |
|-----------------------|-------|----------------------|---------|
| + Standard auth flags |       |                      |         |
| `--force`             | `-f`  | Non-interactive mode | `false` |

---

## CMS Commands

### enonic cms reprocess

Reprocess content metadata (typically after migration).

```
enonic cms reprocess [flags]
```

| Flag                  | Short | Description                  | Default |
|-----------------------|-------|------------------------------|---------|
| `--path`              | —     | Content path (`branch:path`) | —       |
| `--skip-children`     | —     | Don't process descendants    | `false` |
| + Standard auth flags |       |                              |         |
| `--force`             | `-f`  | Non-interactive mode         | `false` |

---

## System Commands

### enonic system info

Show XP instance info (version, mode, build hash, branch, timestamp). Alias: `i`.

```
enonic system info [flags]
```

Accepts `--force` and the standard auth flags. Earlier CLI versions required no auth (info port 2609); 4.0.0 added the auth flags — pass
them if the management API is secured.

---

## Audit Log Commands

### enonic auditlog cleanup

Remove audit log records older than threshold.

```
enonic auditlog cleanup [flags]
```

| Flag                  | Short | Description                           | Default |
|-----------------------|-------|---------------------------------------|---------|
| `--age`               | —     | ISO-8601 duration (`P30D`, `P1DT12H`) | —       |
| + Standard auth flags |       |                                       |         |
| `--force`             | `-f`  | Non-interactive mode                  | `false` |

---

## Vacuum

### enonic vacuum

Purge old node versions and optionally unused blobs.

```
enonic vacuum [flags]
```

| Flag                  | Short | Description                       | Default          |
|-----------------------|-------|-----------------------------------|------------------|
| `--blob`              | `-b`  | Also remove unused binary blobs   | `false`          |
| `--threshold`         | `-t`  | Age threshold (ISO-8601 duration) | `P21D` (21 days) |
| + Standard auth flags |       |                                   |                  |
| `--force`             | `-f`  | Non-interactive mode              | `false`          |

---

## Cloud Commands

### enonic cloud login

Login to Enonic Cloud via browser-based OAuth.

```
enonic cloud login [--qr]
```

| Flag   | Short | Description                     | Default |
|--------|-------|---------------------------------|---------|
| `--qr` | —     | Display QR code for mobile auth | `false` |

**Note:** This is interactive (browser-based). `-f` does not apply.

### enonic cloud logout

Log out from Enonic Cloud.

```
enonic cloud logout
```

No additional flags.

### enonic cloud app install

Install project JAR to Enonic Cloud.

```
enonic cloud app install [flags]
```

| Flag | Short | Description               | Default              |
|------|-------|---------------------------|----------------------|
| `-j` | —     | JAR file path             | `./build/libs/*.jar` |
| `-t` | —     | Upload timeout in seconds | `300`                |
| `-y` | —     | Skip confirmation prompt  | `false`              |

---

## Global Commands

### enonic create

Simplified project creation with defaults.

```
enonic create [project-name] [flags]
```

| Flag           | Short            | Description          | Default |
|----------------|------------------|----------------------|---------|
| `--repository` | `-r` OR `--repo` | Starter repo path    | —       |
| `--sandbox`    | `-s` OR `--sb`   | Link to sandbox      | —       |
| `--prod`       | —                | Non-development mode | `false` |
| `--skip-start` | —                | Don't start sandbox  | `false` |
| `--force`      | `-f`             | Non-interactive mode | `false` |

### enonic dev

Start hot-reload development mode. Alias for `enonic project dev`.

```
enonic dev [-f]
```

Starts sandbox in detached mode, deploys app, watches for changes. Exit with Ctrl-C.

### enonic latest

Show the latest available CLI version.

```
enonic latest [flags]
```

Accepts `--force` and the standard auth flags, though it only checks the CLI version.

### enonic upgrade

Upgrade CLI to the latest version.

```
enonic upgrade
```

### enonic uninstall

Remove CLI from the system.

```
enonic uninstall
```
