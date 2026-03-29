const AGENTS = [
  { label: "Recon",     color: "#00D4FF" },
  { label: "Exploit",   color: "#FF3B30" },
  { label: "Detect",    color: "#FFB300" },
  { label: "Remediate", color: "#00C851" },
  { label: "Monitor",   color: "#9B59B6" },
];

const W         = 900;
const H         = 420;

// Top row
const ROW1_Y    = 55;
const BOX_H     = 54;

// Dashboard
const DASH_X    = 32;
const DASH_W    = 178;

// Command Center
const CC_X      = 350;
const CC_W      = 210;

// target_net badge
const TGT_X     = 730;
const TGT_W     = 138;

// command_net bus
const BUS_Y     = 200;

// Agent row
const AGENT_Y   = 285;
const AGENT_H   = 56;
const AGENT_W   = 116;
const PAD       = 32;
const SLOT      = (W - PAD * 2) / 5;

const agentCx   = AGENTS.map((_, i) => PAD + SLOT * i + SLOT / 2);

const ccCx      = CC_X + CC_W / 2;
const ccBottom  = ROW1_Y + BOX_H;

export default function ArchitectureDiagram() {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full h-auto"
    >
      <defs>
        <pattern id="archgrid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" stroke="#1E2D47" strokeWidth="0.35" fill="none" />
        </pattern>
        {/* Cyan glow filter for CC */}
        <filter id="cyanglow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Background */}
      <rect width={W} height={H} fill="#080C14" rx="12" />
      <rect width={W} height={H} fill="url(#archgrid)" rx="12" />

      {/* ── WebSocket line — drawn first so boxes sit on top ── */}
      <line
        x1={DASH_X + DASH_W + 2} y1={ROW1_Y + BOX_H / 2}
        x2={CC_X - 2}             y2={ROW1_Y + BOX_H / 2}
        stroke="#00D4FF" strokeWidth="1.5" strokeDasharray="5 4" opacity="0.6"
      />
      {/* arrowheads */}
      <polygon fill="#00D4FF" opacity="0.7"
        points={`${CC_X - 2},${ROW1_Y + BOX_H / 2 - 5} ${CC_X + 7},${ROW1_Y + BOX_H / 2} ${CC_X - 2},${ROW1_Y + BOX_H / 2 + 5}`} />
      <polygon fill="#00D4FF" opacity="0.7"
        points={`${DASH_X + DASH_W + 2},${ROW1_Y + BOX_H / 2 - 5} ${DASH_X + DASH_W - 7},${ROW1_Y + BOX_H / 2} ${DASH_X + DASH_W + 2},${ROW1_Y + BOX_H / 2 + 5}`} />
      <text
        x={(DASH_X + DASH_W + CC_X) / 2} y={ROW1_Y + BOX_H / 2 - 9}
        textAnchor="middle" fill="#00D4FF" fontSize="8" fontFamily="monospace" opacity="0.75"
      >WebSocket</text>

      {/* ── target_net dashed line — behind boxes ── */}
      <line
        x1={CC_X + CC_W + 2} y1={ROW1_Y + BOX_H / 2}
        x2={TGT_X - 2}        y2={ROW1_Y + BOX_H / 2}
        stroke="#FF3B30" strokeWidth="1.2" strokeDasharray="4 4" opacity="0.45"
      />

      {/* ── CC → BUS vertical stem ── */}
      <line
        x1={ccCx} y1={ccBottom}
        x2={ccCx} y2={BUS_Y}
        stroke="#2A3D5A" strokeWidth="1.5"
      />

      {/* ── Horizontal bus — spans all agent centers ── */}
      <line
        x1={agentCx[0]} y1={BUS_Y}
        x2={agentCx[4]} y2={BUS_Y}
        stroke="#2A3D5A" strokeWidth="1.5"
      />

      {/* ── Drop lines from bus to agent box tops ── */}
      {agentCx.map((cx, i) => (
        <line
          key={i}
          x1={cx} y1={BUS_Y}
          x2={cx} y2={AGENT_Y - 6}   /* stop 6px above box */
          stroke="#2A3D5A" strokeWidth="1.5"
        />
      ))}

      {/* ── Junction dots on bus (where drops branch off) ── */}
      {agentCx.map((cx, i) => (
        <circle key={i} cx={cx} cy={BUS_Y} r="3.5" fill="#2A3D5A" stroke="#3A5070" strokeWidth="1" />
      ))}

      {/* Center junction dot (CC stem meets bus) */}
      <circle cx={ccCx} cy={BUS_Y} r="3.5" fill="#2A3D5A" stroke="#3A5070" strokeWidth="1" />

      {/* ── command_net label ── */}
      <rect
        x={ccCx - 56} y={BUS_Y - 13}
        width={112} height={22} rx="4"
        fill="#111C2E" stroke="#2A3D5A" strokeWidth="1"
      />
      <text x={ccCx} y={BUS_Y + 3} textAnchor="middle"
        fill="#5A7090" fontSize="8.5" fontFamily="monospace" letterSpacing="1.5">
        command_net
      </text>

      {/* ── Dashboard box ── */}
      <rect x={DASH_X} y={ROW1_Y} width={DASH_W} height={BOX_H}
        rx="7" fill="#0D1321" stroke="#2A3D5A" strokeWidth="1.5" />
      <text x={DASH_X + DASH_W / 2} y={ROW1_Y + 22}
        textAnchor="middle" fill="#E8EDF5" fontSize="11" fontFamily="monospace" fontWeight="700">
        Dashboard
      </text>
      <text x={DASH_X + DASH_W / 2} y={ROW1_Y + 38}
        textAnchor="middle" fill="#5A7090" fontSize="8.5" fontFamily="monospace">
        Next.js · WebSocket client
      </text>

      {/* ── Command Center box ── */}
      <rect x={CC_X} y={ROW1_Y} width={CC_W} height={BOX_H}
        rx="7" fill="#091520" stroke="#00D4FF" strokeWidth="1.8" filter="url(#cyanglow)" />
      <text x={ccCx} y={ROW1_Y + 22}
        textAnchor="middle" fill="#00D4FF" fontSize="11" fontFamily="monospace" fontWeight="700">
        Command Center
      </text>
      <text x={ccCx} y={ROW1_Y + 38}
        textAnchor="middle" fill="#5A7090" fontSize="8.5" fontFamily="monospace">
        Kali Linux · root · all tools
      </text>

      {/* ── target_net badge ── */}
      <rect x={TGT_X} y={ROW1_Y + 8} width={TGT_W} height={BOX_H - 16}
        rx="5" fill="#FF3B30" fillOpacity="0.05" stroke="#FF3B30" strokeWidth="1" strokeOpacity="0.4" />
      <text x={TGT_X + TGT_W / 2} y={ROW1_Y + 27}
        textAnchor="middle" fill="#FF3B30" fontSize="9.5" fontFamily="monospace" fontWeight="700">
        target_net
      </text>
      <text x={TGT_X + TGT_W / 2} y={ROW1_Y + 41}
        textAnchor="middle" fill="#FF3B30" fontSize="8" fontFamily="monospace" opacity="0.6">
        CC only · scoped
      </text>

      {/* ── Agent boxes ── */}
      {AGENTS.map((agent, i) => {
        const cx = agentCx[i];
        const ax = cx - AGENT_W / 2;
        return (
          <g key={agent.label}>
            {/* Entry dot at top of box */}
            <circle cx={cx} cy={AGENT_Y} r="3" fill={agent.color} fillOpacity="0.5" />
            {/* Box */}
            <rect x={ax} y={AGENT_Y} width={AGENT_W} height={AGENT_H}
              rx="6" fill="#0D1321"
              stroke={agent.color} strokeWidth="1.3" strokeOpacity="0.55" />
            {/* Top accent bar */}
            <rect x={ax + 1} y={AGENT_Y + 1} width={AGENT_W - 2} height="3"
              rx="2" fill={agent.color} fillOpacity="0.55" />
            <text x={cx} y={AGENT_Y + 26}
              textAnchor="middle" fill={agent.color} fontSize="10.5" fontFamily="monospace" fontWeight="700">
              {agent.label}
            </text>
            <text x={cx} y={AGENT_Y + 40}
              textAnchor="middle" fill="#5A7090" fontSize="8" fontFamily="monospace">
              Agent
            </text>
          </g>
        );
      })}

      {/* ── Bottom note ── */}
      <text x={W / 2} y={H - 14} textAnchor="middle"
        fill="#2A3D5A" fontSize="8.5" fontFamily="monospace">
        Agents execute tools via CC · never reach target_net directly
      </text>
    </svg>
  );
}
