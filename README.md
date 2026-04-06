# Uni Care At Home, Inc. — UCaaS Golden Number Architecture

## Platform Decision: RingCentral Ultra (over Twilio Interconnect)

### Why RingCentral Ultra Wins for This Use Case

| Requirement | RingCentral Ultra | Twilio + Interconnect |
|---|---|---|
| **Voice/Fax on Single DID** | Native CNG tone detection — built-in | Must build custom `<Gather>` + tone detection; Twilio **deprecated its Fax API** (Dec 2021) |
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
                    │   RingCentral Edge  │
                    │   Signal Detection  │
                    │  (CNG Tone = Fax)   │
                    └───┬────────────┬────┘
                        │            │
               Voice Detected   Fax Detected
                        │            │
              ┌─────────┴──┐   ┌────┴──────────┐
              │ Auto-      │   │ RingCentral   │
              │ Attendant  │   │ Fax Server    │
              │ (IVR)      │   │ (T.38/G.711)  │
              └─────┬──────┘   └────┬──────────┘
                    │               │
          ┌─────────┼─────────┐    Store & Forward
          │         │         │     │
       Press 1   Press 2   Press 3  ├─► PDF → Encrypted
       Complaints Billing   HR     │    Storage (AES-256)
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

### Network Topology

```
Internet (ISP - Dedicated Fiber)
        │
  ┌─────┴─────┐
  │  Firewall  │  ← SonicWall TZ370 or Ubiquiti Dream Machine Pro
  │  (SIP ALG  │    Ports: UDP 5060-5061 (SIP), UDP 16384-32767 (RTP)
  │  DISABLED) │    TCP 5090-5091 (SIP/TLS), TCP 443 (HTTPS/WSS)
  └─────┬─────┘
        │
  ┌─────┴─────┐
  │  Managed   │  ← Ubiquiti USW-24-PoE or Cisco CBS250-24P
  │  PoE Switch│    802.3af PoE for desk phones
  │  (VLAN)    │    VLAN 10: Data, VLAN 20: Voice (QoS DSCP 46)
  └──┬──┬──┬──┘
     │  │  │
     │  │  └── AP (Ubiquiti U6 Pro) → Softphones on WiFi
     │  │
     │  └───── Desk Phone 1..N (PoE powered, VLAN 20)
     │
     └──────── Workstations / Servers (VLAN 10)
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

### Desk Phones

| Device | Role | Qty | Est. Unit Price | Features |
|---|---|---|---|---|
| **Yealink T54W** | Front Desk / Receptionist | 1 | $180 | 4.3" color screen, 16 SIP lines, built-in WiFi+BT, PoE, ZTP |
| **Yealink T43U** | Department Desks (Billing, HR, Complaints) | 4 | $110 | 3.7" screen, 12 SIP lines, PoE, ZTP |
| **Yealink W76P** | Warehouse / Mobile Staff | 2 | $130 | DECT cordless, 10 handsets per base, roaming |
| **Yealink CP920** | Conference Room | 1 | $250 | Conference phone, 6m pickup, Noise Proof |

### Network Equipment

| Device | Role | Qty | Est. Unit Price |
|---|---|---|---|
| **Ubiquiti Dream Machine Pro** | Firewall / Router / VPN | 1 | $379 |
| **Ubiquiti USW-24-PoE** | 24-port PoE managed switch | 1 | $399 |
| **Ubiquiti U6 Pro** | WiFi 6 AP (for softphones) | 1-2 | $149 |

### Cabling

| Item | Spec | Qty |
|---|---|---|
| **Cat6 Ethernet** | Shielded, plenum-rated | 500 ft spool |
| **Patch cables** | Cat6, 3ft & 7ft | 20 each |
| **Keystone jacks** | Cat6 RJ45 | 16 |
| **Wall plates** | Dual-port | 8 |
| **Patch panel** | 24-port Cat6 | 1 |

### Software / Licenses

| Item | Notes | Monthly Cost |
|---|---|---|
| **RingCentral Ultra** | Per user/extension license | ~$35/user/mo |
| **RingCentral Additional DID** | 760-888-8888 porting | Included or $4.99/mo |
| **RingCentral Fax** | Included in Ultra — 10,000 pages/mo | Included |
| **Python SDK** | `ringcentral` — open source | Free |

---

## 3. RingCentral Configuration

### Account Hierarchy

```
Company: Uni Care At Home, Inc.
├── Main Number: (760) 888-8888  ← Golden Number (ported DID)
├── Site: Main Office
│   ├── Auto-Attendant (ext 100)
│   │   ├── Business Hours:  Mon-Fri 8:00 AM - 5:00 PM PST
│   │   └── After Hours:     All other times
│   │
│   ├── Department: Complaints (ext 200)
│   │   └── Ring Group: Simultaneous → 3 phones
│   │       ├── Tier 1: Desk phones (15s timeout)
│   │       ├── Tier 2: Office Manager cell (15s timeout)
│   │       └── Tier 3: Voicemail → complaints@unicareathome.com
│   │
│   ├── Department: Billing (ext 300)
│   │   └── Ring Group: Sequential → 2 phones
│   │       ├── Tier 1: Billing desk (20s timeout)
│   │       ├── Tier 2: Admin cell (15s timeout)
│   │       └── Tier 3: Voicemail → billing@unicareathome.com
│   │
│   ├── Department: HR (ext 400)
│   │   └── Ring Group: Sequential → 1 phone
│   │       ├── Tier 1: HR desk (20s timeout)
│   │       ├── Tier 2: Director cell (15s timeout)
│   │       └── Tier 3: Voicemail → hr@unicareathome.com
│   │
│   ├── Fax Extension (ext 500)
│   │   └── Auto-detected from CNG tone on 760-888-8888
│   │       └── Store-and-forward → fax@unicareathome.com
│   │
│   └── Operator / Front Desk (ext 0)
│       └── Yealink T54W (receptionist phone)
```

### IVR Script (Business Hours)

```
"Thank you for calling Uni Care At Home. Your call may be recorded
 for quality assurance and training purposes.

 Press 1 for Complaints and Grievances.
 Press 2 for Billing and Accounts.
 Press 3 for Human Resources.
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

 For after-hours emergencies, press 0 and your call will be forwarded
 to our on-call administrator.

 To send a fax, please hang up and send your fax to this same number."
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
