#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Jenkins MCP Server — Install Script
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}  Jenkins MCP Server — Installer${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo ""

# ---- Step 1: Create venv and install deps ----
echo -e "${YELLOW}[1/4]${NC} Setting up Python environment..."

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo "  Created virtual environment at .venv/"
fi

source "$SCRIPT_DIR/.venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet mcp pydantic httpx
echo -e "  ${GREEN}✓${NC} Dependencies installed"

# ---- Step 2: Prompt for Jenkins credentials ----
echo ""
echo -e "${YELLOW}[2/4]${NC} Jenkins configuration"
echo "  You can find your API token at: JENKINS_URL/user/YOUR_USERNAME/configure"
echo ""

read -p "  Jenkins URL [https://jenkins.example.com]: " JENKINS_URL
JENKINS_URL=${JENKINS_URL:-https://jenkins.example.com}
# Remove trailing slash
JENKINS_URL="${JENKINS_URL%/}"

read -p "  Jenkins username: " JENKINS_USER
while [ -z "$JENKINS_USER" ]; do
    echo "  Username cannot be empty."
    read -p "  Jenkins username: " JENKINS_USER
done

read -p "  Jenkins API token: " JENKINS_TOKEN
while [ -z "$JENKINS_TOKEN" ]; do
    echo "  API token cannot be empty."
    read -p "  Jenkins API token: " JENKINS_TOKEN
done

read -p "  Jenkins folder (optional, press Enter to skip): " JENKINS_FOLDER

# ---- Step 3: Update Claude Code settings.json ----
echo ""
echo -e "${YELLOW}[3/4]${NC} Configuring Claude Code..."

mkdir -p "$HOME/.claude"

if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
fi

# Build the env JSON based on whether JENKINS_FOLDER is set
if [ -n "$JENKINS_FOLDER" ]; then
    ENV_JSON=$(python3 -c "
import json, sys
print(json.dumps({
    'JENKINS_URL': sys.argv[1],
    'JENKINS_USER': sys.argv[2],
    'JENKINS_TOKEN': sys.argv[3],
    'JENKINS_FOLDER': sys.argv[4],
}))
" "$JENKINS_URL" "$JENKINS_USER" "$JENKINS_TOKEN" "$JENKINS_FOLDER")
else
    ENV_JSON=$(python3 -c "
import json, sys
print(json.dumps({
    'JENKINS_URL': sys.argv[1],
    'JENKINS_USER': sys.argv[2],
    'JENKINS_TOKEN': sys.argv[3],
}))
" "$JENKINS_URL" "$JENKINS_USER" "$JENKINS_TOKEN")
fi

# Use python to safely update JSON
python3 -c "
import json, sys

settings_path = sys.argv[1]
env_json = sys.argv[2]

with open(settings_path, 'r') as f:
    settings = json.load(f)

mcp_servers = settings.get('mcpServers', {})

mcp_servers['jenkins'] = {
    'command': sys.argv[3],
    'args': [sys.argv[4]],
    'env': json.loads(env_json),
    'type': 'stdio'
}

settings['mcpServers'] = mcp_servers

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('OK')
" "$SETTINGS_FILE" "$ENV_JSON" \
    "$SCRIPT_DIR/.venv/bin/python" \
    "$SCRIPT_DIR/jenkins_mcp.py"

echo -e "  ${GREEN}✓${NC} Added 'jenkins' to Claude Code MCP servers"

# ---- Step 4: Install skills ----
echo -e "${YELLOW}[4/4]${NC} Installing skills..."

for skill_dir in "$SKILLS_DIR"/*/; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        target_dir="$HOME/.claude/skills/$skill_name"
        mkdir -p "$target_dir"
        cp "$skill_dir/skill.md" "$target_dir/skill.md"
        echo -e "  ${GREEN}✓${NC} Installed skill: /$skill_name"
    fi
done

# ---- Done ----
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  Available commands:"
echo "    /deploy         — Trigger Jenkins builds interactively"
echo "    /build-status   — Check build status"
echo "    /build-log      — View build logs"
echo ""
echo "  Or use MCP tools directly:"
echo "    jenkins_list_jobs, jenkins_get_build, jenkins_build, ..."
echo ""
echo -e "  ${YELLOW}Restart Claude Code to load the MCP server.${NC}"
