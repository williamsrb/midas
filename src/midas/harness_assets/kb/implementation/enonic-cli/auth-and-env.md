# Authentication & Environment

> Auth methods, environment variables, and port reference for the Enonic CLI.

## Authentication Methods

### 1. Basic Auth (deprecated for XP 7.15+)

```bash
enonic dump create -d my-dump -a su:password -f
```

Pass `user:password` via `--auth` / `-a`. Works with all XP versions but is deprecated in favor of service account keys starting from XP
7.15.

### 2. Service Account Key File (XP 7.15+)

```bash
enonic dump create -d my-dump --cred-file /path/to/sa-key.json -f
```

JSON key file generated in XP Admin Console under _System → Service Accounts_. Preferred method for CI/CD.

### 3. Mutual TLS (mTLS)

```bash
enonic dump create -d my-dump \
  --client-cert /path/to/cert.pem \
  --client-key /path/to/key.pem -f
```

Both `--client-cert` and `--client-key` must be provided together. Used for zero-trust environments.

## Auth Precedence

When multiple methods are configured, CLI resolves in this order:

1. Command-line flags (`--auth`, `--cred-file`, `--client-cert`+`--client-key`)
2. Environment variables (`ENONIC_CLI_REMOTE_USER`+`ENONIC_CLI_REMOTE_PASS`, `ENONIC_CLI_CRED_FILE`, etc.)
3. Fallback: no authentication (only works for local unsecured instances)

Flags always override environment variables.

## Environment Variables

| Variable                 | Description                         | Default          |
|--------------------------|-------------------------------------|------------------|
| `ENONIC_CLI_REMOTE_URL`  | Management API endpoint             | `localhost:4848` |
| `ENONIC_CLI_REMOTE_USER` | Basic auth username                 | —                |
| `ENONIC_CLI_REMOTE_PASS` | Basic auth password                 | —                |
| `ENONIC_CLI_CRED_FILE`   | Path to service account key (JSON)  | —                |
| `ENONIC_CLI_CLIENT_KEY`  | Path to private key for mTLS        | —                |
| `ENONIC_CLI_CLIENT_CERT` | Path to client certificate for mTLS | —                |
| `ENONIC_CLI_HTTP_PROXY`  | HTTP proxy server URL               | —                |
| `ENONIC_CLI_HOME_PATH`   | Custom CLI home directory           | `~/.enonic`      |

### CI/CD Best Practice

Prefer environment variables over flags in CI/CD pipelines to avoid leaking credentials in process listings:

```bash
export ENONIC_CLI_REMOTE_URL="myserver:4848"
export ENONIC_CLI_CRED_FILE="/secrets/sa-key.json"
enonic dump create -d nightly-backup -f
```

## Ports

| Port | Protocol | Service           | Notes                            |
|------|----------|-------------------|----------------------------------|
| 8080 | HTTP     | Web / Content API | Application and content serving  |
| 4848 | HTTP     | Management API    | CLI connects here (not 8080)     |
| 2609 | HTTP     | Info API          | `enonic system info` uses this   |
| 5005 | TCP      | Debug             | Java debug port (`--debug` flag) |

**Critical:** The CLI management API port is **4848**, not 8080. The `ENONIC_CLI_REMOTE_URL` default is `localhost:4848`. When specifying a
remote instance, always use the management port.
