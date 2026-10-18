# Hark Tech MCP server: UK 3D printing prices for AI assistants

[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-uk.co.harktech%2Fquotes-blue)](https://registry.modelcontextprotocol.io/v0.1/servers?search=uk.co.harktech)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI assistant price 3D prints with [Hark Tech](https://harktech.co.uk), a 3D printing service in Basingstoke, UK, and hand back a checkout link.

**Endpoint:** `https://harktech.co.uk/mcp` (streamable HTTP, no sign-in, no API key)

Share a link to your own STL, 3MF or STEP file and ask:

> Price this in PETG, 3 copies: https://github.com/you/your-part/blob/main/bracket.stl

and you get a real price, postage and dispatch time, plus a checkout page with the file already priced in your basket. Nothing is ordered or charged until you pay on harktech.co.uk.

## Add it to your assistant

**Claude** (claude.ai, Desktop or mobile): Settings, Connectors, Add custom connector, then paste `https://harktech.co.uk/mcp`.

**Claude Code:**

```bash
claude mcp add --transport http harktech https://harktech.co.uk/mcp
```

**Other clients** that support remote MCP servers (Cursor, VS Code, Gemini CLI, ChatGPT developer mode and others):

```json
{
  "mcpServers": {
    "harktech": { "type": "http", "url": "https://harktech.co.uk/mcp" }
  }
}
```

Full guide: https://harktech.co.uk/for-ai-assistants.html

## Tools

| Tool | What it does |
| --- | --- |
| `quote_my_file` | Prices your own STL, 3MF or STEP file from a share link (Google Drive or OneDrive "anyone with the link", Dropbox, GitHub, Discord attachment) and returns a `checkout_url` with it priced in your basket. |
| `search_models` | Searches Printables and Thingiverse models whose licence allows commercial printing. |
| `get_quote` | Live price, postage, dispatch time, batch discounts and order link for a catalogue model, material and quantity. |
| `get_upload_page` | Where to upload a file when there is no share link. |
| `get_service_info` | Order minimums, postage, lead times, batch discounts, materials and licence policy. |
| `search_repair_services` | Matches a device and fault to Hark Tech's published mail-in repair services: fixed price or assessment fee, 5 to 7 working day turnaround, warranty and a booking link. |
| `get_repair_service_info` | Repair policies: the mail-in process, what the £40 assessment covers, what is not offered, warranty, return postage, trade terms and privacy. |
| `get_order_status` | Progress of one 3D print order for the customer who placed it (order reference plus the email it was placed with). |
| `get_repair_status` | Progress of one repair booking or enquiry for its customer (reference plus the email it was booked with). Status, dates and return tracking only. |

Materials: PLA, PLA Matte, PLA Silk, PETG, TPU, ABS, ASA, PC, Nylon, PETG-CF and PA-CF. Prints are posted across the UK. Repairs are mail-in only (consoles, controllers, handhelds, laptops, TV and monitor boards, retro computers and circuit boards); the connector never books, orders or takes payment.

## Example prompts

- "Here's my drone frame on Google Drive, how much in PETG-CF?"
- "Find a wall mount for a Dyson V15 and price 2 in PETG."
- "What's the cheapest way to get 20 of these cable clips printed and posted?"
- "My PS5 says no signal on the TV, what would Hark Tech charge to fix it?"
- "Where is my repair? Booking BK-1A2B3C4D, booked with sam@example.com."

## How it works

This repo is the MCP layer only. Each tool is a thin wrapper over a public Hark Tech HTTP endpoint (documented in [openapi.json](https://harktech.co.uk/openapi.json)); slicing and pricing happen on Hark Tech's side. The server runs stateless with JSON responses, and also serves an [MCP Server Card](https://harktech.co.uk/mcp/server-card) and an [AI Catalog](https://harktech.co.uk/.well-known/ai-catalog.json) for discovery.

Privacy: the server receives only what the assistant sends (a model or file link, material, quantity and speed) and does not see your conversation. See https://harktech.co.uk/privacy.html.

## Running it yourself

You don't need to, the hosted endpoint is free to use. To read or run the code:

```bash
pip install -r requirements.txt
HARKTECH_BACKEND=https://harktech.co.uk python server.py
```

It listens on `127.0.0.1:8003/mcp`.

## Contact

Hark Tech, Basingstoke, UK: https://harktech.co.uk/contact.html
