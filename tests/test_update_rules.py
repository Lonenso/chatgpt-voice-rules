import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_rules as rules


def source(*records, **metadata):
    return json.dumps({"prefixes": list(records), **metadata}).encode()


class UpdateTests(unittest.TestCase):
    def test_ipv4_ipv6_deduplicate_and_sort_without_policy(self):
        raw = source({"ipv6Prefix": "2001:4860:4860::8888/128"},
                     {"ipv4Prefix": "8.8.8.8/32"}, {"ipv4Prefix": "1.1.1.0/24"},
                     {"ipv6Prefix": "2001:4860:4860:0:0:0:0:8888/128"},
                     {"ipv4Prefix": "8.8.8.8/32"})
        content = rules.render(rules.parse_prefixes(raw)).decode()
        entries = [line for line in content.splitlines() if not line.startswith("#")]
        self.assertEqual(entries, ["IP-CIDR,1.1.1.0/24,no-resolve", "IP-CIDR,8.8.8.8/32,no-resolve",
                                   "IP-CIDR6,2001:4860:4860::8888/128,no-resolve"])
        self.assertNotIn("PROXY", content)

    def test_invalid_source_never_changes_existing_file(self):
        invalid = [b"<html>blocked</html>", b"{", b"[]", b"{}", source(),
                   source(None), source({"cidr": "8.8.8.8/32"}),
                   source({"ipv4Prefix": "8.8.8.8"}), source({"ipv4Prefix": "8.8.8.8/33"}),
                   source({"ipv4Prefix": "8.8.8.8/24"}), source({"ipv4Prefix": "8.8.8.0/255.255.255.0"}),
                   source({"ipv4Prefix": "2001:4860::/32"}), source({"ipv6Prefix": "8.8.8.8/32"}),
                   source({"ipv4Prefix": "0.0.0.0/0"}), source({"ipv6Prefix": "::/0"}),
                   source({"ipv4Prefix": "192.168.0.0/16"}), source({"ipv6Prefix": "fe80::/64"}),
                   source({"ipv4Prefix": "224.0.0.0/4"}), source({"ipv4Prefix": None}),
                   source({"ipv4Prefix": "8.8.8.8/32"}, {"ipv4Prefix": "broken"}),
                   b'{"prefixes":[],"prefixes":[{"ipv4Prefix":"8.8.8.8/32"}]}',
                   b" " * (rules.MAX_BYTES + 1)]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rules.list"
            output.write_bytes(b"last known good\n")
            for raw in invalid:
                with self.subTest(raw=raw[:120]):
                    with self.assertRaises(rules.ValidationError):
                        rules.update(raw, output)
                    self.assertEqual(output.read_bytes(), b"last known good\n")

    def test_metadata_reordering_and_duplicates_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rules.list"
            self.assertTrue(rules.update(source({"ipv4Prefix": "8.8.8.8/32"},
                                               {"ipv4Prefix": "1.1.1.1/32"}, creationTime="old"), output))
            before = output.stat().st_mtime_ns
            self.assertFalse(rules.update(source({"ipv4Prefix": "1.1.1.1/32"},
                                                {"ipv4Prefix": "8.8.8.8/32"},
                                                {"ipv4Prefix": "8.8.8.8/32"}, creationTime="new"), output))
            self.assertEqual(output.stat().st_mtime_ns, before)

    def test_failed_replacement_retains_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rules.list"
            output.write_bytes(b"old")
            with patch.object(rules.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    rules.update(source({"ipv4Prefix": "8.8.8.8/32"}), output)
            self.assertEqual(output.read_bytes(), b"old")
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["rules.list"])

    def test_download_failure_exits_nonzero_and_retains_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rules.list"
            output.write_bytes(b"old")
            with patch.object(sys, "argv", ["update_rules.py", "--output", str(output)]), \
                 patch.object(rules.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")) as fetch, \
                 patch.object(rules.time, "sleep"):
                self.assertEqual(rules.main(), 1)
                self.assertEqual(fetch.call_count, 3)
            self.assertEqual(output.read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
