# Optional runtime bridge

The runtime work is stacked on top of UMML Manager and remains optional.

## Boundary

The desktop manager owns downloads, archives, profiles, load order, backups, and disk deployment. The in-game adapter may only request status, queue a profile for restart, or invoke a specifically allowlisted hot-reload feature.

Unknown game builds fail closed: the handshake succeeds in disabled mode with an empty feature list. No hook should be installed until the adapter has received a non-empty allowlist for the exact build fingerprint.

## Initial feature policy

- `status`: safe when a compatible adapter is present
- `queue_profile`: always queues; never writes game files from inside the process
- `texture_reload`: experimental and build-gated
- translation reload: reserved for an adapter that can prove a safe reload path
- model, database, account, save, and network modification: prohibited

The Rust crate is a protocol client, not an injector. A future Hachimi-derived adapter can depend on it without merging native hook code into UMML Manager.
