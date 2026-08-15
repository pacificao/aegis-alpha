# Ubuntu Development Setup

The 2026-08-14 inspection found Git 2.43, GitHub CLI 2.45, and Python 3.12. Docker, Compose, Node/npm, Nginx, Make, and GCC were not found. Runtime Nginx/Node/build tools are containerized, so only Docker Engine plus Compose is mandatory on the host.

Installation requires sudo and must be performed by the operator. Use Docker's current official Ubuntu repository instructions, not an unreviewed convenience script. After repository setup, install `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`, add only the intended operator to the `docker` group if the root-equivalent risk is accepted, log out/in, and verify:

```bash
docker version
docker compose version
docker run --rm hello-world
```

The GitHub remote already exists and `gh` is authenticated. Recommended workflow: branch `feature/<topic>` from `develop`, PR to `develop`, then reviewed release PR to protected `main`. Configure GitHub branch protection to require CI and review; repository policy is an external GitHub setting and cannot be guaranteed solely by files.
