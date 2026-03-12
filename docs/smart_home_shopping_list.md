# Ernos Smart Home Shopping List — Amazon UK
*February 2026 — cost-efficient Zigbee + WiFi hybrid setup*

---

## 🔌 ESSENTIALS (get this first — ~£25-35)

| Item | What it does | Price |
|------|-------------|-------|
| **Sonoff Zigbee 3.0 USB Dongle Plus** | Replaces broken Hue bridge, talks to ALL Zigbee devices | ~£20-25 |
| **USB extension cable (1m)** | Keeps dongle away from Mac/Pi to avoid USB3 interference | ~£5 |

This alone gets your existing Hue bulbs working again through Home Assistant.

---

## 💡 LIGHTS (Zigbee — zero WiFi load)

| Item | Price | Notes |
|------|-------|-------|
| **IKEA TRÅDFRI bulbs** (E27/E14) | ~£5-8 each | Cheapest Zigbee bulbs, great HA support |
| **Your existing Hue bulbs** | £0 | Re-pair them to the Sonoff dongle |

---

## 🔌 SMART PLUGS (Zigbee — also extend your mesh)

| Item | Price | Notes |
|------|-------|-------|
| **Sonoff S60ZBTPF** (2-pack) | ~£20-25 | Cheap, power monitoring, acts as Zigbee router |
| **or NOUS A1Z** | ~£12-15 each | 16A rated, energy monitoring, great HA support |

Every mains-powered plug extends your Zigbee mesh range across the large house.

---

## 🌡️ SENSORS (gives Ernos ambient awareness)

| Item | Price | Notes |
|------|-------|-------|
| **Sonoff SNZB-02D** temp/humidity (2-pack) | ~£15-20 | LCD screen, 2-year battery, compact |
| **Sonoff SNZB-03** motion sensor | ~£10-12 | Ernos knows when you're home/which room |
| **Aqara door/window sensor** | ~£10-12 | Open/close detection |

---

## 🖥️ HOME ASSISTANT HOST (pick one)

| Option | Price | Notes |
|--------|-------|-------|
| **Run on your Mac** | £0 | Install HA as Docker container. Simplest to start |
| **Raspberry Pi 4 (4GB) + case + PSU + SSD** | ~£90-110 | Dedicated, always-on, low power (~5W). Best long term |

---

## 💰 COST SUMMARY

| Tier | What you get | Total |
|------|-------------|-------|
| **Minimum viable** (dongle only) | Existing Hue bulbs + Ernos control | **~£25** |
| **Starter home** (dongle + 4 plugs + 2 sensors) | Control + awareness + mesh coverage | **~£75-90** |
| **Full house** (above + Pi + motion + door sensors + extra bulbs) | Always-on, whole-house Ernos awareness | **~£150-200** |

---

## 🏗️ ARCHITECTURE

```
                    ┌─ Zigbee dongle ─── Hue bulbs, IKEA bulbs, Zigbee plugs, sensors
[Ernos] → [HA] ────┤
                    └─ Your WiFi ─────── Any WiFi smart devices (Kasa, Govee, Shelly)
```

## 📝 NOTES

- Start with the dongle + a couple plugs to get Hue bulbs back and build the mesh
- Add sensors once the base is running
- Zigbee mesh: every mains-powered device extends range — great for large houses
- Ernos already has `src/tools/home_assistant.py` ready to wire up
- All devices are local-only, no cloud dependency
