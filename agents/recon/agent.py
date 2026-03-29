"""
Recon Agent — asset discovery and vulnerability surface mapping.

Cycle:
  1. Ask Commander for current mission scope + what's already known
  2. Run host discovery (ping sweep via nmap)
  3. For each live host: port scan + service fingerprint
  4. Cross-reference services against NVD for known CVEs
  5. Optional: Shodan lookup for internet-facing assets
  6. Write all findings to Commander
  7. Broadcast summary to dashboard
  8. Sleep, then repeat
"""
import os
import sys
import asyncio
import logging
import json

# Allow importing from base/
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR  = os.path.join(os.path.dirname(_AGENT_DIR), "base")
for d in (_BASE_DIR, _AGENT_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from base_agent import BaseAgent
from cve_lookup import lookup_service_cves
from parsers.nmap_parser import parse_xml, hosts_to_summary

logger = logging.getLogger(__name__)

RECON_INTERVAL = int(os.getenv("RECON_INTERVAL", "3600"))  # seconds between full scans
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY", "")


class ReconAgent(BaseAgent):
    AGENT_ID     = "recon-agent"
    CAPABILITIES = ["host_discovery", "port_scan", "service_fingerprint",
                    "cve_lookup", "shodan_query", "dns_enum"]

    SYSTEM_PROMPT = """You are the Recon Agent for SecuNet — an autonomous purple team platform.
Your mission: map the complete attack surface of the target network.

You discover:
- Live hosts (ping sweep, ARP, TCP probes)
- Open ports and running services
- Service versions and banners
- Known CVEs for discovered services
- DNS records, subdomains
- Public exposure via Shodan (if applicable)

When planning scans, be methodical:
1. Start broad (host discovery)
2. Go deep (full port scan on live hosts)
3. Fingerprint (service versions)
4. Cross-reference (CVE lookup per service)

Always write findings to Commander. Be precise: include IPs, ports, CVE IDs, CVSS scores.
Never scan outside the authorised scope."""

    def tools(self) -> dict:
        return {
            "nmap_ping_sweep":      self._tool_ping_sweep,
            "nmap_port_scan":       self._tool_port_scan,
            "nmap_service_scan":    self._tool_service_scan,
            "nmap_vuln_scan":       self._tool_vuln_scan,
            "cve_lookup_service":   self._tool_cve_lookup,
            "shodan_lookup":        self._tool_shodan,
            "dns_enum":             self._tool_dns_enum,
        }

    # ── Tool implementations ─────────────────────────────────────────────

    async def _run_nmap(self, args_str: str, target: str) -> tuple[str, str]:
        """
        Run nmap via CC execution API.
        Returns (stdout_text, xml_text) where:
          - stdout_text is human-readable normal output (for terminal feed)
          - xml_text is the full XML output (for parsing)
        """
        import uuid as _uuid
        xml_file = f"/tmp/nmap_{_uuid.uuid4().hex}.xml"
        # Write XML to file, normal format to stdout
        cmd    = f"nmap {args_str} -oX {xml_file} -oN - {target}"
        result = await self.cc.execute(cmd, target=target, timeout=300)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if result.get("exit_code", -1) != 0 and not stdout:
            return f"nmap error: {stderr[:300]}", ""
        # Read the XML file silently (internal housekeeping — don't log to terminal)
        read_result = await self.cc.execute(
            f"cat {xml_file} 2>/dev/null; rm -f {xml_file}",
            target=target, timeout=10, silent=True,
        )
        xml_text = read_result.get("stdout", "")
        return stdout, xml_text

    async def _tool_ping_sweep(self, args: dict) -> str:
        target = args.get("target", "")
        if not target:
            return "ERROR: target required"
        await self.cc.heartbeat(status="running", current_task=f"ping sweep {target}")
        _, xml = await self._run_nmap("-sn -T4", target)
        hosts  = parse_xml(xml) if "<nmaprun" in xml else []
        return hosts_to_summary(hosts)

    async def _tool_port_scan(self, args: dict) -> str:
        target   = args.get("target", "")
        ports    = args.get("ports", "1-1024")
        if not target:
            return "ERROR: target required"
        await self.cc.heartbeat(status="running", current_task=f"port scan {target}")
        _, xml = await self._run_nmap(f"-sS -T4 --open -p {ports}", target)
        hosts  = parse_xml(xml) if "<nmaprun" in xml else []
        return hosts_to_summary(hosts)

    async def _tool_service_scan(self, args: dict) -> str:
        target = args.get("target", "")
        ports  = args.get("ports", "")
        if not target:
            return "ERROR: target required"
        port_flag = f"-p {ports}" if ports else "--top-ports 1000"
        await self.cc.heartbeat(status="running", current_task=f"service scan {target}")
        _, xml = await self._run_nmap(f"-sV -T4 --open {port_flag}", target)
        hosts  = parse_xml(xml) if "<nmaprun" in xml else []
        # Write to Commander
        for h in hosts:
            await self.commander.write_scan_result(
                host=h["ip"], ports=h["ports"], os_guess=h.get("os_guess", "")
            )
            await self.commander.write_asset_discovery(
                host=h["ip"], hostnames=h.get("hostnames", []),
                mac=h.get("mac", ""), os_guess=h.get("os_guess", "")
            )
            for p in h["ports"]:
                if p.get("version"):
                    await self.commander.write_service_fingerprint(
                        host=h["ip"], port=p["port"], protocol=p["protocol"],
                        service=p["service"], version=p["version"], banner=p.get("banner", "")
                    )
        return hosts_to_summary(hosts)

    async def _tool_vuln_scan(self, args: dict) -> str:
        target = args.get("target", "")
        ports  = args.get("ports", "")
        if not target:
            return "ERROR: target required"
        port_flag = f"-p {ports}" if ports else ""
        await self.cc.heartbeat(status="running", current_task=f"vuln scan {target}")
        stdout, _ = await self._run_nmap(f"-sV --script=vuln,default -T4 {port_flag}", target)
        return stdout[:2000]

    async def _tool_cve_lookup(self, args: dict) -> str:
        service = args.get("service", "")
        version = args.get("version", "")
        host    = args.get("host", "")
        port    = args.get("port", 0)
        if not service:
            return "ERROR: service required"
        cves = await lookup_service_cves(service, version, limit=5)
        if not cves:
            return f"No known CVEs found for {service} {version}"
        results = []
        for cve in cves:
            results.append(
                f"{cve['cve']} [{cve['severity'].upper()} CVSS:{cve['cvss']}] {cve['description'][:150]}"
            )
            # Write vulnerability to Commander if host context available
            if host:
                await self.commander.write_vulnerability(
                    host=host, port=int(port), service=service,
                    cve=cve["cve"], cvss=cve["cvss"], severity=cve["severity"],
                    title=f"{cve['cve']} in {service} {version}",
                    description=cve["description"][:300],
                )
        return "\n".join(results)

    async def _tool_shodan(self, args: dict) -> str:
        if not SHODAN_API_KEY:
            return "SHODAN_API_KEY not configured"
        ip = args.get("ip", "")
        if not ip:
            return "ERROR: ip required"
        try:
            from web_client import fetch_json
            data = await fetch_json(
                f"https://api.shodan.io/shodan/host/{ip}?key={SHODAN_API_KEY}"
            )
            if not data:
                return f"No Shodan data for {ip}"
            from parsers.shodan_parser import parse_host
            host = parse_host(data)
            lines = [f"Shodan: {ip}"]
            if host.get("org"):       lines.append(f"  Org: {host['org']}")
            if host.get("country"):   lines.append(f"  Country: {host['country']}")
            if host.get("vulns"):     lines.append(f"  Known vulns: {', '.join(host['vulns'][:5])}")
            lines.append(f"  Open ports: {', '.join(str(p['port']) for p in host['ports'][:10])}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Shodan error: {exc}"

    async def _tool_dns_enum(self, args: dict) -> str:
        target = args.get("target", "")
        if not target:
            return "ERROR: target required"
        await self.cc.heartbeat(status="running", current_task=f"DNS enum {target}")
        stdout, _ = await self._run_nmap("--script=dns-brute,dns-zone-transfer -p 53", target)
        return stdout[:1000]

    # ── Primary cycle ─────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """Full recon cycle: runs indefinitely on RECON_INTERVAL."""
        while True:
            try:
                await self._do_recon()
            except Exception:
                logger.exception("[recon-agent] Cycle failed")
            logger.info("[recon-agent] Cycle complete. Next run in %ds", RECON_INTERVAL)
            await asyncio.sleep(RECON_INTERVAL)

    async def _do_recon(self) -> None:
        logger.info("[recon-agent] Starting recon cycle")

        # 1. Get mission scope from Commander
        context = await self.commander.ask(
            "What is the current target scope and what hosts have already been discovered? "
            "What should I prioritize in this recon cycle?"
        )
        scope = await self.cc.get_target_scope()
        if not scope:
            logger.error("[recon-agent] target_scope not set — cannot scan")
            await self.cc.send_message(
                "Recon aborted: target scope not configured. Set it from the dashboard."
            )
            return

        await self.cc.send_message(
            f"Recon cycle starting. Target scope: {scope}. Context from Commander: {context[:200]}"
        )

        # 2. Build and execute recon plan via LLM
        prompt = f"""TARGET SCOPE: {scope}

COMMANDER CONTEXT: {context}

Plan and execute a complete recon cycle for this scope.
Start with a ping sweep, then do service scans on live hosts,
then look up CVEs for interesting services.
Use the available tools systematically.
Report what you find as you go."""

        result = await self.think_and_act(prompt, max_tokens=4096)

        # 3. Broadcast summary
        await self.cc.send_message(
            f"Recon cycle complete.\n\n{result[:2000]}"
        )
        logger.info("[recon-agent] Recon cycle complete")
