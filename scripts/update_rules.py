#!/usr/bin/env python3
"""Validate OpenAI Voice CIDRs and atomically publish a policy-free rule set."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.error
import urllib.request

SOURCE = "https://openai.com/chatgpt-voice.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "rules/chatgpt-voice.list"
MAX_BYTES = 2 * 1024 * 1024


class ValidationError(ValueError):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_prefixes(raw):
    if len(raw) > MAX_BYTES:
        raise ValidationError("Source exceeds the 2 MiB safety limit")
    try:
        data = json.loads(raw, object_pairs_hook=unique_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Source is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("prefixes"), list):
        raise ValidationError("Expected an object containing a prefixes array")
    if not data["prefixes"]:
        raise ValidationError("Refusing an empty prefixes array")
    networks = set()
    for index, record in enumerate(data["prefixes"]):
        if not isinstance(record, dict):
            raise ValidationError(f"prefixes[{index}] is not an object")
        keys = set(record) & {"ipv4Prefix", "ipv6Prefix"}
        if not keys or any(key.lower().endswith("prefix") and key not in keys for key in record):
            raise ValidationError(f"Unknown or missing CIDR field at prefixes[{index}]")
        for key in sorted(keys):
            value = record[key]
            if not isinstance(value, str) or value.count("/") != 1:
                raise ValidationError(f"{key} must contain a CIDR string")
            address, length = value.split("/")
            if value.strip() != value or not length.isascii() or not length.isdecimal():
                raise ValidationError(f"Invalid CIDR notation at prefixes[{index}]")
            try:
                network = ipaddress.ip_network(value, strict=True)
            except ValueError as exc:
                raise ValidationError(f"Invalid CIDR at prefixes[{index}]: {value}") from exc
            expected_version = 4 if key == "ipv4Prefix" else 6
            if network.version != expected_version:
                raise ValidationError(f"Address family does not match {key}")
            if "%" in address or network.prefixlen == 0 or not network.is_global or network.is_multicast:
                raise ValidationError(f"Refusing non-public or default-route network: {value}")
            networks.add(network)
    return sorted(networks, key=lambda n: (n.version, int(n.network_address), n.prefixlen))


def render(networks):
    canonical = "".join(f"{network}\n" for network in networks)
    digest = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    count4 = sum(network.version == 4 for network in networks)
    lines = [
        "# ChatGPT Voice - Shadowrocket remote rule set",
        f"# Source: {SOURCE}",
        f"# IPv4: {count4}; IPv6: {len(networks) - count4}",
        f"# CIDR SHA256: {digest}",
        "# Select the policy in your local RULE-SET entry.",
    ]
    lines.extend(
        f"{'IP-CIDR' if network.version == 4 else 'IP-CIDR6'},{network},no-resolve"
        for network in networks
    )
    return ("\n".join(lines) + "\n").encode("ascii")


def fetch_source():
    request = urllib.request.Request(SOURCE, headers={
        "User-Agent": "chatgpt-voice-rules/1.0",
        "Accept": "application/json, application/octet-stream",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200 or not response.url.startswith("https://"):
                    raise ValidationError("Expected a complete HTTPS 200 response")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValidationError("Source exceeds the 2 MiB safety limit")
                return raw
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def update(raw, output):
    content = render(parse_prefixes(raw))  # Validate everything before any write.
    output = Path(output)
    if output.exists() and output.read_bytes() == content:
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".voice-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Use a local official JSON snapshot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes() if args.input else fetch_source()
        changed = update(raw, args.output)
    except (ValueError, OSError, urllib.error.URLError) as exc:
        print(f"Update failed; previous rule set retained: {exc}", file=sys.stderr)
        return 1
    print("Rule set updated." if changed else "No CIDR changes; rule set unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
