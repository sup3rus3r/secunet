# FILE: agents/remediate/fix_generator.py
"""
Fix generator — produces remediation actions for vulnerabilities.
Uses LLM to generate appropriate fix commands, Ansible tasks, or config changes.
"""
import os
import sys
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR  = os.path.join(os.path.dirname(_AGENT_DIR), "base")
for d in (_BASE_DIR, _AGENT_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
LLM_MODEL    = os.getenv("LLM_MODEL", "claude-sonnet-4-6")


# ── Enums and dataclasses ────────────────────────────────────────────────────

class FixType(Enum):
    PATCH           = "patch"
    CONFIG_CHANGE   = "config_change"
    FIREWALL_RULE   = "firewall_rule"
    SERVICE_DISABLE = "service_disable"
    ANSIBLE_TASK    = "ansible_task"
    MANUAL          = "manual"


@dataclass
class Fix:
    fix_type:             FixType
    title:                str
    description:          str
    commands:             list[str] = field(default_factory=list)
    ansible_task:         Optional[str] = None
    estimated_risk:       str = "medium"
    reversible:           bool = True
    verification_command: Optional[str] = None


# ── LLM helper ───────────────────────────────────────────────────────────────

async def _llm_complete(system: str, user: str, max_tokens: int = 4096) -> str:
    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        resp = await client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text
    elif LLM_PROVIDER in ("openai", "lmstudio"):
        from openai import AsyncOpenAI
        kwargs: dict = {"api_key": os.getenv("OPENAI_API_KEY", "none")}
        if LLM_PROVIDER == "lmstudio":
            kwargs["base_url"] = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
        client = AsyncOpenAI(**kwargs)
        resp = await client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


# ── Deterministic fix catalogue ──────────────────────────────────────────────

def _deterministic_fix(host: str, port: int, service: str, cve: str, severity: str) -> Optional[Fix]:
    """
    Return a Fix for well-known vulnerability patterns without calling the LLM.
    Returns None if no deterministic fix applies.
    """
    svc_lower = service.lower()
    cve_upper = cve.upper()

    # MS17-010 / EternalBlue — disable SMBv1
    if "ms17-010" in cve_upper or ("smb" in svc_lower and "ms17" in cve_upper):
        return Fix(
            fix_type=FixType.CONFIG_CHANGE,
            title="Disable SMBv1 (MS17-010 / EternalBlue mitigation)",
            description=(
                "SMBv1 is vulnerable to MS17-010 (EternalBlue). "
                "Disabling it eliminates the attack vector."
            ),
            commands=[
                # Windows
                "powershell -Command \"Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force\"",
                # Linux fallback
                "echo 0 > /proc/fs/cifs/OldSMBProtocolSupport 2>/dev/null || true",
            ],
            ansible_task=(
                "- name: Disable SMBv1\n"
                "  win_shell: Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force\n"
                "  ignore_errors: yes"
            ),
            estimated_risk="low",
            reversible=True,
            verification_command=(
                "powershell -Command \"Get-SmbServerConfiguration | Select EnableSMB1Protocol\""
            ),
        )

    # OpenSSH outdated
    if "openssh" in svc_lower or (svc_lower == "ssh" and "cve" in cve_upper):
        return Fix(
            fix_type=FixType.PATCH,
            title=f"Update OpenSSH to latest version ({cve})",
            description="Upgrade OpenSSH to patch the reported vulnerability.",
            commands=[
                "apt-get update -y",
                "apt-get install -y --only-upgrade openssh-server openssh-client",
                "systemctl restart ssh || systemctl restart sshd",
            ],
            ansible_task=(
                "- name: Upgrade OpenSSH\n"
                "  apt:\n"
                "    name: openssh-server\n"
                "    state: latest\n"
                "    update_cache: yes\n"
                "  notify: Restart SSH"
            ),
            estimated_risk="low",
            reversible=False,
            verification_command="ssh -V 2>&1",
        )

    # Apache CVEs
    if "apache" in svc_lower or "httpd" in svc_lower:
        return Fix(
            fix_type=FixType.PATCH,
            title=f"Update Apache HTTP Server ({cve})",
            description="Upgrade Apache to the latest patched release.",
            commands=[
                "apt-get update -y",
                "apt-get install -y --only-upgrade apache2",
                "systemctl restart apache2",
            ],
            ansible_task=(
                "- name: Upgrade Apache\n"
                "  apt:\n"
                "    name: apache2\n"
                "    state: latest\n"
                "    update_cache: yes\n"
                "  notify: Restart Apache"
            ),
            estimated_risk="low",
            reversible=False,
            verification_command="apache2 -v 2>&1 || httpd -v 2>&1",
        )

    # Nginx CVEs
    if "nginx" in svc_lower:
        return Fix(
            fix_type=FixType.PATCH,
            title=f"Update Nginx ({cve})",
            description="Upgrade Nginx to the latest patched release.",
            commands=[
                "apt-get update -y",
                "apt-get install -y --only-upgrade nginx",
                "systemctl restart nginx",
            ],
            ansible_task=(
                "- name: Upgrade Nginx\n"
                "  apt:\n"
                "    name: nginx\n"
                "    state: latest\n"
                "    update_cache: yes\n"
                "  notify: Restart Nginx"
            ),
            estimated_risk="low",
            reversible=False,
            verification_command="nginx -v 2>&1",
        )

    # FTP anonymous login
    if "ftp" in svc_lower and "anon" in cve_upper.lower() or (
        "vsftpd" in svc_lower and "anonymous" in cve_upper.lower()
    ):
        return Fix(
            fix_type=FixType.CONFIG_CHANGE,
            title="Disable FTP anonymous login",
            description="Set anonymous_enable=NO in vsftpd.conf to block unauthenticated FTP access.",
            commands=[
                "sed -i 's/^anonymous_enable=YES/anonymous_enable=NO/' /etc/vsftpd.conf",
                "grep -q 'anonymous_enable=NO' /etc/vsftpd.conf || echo 'anonymous_enable=NO' >> /etc/vsftpd.conf",
                "systemctl restart vsftpd",
            ],
            ansible_task=(
                "- name: Disable FTP anonymous login\n"
                "  lineinfile:\n"
                "    path: /etc/vsftpd.conf\n"
                "    regexp: '^anonymous_enable'\n"
                "    line: 'anonymous_enable=NO'\n"
                "  notify: Restart vsftpd"
            ),
            estimated_risk="low",
            reversible=True,
            verification_command="grep anonymous_enable /etc/vsftpd.conf",
        )

    # Default credentials
    if "default" in cve_upper.lower() and "cred" in cve_upper.lower():
        return Fix(
            fix_type=FixType.CONFIG_CHANGE,
            title="Force password reset for service account",
            description=(
                "Default credentials were detected. Force an immediate password change "
                "and disable the default account if not required."
            ),
            commands=[
                f"passwd {service} 2>/dev/null || echo 'Manual password reset required for service: {service}'",
                "chage -d 0 root 2>/dev/null || true",
            ],
            estimated_risk="low",
            reversible=True,
            verification_command="passwd -S root 2>/dev/null || true",
        )

    return None  # No deterministic fix — fall through to LLM


# ── LLM-based fix generation ─────────────────────────────────────────────────

_FIX_SYSTEM_PROMPT = """\
You are an expert Linux and Windows security hardening engineer with deep knowledge of
CVE remediations, system administration, and secure configuration. You produce precise,
actionable remediation plans for discovered vulnerabilities.

When given a vulnerability, respond ONLY with a JSON object in this exact schema:
{
  "fix_type": "<patch|config_change|firewall_rule|service_disable|ansible_task|manual>",
  "title": "<short title>",
  "description": "<one paragraph explanation>",
  "commands": ["<shell command 1>", "<shell command 2>"],
  "ansible_task": "<YAML ansible task string or null>",
  "estimated_risk": "<low|medium|high>",
  "reversible": <true|false>,
  "verification_command": "<single shell command to verify fix or null>"
}

Rules:
- Prefer package manager upgrades over manual builds.
- Always restart affected services after config changes.
- estimated_risk refers to risk of the remediation action itself breaking things.
- If the fix cannot be scripted safely, set fix_type to "manual" and explain in description.
- Output raw JSON only — no markdown, no prose outside the JSON object.
"""


async def generate_fix(
    host: str,
    port: int,
    service: str,
    cve: str,
    severity: str,
    description: str,
    context: str = "",
) -> Fix:
    """
    Generate a remediation Fix for the given vulnerability.
    Uses deterministic fixes for well-known cases; falls back to LLM for others.
    """
    # Try deterministic first
    det = _deterministic_fix(host, port, service, cve, severity)
    if det is not None:
        logger.info("[fix_generator] Deterministic fix applied for %s / %s", cve, service)
        return det

    # LLM-based generation
    logger.info("[fix_generator] Generating LLM fix for %s on %s:%d (%s)", cve, host, port, service)

    user_prompt = (
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Service: {service}\n"
        f"CVE: {cve}\n"
        f"Severity: {severity}\n"
        f"Vulnerability description: {description}\n"
    )
    if context:
        user_prompt += f"\nAdditional context:\n{context}\n"

    try:
        raw = await _llm_complete(_FIX_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.error("[fix_generator] LLM call failed: %s", exc)
        return Fix(
            fix_type=FixType.MANUAL,
            title=f"Manual remediation required: {cve}",
            description=(
                f"Automated fix generation failed ({exc}). "
                f"Please investigate {cve} on {host}:{port} ({service}) manually."
            ),
            commands=[],
            estimated_risk="unknown",
            reversible=False,
            verification_command=None,
        )

    # Strip any markdown fences if the LLM added them
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract embedded JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    if not data:
        logger.warning("[fix_generator] Could not parse LLM fix JSON for %s", cve)
        return Fix(
            fix_type=FixType.MANUAL,
            title=f"Manual remediation required: {cve}",
            description=(
                f"Could not parse automated fix for {cve} on {host}:{port} ({service}). "
                f"LLM response: {raw[:300]}"
            ),
            commands=[],
            estimated_risk="unknown",
            reversible=False,
            verification_command=None,
        )

    # Map fix_type string to enum
    ft_map = {e.value: e for e in FixType}
    fix_type_str = data.get("fix_type", "manual").lower()
    fix_type = ft_map.get(fix_type_str, FixType.MANUAL)

    return Fix(
        fix_type=fix_type,
        title=data.get("title", f"Fix for {cve}"),
        description=data.get("description", ""),
        commands=data.get("commands", []),
        ansible_task=data.get("ansible_task"),
        estimated_risk=data.get("estimated_risk", "medium"),
        reversible=bool(data.get("reversible", True)),
        verification_command=data.get("verification_command"),
    )


# ── HITL formatting ──────────────────────────────────────────────────────────

def format_fix_for_hitl(fix: Fix, host: str, cve: str) -> str:
    """
    Format a Fix as a human-readable summary for the HITL approval dialog
    shown to the security engineer.
    """
    lines = [
        f"REMEDIATION REQUEST",
        f"{'='*50}",
        f"Target:       {host}",
        f"CVE:          {cve}",
        f"Fix type:     {fix.fix_type.value.upper().replace('_', ' ')}",
        f"Title:        {fix.title}",
        f"Risk level:   {fix.estimated_risk.upper()}",
        f"Reversible:   {'Yes' if fix.reversible else 'No'}",
        f"",
        f"Description:",
        f"  {fix.description}",
        f"",
    ]

    if fix.commands:
        lines.append("Commands to execute:")
        for i, cmd in enumerate(fix.commands, 1):
            lines.append(f"  {i}. {cmd}")
        lines.append("")

    if fix.ansible_task:
        lines.append("Ansible task:")
        for line in fix.ansible_task.splitlines():
            lines.append(f"  {line}")
        lines.append("")

    if fix.verification_command:
        lines.append(f"Verification command:")
        lines.append(f"  {fix.verification_command}")
        lines.append("")

    lines.append(f"{'='*50}")
    lines.append("Approve to deploy this fix. Reject to skip.")

    return "\n".join(lines)
