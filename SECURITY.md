# Security and privacy

This is an application routing utility, not a kill switch or a security isolation boundary. Unmatched traffic is direct. DNS uses configured upstream resolvers and is not guaranteed to use each application's selected node. UDP/QUIC/IPv6 compatibility needs additional testing.

Local `data/` files contain plaintext node credentials. Logs may contain network targets and local paths. Do not attach raw settings, subscriptions, runtime YAML, logs or live connection screenshots to public issues. Use redacted examples with example.com and dummy credentials.

The Git repository excludes user data, build output, vendored dependencies and local shortcuts. Releases must be assembled from a clean checkout, never by zipping a working installation. Local loopback proxy ports are not authenticated app identities.

Please report reproducible issues without secrets. If GitHub private vulnerability reporting is enabled, use it for sensitive reports; otherwise avoid publishing exploitable details or credentials in public issues.
