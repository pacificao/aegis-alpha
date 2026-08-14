# ADR: Host PAM authentication

Status: implementation blocked on reviewed host installation.

Nathan requested authentication with the existing Ubuntu account password without copying or storing it. Mounting `/etc/shadow`, the host PAM stack, or a Docker socket into the web container would give an internet-facing process excessive host privilege and is rejected. Environment passwords, duplicate hashes, and hard-coded credentials are also rejected.

The chosen design is a minimal root-owned host service listening on `/run/aegis-auth/pam.sock`. It accepts only username `nathan` plus a transient password over a Unix socket, invokes PAM service `aegis-alpha`, returns success/failure, zeroes request buffers where practical, logs no credentials, rate-limits, and exposes no network port. The backend receives socket access through a narrowly scoped group and read-write bind mount. Until the bridge is reviewed, installed, and started by Nathan using sudo, login fails closed with HTTP 503. The repository contains the unprivileged caller contract, but deliberately does not install or launch a privileged authenticator automatically.

Required follow-up: security-review and implement the small host helper and systemd unit, then have Nathan manually install them. Do not replace this decision with a weaker credential store.

