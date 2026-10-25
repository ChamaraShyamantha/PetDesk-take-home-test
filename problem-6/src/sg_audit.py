"""Daily audit: flag security group ingress open to the internet on anything but 80/443.

Scans every enabled region, then publishes a single report to an SNS topic.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_PORTS = {80, 443}
OPEN_CIDRS = {"0.0.0.0/0", "::/0"}
PORT_PROTOCOLS = {"tcp", "udp", "6", "17"}
PROTOCOL_NAMES = {"-1": "all", "6": "tcp", "17": "udp", "1": "icmp", "58": "icmpv6"}

SNS_MAX_BYTES = 250_000  # SNS hard limit is 256 KB; leave headroom
BOTO_CONFIG = Config(retries={"max_attempts": 10, "mode": "adaptive"})


def rule_is_exposed(perm):
    """Return True if a rule's protocol/port span reaches beyond 80 and 443."""
    protocol = str(perm.get("IpProtocol", "")).lower()
    if protocol not in PORT_PROTOCOLS:
        # "-1" (all traffic), icmp, or any other IP protocol: not web traffic.
        return True
    from_port, to_port = perm.get("FromPort"), perm.get("ToPort")
    if from_port is None or to_port is None:
        return True
    # Only a single-port rule on 80 or 443 is acceptable; any range, even
    # 80-443, contains other ports.
    return not (from_port == to_port and from_port in ALLOWED_PORTS)


def describe_ports(perm):
    protocol = str(perm.get("IpProtocol", "")).lower()
    name = PROTOCOL_NAMES.get(protocol, protocol)
    if protocol == "-1":
        return "All traffic (all protocols, all ports)"
    if protocol not in PORT_PROTOCOLS:
        return f"protocol {name}"
    from_port, to_port = perm.get("FromPort"), perm.get("ToPort")
    if from_port == 0 and to_port == 65535:
        return f"{name} all ports (0-65535)"
    if from_port == to_port:
        return f"{name} port {from_port}"
    return f"{name} ports {from_port}-{to_port}"


def find_exposed_rules(security_group):
    """Yield one finding per (rule, open CIDR) pair in a security group."""
    for perm in security_group.get("IpPermissions", []):
        if not rule_is_exposed(perm):
            continue
        ranges = [(r.get("CidrIp"), r.get("Description")) for r in perm.get("IpRanges", [])]
        ranges += [(r.get("CidrIpv6"), r.get("Description")) for r in perm.get("Ipv6Ranges", [])]
        for cidr, description in ranges:
            if cidr in OPEN_CIDRS:
                yield {
                    "group_id": security_group["GroupId"],
                    "group_name": security_group.get("GroupName", ""),
                    "vpc_id": security_group.get("VpcId", "-"),
                    "rule": f"{describe_ports(perm)} from {cidr}",
                    "rule_description": description or "",
                }


def scan_region(region):
    ec2 = boto3.client("ec2", region_name=region, config=BOTO_CONFIG)
    findings = []
    for page in ec2.get_paginator("describe_security_groups").paginate():
        for sg in page["SecurityGroups"]:
            for finding in find_exposed_rules(sg):
                finding["region"] = region
                findings.append(finding)
    return findings


def enabled_regions():
    ec2 = boto3.client("ec2", config=BOTO_CONFIG)
    # AllRegions=False returns only regions enabled for this account
    # (default regions plus opted-in ones).
    response = ec2.describe_regions(AllRegions=False)
    return sorted(r["RegionName"] for r in response["Regions"])


def build_report(account_id, regions, findings, errors):
    lines = [
        f"Security group audit for account {account_id}",
        f"Regions scanned: {len(regions) - len(errors)}/{len(regions)}",
        f"Findings: {len(findings)} inbound rule(s) open to 0.0.0.0/0 or ::/0 "
        "on ports other than 80/443",
        "",
    ]
    for f in sorted(findings, key=lambda f: (f["region"], f["group_id"], f["rule"])):
        lines += [
            f"Region:      {f['region']}",
            f"Group name:  {f['group_name']}",
            f"Group ID:    {f['group_id']} (VPC {f['vpc_id']})",
            f"Rule:        {f['rule']}",
        ]
        if f["rule_description"]:
            lines.append(f"Description: {f['rule_description']}")
        lines.append("")
    if errors:
        lines.append("Regions that could not be scanned (results are incomplete):")
        lines += [f"  {region}: {err}" for region, err in sorted(errors.items())]
    return "\n".join(lines)


def truncate(message):
    encoded = message.encode("utf-8")
    if len(encoded) <= SNS_MAX_BYTES:
        return message
    note = "\n\n[Report truncated to fit SNS size limit; see Lambda logs for the full list.]"
    return encoded[: SNS_MAX_BYTES - len(note)].decode("utf-8", "ignore") + note


def handler(event, context):
    topic_arn = os.environ["SNS_TOPIC_ARN"]
    notify_when_clean = os.environ.get("NOTIFY_WHEN_CLEAN", "false").lower() == "true"
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    regions = enabled_regions()
    findings, errors = [], {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {region: pool.submit(scan_region, region) for region in regions}
        for region, future in futures.items():
            try:
                findings.extend(future.result())
            except Exception as exc:  # keep going; report the gap instead of failing
                logger.exception("Failed to scan %s", region)
                errors[region] = str(exc)

    report = build_report(account_id, regions, findings, errors)
    logger.info(report)

    if findings or errors or notify_when_clean:
        status = f"{len(findings)} open rule(s)" if findings else "no open rules"
        if errors:
            status += f", {len(errors)} region error(s)"
        boto3.client("sns").publish(
            TopicArn=topic_arn,
            Subject=f"[SG audit] {account_id}: {status}"[:100],
            Message=truncate(report),
        )

    return {"findings": len(findings), "regions": len(regions), "errors": len(errors)}
