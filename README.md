# Drata MCP Server

A Model Context Protocol (MCP) server that connects Claude to your Drata compliance platform. Designed for SOC2 Type II audit preparation and ongoing compliance monitoring.

## What it does

This MCP server gives Claude direct access to your Drata data, allowing you to:

- **Monitor compliance status** - Get real-time summaries of controls, tests, and personnel compliance
- **Track failing tests** - Identify which automated monitors are failing and why
- **Review controls** - See which controls need attention (missing evidence, no owner, not ready)
- **Check personnel compliance** - Find employees with device compliance issues
- **Prepare for audits** - Generate comprehensive audit readiness reports

## Tools Available

| Tool | Description |
|------|-------------|
| `get_compliance_summary` | Dashboard overview of all compliance areas |
| `list_controls` | List controls with optional search and filtering |
| `list_controls_with_issues` | Controls that need attention (NOT_READY, NO_OWNER, NEEDS_EVIDENCE) |
| `get_control_details` | Detailed info about a specific control including linked monitors |
| `get_monitors_for_control` | All tests linked to a specific control |
| `list_monitors` | All automated monitoring tests with status summary |
| `list_failing_monitors` | Tests currently failing - critical for SOC2 |
| `list_personnel` | Personnel with compliance status |
| `list_personnel_with_issues` | Personnel with device compliance problems |
| `list_policies` | Company policies with version info |
| `list_pending_policy_acknowledgments` | Policies awaiting user acknowledgment |
| `list_connections` | Integration status (GitHub, AWS, etc.) |
| `list_vendors` | Third-party vendors |
| `list_devices` | Registered devices |

## Installation

```bash
# Clone the repository
git clone https://github.com/sderosiaux/drata-mcp.git
cd drata-mcp

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Configure your API key
cp .env.example .env
# Edit .env and add your DRATA_API_KEY
```

### Get your Drata API Key

1. Log into Drata
2. Go to **Settings** → **API Keys**
3. Click **Create API Key**
4. Copy the key to your `.env` file

## Usage with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "drata": {
      "command": "/path/to/drata-mcp/.venv/bin/python",
      "args": ["-m", "drata_mcp.server"],
      "cwd": "/path/to/drata-mcp"
    }
  }
}
```

Then restart Claude Desktop.

## Example Prompts

Once configured, you can ask Claude:

- "What's my Drata compliance status?"
- "Show me failing tests"
- "Which controls need attention?"
- "List personnel with device issues"
- "Prepare me for the SOC2 audit"
- "What tests are linked to control DCF-71?"

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Requirements

- Python 3.11+
- Drata account with API access
- Claude Desktop (for MCP integration)

## License

MIT
