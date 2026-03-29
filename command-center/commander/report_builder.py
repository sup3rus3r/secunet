"""
PDF Report Builder — weasyprint-based.
Renders a professional penetration test & remediation report.
"""
from __future__ import annotations
from datetime import datetime, timezone

COLORS = {
    "primary":  "#00D4FF",
    "critical": "#FF3B30",
    "high":     "#FF6B35",
    "medium":   "#FFB300",
    "low":      "#00C851",
    "info":     "#94A3B8",
    "bg_dark":  "#0A0E1A",
    "bg_card":  "#111827",
    "bg_mid":   "#0D1520",
    "border":   "#1E2A3A",
    "text":     "#E2E8F0",
    "muted":    "#64748B",
    "white":    "#FFFFFF",
}

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

def _sev_color(sev: str) -> str:
    return COLORS.get(sev.lower(), COLORS["muted"])

def _badge(sev: str) -> str:
    c = _sev_color(sev)
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:3px;'
        f'background:{c}20;border:1px solid {c}70;color:{c};'
        f'font-size:9px;font-weight:700;letter-spacing:0.08em;'
        f'text-transform:uppercase;white-space:nowrap;">{sev}</span>'
    )

def _ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts or "—"

def _bar(pct: float, color: str) -> str:
    v = max(0, min(100, float(pct)))
    return (
        f'<div style="background:#1E2A3A;border-radius:4px;height:7px;width:100%;">'
        f'<div style="background:{color};border-radius:4px;height:7px;width:{v}%;"></div>'
        f'</div>'
    )

def _payload(item: dict) -> dict:
    """Cold storage wraps events in a 'payload' key."""
    return item.get("payload", item)

# ─────────────────────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────────────────────
CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background:{COLORS['bg_dark']};
  color:{COLORS['text']};
  font-size:12px;
  line-height:1.55;
}}

/* ── Cover ── */
.cover {{
  width:100%; min-height:297mm;
  background:{COLORS['bg_dark']};
  display:flex; flex-direction:column;
  page-break-after:always;
  position:relative; overflow:hidden;
}}
.cover-stripe {{
  height:5px;
  background:linear-gradient(90deg,{COLORS['primary']} 0%,#3B82F6 45%,#8B5CF6 100%);
}}
.cover-grid {{
  position:absolute; top:0; left:0; width:100%; height:100%;
  background-image:
    linear-gradient(rgba(0,212,255,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,212,255,.025) 1px, transparent 1px);
  background-size:44px 44px;
  pointer-events:none;
}}
.cover-body {{
  position:relative; z-index:1; flex:1;
  padding:56px 60px 44px;
  display:flex; flex-direction:column; justify-content:space-between;
}}
.logo-row {{ display:flex; align-items:center; gap:12px; margin-bottom:70px; }}
.logo-hex {{
  width:42px; height:42px;
  background:{COLORS['primary']}18;
  border:1.5px solid {COLORS['primary']}55;
  border-radius:8px;
  display:flex; align-items:center; justify-content:center;
  font-size:16px; font-weight:700; font-family:monospace;
  color:{COLORS['primary']}; letter-spacing:-1px;
}}
.logo-name {{ font-size:18px; font-weight:800; letter-spacing:.18em; color:#fff; }}
.logo-sub  {{ font-size:9px; color:{COLORS['muted']}; letter-spacing:.2em; margin-top:2px; }}

.cover-main {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:30px 0; }}
.eyebrow {{ font-size:10px; letter-spacing:.3em; color:{COLORS['primary']}; font-weight:700; margin-bottom:14px; text-transform:uppercase; }}
.cover-h1 {{ font-size:44px; font-weight:900; color:#fff; letter-spacing:-.02em; line-height:1.05; margin-bottom:6px; }}
.cover-h2 {{ font-size:20px; font-weight:300; color:{COLORS['muted']}; letter-spacing:.04em; }}
.cover-rule {{ width:56px; height:3px; background:linear-gradient(90deg,{COLORS['primary']},transparent); margin:26px 0; border-radius:2px; }}
.meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; max-width:480px; }}
.meta-item {{ display:flex; flex-direction:column; gap:3px; }}
.meta-label {{ font-size:8.5px; letter-spacing:.2em; text-transform:uppercase; color:{COLORS['muted']}; font-weight:700; }}
.meta-val {{ font-family:monospace; font-size:12px; color:{COLORS['text']}; }}

.cover-foot {{
  display:flex; justify-content:space-between; align-items:center;
  padding-top:26px; border-top:1px solid {COLORS['border']};
}}
.cover-foot-txt {{ font-size:9px; color:{COLORS['muted']}; letter-spacing:.08em; }}
.risk-pill {{
  padding:5px 16px; border-radius:4px;
  font-size:10px; font-weight:800; letter-spacing:.2em;
}}

/* ── Page ── */
.page {{
  padding:38px 48px 36px;
  page-break-inside:avoid;
  background:{COLORS['bg_dark']};
}}
.page-hdr {{
  display:flex; justify-content:space-between; align-items:center;
  padding-bottom:14px; border-bottom:1px solid {COLORS['border']}; margin-bottom:28px;
}}
.page-hdr-left  {{ font-size:9px; letter-spacing:.22em; text-transform:uppercase; color:{COLORS['muted']}; font-weight:700; }}
.page-hdr-right {{ font-family:monospace; font-size:9px; color:{COLORS['primary']}; }}

.section {{ margin-bottom:36px; }}
.sec-title {{
  font-size:10px; letter-spacing:.25em; text-transform:uppercase;
  color:{COLORS['primary']}; font-weight:700; margin-bottom:14px;
  display:flex; align-items:center; gap:8px;
}}
.sec-title::after {{ content:''; flex:1; height:1px; background:{COLORS['border']}; }}

/* ── Metric cards ── */
.metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
.m-card {{
  background:{COLORS['bg_card']}; border:1px solid {COLORS['border']};
  border-radius:7px; padding:14px 16px;
}}
.m-label {{ font-size:8.5px; letter-spacing:.15em; text-transform:uppercase; color:{COLORS['muted']}; font-weight:700; margin-bottom:7px; }}
.m-val   {{ font-size:26px; font-weight:900; line-height:1; margin-bottom:8px; }}
.m-sub   {{ font-size:9px; color:{COLORS['muted']}; }}

/* ── Wide metric card (span 2) ── */
.m-wide  {{ grid-column:span 2; }}

/* ── Tables ── */
.tbl {{
  width:100%; border-collapse:collapse;
  background:{COLORS['bg_card']};
  border:1px solid {COLORS['border']}; border-radius:7px; overflow:hidden;
  font-size:11px;
}}
.tbl thead tr {{ background:{COLORS['bg_mid']}; }}
.tbl thead th {{
  padding:9px 11px; text-align:left;
  font-size:8.5px; letter-spacing:.15em; text-transform:uppercase;
  color:{COLORS['muted']}; font-weight:700; border-bottom:1px solid {COLORS['border']};
  white-space:nowrap;
}}
.tbl tbody td {{ padding:8px 11px; border-bottom:1px solid {COLORS['border']}40; vertical-align:top; }}
.tbl tbody tr:last-child td {{ border-bottom:none; }}

/* ── Rec cards ── */
.rec-card {{
  background:{COLORS['bg_card']}; border:1px solid {COLORS['border']};
  border-radius:7px; padding:14px 16px; margin-bottom:10px;
  border-left:3px solid #ccc;
}}
.rec-host {{ font-family:monospace; font-size:10px; color:{COLORS['primary']}; margin-bottom:4px; }}
.rec-title {{ font-size:12px; font-weight:700; color:{COLORS['white']}; margin-bottom:6px; }}
.rec-body {{ font-size:11px; color:{COLORS['muted']}; line-height:1.6; }}
.rec-step {{
  display:flex; gap:8px; align-items:flex-start;
  margin-top:5px; font-size:10.5px; color:{COLORS['text']};
}}
.rec-num {{
  min-width:18px; height:18px; border-radius:50%;
  background:{COLORS['primary']}20; border:1px solid {COLORS['primary']}50;
  color:{COLORS['primary']}; font-size:9px; font-weight:700;
  display:flex; align-items:center; justify-content:center;
}}

/* ── Page footer ── */
.page-foot {{
  margin-top:40px; padding-top:11px; border-top:1px solid {COLORS['border']};
  display:flex; justify-content:space-between; align-items:center;
}}
.page-foot-txt {{ font-size:8.5px; color:{COLORS['muted']}; letter-spacing:.08em; }}

@page {{ size:A4; margin:0; }}
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Remediation guidance per severity / common finding types
# ─────────────────────────────────────────────────────────────────────────────
_REC_STEPS: dict[str, list[str]] = {
    "critical": [
        "Isolate affected host(s) from the network immediately.",
        "Apply vendor security patch or implement compensating control.",
        "Reset all credentials associated with the affected service.",
        "Conduct forensic review to determine blast radius.",
        "Re-test after patching to confirm vulnerability closure.",
    ],
    "high": [
        "Schedule emergency change window within 48 hours.",
        "Apply available security patches or configuration hardening.",
        "Review access logs for evidence of exploitation.",
        "Re-test after remediation.",
    ],
    "medium": [
        "Apply patch or configuration change in next scheduled maintenance window.",
        "Implement monitoring/alerting for exploitation attempts.",
        "Re-test within 30 days.",
    ],
    "low": [
        "Address during next quarterly hardening cycle.",
        "Consider defense-in-depth control to reduce exposure.",
    ],
    "info": [
        "Review and assess relevance to security posture.",
        "Update asset inventory and security documentation.",
    ],
}

def _rec_steps_html(sev: str) -> str:
    steps = _REC_STEPS.get(sev.lower(), _REC_STEPS["medium"])
    out = ""
    for i, step in enumerate(steps, 1):
        out += (
            f'<div class="rec-step">'
            f'<div class="rec-num">{i}</div>'
            f'<div>{step}</div>'
            f'</div>'
        )
    return out

# ─────────────────────────────────────────────────────────────────────────────
#  HTML builder
# ─────────────────────────────────────────────────────────────────────────────
def build_html(data: dict) -> str:
    summary      = data.get("summary", {})
    findings_raw = data.get("findings", [])
    exploits_raw = data.get("exploits", [])
    patches_raw  = data.get("patches", [])

    generated_at = _ts(data.get("generated_at", ""))
    start_time   = _ts(data.get("start_time", ""))
    mission_name = data.get("mission_name", "SecuNet")
    target_scope = data.get("target_scope") or "Not defined"
    mission_id   = data.get("mission_id", "")

    hosts_disc   = summary.get("hosts_discovered",    0)
    hosts_tested = summary.get("hosts_tested",        0)
    open_cnt     = summary.get("open_findings",       0)
    critical_cnt = summary.get("critical_findings",   0)
    high_cnt     = summary.get("high_findings",       0)
    patches_cnt  = summary.get("patches_deployed",    0)
    coverage_pct = summary.get("attack_coverage_pct", 0)
    detect_pct   = summary.get("detection_score_pct", 0)

    # Unpack payloads + sort findings by severity
    findings = sorted(
        [_payload(f) for f in findings_raw],
        key=lambda f: _SEV_ORDER.get(f.get("severity","info").lower(), 99)
    )
    exploits = [_payload(e) for e in exploits_raw]
    patches  = [_payload(p) for p in patches_raw]

    open_findings  = [f for f in findings if not f.get("remediated")]
    fixed_findings = [f for f in findings if f.get("remediated")]

    risk_color = COLORS["critical"] if critical_cnt > 0 else (COLORS["high"] if high_cnt > 0 else COLORS["low"])
    risk_label = "CRITICAL" if critical_cnt > 0 else ("HIGH" if high_cnt > 0 else "LOW")

    # ── Findings table ────────────────────────────────────────────
    finding_rows = ""
    for f in findings:
        sev   = f.get("severity", "info")
        color = _sev_color(sev)
        status = (
            f'<span style="color:{COLORS["low"]};font-weight:700;font-size:10px;">&#10003; REMEDIATED</span>'
            if f.get("remediated") else
            f'<span style="color:{COLORS["high"]};font-weight:700;font-size:10px;">OPEN</span>'
        )
        finding_rows += f"""
        <tr>
          <td style="font-family:monospace;color:{COLORS['primary']};font-size:10px;">{f.get('host','—')}</td>
          <td>{_badge(sev)}</td>
          <td style="color:{COLORS['white']};font-weight:600;">{f.get('title','—')}</td>
          <td style="color:{COLORS['muted']};max-width:220px;">{f.get('description','—')}</td>
          <td style="font-family:monospace;color:{COLORS['muted']};font-size:10px;">{f.get('cve','—')}</td>
          <td>{status}</td>
        </tr>"""

    if not finding_rows:
        finding_rows = f'<tr><td colspan="6" style="padding:20px;text-align:center;color:{COLORS["muted"]};">No findings recorded.</td></tr>'

    # ── Exploit rows ──────────────────────────────────────────────
    exploit_rows = ""
    for e in exploits[:60]:
        outcome = e.get("outcome", e.get("status","—"))
        ok = str(outcome).lower() in ("success","exploited","confirmed")
        outcome_html = (
            f'<span style="color:{COLORS["critical"]};font-weight:700;font-size:10px;">&#9888; {outcome.upper()}</span>'
            if ok else
            f'<span style="color:{COLORS["muted"]};font-size:10px;">{outcome}</span>'
        )
        exploit_rows += f"""
        <tr>
          <td style="font-family:monospace;color:{COLORS['primary']};font-size:10px;">{e.get('target',e.get('host','—'))}</td>
          <td style="color:{COLORS['text']};">{e.get('technique',e.get('title','—'))}</td>
          <td>{outcome_html}</td>
          <td style="color:{COLORS['muted']};font-family:monospace;font-size:10px;white-space:nowrap;">{_ts(e.get('timestamp',''))}</td>
        </tr>"""

    if not exploit_rows:
        exploit_rows = f'<tr><td colspan="4" style="padding:20px;text-align:center;color:{COLORS["muted"]};">No exploit attempts recorded.</td></tr>'

    # ── Patch rows ────────────────────────────────────────────────
    patch_rows = ""
    for p in patches[:40]:
        patch_rows += f"""
        <tr>
          <td style="font-family:monospace;color:{COLORS['primary']};font-size:10px;">{p.get('host','—')}</td>
          <td style="color:{COLORS['text']};">{p.get('fix_description',p.get('title','—'))}</td>
          <td><span style="color:{COLORS['low']};font-weight:700;font-size:10px;">&#10003; DEPLOYED</span></td>
          <td style="color:{COLORS['muted']};font-family:monospace;font-size:10px;white-space:nowrap;">{_ts(p.get('timestamp',''))}</td>
        </tr>"""

    if not patch_rows:
        patch_rows = f'<tr><td colspan="4" style="padding:20px;text-align:center;color:{COLORS["muted"]};">No patches deployed.</td></tr>'

    # ── Remediation recommendation cards (open findings only) ─────
    rec_cards = ""
    for f in open_findings[:25]:  # cap for readability
        sev   = f.get("severity", "info")
        color = _sev_color(sev)
        rec_cards += f"""
        <div class="rec-card" style="border-left-color:{color};">
          <div class="rec-host">{f.get('host','—')}</div>
          <div class="rec-title">{f.get('title','—')} &nbsp; {_badge(sev)}</div>
          <div class="rec-body" style="margin-bottom:8px;">{f.get('description','No description provided.')}</div>
          {"<div style='font-size:9px;color:"+COLORS['muted']+"letter-spacing:.1em;margin-bottom:4px;'>CVE: "+f.get('cve','—')+"</div>" if f.get('cve') else ""}
          <div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:{COLORS['muted']};font-weight:700;margin:8px 0 4px;">Recommended Actions</div>
          {_rec_steps_html(sev)}
        </div>"""

    if not rec_cards:
        rec_cards = f'<div style="padding:20px;text-align:center;color:{COLORS["muted"]};background:{COLORS["bg_card"]};border-radius:7px;border:1px solid {COLORS["border"]};">All findings have been remediated. No outstanding actions required.</div>'

    # ── Severity distribution bar ─────────────────────────────────
    total = len(findings) or 1
    sev_counts = {s: sum(1 for f in findings if f.get("severity","").lower()==s) for s in ["critical","high","medium","low","info"]}
    sev_bar = ""
    for sev, cnt in sev_counts.items():
        if cnt > 0:
            w = round(cnt / total * 100)
            sev_bar += f'<div style="width:{w}%;background:{_sev_color(sev)};height:100%;display:inline-block;" title="{sev}: {cnt}"></div>'

    # Build these outside the main f-string to avoid nested quote escaping
    sev_pills_html = "".join(
        f'<span>{_badge(s)}&nbsp;<span style="color:{COLORS["muted"]};font-size:10px;">{c}</span></span>'
        for s, c in sev_counts.items() if c > 0
    )
    fixed_findings_rows = "".join(
        f'<tr>'
        f'<td style="font-family:monospace;color:{COLORS["primary"]};font-size:10px;">{f.get("host","—")}</td>'
        f'<td style="color:{COLORS["text"]};">{f.get("title","—")}</td>'
        f'<td>{_badge(f.get("severity","info"))}</td>'
        f'<td><span style="color:{COLORS["low"]};font-weight:700;font-size:10px;">&#10003; REMEDIATED</span></td>'
        f'</tr>'
        for f in fixed_findings
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>{CSS}</style>
</head>
<body>

<!-- ═══════════════════════════════════════ COVER -->
<div class="cover">
  <div class="cover-stripe"></div>
  <div class="cover-grid"></div>
  <div class="cover-body">

    <div class="logo-row">
      <div class="logo-hex">SN</div>
      <div>
        <div class="logo-name">SECUNET</div>
        <div class="logo-sub">Autonomous Security Operations Platform</div>
      </div>
    </div>

    <div class="cover-main">
      <div class="eyebrow">Penetration Test &amp; Remediation Report</div>
      <div class="cover-h1">{mission_name}</div>
      <div class="cover-h2">Security Assessment Report</div>
      <div class="cover-rule"></div>
      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">Target Scope</span>
          <span class="meta-val">{target_scope}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Classification</span>
          <span class="meta-val">CONFIDENTIAL</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Engagement Start</span>
          <span class="meta-val">{start_time}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Report Generated</span>
          <span class="meta-val">{generated_at}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Mission ID</span>
          <span class="meta-val" style="font-size:10px;">{mission_id[:20] if mission_id else '—'}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Total Findings</span>
          <span class="meta-val" style="color:{risk_color};">{len(findings)}</span>
        </div>
      </div>
    </div>

    <div class="cover-foot">
      <div class="cover-foot-txt">
        SECUNET PLATFORM — AUTONOMOUS PENETRATION TESTING<br>
        <span style="font-size:8.5px;">This report is confidential. Distribute only to authorised personnel.</span>
      </div>
      <div class="risk-pill" style="background:{risk_color}18;border:1px solid {risk_color}60;color:{risk_color};">
        RISK LEVEL: {risk_label}
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════ EXECUTIVE SUMMARY -->
<div class="page">
  <div class="page-hdr">
    <span class="page-hdr-left">Executive Summary</span>
    <span class="page-hdr-right">{mission_name} &nbsp;·&nbsp; {generated_at}</span>
  </div>

  <div class="section">
    <div class="sec-title">Assessment Overview</div>
    <p style="color:{COLORS['muted']};font-size:12px;line-height:1.7;max-width:680px;">
      SecuNet conducted an autonomous penetration test against <strong style="color:{COLORS['text']};">{target_scope}</strong>.
      The assessment exercised reconnaissance, exploitation, detection validation, and remediation workflows
      across the in-scope environment. This report documents all findings, exploit outcomes,
      patches deployed, and outstanding remediation actions required.
    </p>
  </div>

  <div class="section">
    <div class="sec-title">Key Metrics</div>
    <div class="metrics">
      <div class="m-card">
        <div class="m-label">Hosts Discovered</div>
        <div class="m-val" style="color:{COLORS['primary']};">{hosts_disc}</div>
        <div class="m-sub">{hosts_tested} tested</div>
      </div>
      <div class="m-card">
        <div class="m-label">Open Findings</div>
        <div class="m-val" style="color:{COLORS['critical'] if open_cnt>0 else COLORS['low']};">{open_cnt}</div>
        <div class="m-sub">{patches_cnt} remediated</div>
      </div>
      <div class="m-card">
        <div class="m-label">Critical &nbsp;/&nbsp; High</div>
        <div class="m-val" style="color:{COLORS['critical'] if critical_cnt>0 else COLORS['high']};">
          {critical_cnt}<span style="font-size:16px;color:{COLORS['muted']};">&nbsp;/&nbsp;</span>{high_cnt}
        </div>
        <div class="m-sub">{len(findings)-critical_cnt-high_cnt} med / low / info</div>
      </div>
      <div class="m-card">
        <div class="m-label">Exploit Attempts</div>
        <div class="m-val" style="color:{COLORS['high']};">{len(exploits)}</div>
        <div class="m-sub">{len(patches)} patches deployed</div>
      </div>

      <div class="m-card m-wide">
        <div class="m-label">ATT&amp;CK Coverage</div>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
          <span class="m-val" style="font-size:20px;color:{COLORS['primary']};">{coverage_pct}%</span>
          <span style="font-size:10px;color:{COLORS['muted']};">techniques exercised</span>
        </div>
        {_bar(coverage_pct, COLORS['primary'])}
      </div>
      <div class="m-card m-wide">
        <div class="m-label">Detection Score</div>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
          <span class="m-val" style="font-size:20px;color:{COLORS['medium']};">{detect_pct}%</span>
          <span style="font-size:10px;color:{COLORS['muted']};">attacks detected by blue team controls</span>
        </div>
        {_bar(detect_pct, COLORS['medium'])}
      </div>
    </div>
  </div>

  {("" if not findings else
  f"""<div class="section">
    <div class="sec-title">Severity Distribution</div>
    <div style="display:flex;gap:16px;align-items:center;margin-bottom:10px;">{sev_pills_html}</div>
    <div style="height:12px;border-radius:4px;overflow:hidden;background:{COLORS['border']};display:flex;">{sev_bar}</div>
  </div>""")}

  <div class="page-foot">
    <span class="page-foot-txt">SECUNET &nbsp;·&nbsp; {mission_name} &nbsp;·&nbsp; CONFIDENTIAL</span>
    <span class="page-foot-txt">Generated {generated_at}</span>
  </div>
</div>

<!-- ═══════════════════════════════════════ FINDINGS -->
<div class="page">
  <div class="page-hdr">
    <span class="page-hdr-left">Vulnerability Findings</span>
    <span class="page-hdr-right">{len(findings)} findings &nbsp;·&nbsp; {len(open_findings)} open &nbsp;·&nbsp; {len(fixed_findings)} remediated</span>
  </div>

  <div class="section">
    <div class="sec-title">All Findings</div>
    <table class="tbl">
      <thead>
        <tr>
          <th>Host</th>
          <th>Severity</th>
          <th>Title</th>
          <th>Description</th>
          <th>CVE</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>{finding_rows}</tbody>
    </table>
  </div>

  <div class="page-foot">
    <span class="page-foot-txt">SECUNET &nbsp;·&nbsp; {mission_name} &nbsp;·&nbsp; CONFIDENTIAL</span>
    <span class="page-foot-txt">Generated {generated_at}</span>
  </div>
</div>

<!-- ═══════════════════════════════════════ EXPLOIT ATTEMPTS -->
<div class="page">
  <div class="page-hdr">
    <span class="page-hdr-left">Attack &amp; Exploit Log</span>
    <span class="page-hdr-right">{len(exploits)} attempts recorded</span>
  </div>

  <div class="section">
    <div class="sec-title">Exploit Attempts</div>
    <table class="tbl">
      <thead>
        <tr>
          <th>Target</th>
          <th>Technique / Module</th>
          <th>Outcome</th>
          <th>Timestamp</th>
        </tr>
      </thead>
      <tbody>{exploit_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <div class="sec-title">Patches &amp; Fixes Deployed</div>
    <table class="tbl">
      <thead>
        <tr>
          <th>Host</th>
          <th>Fix Applied</th>
          <th>Status</th>
          <th>Timestamp</th>
        </tr>
      </thead>
      <tbody>{patch_rows}</tbody>
    </table>
  </div>

  <div class="page-foot">
    <span class="page-foot-txt">SECUNET &nbsp;·&nbsp; {mission_name} &nbsp;·&nbsp; CONFIDENTIAL</span>
    <span class="page-foot-txt">Generated {generated_at}</span>
  </div>
</div>

<!-- ═══════════════════════════════════════ REMEDIATION PLAN -->
<div class="page">
  <div class="page-hdr">
    <span class="page-hdr-left">Remediation Plan</span>
    <span class="page-hdr-right">{len(open_findings)} open actions required</span>
  </div>

  <div class="section">
    <div class="sec-title">Outstanding Remediation Actions</div>
    <p style="color:{COLORS['muted']};font-size:11px;margin-bottom:16px;line-height:1.7;">
      The following vulnerabilities remain open and require remediation before this engagement can be closed.
      Each item includes targeted remediation steps ordered by severity.
      Critical and High findings should be addressed immediately.
    </p>
    {rec_cards}
  </div>

  {("" if not fixed_findings else
  f"""<div class="section">
    <div class="sec-title">Remediation Completed</div>
    <table class="tbl">
      <thead><tr><th>Host</th><th>Finding</th><th>Severity</th><th>Status</th></tr></thead>
      <tbody>{fixed_findings_rows}</tbody>
    </table>
  </div>""")}

  <div class="page-foot">
    <span class="page-foot-txt">SECUNET &nbsp;·&nbsp; {mission_name} &nbsp;·&nbsp; CONFIDENTIAL</span>
    <span class="page-foot-txt">Generated {generated_at}</span>
  </div>
</div>

<!-- ═══════════════════════════════════════ CLOSING -->
<div class="page">
  <div class="page-hdr">
    <span class="page-hdr-left">Conclusion &amp; Sign-off</span>
    <span class="page-hdr-right">{mission_name}</span>
  </div>

  <div class="section">
    <div class="sec-title">Assessment Conclusion</div>
    <p style="color:{COLORS['muted']};font-size:12px;line-height:1.75;max-width:680px;margin-bottom:18px;">
      This penetration test identified <strong style="color:{COLORS['text']};">{len(findings)} vulnerabilities</strong>
      across <strong style="color:{COLORS['text']};">{hosts_tested} hosts</strong> in scope.
      {"Of these, <strong style='color:"+COLORS["critical"]+";'>"+str(critical_cnt)+" critical</strong> and <strong style='color:"+COLORS["high"]+";'>"+str(high_cnt)+" high</strong> severity issues require immediate attention." if (critical_cnt+high_cnt)>0 else "No critical or high severity issues were identified."}
      &nbsp;{patches_cnt} finding{"s" if patches_cnt!=1 else ""} {"have" if patches_cnt!=1 else "has"} been remediated during this engagement.
      {str(len(open_findings))+" finding"+ ("s remain" if len(open_findings)!=1 else " remains") +" open and" if open_findings else "All findings have been resolved and"}
      {"require further action as detailed in the Remediation Plan section." if open_findings else "this engagement may be formally closed."}
    </p>
    <p style="color:{COLORS['muted']};font-size:12px;line-height:1.75;max-width:680px;">
      ATT&amp;CK framework coverage achieved: <strong style="color:{COLORS['primary']};">{coverage_pct}%</strong>.
      Blue team detection rate: <strong style="color:{COLORS['medium']};">{detect_pct}%</strong>.
      {"Detection gaps identified — consider tuning SIEM rules and endpoint monitoring." if detect_pct < 70 else "Detection posture is adequate for the tested attack surface."}
    </p>
  </div>

  <div class="section">
    <div class="sec-title">Report Metadata</div>
    <table class="tbl">
      <tbody>
        <tr><td style="color:{COLORS['muted']};width:180px;">Mission Name</td><td style="font-family:monospace;">{mission_name}</td></tr>
        <tr><td style="color:{COLORS['muted']};">Mission ID</td><td style="font-family:monospace;font-size:10px;">{mission_id}</td></tr>
        <tr><td style="color:{COLORS['muted']};">Target Scope</td><td style="font-family:monospace;">{target_scope}</td></tr>
        <tr><td style="color:{COLORS['muted']};">Engagement Start</td><td style="font-family:monospace;">{start_time}</td></tr>
        <tr><td style="color:{COLORS['muted']};">Report Generated</td><td style="font-family:monospace;">{generated_at}</td></tr>
        <tr><td style="color:{COLORS['muted']};">Platform</td><td>SecuNet Autonomous Security Operations v1.0</td></tr>
        <tr><td style="color:{COLORS['muted']};">Classification</td><td><strong style="color:{risk_color};">CONFIDENTIAL — {risk_label} RISK</strong></td></tr>
      </tbody>
    </table>
  </div>

  <div style="margin-top:36px;padding:24px;background:{COLORS['bg_card']};border:1px solid {COLORS['border']};border-radius:7px;">
    <div style="font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:{COLORS['muted']};font-weight:700;margin-bottom:16px;">Authorised By</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;">
      <div>
        <div style="height:1px;background:{COLORS['border']};margin-bottom:8px;"></div>
        <div style="font-size:10px;color:{COLORS['muted']};">Lead Security Engineer</div>
        <div style="font-size:10px;color:{COLORS['muted']};margin-top:2px;">Date: _______________</div>
      </div>
      <div>
        <div style="height:1px;background:{COLORS['border']};margin-bottom:8px;"></div>
        <div style="font-size:10px;color:{COLORS['muted']};">Client Representative</div>
        <div style="font-size:10px;color:{COLORS['muted']};margin-top:2px;">Date: _______________</div>
      </div>
    </div>
  </div>

  <div class="page-foot">
    <span class="page-foot-txt">SECUNET &nbsp;·&nbsp; {mission_name} &nbsp;·&nbsp; CONFIDENTIAL</span>
    <span class="page-foot-txt">Generated {generated_at}</span>
  </div>
</div>

</body>
</html>"""

    return html


def build_pdf(data: dict) -> bytes:
    """Render the HTML report to PDF bytes via weasyprint."""
    import weasyprint  # type: ignore
    return weasyprint.HTML(string=build_html(data)).write_pdf()
