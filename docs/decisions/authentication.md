# ADR: Host PAM authentication

Status: implemented, operator-installed, and manually validated.

The operator requested authentication with an existing Ubuntu account password without copying or storing it. Mounting `/etc/shadow`, the host PAM stack, or a Docker socket into the web container would give an internet-facing process excessive host privilege and is rejected. Environment passwords, duplicate hashes, and hard-coded credentials are also rejected.

The chosen design is a minimal root-owned host service listening on `/run/aegis-auth/pam.sock`. It accepts only the operator named in the root-only `/etc/aegis/auth-bridge.env` plus a transient password over a Unix socket, invokes PAM service `aegis-alpha`, returns success/failure, zeroes request buffers where practical, logs no credentials, rate-limits, and exposes no network port. Linux `SO_PEERCRED` checks restrict requests to the backend container's fixed UID 100/GID 101; the socket is root-owned, group 101, and mode 0660. The backend receives socket access through its bind mount. Until the bridge is installed by the operator using sudo, login fails closed with HTTP 503.

Implementation lives under `infra/auth/`; `scripts/install-pam-bridge.sh` installs the root-owned helper, dedicated PAM policy, and hardened systemd unit. The operator reviews and executes the privileged installation. Do not replace this decision with a weaker credential store.
