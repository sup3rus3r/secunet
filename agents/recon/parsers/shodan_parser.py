"""
Shodan API response parser.
Normalises Shodan host data into the same port dict format as nmap_parser.
"""
import logging

logger = logging.getLogger(__name__)


def parse_host(data: dict) -> dict:
    """
    Parse a Shodan /shodan/host/{ip} response into our standard host dict.
    """
    if not data:
        return {}

    ports = []
    for item in data.get("data", []):
        port_num  = item.get("port", 0)
        transport = item.get("transport", "tcp")
        service   = item.get("_shodan", {}).get("module", "")
        banner    = (item.get("data") or "")[:200]
        version   = ""

        # Try to extract version from common fields
        for key in ("product", "version", "info"):
            v = item.get(key, "")
            if v:
                version += f" {v}"
        version = version.strip()

        ports.append({
            "port":     port_num,
            "protocol": transport,
            "state":    "open",
            "service":  service,
            "version":  version,
            "banner":   banner,
            "scripts":  {},
        })

    hostnames = data.get("hostnames", [])
    os_guess  = data.get("os", "") or ""

    return {
        "ip":        data.get("ip_str", ""),
        "hostnames": hostnames,
        "state":     "up",
        "os_guess":  os_guess,
        "mac":       "",
        "ports":     ports,
        "org":       data.get("org", ""),
        "isp":       data.get("isp", ""),
        "country":   data.get("country_name", ""),
        "vulns":     list(data.get("vulns", {}).keys()),
    }
