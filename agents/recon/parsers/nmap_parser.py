"""
Nmap XML output parser.
Takes raw nmap XML and returns structured host/port/service data.
"""
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)


def parse_xml(xml_text: str) -> list[dict]:
    """
    Parse nmap XML output into a list of host dicts.

    Returns:
        [
          {
            "ip": "10.0.0.1",
            "hostnames": ["router.local"],
            "state": "up",
            "os_guess": "Linux 4.x",
            "mac": "AA:BB:CC:...",
            "ports": [
              {
                "port": 22,
                "protocol": "tcp",
                "state": "open",
                "service": "ssh",
                "version": "OpenSSH 8.2",
                "banner": "...",
                "scripts": {...}
              }
            ]
          }
        ]
    """
    if not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("nmap XML parse error: %s", exc)
        return []

    hosts = []
    for host_el in root.findall("host"):
        # State
        state_el = host_el.find("status")
        if state_el is None or state_el.get("state") != "up":
            continue

        # IP
        ip = ""
        mac = ""
        hostnames = []
        for addr_el in host_el.findall("address"):
            if addr_el.get("addrtype") == "ipv4":
                ip = addr_el.get("addr", "")
            elif addr_el.get("addrtype") == "mac":
                mac = addr_el.get("addr", "")

        # Hostnames
        hnames_el = host_el.find("hostnames")
        if hnames_el is not None:
            for hn in hnames_el.findall("hostname"):
                name = hn.get("name", "")
                if name:
                    hostnames.append(name)

        # OS guess
        os_guess = ""
        os_el = host_el.find("os")
        if os_el is not None:
            best = os_el.find("osmatch")
            if best is not None:
                os_guess = best.get("name", "")

        # Ports
        ports = []
        ports_el = host_el.find("ports")
        if ports_el is not None:
            for port_el in ports_el.findall("port"):
                state_p = port_el.find("state")
                if state_p is None or state_p.get("state") != "open":
                    continue

                port_num  = int(port_el.get("portid", 0))
                protocol  = port_el.get("protocol", "tcp")
                svc_el    = port_el.find("service")
                service   = ""
                version   = ""
                banner    = ""
                if svc_el is not None:
                    service  = svc_el.get("name", "")
                    product  = svc_el.get("product", "")
                    ver      = svc_el.get("version", "")
                    extrainfo= svc_el.get("extrainfo", "")
                    parts    = [p for p in [product, ver, extrainfo] if p]
                    version  = " ".join(parts)

                # Script output
                scripts = {}
                for script_el in port_el.findall("script"):
                    sid    = script_el.get("id", "")
                    output = script_el.get("output", "")
                    if sid:
                        scripts[sid] = output
                        if "banner" in sid.lower():
                            banner = output

                ports.append({
                    "port":     port_num,
                    "protocol": protocol,
                    "state":    "open",
                    "service":  service,
                    "version":  version,
                    "banner":   banner,
                    "scripts":  scripts,
                })

        if ip:
            hosts.append({
                "ip":        ip,
                "hostnames": hostnames,
                "state":     "up",
                "os_guess":  os_guess,
                "mac":       mac,
                "ports":     ports,
            })

    return hosts


def hosts_to_summary(hosts: list[dict]) -> str:
    """Human-readable summary of parsed nmap results."""
    if not hosts:
        return "No live hosts found."
    lines = []
    for h in hosts:
        line = f"{h['ip']}"
        if h["hostnames"]:
            line += f" ({', '.join(h['hostnames'][:2])})"
        if h["os_guess"]:
            line += f" [{h['os_guess']}]"
        open_ports = [str(p["port"]) for p in h["ports"]]
        if open_ports:
            line += f" — ports: {', '.join(open_ports[:10])}"
            if len(open_ports) > 10:
                line += f" (+{len(open_ports)-10} more)"
        lines.append(line)
    return "\n".join(lines)
