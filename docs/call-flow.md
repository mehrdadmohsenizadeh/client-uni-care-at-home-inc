# Call Flow & IVR State Machine

## Inbound Call Flow — 760-888-8888

> **Design Note:** Automatic CNG tone detection on a shared Voice+Fax DID is
> unreliable in RingCentral — IVR greetings interfere with T.30 handshakes.
> Instead, fax callers use **Press 4** in the IVR to reach a clean, greeting-free
> Message-Only Extension for fax. This guarantees a proper T.38 negotiation.

```
Caller dials (760) 888-8888
        │
        ▼
┌───────────────────┐
│ RingCentral       │
│ Auto-Attendant    │
│ (IVR Greeting)    │
└────┬──┬──┬──┬─────┘
     │  │  │  │
  [1-3,0,9]  [4]
  Voice      "Send a Fax"
  Options         │
     │            ▼
     │   ┌──────────────────┐
     │   │ Fax Extension    │
     ▼   │ (ext 500)        │
 Check   │ Message-Only     │
 Time    │ No greeting/VM   │
 of Day  │                  │
     │   │ T.38 Negotiation │
     │   │ Fallback: G.711  │
     │   │ passthrough      │
     │   │                  │
Bus.     │ Store & Forward: │
Hrs &    │ ┌──────────────┐ │
After    │ │Receive pages │ │
Hrs      │ │Render to PDF │ │
     │   │ │Encrypt (AES) │ │
     │   │ │Store 90 days │ │
     │   │ │Email notify  │ │
     │   │ │Webhook POST  │ │
     │   │ └──────────────┘ │
     ▼   └──────────────────┘
```

## Business Hours IVR (Mon-Fri 8:00 AM - 5:00 PM PST)

```
┌──────────────────────────────────┐
│ GREETING                         │
│ "Thank you for calling           │
│  Uni Care At Home..."            │
│                                  │
│  DTMF Timeout: 10 seconds       │
│  Max Retries: 3                  │
│  On Timeout: Repeat prompt       │
│  On Max Retry: Route to Operator │
└──────┬───┬───┬───┬───┬───┬──────┘
       │   │   │   │   │   │
    [1]│ [2]│ [3]│ [4]│ [0]│ [9]
       │   │   │   │   │   │
       ▼   ▼   ▼   ▼   ▼   ▼

[1] COMPLAINTS & GRIEVANCES
    │
    ├─► "Connecting you to our Complaints department..."
    │
    ├─► Ring Group: SIMULTANEOUS (all phones ring at once)
    │   ├── Phone A: Complaints Desk 1 (Yealink T43U)
    │   ├── Phone B: Complaints Desk 2 (Yealink T43U)
    │   └── Phone C: Complaints Desk 3 (Yealink T43U)
    │   Timeout: 15 seconds
    │
    ├─► TIER 2 FAILOVER (Find Me / Follow Me)
    │   └── Office Manager Cell: (760) XXX-XXXX
    │   Timeout: 15 seconds
    │
    └─► TIER 3 FAILOVER
        └── Voicemail Box → complaints@unicareathome.com
            Recording saved + transcribed + encrypted

[2] BILLING & ACCOUNTS
    │
    ├─► "Connecting you to our Billing department..."
    │
    ├─► Ring Group: SEQUENTIAL (one phone at a time)
    │   ├── Phone A: Billing Desk (Yealink T43U) — 20 sec
    │   └── Phone B: Billing Backup (Yealink T43U) — 20 sec
    │
    ├─► TIER 2 FAILOVER
    │   └── Admin Cell: (760) XXX-XXXX — 15 sec
    │
    └─► TIER 3 FAILOVER
        └── Voicemail Box → billing@unicareathome.com

[3] HUMAN RESOURCES
    │
    ├─► "Connecting you to Human Resources..."
    │
    ├─► Ring Group: SEQUENTIAL
    │   └── Phone A: HR Desk (Yealink T43U) — 20 sec
    │
    ├─► TIER 2 FAILOVER
    │   └── HR Director Cell: (760) XXX-XXXX — 15 sec
    │
    └─► TIER 3 FAILOVER
        └── Voicemail Box → hr@unicareathome.com

[4] SEND A FAX
    │
    ├─► "Please start your fax transmission now."
    │
    └─► Route to Fax Extension (500) — Message-Only
        ├── No greeting, no voicemail, no call queue
        ├── Clean T.38 handshake (fallback: G.711 passthrough)
        ├── Receive all pages → render to PDF → AES-256 encrypt
        ├── Email notification → fax@unicareathome.com
        └── Webhook POST → /webhooks/ringcentral (fax.received)

[0] OPERATOR / FRONT DESK
    │
    ├─► Direct ring: Receptionist (Yealink T54W)
    │   Timeout: 20 seconds
    │
    └─► Failover: Office Manager voicemail

[9] COMPANY DIRECTORY
    │
    └─► Dial-by-Name directory (first 3 letters of last name)
```

## After Hours IVR

```
┌──────────────────────────────────┐
│ AFTER HOURS GREETING             │
│ "Our office is currently closed. │
│  Hours: Mon-Fri 8AM-5PM PST"    │
└──────┬───┬───┬───┬───┬──────────┘
       │   │   │   │   │
    [1]│ [2]│ [3]│ [4]│ [0]
       │   │   │   │   │
       ▼   ▼   ▼   ▼   ▼

[1] → Voicemail: complaints@unicareathome.com
[2] → Voicemail: billing@unicareathome.com
[3] → Voicemail: hr@unicareathome.com
[4] → Fax Extension (500) — available 24/7, no greeting
[0] → EMERGENCY FORWARD
      └── On-Call Admin Cell (Find Me / Follow Me)
          ├── Admin 1: 15 sec
          ├── Admin 2: 15 sec
          └── Final: Emergency voicemail + SMS alert
```

## Holiday Schedule

Configure in RingCentral Admin > Phone System > Auto-Receptionist > Holiday Hours:

| Holiday | Date | Routing |
|---|---|---|
| New Year's Day | Jan 1 | After Hours IVR |
| Memorial Day | Last Mon in May | After Hours IVR |
| Independence Day | Jul 4 | After Hours IVR |
| Labor Day | First Mon in Sep | After Hours IVR |
| Thanksgiving | 4th Thu in Nov | After Hours IVR |
| Christmas | Dec 25 | After Hours IVR |

## Ring Group Configuration Summary

| Group | Strategy | Members | Per-Member Timeout | Total Max Wait |
|---|---|---|---|---|
| Complaints | Simultaneous | 3 desk phones | 15s | 15s before failover |
| Billing | Sequential | 2 desk phones | 20s each | 40s before failover |
| HR | Sequential | 1 desk phone | 20s | 20s before failover |
| After-Hours Emergency | Sequential | 2 cell phones | 15s each | 30s before voicemail |
