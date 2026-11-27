# ImRabo Sub-Agents

Public, versioned catalog of declarative specialist-agent manifests for ImRabo.

## Contract

- `registry.json` is the catalog index. Each item has a stable ID, semantic version and repository-relative manifest path.
- `agents/<id>/agent.json` contains identity, instructions, capabilities, connector/builtin dependencies, configuration metadata, execution limits and compatibility.
- Manifests are data, not executable plugins. No scripts, source code, dynamic imports, shell commands, or arbitrary runtime expressions are permitted.
- The app validates the manifest, checks required connector and builtin dependencies, then imports it into the local Sub-Agent registry. Optional dependencies are surfaced as optional capabilities.
- Credentials are never stored in agent manifests. Connector credentials are managed by the Connectors system.

## Install lifecycle

1. Fetch and validate the registry and selected manifest.
2. Verify manifest ID matches the catalog entry and enforce size/version limits.
3. Check required connector IDs against installed/enabled connectors and builtin names against the app's builtin catalogue.
4. Show detail, dependencies, requested capabilities, permissions and documentation before installation.
5. On install, map the manifest into the supported local sub-agent model. Preserve source catalog ID/version in app-owned metadata when available.
6. Re-check dependencies at execution time; a previously installed dependency can become unavailable.
7. Support enable, disable, update and uninstall without deleting user-created agents that happen to share similar names.

## Publish

Add a manifest under `agents/<id>/agent.json`, register it in `registry.json`, validate against `agent.schema.json`, document purpose and dependencies, and open a pull request. Keep IDs stable. Increment the version for every published change.

## Validate locally

Run `python scripts/validate_registry.py`. GitHub Actions runs the same validator for pull requests and pushes to `main`.

## Security

Treat all remote metadata as untrusted. Validate URLs and repository-relative paths; impose response size/time limits; never execute manifest content; restrict tool access to declared, installed capabilities; and require explicit user consent for side-effecting actions. Required dependencies must be installed and enabled before execution. Do not request broad permissions when a narrow capability is sufficient.

## Current catalog

- Research Agent — optional Brave Search connector dependency.
- Code Reviewer — no external connector dependency.
- Writing Editor — no external connector dependency.
