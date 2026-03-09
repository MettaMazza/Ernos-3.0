# Ernos Minecraft User Guide

## Quick Start

### 1. Link Your Account (Discord)
```
/link_minecraft minecraft_username:YourMCName
```
This lets Ernos recognize you across both platforms.

### 2. Start Gaming Session (Discord)
```
!game start
```

### 3. Talk to Ernos (In-Game)
Just chat in Minecraft! Press `T` and type.

---

## 🧠 Ernos's Full Brain in MC

**Ernos uses his COMPLETE system while playing:**

| Capability | Status |
|------------|--------|
| Memory | ✅ Remembers everything |
| Planning | ✅ Sets & tracks goals |
| Web Search | ✅ Can look things up |
| Tool Execution | ✅ Full tool access |
| Vision | ✅ Sees the game (Gemini 3) |
| Cross-Platform | ✅ Knows Discord + MC are same person |

---

## All 23 Commands

### Movement & Follow
| Say This | Ernos Does |
|----------|------------|
| `@Ernos follow me` | Follows until stopped |
| `@Ernos come here` | Comes to you |
| `stop` / `stay` / `wait` | Stops following |

### Combat & Survival
| Command | Description |
|---------|-------------|
| `@Ernos equip diamond_sword` | Equip weapon/tool |
| `@Ernos equip helmet head` | Equip armor slot |
| `@Ernos shield` | Block with shield |
| `@Ernos sleep` | Sleep in bed (night only) |
| `@Ernos wake` | Wake from bed |

### Resource Management
| Command | Description |
|---------|-------------|
| `@Ernos collect wood 32` | Gather resources |
| `@Ernos smelt iron_ore` | Cook/smelt in furnace |
| `@Ernos store` | Store items in chest |
| `@Ernos take iron` | Take from chest |
| `@Ernos place cobblestone` | Place block |

### Farming
| Command | Description |
|---------|-------------|
| `@Ernos farm wheat` | Till soil + plant |
| `@Ernos harvest` | Harvest mature crops |
| `@Ernos plant carrot 5` | Plant seeds |
| `@Ernos fish 30` | Fish for 30 seconds |

### Location & Building
| Command | Description |
|---------|-------------|
| `@Ernos save location as home` | Save waypoint |
| `@Ernos take me to home` | Navigate to saved location |
| `@Ernos copy this build as shelter` | Save blueprint |
| `@Ernos build shelter` | Construct from blueprint |

### 🤝 Co-op Mode (NEW!)
| Command | Description |
|---------|-------------|
| `@Ernos coop metta_mazza` | Enable co-op mode |
| `@Ernos give me iron` | Give items to player |
| `@Ernos drop cobblestone 10` | Drop items |
| `@Ernos share coal` | Drop half your stack |
| `@Ernos find diamond_ore` | Locate block type |
| `@Ernos find iron go` | Find and navigate |
| `@Ernos scan` | Scan for nearby ores |
| `@Ernos eat` | Eat food |

**Co-op Mode Features:**
- Follows at 5-block distance (not clingy)
- Scans for ores automatically
- Shares resources when asked
- Helps with collection & combat

---

## Discord Commands

| Command | Description |
|---------|-------------|
| `/link_minecraft minecraft_username:NAME` | Link MC account |
| `!game start` | Start Minecraft session |
| `!game stop` | Stop Minecraft session |

---

## Cross-Platform Memory

After linking, Ernos knows you're the same person:

**In Minecraft:**
> metta_mazza: "Hey Ernos!"
> Ernos: "Hey metta_mazza!"

**Later in Discord:**
> You: "Who did you talk to in Minecraft?"
> Ernos: "I talked to you (metta_mazza)! You said hi!"

---

## Ernos's Behaviors

### Safety First
- If health < 8: Prioritizes food/safety
- Auto-eats when hungry
- Won't fight when low health

### Block Protection (Temporary)
- Won't break blocks within 20 blocks of players
- Only collects natural resources
- Won't destroy player structures

### Protected Zones (PERMANENT)
Say in-game: **"protect here"** or **"protect 50 blocks"**

```
> metta_mazza: "protect here"
> Ernos: "Protected zone created! 50 block radius. I will never break blocks here."
```
- Saved forever in `memory/public/protected_zones.json`

### Aggro System
If you hit Ernos:
1. He warns: *"Say sorry or I'm taking your blocks!"*
2. Your protection is DISABLED
3. Say "sorry" → Forgiven

---

## What Ernos Can See

| Perception | Source |
|------------|--------|
| Health & Food | Bot state |
| Day/Night | Time check |
| Players & Mobs | Entity scan |
| Inventory | Inventory API |
| **Game View** | Screenshot + Gemini 3 |

---

## Visual Perception

Ernos captures screenshots and sends them to **Gemini 3** for vision analysis. This means:
- He can describe what he sees
- Recognizes biomes, structures, entities
- Makes decisions based on visuals

Try: `@Ernos what do you see?`

---

