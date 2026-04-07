# Uni Care At Home, Inc. — UCaaS Golden Number Architecture

## Platform Decision: RingCentral Ultra (over Twilio Interconnect)

### Why RingCentral Ultra Wins for This Use Case

| Requirement | RingCentral Ultra | Twilio + Interconnect |
|---|---|---|
| **Voice/Fax on Single DID** | IVR menu option routes to fax extension cleanly (see "Important" below) | Must build custom `<Gather>` + tone detection; Twilio **deprecated its Fax API** (Dec 2021) |
| **100+ Page Fax** | Server-side store-and-forward, up to 200 pages via API | No native fax — requires third-party (Phaxio, SRFax) adding a second vendor + BAA |
| **HIPAA BAA** | Single BAA covers voice, fax, storage, API | Twilio signs BAA (via Shield add-on, ~$100/mo extra) but fax vendor needs a separate BAA |
| **IVR / Auto-Attendant** | Drag-and-drop multi-level IVR in admin portal | Must code every menu in TwiML/Studio — weeks of development |
| **Ring Groups & Failover** | Native: simultaneous, sequential, tiered overflow | Must code with `<Dial>` + `<Queue>` + status callbacks — fragile |
| **Desk Phone ZTP** | Poly & Yealink auto-provisioned via MAC pairing | Twilio Interconnect provides SIP trunk only — you manage provisioning yourself |
| **Python SDK** | `ringcentral` PyPI package, REST API, webhooks | `twilio` PyPI package (excellent), but no fax support |
| **Total Dev Effort** | ~2 weeks integration | ~8-12 weeks building IVR, fax pipeline, provisioning |
| **Monthly Cost (est.)** | ~$35/user/mo (Ultra) | ~$50-80/user/mo (Twilio usage + Interconnect + fax vendor + Shield) |

**Verdict:** RingCentral Ultra delivers 80% of the solution out-of-the-box. Twilio is powerful but overkill — you'd be rebuilding what RingCentral already provides, with the critical disadvantage of having no native fax capability.

---

### Important: Voice/Fax on a Single DID — Real-World Behavior

RingCentral supports setting a number to "Voice and Fax" mode, which attempts automatic CNG tone detection. **However, in practice this is unreliable** — IVR greetings, auto-attendant prompts, and voicemail pickup interfere with the T.30 fax handshake timing, causing fax failures and phantom voicemail artifacts.

**Production-grade approach (recommended):** Use the IVR menu on the Golden Number to give fax callers a clean path:

> *"Press 4 to send a fax."*

Pressing 4 routes directly to the **Message-Only Fax Extension (500)**, which has no greeting, no voicemail, and no call queue — just a clean T.30/T.38 handshake. This is the architecture used below.

**Alternative:** Use a second DID dedicated to fax (e.g., 760-888-8889). This is the most reliable option but requires communicating two numbers externally. If budget permits, this is the safest choice.

---

## Architecture Overview

```
                        PSTN / Carrier Network
                               │
                    ┌──────────┴──────────┐
                    │  DID: 760-888-8888  │
                    │   (Golden Number)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │   RingCentral       │
                    │   Auto-Attendant    │
                    │   (IVR Menu)        │
                    └───┬───┬───┬───┬─────┘
                        │   │   │   │
              Press 1   │ 2 │ 3 │   Press 4
              Complaints│   │   │   "Send a Fax"
                        │   │   │        │
              ┌─────────┘   │   │   ┌────┴──────────┐
              │    Billing──┘   │   │ Fax Extension │
              │         HR──────┘   │ (ext 500)     │
              │                     │ Message-Only  │
              │                     │ Clean T.38    │
              │                     │ No greeting   │
              │                     └────┬──────────┘
              │                          │
              │                     Store & Forward
    ┌─────────┼─────────┐               │
    │         │         │          ┌────┴────┐
 Press 1   Press 2   Press 3      │         │
 Complaints Billing   HR     PDF Rendered  Webhook
    │         │         │     AES-256       POST
          │         │         │     │
     ┌────┴────┐ ┌──┴──┐ ┌───┴──┐  ├─► Webhook Callback
     │Ring Grp │ │Ring  │ │Ring  │  │    (fax.received)
     │Complaints│ │Grp  │ │Grp  │  │
     │         │ │Billing│ │HR  │  └─► Audit Log Entry
     └────┬────┘ └──┬──┘ └───┬──┘
          │         │        │
     Tier 1: Desk Phones (Poly VVX / Yealink T5x)
          │         │        │
     Tier 2: Softphones (RingCentral App - Mobile/Desktop)
          │         │        │
     Tier 3: Voicemail → Email (Encrypted Transcript)
```

---

## Table of Contents

1. [Network & Infrastructure](#1-network--infrastructure)
2. [Hardware Bill of Materials](#2-hardware-bill-of-materials)
3. [RingCentral Configuration](#3-ringcentral-configuration)
4. [Call Flow & IVR Design](#4-call-flow--ivr-design)
5. [Fax Architecture](#5-fax-architecture)
6. [Python Integration Code](#6-python-integration-code)
7. [HIPAA Compliance](#7-hipaa-compliance)
8. [Deployment Checklist](#8-deployment-checklist)

---

## 1. Network & Infrastructure

### WAN Requirements

| Spec | Minimum | Recommended |
|---|---|---|
| **Bandwidth per call** | 100 Kbps (G.729) | 200 Kbps (G.711 μ-law) |
| **Total bandwidth** | 5 Mbps symmetric | 25+ Mbps symmetric |
| **Jitter** | < 30 ms | < 10 ms |
| **Packet loss** | < 1% | < 0.1% |
| **Latency** | < 150 ms | < 50 ms |
| **Connection type** | Business-grade cable | Dedicated fiber (DIA) |

### Network Topology (Your Actual Closet)

```
AT&T Fiber (street)
        │
  ┌─────┴──────┐
  │ AT&T Demarc │  ← Gray box "1520-1.1" (fiber termination)
  │ (NID)       │
  └─────┬──────┘
        │ Fiber
  ┌─────┴──────┐
  │ Ciena ONT  │  ← White AT&T box (fiber → Ethernet conversion)
  └─────┬──────┘
        │ Ethernet
  ┌─────┴──────┐
  │ AT&T       │  ← White cylindrical gateway (router/firewall/WiFi)
  │ Gateway    │    *** DISABLE SIP ALG HERE ***
  │ (Router)   │    Must allow: UDP 5060-5061, UDP 16384-32767,
  │            │    TCP 443, TCP 8083 outbound
  └─────┬──────┘
        │ Ethernet
  ┌─────┴──────┐
  │ Netgear    │  ← Existing 24-port switch (rack-mounted)
  │ Switch     │    Distributes via Cat5e patch panel
  └──┬──┬──┬──┘
     │  │  │
     │  │  └── Yealink W76P Base Station #1 (Ethernet)
     │  │       └── DECT wireless → Handsets 201, 202, 203
     │  │
     │  └───── Yealink W76P Base Station #2 (Ethernet)
     │          └── DECT wireless → Handsets 204, 205, 206
     │
     └──────── Workstations (existing Cat5e runs)

Power: WattBox (surge protection) + APC Back-UPS 600 (battery backup)
Alarm: Protection One panel (independent — not on data network)
```

### Critical Firewall Rules

```
# MUST DISABLE SIP ALG — this is the #1 cause of VoIP issues
# On SonicWall: Manage > VoIP > Disable SIP Transformations
# On Ubiquiti: Settings > Threat Management > Disable SIP ALG

# Required outbound rules (RingCentral infrastructure):
Protocol  Port Range        Direction  Purpose
UDP       5060-5061         Outbound   SIP Signaling
TCP       5060-5061         Outbound   SIP over TLS
UDP       16384-32767       Outbound   RTP/SRTP Media
TCP       443               Outbound   HTTPS API + WebSocket
TCP       8083              Outbound   Phone provisioning
```

---

## 2. Hardware Bill of Materials

### Existing Infrastructure (Already In Place)

| Device | Role | Status |
|---|---|---|
| **AT&T Fiber (Ciena ONT)** | ISP handoff — fiber to Ethernet conversion | Existing |
| **AT&T Gateway (Router)** | NAT, DHCP, firewall, WiFi | Existing — **must disable SIP ALG** |
| **Netgear Switch (24-port)** | Distributes Ethernet to office via Cat5e patch panel | Existing — works fine for VoIP |
| **WattBox Power Conditioner** | Surge protection for rack equipment | Existing |
| **APC Back-UPS 600** | Battery backup for network gear during outages | Existing |
| **Cat5e Patch Panel + Cabling** | Wired connections to office wall jacks | Existing — no new cabling needed |
| **Protection One Alarm Panel** | Building security (independent of data network) | Existing — no changes needed |

### New Equipment to Purchase

| Device | Role | Qty | Est. Unit Price | Total |
|---|---|---|---|---|
| **Yealink W76P** | DECT cordless base + 1 handset (8 handsets per base) | 2 | $130 | $260 |
| **Yealink W56H** | Additional DECT handsets (pair with W76P bases) | 4 | $70 | $280 |
| **Yealink CP920** | Conference room speakerphone (optional) | 1 | $250 | $250 |
| | | | **Total** | **~$790** |

> **Why all-cordless?** With only 5-6 users and existing Cat5e cabling to the
> closet, DECT cordless eliminates desk phone cabling entirely. Each W76P base
> plugs into one Ethernet port on your existing Netgear switch. Handsets are
> wireless via DECT (dedicated frequency — does NOT compete with WiFi).
> Range: ~165 ft indoors / ~980 ft outdoors. Two bases provide full office
> coverage with handset roaming between them.

### Handset Assignment

| Handset | User / Role | Extension | Base Station |
|---|---|---|---|
| W76P #1 (included) | Front Desk / Receptionist | 201 | Base 1 |
| W56H #1 | Complaints | 202 | Base 1 |
| W56H #2 | Billing | 203 | Base 1 |
| W76P #2 (included) | HR | 204 | Base 2 |
| W56H #3 | Office Manager | 205 | Base 2 |
| W56H #4 | Admin | 206 | Base 2 |

### Network Equipment — What to Keep vs. Replace

Your existing AT&T Gateway works as-is, but with one critical configuration change:

**You MUST disable SIP ALG** on the AT&T Gateway. SIP ALG (Application Layer
Gateway) "helps" with VoIP by rewriting SIP packets — but it actually breaks
RingCentral calls, causing one-way audio, dropped calls, and registration
failures. It is the #1 cause of VoIP issues.

How to disable it depends on your AT&T Gateway model:
- **BGW320:** Settings > Firewall > Applications, Pinholes and DMZ > disable SIP ALG
- **BGW210:** Settings > Firewall > Advanced > disable SIP ALG
- If the option isn't available, enable **IP Passthrough** mode and add a
  dedicated router (Ubiquiti Dream Machine, ~$379) where you have full control

### Software / Licenses

| Item | Qty | Monthly Cost (annual billing) |
|---|---|---|
| **RingCentral Ultra** | 6 users | 6 x $35 = **$210/mo** |
| **Port 760-888-8888** | 1 number | Included |
| **Fax (10,000 pages/mo)** | Included in Ultra | Included |
| **Python SDK** | Open source (`ringcentral`) | Free |
| | **Total** | **$210/mo ($2,520/yr)** |

---

## 3. RingCentral Configuration

### Account Hierarchy

```
Company: Uni Care At Home, Inc.
├── Main Number: (760) 888-8888  ← Golden Number (ported DID)
├── RingCentral Ultra Licenses: 6
│
├── Site: Main Office
│   ├── Auto-Attendant (ext 100) ← system extension, no license needed
│   │   ├── Business Hours:  Mon-Fri 8:00 AM - 5:00 PM PST
│   │   └── After Hours:     All other times
│   │
│   ├── Users (6 licenses):
│   │   ├── ext 201: Front Desk / Receptionist  (W76P handset, Base 1)
│   │   ├── ext 202: Complaints                 (W56H handset, Base 1)
│   │   ├── ext 203: Billing                    (W56H handset, Base 1)
│   │   ├── ext 204: HR                         (W56H handset, Base 2)
│   │   ├── ext 205: Office Manager             (W76P handset, Base 2)
│   │   └── ext 206: Admin                      (W56H handset, Base 2)
│   │
│   ├── Ring Group: Complaints (ext 200)
│   │   └── Simultaneous ring → ext 202 + ext 205
│   │       ├── Tier 1: DECT handsets (15s timeout)
│   │       ├── Tier 2: Office Manager cell (15s timeout)
│   │       └── Tier 3: Voicemail → complaints@unicareathome.com
│   │
│   ├── Ring Group: Billing (ext 300)
│   │   └── Sequential ring → ext 203
│   │       ├── Tier 1: Billing handset (20s timeout)
│   │       ├── Tier 2: Admin cell (15s timeout)
│   │       └── Tier 3: Voicemail → billing@unicareathome.com
│   │
│   ├── Ring Group: HR (ext 400)
│   │   └── Sequential ring → ext 204
│   │       ├── Tier 1: HR handset (20s timeout)
│   │       ├── Tier 2: Office Manager cell (15s timeout)
│   │       └── Tier 3: Voicemail → hr@unicareathome.com
│   │
│   ├── Fax Extension (ext 500) — Message-Only, no license needed
│   │   └── Reached via IVR "Press 4" (clean T.38 path, no greeting)
│   │       └── Store-and-forward → fax@unicareathome.com
│   │
│   └── Operator / Front Desk (ext 0 → routes to ext 201)
│       └── Yealink W76P cordless handset (receptionist)
```

### IVR Script (Business Hours)

```
"Thank you for calling Uni Care At Home. Your call may be recorded
 for quality assurance and training purposes.

 Press 1 for Complaints and Grievances.
 Press 2 for Billing and Accounts.
 Press 3 for Human Resources.
 Press 4 to send a fax.
 Press 0 to speak with the Front Desk.

 If you know your party's extension, you may dial it at any time.
 For a company directory, press 9."
```

### IVR Script (After Hours)

```
"Thank you for calling Uni Care At Home. Our office is currently closed.
 Our business hours are Monday through Friday, 8 AM to 5 PM Pacific Time.

 Press 1 to leave a message for Complaints and Grievances.
 Press 2 to leave a message for Billing.
 Press 3 to leave a message for Human Resources.
 Press 4 to send a fax.

 For after-hours emergencies, press 0 and your call will be forwarded
 to our on-call administrator."
```

---

## 4. Call Flow & IVR Design

See `docs/call-flow.md` for the detailed state machine.

## 5. Fax Architecture

See `docs/fax-architecture.md` for the store-and-forward pipeline.

## 6. Python Integration Code

All integration code lives in `src/`. See:
- `src/core/client.py` — RingCentral API client wrapper
- `src/fax/sender.py` — High-volume fax transmission
- `src/fax/receiver.py` — Inbound fax webhook handler
- `src/ivr/manager.py` — IVR/auto-attendant configuration
- `src/webhooks/server.py` — Webhook endpoint (Flask)
- `src/compliance/audit.py` — Audit trail logger

## 7. HIPAA Compliance

See `docs/hipaa-compliance.md` for the full compliance matrix.

## 8. Deployment Checklist

See `docs/deployment-checklist.md` for the step-by-step rollout plan.
