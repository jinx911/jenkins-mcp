#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Jenkins MCP Server — Uninstall Script
# ============================================================

SETTINGS_FILE="$HOME/.claude/settings.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}  Jenkins MCP Server — Uninstaller${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo ""

# ---- Step 1: Remove from settings.json ----
echo -e "${YELLOW}[1/2]${NC} Removing MCP server configuration..."

if [ -f "$SETTINGS_FILE" ]; then
    python3 -c "
import json, sys

settings_path = sys.argv[1]
with open(settings_path, 'r') as f:
    settings = json.load(f)

mcp_servers = settings.get('mcpServers', {})
if 'jenkins' in mcp_servers:
    del mcp_servers['jenkins']
    settings['mcpServers'] = mcp_servers
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('removed')
else:
    print('not_found')
" "$SETTINGS_FILE"
    echo -e "  ${GREEN}✓${NC} Removed 'jenkins' from Claude Code settings"
else
    echo "  No settings.json found, skipping."
fi

# ---- Step 2: Remove skills ----
echo -e "${YELLOW}[2/2]${NC} Removing skills..."

for skill_name in deploy build-status build-log; do
    skill_dir="$HOME/.claude/skills/$skill_name"
    if [ -d "$skill_dir" ]; then
        rm -rf "$skill_dir"
        echo -e "  ${GREEN}✓${NC} Removed skill: /$skill_name"
    else
        echo "  Skill /$skill_name not found, skipping."
    fi
done

# ---- Done ----
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Uninstallation complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  The project directory was NOT removed. To fully clean up:"
echo "    rm -rf $(cd "$(dirname "$0")" && pwd)"
echo ""
echo -e "  ${YELLOW}Restart Claude Code to apply changes.${NC}"
