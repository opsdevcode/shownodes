import re

# Regex for IP addresses, including AWS DNS names that stand in for IP addresses
IP_REGEX = re.compile(
    r"""(?P<prefix>(?:fargate-ip-|ec2-|ip-)?)
        (?P<octets>\d+[\-\.]\d+[\-\.]\d+[\-\.]\d+)
        (?P<suffix>[\w\.\-]*)""",
    re.X,
)

# recognize pod names
# (pattern should also find AWS instance ids)
POD_REGEX = re.compile(r"([a-z0-9]+(-[a-z0-9]+)+)")


def canonical_ip(raw_ip: str) -> str:
    """
    Convert all typical formats of IP addresses to a canonical format. For
    example, AWS prefers to wrap IP addresses in DNS names
    `ip-10-128-1-20.ec2.internal`. It's canonical form is `10.128.1.20`.
    """
    if match := re.search(IP_REGEX, raw_ip):
        return match.group("octets").replace("-", ".")
    return ""
