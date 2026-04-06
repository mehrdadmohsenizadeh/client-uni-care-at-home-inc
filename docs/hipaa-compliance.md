# HIPAA/HITECH Compliance Matrix

## Business Associate Agreement (BAA)

RingCentral signs a BAA as part of the Ultra plan for healthcare customers. The BAA covers:

- Voice calls (recordings, voicemails, transcriptions)
- Fax transmissions (inbound and outbound, stored PDFs)
- Message content (SMS, team messaging within RingCentral)
- API access and data retrieved via the REST API
- Cloud storage of all the above

**Action Required:** Request the BAA during account setup. RingCentral provides it via their compliance team — typically a 3-5 business day turnaround.

## Encryption Matrix

| Data Type | In Transit | At Rest | Protocol/Standard |
|---|---|---|---|
| Voice calls | SRTP (AES-128) | N/A (real-time) | RFC 3711 |
| SIP signaling | TLS 1.2+ | N/A | RFC 5246 |
| Fax transmission | T.38 over TLS | AES-256 | ITU-T T.38 |
| Stored fax PDFs | TLS 1.2+ (download) | AES-256 | FIPS 140-2 |
| Voicemail recordings | TLS 1.2+ (download) | AES-256 | FIPS 140-2 |
| API communications | TLS 1.2+ (HTTPS) | N/A | RFC 5246 |
| Webhook payloads | TLS 1.2+ (HTTPS) | N/A | Verification token |
| Call recordings | TLS 1.2+ (download) | AES-256 | FIPS 140-2 |

## Access Controls

### Role-Based Access (Configure in RingCentral Admin)

| Role | Permissions |
|---|---|
| **Super Admin** | Full system access, BAA management, user provisioning |
| **Phone Admin** | Phone system config, IVR, ring groups — no billing |
| **Billing Admin** | Billing and subscription only |
| **User Manager** | Add/remove users, reset passwords |
| **Standard User** | Own extension, voicemail, call log, fax send/receive |

### Minimum Necessary Access

Each department should only have access to their own:
- Call recordings
- Voicemails
- Fax inbox
- Call logs

Cross-department access requires Super Admin authorization.

## Audit Trail Requirements

### What RingCentral Logs Automatically

| Event | Logged Data | Retention |
|---|---|---|
| Inbound call | Caller ID, time, duration, recording ID, extension | 12 months |
| Outbound call | Destination, time, duration, recording ID, extension | 12 months |
| Fax sent | Recipient, pages, status, messageId, timestamp | 12 months |
| Fax received | Sender, pages, messageId, timestamp | 12 months |
| Fax viewed/downloaded | User, timestamp, IP address | 12 months |
| Login/logout | User, timestamp, IP, device | 12 months |
| Admin changes | User, action, before/after values, timestamp | 12 months |
| Password changes | User, timestamp | 12 months |

### Additional Audit Logging (Our Python Integration)

Our `src/compliance/audit.py` module supplements RingCentral's native logging:

| Event | Our Additional Data |
|---|---|
| Fax batch sent | Batch ID, document name, total pages, split info |
| Fax batch status | Per-chunk status, retry count, final disposition |
| API token refresh | Timestamp, success/failure |
| Webhook received | Event type, payload hash (not PHI), processing status |
| Fax PDF downloaded | User, purpose, destination system |

## HIPAA Technical Safeguards Checklist

| Safeguard (45 CFR 164.312) | Implementation |
|---|---|
| **Access Control (a)(1)** | Role-based access in RingCentral Admin; unique user IDs |
| **Audit Controls (b)** | Native RC audit logs + custom Python audit trail |
| **Integrity (c)(1)** | AES-256 at rest; checksums on fax PDFs |
| **Transmission Security (e)(1)** | SRTP for voice; TLS 1.2+ for all API/data; T.38 for fax |
| **Authentication (d)** | Username + password + optional 2FA (TOTP) |
| **Automatic Logoff (a)(2)(iii)** | Session timeout on admin portal (configurable) |
| **Emergency Access (a)(2)(ii)** | Super Admin break-glass procedure documented |

## PHI Handling in Code

**Critical Rules for the Python Integration:**

1. **Never log PHI** — Fax content, caller names, patient data must NEVER appear in application logs.
2. **Never store PHI locally** — All fax PDFs stay in RingCentral's encrypted cloud. Our code only references message IDs.
3. **Token security** — OAuth tokens stored in environment variables, never in code or config files.
4. **Webhook validation** — Always verify webhook signatures before processing.
5. **Secure transport only** — All webhook endpoints must use HTTPS with valid certificates.

## Compliance Contacts

| Role | Responsibility |
|---|---|
| HIPAA Privacy Officer | Overall compliance, breach notification |
| HIPAA Security Officer | Technical safeguards, access reviews |
| RingCentral Account Rep | BAA execution, platform compliance questions |
| IT Administrator | System configuration, user provisioning, network security |

## Breach Response

In the event of a suspected breach involving the phone/fax system:

1. **Contain** — Disable affected user accounts immediately via RingCentral Admin
2. **Assess** — Review audit logs (RingCentral + our Python logs) to determine scope
3. **Notify** — Follow organization's breach notification procedure (per HITECH Act, within 60 days)
4. **Remediate** — Change credentials, review access controls, update procedures
5. **Document** — Log the entire incident and response in the compliance file
