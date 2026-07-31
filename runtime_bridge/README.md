# UMML Runtime Bridge core

This crate is deliberately **not an injector**. It is the small, memory-safe client core an eventual Hachimi-compatible or other in-game adapter can call.

Current guarantees:

- no `unsafe` Rust
- loopback connections only
- token-authenticated protocol
- explicit game-build handshake
- unknown builds expose zero hot-reload features
- profile changes are queued for desktop application after the game closes
- a feature reload is only sent after the manager explicitly advertises that feature for the exact build

Injection/bootstrap, Unity hooks, IL2CPP bindings, and graphics overlay code remain outside this crate. They should be separate adapters so a broken adapter can be disabled without risking the desktop manager or its mod library.
