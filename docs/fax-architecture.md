# Fax Architecture — Store-and-Forward Pipeline

## Overview

RingCentral's fax system uses a **store-and-forward** model. Unlike real-time fax (which requires both sides online simultaneously), store-and-forward decouples send and receive:

1. **Outbound:** Your application uploads a PDF to RingCentral's API. RingCentral's fax servers spool the document, negotiate T.38 or G.711 passthrough with the remote fax machine, handle retries on failure, and report back via webhook.

2. **Inbound:** When a fax arrives on 760-888-8888, RingCentral detects the CNG tone, routes to the fax extension, receives all pages server-side, renders to PDF, encrypts, stores, and fires a webhook notification.

## Signal Detection (How One Number Handles Both Voice and Fax)

```
Incoming Call to 760-888-8888
         │
         ▼
┌─────────────────────────┐
│ RingCentral Edge SBC    │
│                         │
│ Listen for CNG tone     │
│ (1100 Hz, 0.5s bursts)  │
│ during first 2-4 sec    │
│                         │
│ CNG detected?           │
│   YES → Route to Fax   │
│   NO  → Route to IVR   │
└─────────────────────────┘
```

**CNG (Calling Tone):** Every fax machine sends a 1100 Hz tone when initiating. RingCentral's Session Border Controller (SBC) listens for this during the initial seconds of a call. This is industry-standard and requires no configuration — it is automatic when fax is enabled on the company number.

## Outbound Fax Flow (API-Driven)

```
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐
│ Python App  │     │ RingCentral API   │     │ Remote Fax      │
│             │     │                   │     │ Machine/Server  │
│ Upload PDF  ├────►│ POST /fax         │     │                 │
│ (multipart) │     │                   │     │                 │
│             │     │ Spool to queue    │     │                 │
│             │     │                   │     │                 │
│ Return:     │◄────┤ 200 OK            │     │                 │
│ messageId   │     │ {id, status:      │     │                 │
│             │     │  "Queued"}        │     │                 │
│             │     │                   │     │                 │
│             │     │ T.38 negotiation  ├────►│                 │
│             │     │ (or G.711 fback)  │     │ CED tone        │
│             │     │                   │◄────┤ (2100 Hz)       │
│             │     │                   │     │                 │
│             │     │ Transmit pages    ├────►│ Receive pages   │
│             │     │ (ECM error corr.) │     │                 │
│             │     │                   │     │                 │
│ Webhook:    │◄────┤ POST /webhook     │     │                 │
│ fax.sent    │     │ {status: "Sent",  │     │                 │
│ or          │     │  pages: 120,      │     │                 │
│ fax.failed  │     │  duration: "4m"}  │     │                 │
└─────────────┘     └───────────────────┘     └─────────────────┘
```

### Key Behaviors:

- **Retries:** RingCentral automatically retries failed transmissions (busy signal, no answer) up to 3 times with exponential backoff.
- **ECM (Error Correction Mode):** Enabled by default — detects corrupted pages and retransmits them.
- **Large Documents:** The API accepts PDFs up to 200 pages or 20 MB per request. For documents exceeding this, batch into multiple fax messages.
- **Supported Formats:** PDF, TIFF, DOC, DOCX, TXT, JPG, PNG — all server-side converted to TIFF for transmission.

## Inbound Fax Flow

```
Remote Fax Machine
        │
        │ Dials 760-888-8888
        ▼
┌───────────────────┐
│ RingCentral SBC   │
│ CNG tone detected │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Fax Server        │
│                   │
│ 1. T.38 handshake │
│ 2. Receive pages  │
│ 3. ECM validation │
│ 4. Render → PDF   │
│ 5. OCR (optional) │
│ 6. Encrypt AES-256│
│ 7. Store (90 days)│
└────────┬──────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│ Email  │ │ Webhook  │
│ Notify │ │ POST     │
│        │ │          │
│ To:    │ │ Event:   │
│ fax@   │ │ fax.recv │
│ ucare  │ │ +PDF URL │
│ .com   │ │ +metadata│
└────────┘ └──────────┘
```

## Fax Storage & Retention

| Aspect | Detail |
|---|---|
| **Storage location** | RingCentral cloud (US data centers, SOC 2 Type II) |
| **Encryption at rest** | AES-256 |
| **Encryption in transit** | TLS 1.2+ |
| **Default retention** | 90 days (configurable via API) |
| **Download format** | PDF |
| **Access control** | Role-based — only assigned users can view fax content |
| **Audit trail** | Every view, download, forward, and delete is logged |

## Batching Strategy for 100+ Page Documents

For documents exceeding 200 pages:

```python
# See src/fax/sender.py for full implementation
# Strategy: Split PDF into ≤200-page chunks, send sequentially,
# track as a single logical "batch" in our audit log.

Batch ID: batch_20260406_001
├── Fax 1: Pages 1-200   → messageId: abc123
├── Fax 2: Pages 201-400 → messageId: def456
└── Fax 3: Pages 401-450 → messageId: ghi789

Status: ALL must succeed for batch = "Complete"
        ANY failure triggers alert + retry of failed chunk
```

## T.38 vs G.711 Passthrough

| Protocol | How It Works | When Used |
|---|---|---|
| **T.38** | Fax-over-IP protocol; encodes fax data in UDPTL packets. Error correction built-in. | Preferred — used when both sides support T.38 |
| **G.711 Passthrough** | Raw audio codec carrying fax tones over RTP. Less reliable but universal. | Fallback — used when remote side doesn't support T.38 |

RingCentral automatically negotiates the best protocol. No configuration needed.
