#!/usr/bin/env python3
"""Validate the ImRabo declarative sub-agent catalog without third-party packages."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
ALLOWED_TOP_LEVEL = {
    "schema_version", "id", "name", "description", "version", "type",
    "instructions", "llm", "capabilities", "dependencies", "memory",
    "execution", "permissions", "configuration", "compatibility",
    "documentation",
}
FORBIDDEN_KEYS = {
    "script", "shell", "command", "executable", "entrypoint",
    "runtime_code", "source_code", "javascript", "python_code",
}


def fail(message):
    raise ValueError(message)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")


def validate_dependencies(manifest, agent_id):
    dependencies = manifest.get("dependencies", {})
    if not isinstance(dependencies, dict):
        fail(f"{agent_id}: dependencies must be an object")
    if set(dependencies) - {"connectors", "builtin"}:
        fail(f"{agent_id}: unsupported dependency field")
    connectors = dependencies.get("connectors", [])
    builtins = dependencies.get("builtin", [])
    if not isinstance(connectors, list) or not isinstance(builtins, list):
        fail(f"{agent_id}: dependencies.connectors and builtin must be arrays")
    seen = set()
    for item in connectors:
        if not isinstance(item, dict) or not ID_RE.fullmatch(str(item.get("id", ""))):
            fail(f"{agent_id}: connector dependency requires a valid id")
        if set(item) - {"id", "required", "reason"}:
            fail(f"{agent_id}: connector dependency has unsupported fields")
        if "required" in item and not isinstance(item["required"], bool):
            fail(f"{agent_id}: connector dependency required must be boolean")
        if item["id"] in seen:
            fail(f"{agent_id}: duplicate connector dependency {item['id']}")
        seen.add(item["id"])
    for name in builtins:
        if not isinstance(name, str) or not ID_RE.fullmatch(name):
            fail(f"{agent_id}: builtin dependency names must be stable lowercase IDs")


def walk_forbidden(value, agent_id, location="manifest"):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                fail(f"{agent_id}: executable content field is not allowed: {location}.{key}")
            walk_forbidden(child, agent_id, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_forbidden(child, agent_id, f"{location}[{index}]")


def validate_manifest(entry):
    agent_id = entry.get("id")
    rel = entry.get("manifest")
    if not isinstance(rel, str) or not rel:
        fail(f"{agent_id}: registry entry is missing manifest path")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or "\\" in rel:
        fail(f"{agent_id}: unsafe manifest path")
    target = (ROOT / path).resolve()
    if ROOT.resolve() not in target.parents or not target.is_file():
        fail(f"{agent_id}: manifest file does not exist inside repository")
    manifest = read_json(target)
    if set(manifest) - ALLOWED_TOP_LEVEL:
        fail(f"{agent_id}: unsupported manifest fields: {sorted(set(manifest) - ALLOWED_TOP_LEVEL)}")
    walk_forbidden(manifest, agent_id)
    if manifest.get("schema_version") != 1 or manifest.get("type") != "sub-agent":
        fail(f"{agent_id}: unsupported manifest schema or type")
    if manifest.get("id") != agent_id:
        fail(f"{agent_id}: registry/manifest ID mismatch")
    if manifest.get("version") != entry.get("version") or not VERSION_RE.fullmatch(str(manifest.get("version", ""))):
        fail(f"{agent_id}: registry/manifest version mismatch or invalid version")
    for field in ("name", "description", "instructions"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            fail(f"{agent_id}: {field} must be a non-empty string")
    if len(manifest["instructions"]) > 20000:
        fail(f"{agent_id}: instructions exceed 20000 characters")
    llm = manifest.get("llm", {"mode": "inherit"})
    if llm.get("mode", "inherit") != "inherit":
        fail(f"{agent_id}: schema v1 currently supports inherited LLM configuration only")
    memory = manifest.get("memory", {"mode": "hybrid"})
    if memory.get("mode", "hybrid") not in {"shared", "isolated", "hybrid"}:
        fail(f"{agent_id}: invalid memory mode")
    execution = manifest.get("execution", {})
    iterations = execution.get("max_iterations", 5)
    timeout = execution.get("timeout_seconds", 120)
    depth = execution.get("max_delegation_depth", 0)
    if not isinstance(iterations, int) or not 1 <= iterations <= 12:
        fail(f"{agent_id}: max_iterations must be in 1..12")
    if not isinstance(timeout, int) or not 5 <= timeout <= 600:
        fail(f"{agent_id}: timeout_seconds must be in 5..600")
    if depth != 0:
        fail(f"{agent_id}: nested delegation is disabled in schema v1")
    for field in ("capabilities",):
        values = manifest.get(field, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            fail(f"{agent_id}: {field} must be an array of non-empty strings")
    validate_dependencies(manifest, agent_id)
    documentation = manifest.get("documentation")
    if documentation:
        doc_path = Path(documentation)
        if doc_path.is_absolute() or ".." in doc_path.parts or "\\" in documentation:
            fail(f"{agent_id}: unsafe documentation path")
        doc_target = (target.parent / doc_path).resolve()
        if target.parent.resolve() not in doc_target.parents or not doc_target.is_file():
            fail(f"{agent_id}: documentation file does not exist in agent folder")
    encoded = json.dumps(manifest).lower()
    for marker in ('"api_key":', '"access_token":', '"client_secret":', '"password":', '"secret_value":'):
        if marker in encoded:
            fail(f"{agent_id}: possible credential field found in manifest")


def main():
    registry = read_json(REGISTRY_PATH)
    if registry.get("schemaVersion") != 1 or not isinstance(registry.get("agents"), list):
        fail("registry.json must use schemaVersion 1 and contain an agents array")
    seen = set()
    for entry in registry["agents"]:
        if not isinstance(entry, dict):
            fail("registry entries must be objects")
        agent_id = entry.get("id")
        if not isinstance(agent_id, str) or not ID_RE.fullmatch(agent_id):
            fail(f"invalid agent ID: {agent_id!r}")
        if agent_id in seen:
            fail(f"duplicate agent ID: {agent_id}")
        seen.add(agent_id)
        if not isinstance(entry.get("name"), str) or not entry["name"].strip():
            fail(f"{agent_id}: registry name is required")
        if not isinstance(entry.get("category"), str) or not entry["category"].strip():
            fail(f"{agent_id}: registry category is required")
        validate_manifest(entry)
    if len(seen) == 0:
        fail("registry must contain at least one agent")
    print(f"Validated {len(seen)} sub-agent manifests.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
