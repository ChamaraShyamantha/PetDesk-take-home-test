import os
import sys
import types
import unittest

# The rule logic doesn't touch AWS; stub boto3 so tests run without it installed.
for name in ("boto3", "botocore", "botocore.config"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["botocore.config"].Config = lambda **kwargs: None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sg_audit  # noqa: E402


def sg(*perms):
    return {"GroupId": "sg-123", "GroupName": "web", "VpcId": "vpc-1", "IpPermissions": list(perms)}


def perm(protocol, from_port=None, to_port=None, v4=("0.0.0.0/0",), v6=()):
    p = {
        "IpProtocol": protocol,
        "IpRanges": [{"CidrIp": c} for c in v4],
        "Ipv6Ranges": [{"CidrIpv6": c} for c in v6],
    }
    if from_port is not None:
        p["FromPort"], p["ToPort"] = from_port, to_port
    return p


def rules(group):
    return [f["rule"] for f in sg_audit.find_exposed_rules(group)]


class FindExposedRulesTest(unittest.TestCase):
    def test_web_ports_are_allowed(self):
        self.assertEqual(rules(sg(perm("tcp", 80, 80), perm("tcp", 443, 443, v6=("::/0",)))), [])

    def test_ssh_open_to_world_is_flagged(self):
        self.assertEqual(rules(sg(perm("tcp", 22, 22))), ["tcp port 22 from 0.0.0.0/0"])

    def test_all_traffic_is_flagged(self):
        self.assertEqual(rules(sg(perm("-1"))), ["All traffic (all protocols, all ports) from 0.0.0.0/0"])

    def test_range_spanning_web_ports_is_flagged(self):
        self.assertEqual(rules(sg(perm("tcp", 80, 443))), ["tcp ports 80-443 from 0.0.0.0/0"])

    def test_full_port_range_is_flagged(self):
        self.assertEqual(rules(sg(perm("udp", 0, 65535))), ["udp all ports (0-65535) from 0.0.0.0/0"])

    def test_udp_443_is_allowed(self):
        self.assertEqual(rules(sg(perm("udp", 443, 443))), [])

    def test_ipv6_is_flagged(self):
        self.assertEqual(rules(sg(perm("tcp", 3389, 3389, v4=(), v6=("::/0",)))), ["tcp port 3389 from ::/0"])

    def test_both_families_yield_two_findings(self):
        self.assertEqual(len(rules(sg(perm("tcp", 22, 22, v6=("::/0",))))), 2)

    def test_icmp_is_flagged(self):
        self.assertEqual(rules(sg(perm("icmp", -1, -1))), ["protocol icmp from 0.0.0.0/0"])

    def test_restricted_cidr_is_ignored(self):
        self.assertEqual(rules(sg(perm("tcp", 22, 22, v4=("10.0.0.0/8", "203.0.113.0/24")))), [])

    def test_group_reference_is_ignored(self):
        p = perm("-1", v4=())
        p["UserIdGroupPairs"] = [{"GroupId": "sg-other"}]
        self.assertEqual(rules(sg(p)), [])


if __name__ == "__main__":
    unittest.main()
