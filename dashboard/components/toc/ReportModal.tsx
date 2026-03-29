"use client";
import { useState, useCallback } from "react";
import {
  X, Download, FileText, AlertTriangle,
  ShieldCheck, Activity, Target, Loader2,
} from "lucide-react";

const CC = process.env.NEXT_PUBLIC_CC_URL ?? "http://localhost:8001";

type Severity = "critical" | "high" | "medium" | "low" | "info";

const SEV_COLOR: Record<Severity, string> = {
  critical: "#FF3B30",
  high:     "#FF6B35",
  medium:   "#FFB300",
  low:      "#00C851",
  info:     "#94A3B8",
};

const SEV_BG: Record<Severity, string> = {
  critical: "rgba(255,59,48,.12)",
  high:     "rgba(255,107,53,.10)",
  medium:   "rgba(255,179,0,.10)",
  low:      "rgba(0,200,81,.08)",
  info:     "rgba(148,163,184,.08)",
};

interface ReportData {
  mission_name:  string;
  target_scope:  string;
  generated_at:  string;
  start_time:    string;
  summary: {
    hosts_discovered:    number;
    hosts_tested:        number;
    open_findings:       number;
    critical_findings:   number;
    high_findings:       number;
    patches_deployed:    number;
    attack_coverage_pct: number;
    detection_score_pct: number;
  };
  findings: {
    payload?: {
      host?:        string;
      title?:       string;
      severity?:    string;
      description?: string;
      cve?:         string;
      remediated?:  boolean;
    };
    host?:        string;
    title?:       string;
    severity?:    string;
    description?: string;
    cve?:         string;
    remediated?:  boolean;
  }[];
}

function SevBadge({ sev }: { sev: string }) {
  const s = (sev ?? "info").toLowerCase() as Severity;
  const c = SEV_COLOR[s] ?? SEV_COLOR.info;
  const b = SEV_BG[s]    ?? SEV_BG.info;
  return (
    <span style={{
      display: "inline-block", padding: "1px 7px", borderRadius: 3,
      background: b, border: `1px solid ${c}60`,
      color: c, fontSize: 9, fontWeight: 700,
      letterSpacing: "0.07em", textTransform: "uppercase",
    }}>
      {sev}
    </span>
  );
}

function MetricCard({
  label, value, sub, color,
}: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div style={{
      background: "#111827", border: "1px solid #1E2A3A",
      borderRadius: 8, padding: "14px 16px",
    }}>
      <div style={{ fontSize: 9, letterSpacing: "0.15em", textTransform: "uppercase", color: "#64748B", fontWeight: 700, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 900, lineHeight: 1, color: color ?? "#E2E8F0", marginBottom: sub ? 6 : 0 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 10, color: "#64748B" }}>{sub}</div>}
    </div>
  );
}

function BarMeter({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ background: "#1E2A3A", borderRadius: 4, height: 6, width: "100%" }}>
      <div style={{ background: color, borderRadius: 4, height: 6, width: `${Math.max(0, Math.min(100, pct))}%`, transition: "width .4s" }} />
    </div>
  );
}

interface Props {
  onClose: () => void;
}

export default function ReportModal({ onClose }: Props) {
  const [report,      setReport]      = useState<ReportData | null>(null);
  const [loading,     setLoading]     = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [generated,   setGenerated]   = useState(false);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CC}/report`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json() as ReportData;
      setReport(data);
      setGenerated(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, []);

  const downloadPdf = useCallback(async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${CC}/report/pdf`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = res.headers.get("content-disposition")
        ?.split("filename=")[1]?.replace(/"/g, "")
        ?? "secunet-report.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setDownloading(false);
    }
  }, []);

  const findings = report
    ? report.findings.map((f) => f.payload ?? f)
    : [];

  const open  = findings.filter((f) => !f.remediated);
  const fixed = findings.filter((f) => f.remediated);

  const sevCounts: Record<string, number> = {};
  for (const f of findings) {
    const s = (f.severity ?? "info").toLowerCase();
    sevCounts[s] = (sevCounts[s] ?? 0) + 1;
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "rgba(0,0,0,.75)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "24px",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "#0A0E1A", border: "1px solid #1E2A3A", borderRadius: 12,
        width: "100%", maxWidth: 860, maxHeight: "90vh",
        display: "flex", flexDirection: "column",
        boxShadow: "0 25px 80px rgba(0,0,0,.6)",
        overflow: "hidden",
      }}>

        {/* ── Header ── */}
        <div style={{
          padding: "16px 20px", borderBottom: "1px solid #1E2A3A",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "#0D1520", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 7,
              background: "rgba(0,212,255,.1)", border: "1px solid rgba(0,212,255,.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <FileText style={{ width: 15, height: 15, color: "#00D4FF" }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", letterSpacing: ".02em" }}>
                Mission Report
              </div>
              <div style={{ fontSize: 10, color: "#64748B", fontFamily: "monospace" }}>
                {report ? report.mission_name : "Generate to preview"}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {generated && (
              <button
                onClick={downloadPdf}
                disabled={downloading}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "7px 14px", borderRadius: 6,
                  background: downloading ? "rgba(0,212,255,.05)" : "rgba(0,212,255,.12)",
                  border: "1px solid rgba(0,212,255,.4)",
                  color: "#00D4FF", fontSize: 11, fontWeight: 700,
                  cursor: downloading ? "not-allowed" : "pointer",
                  letterSpacing: ".08em", transition: "all .15s",
                }}
              >
                {downloading
                  ? <Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} />
                  : <Download style={{ width: 13, height: 13 }} />
                }
                {downloading ? "RENDERING PDF…" : "DOWNLOAD PDF"}
              </button>
            )}
            {!generated && (
              <button
                onClick={fetchReport}
                disabled={loading}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "7px 14px", borderRadius: 6,
                  background: loading ? "rgba(0,212,255,.05)" : "rgba(0,212,255,.12)",
                  border: "1px solid rgba(0,212,255,.4)",
                  color: "#00D4FF", fontSize: 11, fontWeight: 700,
                  cursor: loading ? "not-allowed" : "pointer",
                  letterSpacing: ".08em",
                }}
              >
                {loading
                  ? <Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} />
                  : <Activity style={{ width: 13, height: 13 }} />
                }
                {loading ? "GENERATING…" : "GENERATE REPORT"}
              </button>
            )}
            {generated && (
              <button
                onClick={fetchReport}
                disabled={loading}
                title="Refresh data"
                style={{
                  padding: "7px 10px", borderRadius: 6,
                  background: "rgba(255,255,255,.03)", border: "1px solid #1E2A3A",
                  color: "#64748B", cursor: "pointer", fontSize: 10, fontWeight: 700,
                }}
              >
                {loading ? <Loader2 style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} /> : "↺"}
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                padding: "7px 8px", borderRadius: 6,
                background: "rgba(255,255,255,.03)", border: "1px solid #1E2A3A",
                color: "#64748B", cursor: "pointer",
              }}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </div>

        {/* ── Body ── */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>

          {/* Empty state */}
          {!generated && !loading && (
            <div style={{
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              minHeight: 320, gap: 14, color: "#64748B",
            }}>
              <div style={{
                width: 60, height: 60, borderRadius: 12,
                background: "rgba(0,212,255,.06)", border: "1px solid rgba(0,212,255,.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <FileText style={{ width: 28, height: 28, color: "#00D4FF", opacity: .5 }} />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#94A3B8" }}>No report generated yet</div>
              <div style={{ fontSize: 11, color: "#64748B", textAlign: "center", maxWidth: 320 }}>
                Click <strong style={{ color: "#00D4FF" }}>Generate Report</strong> to compile findings,
                exploits, and remediation data from this session into a structured report.
              </div>
            </div>
          )}

          {loading && (
            <div style={{
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              minHeight: 320, gap: 14, color: "#64748B",
            }}>
              <Loader2 style={{ width: 28, height: 28, color: "#00D4FF", animation: "spin 1s linear infinite" }} />
              <div style={{ fontSize: 12, color: "#94A3B8" }}>Compiling mission data…</div>
            </div>
          )}

          {error && (
            <div style={{
              margin: "12px 0", padding: "12px 16px", borderRadius: 7,
              background: "rgba(255,59,48,.08)", border: "1px solid rgba(255,59,48,.3)",
              color: "#FF3B30", fontSize: 12, display: "flex", gap: 8, alignItems: "center",
            }}>
              <AlertTriangle style={{ width: 14, height: 14, flexShrink: 0 }} />
              {error}
            </div>
          )}

          {report && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

              {/* Mission meta */}
              <div style={{
                padding: "14px 16px", background: "#111827",
                border: "1px solid #1E2A3A", borderRadius: 8,
                display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px 20px",
              }}>
                {[
                  ["Mission",    report.mission_name],
                  ["Scope",      report.target_scope || "—"],
                  ["Generated",  new Date(report.generated_at).toLocaleString()],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: 9, letterSpacing: ".15em", textTransform: "uppercase", color: "#64748B", fontWeight: 700, marginBottom: 3 }}>{k}</div>
                    <div style={{ fontSize: 11, fontFamily: "monospace", color: "#E2E8F0" }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* Metric cards */}
              <div>
                <div style={{ fontSize: 10, letterSpacing: ".2em", textTransform: "uppercase", color: "#00D4FF", fontWeight: 700, marginBottom: 12 }}>
                  KEY METRICS
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 10 }}>
                  <MetricCard label="Hosts Discovered" value={report.summary.hosts_discovered} sub={`${report.summary.hosts_tested} tested`} color="#00D4FF" />
                  <MetricCard label="Open Findings"    value={report.summary.open_findings}    sub={`${report.summary.patches_deployed} remediated`} color={report.summary.open_findings > 0 ? "#FF3B30" : "#00C851"} />
                  <MetricCard label="Critical / High"  value={`${report.summary.critical_findings} / ${report.summary.high_findings}`} color={report.summary.critical_findings > 0 ? "#FF3B30" : "#FF6B35"} />
                  <MetricCard label="Exploit Attempts" value={report.findings.length} color="#FF6B35" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ background: "#111827", border: "1px solid #1E2A3A", borderRadius: 8, padding: "14px 16px" }}>
                    <div style={{ fontSize: 9, letterSpacing: ".15em", textTransform: "uppercase", color: "#64748B", fontWeight: 700, marginBottom: 8 }}>ATT&CK Coverage</div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 8 }}>
                      <span style={{ fontSize: 22, fontWeight: 900, color: "#00D4FF" }}>{report.summary.attack_coverage_pct}%</span>
                      <span style={{ fontSize: 10, color: "#64748B" }}>techniques exercised</span>
                    </div>
                    <BarMeter pct={report.summary.attack_coverage_pct} color="#00D4FF" />
                  </div>
                  <div style={{ background: "#111827", border: "1px solid #1E2A3A", borderRadius: 8, padding: "14px 16px" }}>
                    <div style={{ fontSize: 9, letterSpacing: ".15em", textTransform: "uppercase", color: "#64748B", fontWeight: 700, marginBottom: 8 }}>Detection Score</div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 8 }}>
                      <span style={{ fontSize: 22, fontWeight: 900, color: "#FFB300" }}>{report.summary.detection_score_pct}%</span>
                      <span style={{ fontSize: 10, color: "#64748B" }}>attacks detected</span>
                    </div>
                    <BarMeter pct={report.summary.detection_score_pct} color="#FFB300" />
                  </div>
                </div>
              </div>

              {/* Severity breakdown */}
              {findings.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, letterSpacing: ".2em", textTransform: "uppercase", color: "#00D4FF", fontWeight: 700, marginBottom: 12 }}>
                    SEVERITY BREAKDOWN &nbsp;
                    <span style={{ color: "#64748B", fontWeight: 400, fontSize: 10 }}>— {findings.length} total</span>
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                    {(["critical","high","medium","low","info"] as Severity[])
                      .filter((s) => sevCounts[s] > 0)
                      .map((s) => (
                        <div key={s} style={{
                          padding: "6px 12px", borderRadius: 6,
                          background: SEV_BG[s], border: `1px solid ${SEV_COLOR[s]}40`,
                          display: "flex", alignItems: "center", gap: 6,
                        }}>
                          <span style={{ fontSize: 20, fontWeight: 900, color: SEV_COLOR[s], lineHeight: 1 }}>{sevCounts[s]}</span>
                          <span style={{ fontSize: 9, color: SEV_COLOR[s], fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase" }}>{s}</span>
                        </div>
                      ))
                    }
                  </div>
                  {/* Stacked bar */}
                  <div style={{ height: 8, borderRadius: 4, overflow: "hidden", display: "flex", background: "#1E2A3A" }}>
                    {(["critical","high","medium","low","info"] as Severity[]).map((s) => {
                      const cnt = sevCounts[s] ?? 0;
                      if (!cnt) return null;
                      return (
                        <div key={s} style={{ width: `${cnt/findings.length*100}%`, background: SEV_COLOR[s], height: "100%" }} title={`${s}: ${cnt}`} />
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Findings table */}
              {findings.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, letterSpacing: ".2em", textTransform: "uppercase", color: "#00D4FF", fontWeight: 700, marginBottom: 12 }}>
                    FINDINGS &nbsp;
                    <span style={{ color: "#FF6B35", fontWeight: 700 }}>{open.length} open</span>
                    <span style={{ color: "#64748B" }}> &nbsp;·&nbsp; </span>
                    <span style={{ color: "#00C851", fontWeight: 700 }}>{fixed.length} remediated</span>
                  </div>
                  <div style={{ background: "#111827", border: "1px solid #1E2A3A", borderRadius: 8, overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                      <thead>
                        <tr style={{ background: "#0D1520" }}>
                          {["Host","Severity","Title","CVE","Status"].map((h) => (
                            <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 8.5, letterSpacing: ".15em", textTransform: "uppercase", color: "#64748B", fontWeight: 700, borderBottom: "1px solid #1E2A3A", whiteSpace: "nowrap" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {findings.map((f, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid rgba(30,42,58,.5)" }}>
                            <td style={{ padding: "7px 10px", fontFamily: "monospace", color: "#00D4FF", fontSize: 10 }}>{f.host ?? "—"}</td>
                            <td style={{ padding: "7px 10px" }}><SevBadge sev={f.severity ?? "info"} /></td>
                            <td style={{ padding: "7px 10px", color: "#E2E8F0", fontWeight: 600 }}>{f.title ?? "—"}</td>
                            <td style={{ padding: "7px 10px", fontFamily: "monospace", color: "#64748B", fontSize: 10 }}>{f.cve ?? "—"}</td>
                            <td style={{ padding: "7px 10px", whiteSpace: "nowrap" }}>
                              {f.remediated
                                ? <span style={{ color: "#00C851", fontSize: 10, fontWeight: 700 }}>✓ PATCHED</span>
                                : <span style={{ color: "#FF6B35", fontSize: 10, fontWeight: 700 }}>OPEN</span>
                              }
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Remediation summary */}
              {open.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, letterSpacing: ".2em", textTransform: "uppercase", color: "#FF6B35", fontWeight: 700, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
                    <AlertTriangle style={{ width: 12, height: 12 }} />
                    OUTSTANDING REMEDIATION — {open.length} action{open.length !== 1 ? "s" : ""} required
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {open.slice(0, 20).map((f, i) => {
                      const sev = (f.severity ?? "info").toLowerCase() as Severity;
                      const c   = SEV_COLOR[sev] ?? SEV_COLOR.info;
                      return (
                        <div key={i} style={{
                          padding: "12px 14px", background: "#111827",
                          border: "1px solid #1E2A3A", borderRadius: 7,
                          borderLeft: `3px solid ${c}`,
                        }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                            <span style={{ fontFamily: "monospace", fontSize: 10, color: "#00D4FF" }}>{f.host ?? "—"}</span>
                            <SevBadge sev={f.severity ?? "info"} />
                            <span style={{ fontSize: 11, fontWeight: 700, color: "#fff" }}>{f.title ?? "—"}</span>
                          </div>
                          {f.description && (
                            <div style={{ fontSize: 10.5, color: "#94A3B8", lineHeight: 1.6 }}>{f.description}</div>
                          )}
                          {f.cve && (
                            <div style={{ fontSize: 9, color: "#64748B", marginTop: 4, fontFamily: "monospace" }}>CVE: {f.cve}</div>
                          )}
                        </div>
                      );
                    })}
                    {open.length > 20 && (
                      <div style={{ fontSize: 10, color: "#64748B", textAlign: "center", padding: "8px 0" }}>
                        + {open.length - 20} more findings in the full PDF report
                      </div>
                    )}
                  </div>
                </div>
              )}

              {open.length === 0 && fixed.length > 0 && (
                <div style={{
                  padding: "16px", borderRadius: 8,
                  background: "rgba(0,200,81,.06)", border: "1px solid rgba(0,200,81,.25)",
                  display: "flex", alignItems: "center", gap: 10,
                }}>
                  <ShieldCheck style={{ width: 18, height: 18, color: "#00C851", flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#00C851" }}>All findings remediated</div>
                    <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>This engagement is ready to be formally closed.</div>
                  </div>
                </div>
              )}

              {/* Download CTA */}
              <div style={{
                padding: "16px 18px", borderRadius: 8,
                background: "rgba(0,212,255,.05)", border: "1px solid rgba(0,212,255,.2)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#E2E8F0" }}>Full PDF Report</div>
                  <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>
                    Includes cover page, executive summary, all findings, exploit log, and remediation plan.
                  </div>
                </div>
                <button
                  onClick={downloadPdf}
                  disabled={downloading}
                  style={{
                    display: "flex", alignItems: "center", gap: 7,
                    padding: "9px 18px", borderRadius: 7,
                    background: downloading ? "rgba(0,212,255,.05)" : "#00D4FF18",
                    border: "1px solid #00D4FF60",
                    color: "#00D4FF", fontSize: 11, fontWeight: 700,
                    cursor: downloading ? "not-allowed" : "pointer",
                    letterSpacing: ".08em", whiteSpace: "nowrap",
                  }}
                >
                  {downloading
                    ? <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
                    : <Download style={{ width: 14, height: 14 }} />
                  }
                  {downloading ? "RENDERING…" : "DOWNLOAD PDF"}
                </button>
              </div>

            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
