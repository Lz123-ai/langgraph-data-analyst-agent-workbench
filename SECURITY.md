# Security Policy

The supported default is a trusted local user on loopback. Do not expose the development server directly to the internet.

For shared environments, set `API_ACCESS_TOKEN`, terminate TLS at a reverse proxy, apply container CPU/memory limits, and use an external identity layer for user-level authorization.

Report vulnerabilities through a private GitHub security advisory with reproduction steps, affected version, and impact. Never attach credentials or sensitive datasets.
