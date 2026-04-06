# Deployment Checklist

## Phase 1: Pre-Deployment (Week 1-2)

### Account & Compliance
- [ ] Sign up for RingCentral Ultra plan
- [ ] Request and execute Business Associate Agreement (BAA)
- [ ] Confirm HIPAA compliance features are enabled on the account
- [ ] Designate Super Admin (limit to 2 people max)
- [ ] Enable Two-Factor Authentication (2FA) for all admin accounts

### Number Porting
- [ ] Submit Letter of Authorization (LOA) to port 760-888-8888
- [ ] Provide current carrier account number and PIN
- [ ] Confirm port date with RingCentral (typically 7-14 business days)
- [ ] Set up temporary forwarding from old carrier during transition
- [ ] Verify number is active on RingCentral after port completes

### Network Preparation
- [ ] Verify internet bandwidth (minimum 25 Mbps symmetric recommended)
- [ ] Run RingCentral Network Assessment Tool (Quality of Service test)
- [ ] Configure firewall rules (see README.md § Network)
- [ ] **DISABLE SIP ALG** on firewall/router
- [ ] Create Voice VLAN (VLAN 20) on managed switch
- [ ] Configure QoS: DSCP 46 (EF) for VLAN 20 traffic
- [ ] Install and test PoE switch
- [ ] Run Cat6 cabling to all desk phone locations
- [ ] Install WiFi access point(s) for softphone connectivity

## Phase 2: Hardware Setup (Week 2-3)

### Desk Phone Provisioning
- [ ] Unbox and connect Yealink T54W (receptionist)
- [ ] Unbox and connect Yealink T43U x4 (department desks)
- [ ] Unbox and connect Yealink W76P x2 (cordless for mobile staff)
- [ ] Unbox and connect Yealink CP920 (conference room)
- [ ] Register each phone's MAC address in RingCentral Admin
- [ ] Assign each phone to its user/extension
- [ ] Verify Zero-Touch Provisioning (ZTP) — phones should auto-configure
- [ ] Test each phone: make/receive a call, check display, test hold/transfer

### Softphone Setup
- [ ] Install RingCentral App on receptionist's PC
- [ ] Install RingCentral App on Office Manager's mobile (iOS/Android)
- [ ] Install RingCentral App on each department lead's mobile
- [ ] Verify softphone audio quality on WiFi and cellular

## Phase 3: System Configuration (Week 3-4)

### User & Extension Setup
- [ ] Create user accounts for all staff
- [ ] Assign extensions (see README.md § Account Hierarchy)
- [ ] Set voicemail greetings for each department mailbox
- [ ] Configure voicemail-to-email for each department
- [ ] Set call recording policy (automatic for all inbound/outbound)

### Auto-Attendant / IVR
- [ ] Record or upload Business Hours greeting (professional voice)
- [ ] Record or upload After Hours greeting
- [ ] Configure menu options (1=Complaints, 2=Billing, 3=HR, 0=Operator, 9=Directory)
- [ ] Set business hours schedule (Mon-Fri 8:00 AM - 5:00 PM PST)
- [ ] Configure holiday schedule
- [ ] Test each menu option end-to-end

### Ring Groups & Failover
- [ ] Create Complaints ring group (simultaneous, 3 phones, 15s timeout)
- [ ] Create Billing ring group (sequential, 2 phones, 20s timeout)
- [ ] Create HR ring group (sequential, 1 phone, 20s timeout)
- [ ] Configure Tier 2 failover (cell phone forwarding) for each group
- [ ] Configure Tier 3 failover (voicemail) for each group
- [ ] Test failover by not answering — verify call escalates correctly

### Fax Configuration
- [ ] Enable fax on company number (760-888-8888)
- [ ] Assign fax extension (500)
- [ ] Configure fax-to-email: fax@unicareathome.com
- [ ] Test inbound fax: send test fax from external machine
- [ ] Test outbound fax: send via API (see Phase 4)
- [ ] Verify fax PDF quality and encryption

## Phase 4: Software Integration (Week 4-5)

### Python Environment
- [ ] Set up Python 3.11+ environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Configure environment variables (see `config/env.example`)
- [ ] Verify RingCentral API credentials (OAuth client ID + secret)
- [ ] Test authentication: run `python -m src.core.client`

### API Integration Testing
- [ ] Test outbound fax via API (single page)
- [ ] Test outbound fax via API (100+ pages, batch mode)
- [ ] Test call log retrieval
- [ ] Test fax status polling
- [ ] Test webhook subscription creation

### Webhook Setup
- [ ] Deploy webhook server (Flask) to HTTPS endpoint
- [ ] Register webhook subscriptions for fax events
- [ ] Register webhook subscriptions for missed call events
- [ ] Test webhook delivery with a live fax
- [ ] Verify webhook signature validation

### Compliance Integration
- [ ] Verify audit logger is capturing all events
- [ ] Test log rotation and retention
- [ ] Verify no PHI appears in application logs
- [ ] Run a compliance review of all log outputs

## Phase 5: Testing & Go-Live (Week 5-6)

### Functional Testing
- [ ] Call 760-888-8888 from external phone — verify IVR plays
- [ ] Press each menu option — verify routing
- [ ] Let phones ring unanswered — verify failover chain
- [ ] Send fax to 760-888-8888 — verify auto-detection and receipt
- [ ] Send 100+ page fax via API — verify batch completion
- [ ] Test after-hours routing — call outside business hours
- [ ] Test holiday routing
- [ ] Test call recording — verify recording is accessible and encrypted

### Load Testing
- [ ] Simulate 5 concurrent inbound calls — verify all route correctly
- [ ] Send 10 concurrent outbound faxes via API — verify queue handling
- [ ] Verify no call quality degradation under load

### Security Testing
- [ ] Verify TLS on all API connections (no HTTP fallback)
- [ ] Verify SRTP on all voice calls
- [ ] Attempt access with wrong credentials — verify rejection
- [ ] Review RingCentral admin audit log for test activity

### Go-Live
- [ ] Confirm number port is complete and number is active
- [ ] Remove temporary call forwarding from old carrier
- [ ] Notify all staff of new system and provide training
- [ ] Notify external contacts of fax capability on main number
- [ ] Monitor system for 48 hours post-launch
- [ ] Address any issues and document in runbook

## Phase 6: Post-Deployment (Ongoing)

- [ ] Weekly: Review call logs and fax delivery reports
- [ ] Monthly: Review audit trails for compliance
- [ ] Monthly: Check for RingCentral platform updates
- [ ] Quarterly: Access control review (add/remove users)
- [ ] Annually: Renew BAA and review compliance posture
- [ ] Annually: Conduct security risk assessment
