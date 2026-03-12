# Self-Hosting Ernos 3.0

Run your own instance of Ernos — full access, no restrictions, your hardware.

## Prerequisites

- **Docker** + **Docker Compose** installed
- **Discord bot token** ([create one here](https://discord.com/developers/applications))
- **LLM access** — either:
  - A machine with a GPU to run models locally via Ollama, **or**
  - API keys for a cloud LLM provider routed through Ollama

## Quick Start

### 1. Pull the image (when available)

```bash
docker pull ghcr.io/mettamazza/ernos:latest
```

### 2. Configure your environment

```bash
cp .env.template .env
```

Open `.env` and fill in at minimum:
- `DISCORD_TOKEN` — your bot token
- `ADMIN_ID` — your Discord user ID

### 3. Create your Discord bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it whatever you want
3. Go to **Bot** → click **Reset Token** → copy it into `DISCORD_TOKEN`
4. Enable these **Privileged Intents**:
   - ✅ Message Content Intent
   - ✅ Server Members Intent
   - ✅ Presence Intent
5. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Read Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Add Reactions`, `Use Slash Commands`
6. Copy the generated URL and open it to invite the bot to your server

### 4. Launch

```bash
docker compose up -d
```

This starts three services:
- **Ernos** — the bot itself
- **Neo4j** — knowledge graph database
- **Ollama** — local LLM server

### 5. Pull your first model

```bash
# Pull a cloud-routed model (requires API key in Ollama config)
docker exec ernos-ollama ollama pull gemini-3-flash-preview:cloud

# Or pull a local model (requires GPU)
docker exec ernos-ollama ollama pull qwen3-vl:32b
```

## Useful Commands

```bash
# View logs
docker compose logs -f ernos

# Restart
docker compose restart ernos

# Stop everything
docker compose down

# Update to latest version
docker compose pull && docker compose up -d
```

## Configuration Reference

See `.env.template` for all available settings. Key sections:

| Category | Variables | Required? |
|----------|-----------|-----------|
| Discord | `DISCORD_TOKEN`, `ADMIN_ID` | ✅ Yes |
| LLM | `OLLAMA_BASE_URL`, `OLLAMA_CLOUD_MODEL` | ✅ Yes |
| Neo4j | `NEO4J_URI`, `NEO4J_PASSWORD` | Has defaults |
| Channels | `TARGET_CHANNEL_ID`, etc. | Optional |
| Media | `HF_API_TOKEN` | Optional |

## Hardware Requirements

| Setup | RAM | GPU | Disk |
|-------|-----|-----|------|
| Cloud models only | 4 GB | Not needed | 5 GB |
| Small local model (7B) | 16 GB | 8 GB VRAM | 20 GB |
| Large local model (32B+) | 32 GB+ | 24 GB+ VRAM | 50 GB+ |

## Troubleshooting

**Bot is online but not responding:**
- Check that Message Content Intent is enabled in Discord Developer Portal
- Verify `DISCORD_TOKEN` is correct in `.env`

**Ollama connection errors:**
- Ensure Ollama container is running: `docker compose ps`
- Check if model is pulled: `docker exec ernos-ollama ollama list`

**Neo4j connection refused:**
- Wait 30 seconds after startup — Neo4j takes time to initialize
- Check password matches between `.env` and `docker-compose.yml`
