"""SSRF Protection and Strict URL Validation for NEXUS Browser Automation."""

import ipaddress
import socket
from urllib.parse import urlparse

from packages.shared.nexus_shared.errors import PolicyViolationError


class SSRFSecurityViolation(PolicyViolationError):
    """Raised when an outbound URL violates SSRF security boundaries."""


BLOCKED_NETWORKS = [
    # IPv4 loopback
    ipaddress.ip_network("127.0.0.0/8"),
    # RFC 1918 Private networks
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local & AWS/GCP/Azure Metadata service
    ipaddress.ip_network("169.254.0.0/16"),
    # Multicast & Broadcast
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 loopback and private/link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def validate_url_safe(url: str) -> str:
    """Validate target URL against SSRF boundaries.

    Ensures only http/https schemes, resolves hostnames to IPs, and rejects private/loopback/metadata addresses.
    Returns normalized safe URL string or raises SSRFSecurityViolation.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityViolation("Empty or invalid URL supplied")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFSecurityViolation(
            f"Unsupported or forbidden URL scheme '{parsed.scheme}'. Only HTTP/HTTPS permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityViolation("URL does not contain a valid hostname")

    # Reject localhost directly
    if hostname.lower() in ("localhost", "localhost.", "ip6-localhost", "ip6-loopback"):
        raise SSRFSecurityViolation(
            f"Target host '{hostname}' resolves to loopback (SSRF blocked)."
        )

    # Resolve IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFSecurityViolation(f"Unable to resolve hostname '{hostname}': {e}") from e

    resolved_ips: set[str] = set()
    for item in addr_info:
        ip_str = str(item[4][0])
        resolved_ips.add(ip_str)

    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as e:
            raise SSRFSecurityViolation(f"Invalid resolved IP '{ip_str}': {e}") from e

        # Check for NAT64 well-known prefix (64:ff9b::/96)
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj in ipaddress.ip_network(
            "64:ff9b::/96"
        ):
            # Extract embedded IPv4 (last 32 bits)
            ipv4_int = int(ip_obj) & 0xFFFFFFFF
            embedded_v4 = ipaddress.IPv4Address(ipv4_int)
            if (
                embedded_v4.is_loopback
                or embedded_v4.is_private
                or embedded_v4.is_link_local
                or embedded_v4.is_multicast
            ):
                raise SSRFSecurityViolation(
                    f"Target hostname '{hostname}' resolves to NAT64 restricted IPv4 '{embedded_v4}'."
                )
            continue

        # Check loopback, private, link_local, multicast properties
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast:
            raise SSRFSecurityViolation(
                f"Target hostname '{hostname}' resolves to restricted IP '{ip_str}' (SSRF blocked)."
            )

        for blocked in BLOCKED_NETWORKS:
            if ip_obj in blocked:
                raise SSRFSecurityViolation(
                    f"Target hostname '{hostname}' resolves to blocked CIDR '{blocked}' ({ip_str})."
                )

    return url.strip()
