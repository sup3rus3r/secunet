FROM kalilinux/kali-rolling:latest

USER root

# Full offensive tool suite + Python runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Network tools
    nmap ncat netcat-traditional masscan \
    # Exploitation
    metasploit-framework \
    # Credential testing
    hydra medusa \
    # Web scanning
    nikto gobuster dirb \
    # Enumeration
    enum4linux smbclient \
    # Packet capture
    tcpdump wireshark-common tshark \
    # Impacket dependencies
    python3-impacket \
    # Misc tools
    curl wget dnsutils whois netdiscover arp-scan \
    # Audit
    auditd \
    # Python
    python3 python3-pip python3-venv \
    # WeasyPrint system dependencies (PDF report generation)
    libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared schemas
COPY shared/ /shared/

# Copy command center source
COPY command-center/ /app/

# Install Python deps
RUN pip3 install --no-cache-dir \
    fastapi[standard] uvicorn[standard] \
    redis httpx pydantic python-dotenv \
    anthropic "openai>=1.50.0" \
    chromadb asyncpg weasyprint

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/shared

# Copy and set entrypoint
COPY agents/base/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
