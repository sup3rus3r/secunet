# Canonical WebSocket event type constants
# Used by Command Center (emit) and Dashboard (consume)

# ── Agent events ─────────────────────────────────────────────
AGENT_MESSAGE        = "agent.message"         # chat message from any agent
AGENT_STATUS         = "agent.status"          # agent state change
AGENT_FINDING        = "agent.finding"         # new vulnerability found
AGENT_COMMAND_RESULT = "agent.command_result"  # tool execution output
AGENT_HEALTH         = "agent.health"          # heartbeat / uptime

# ── Human events ─────────────────────────────────────────────
HUMAN_MESSAGE        = "human.message"         # engineer message from dashboard

# ── HITL events ──────────────────────────────────────────────
HITL_REQUEST         = "hitl.request"          # agent requests approval
HITL_RESOLVED        = "hitl.resolved"         # engineer approved or rejected

# ── Mission events ────────────────────────────────────────────
MISSION_STATE        = "mission.state"         # full state snapshot (on connect)
MISSION_METRIC       = "mission.metric"        # metric update
MISSION_PHASE_CHANGE = "mission.phase_change"  # phase transition

# ── Attack coverage events ────────────────────────────────────
ATTACK_COVERAGE      = "attack.coverage"       # ATT&CK technique status update

# ── Target events ────────────────────────────────────────────
TARGET_EVENT         = "target.event"          # something happened on target network

# ── Patch / remediation events ────────────────────────────────
PATCH_DEPLOYED       = "patch.deployed"        # fix deployed to a host

# ── System events ────────────────────────────────────────────
SYSTEM_ERROR         = "system.error"          # platform-level error
SYSTEM_INFO          = "system.info"           # platform-level info message

# ── Commander events ──────────────────────────────────────────
COMMANDER_SUMMARY    = "commander.summary"     # rolling window compression completed

# ── Activity feed events ──────────────────────────────────────
ACTIVITY_EVENT       = "activity.event"        # Commander decision trail entry

# ── Fix Advisor events ────────────────────────────────────────
FIX_READY            = "fix.ready"             # Fix package ZIP available for download

# ── Context write event types (stored in vector store) ───────
EVT_SCAN_RESULT         = "scan_result"
EVT_ASSET_DISCOVERY     = "asset_discovery"
EVT_SERVICE_FINGERPRINT = "service_fingerprint"
EVT_VULNERABILITY       = "vulnerability_finding"
EVT_EXPLOIT_ATTEMPT     = "exploit_attempt"
EVT_CREDENTIAL_FOUND    = "credential_found"
EVT_ACCESS_PATH         = "access_path"
EVT_DETECTION_SCORE     = "detection_score"
EVT_ALERT_RESULT        = "alert_result"
EVT_PATCH_DEPLOYED      = "patch_deployed"
EVT_HITL_APPROVAL       = "hitl_approval"
EVT_ANOMALY             = "anomaly_event"
EVT_TRIPWIRE            = "tripwire_state"
EVT_COMMAND_EXECUTION   = "command_execution"
EVT_MESSAGE             = "message"
EVT_SUMMARY             = "summary"
