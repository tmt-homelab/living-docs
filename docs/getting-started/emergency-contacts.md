# Emergency Contacts

> **Print this page and keep it in a visible location** (fridge, home office)
> This is for emergency situations when services are down or something is broken.

---

## Critical Contacts (Fill In)

| Role | Name | Phone | Email | When to Call |
|------|------|-------|-------|--------------|
| **Primary (Todd)** | Todd Miller | [INSERT] | [INSERT] | Anything critical, everything down |
| **Backup Contact** | [NAME] | [INSERT] | [INSERT] | Todd unavailable, urgent issues |
| **ISP Support** | [YOUR ISP] | [INSERT] | [INSERT] | Internet down (not internal services) |
| **Hardware Support** | [IF APPLICABLE] | [INSERT] | [INSERT] | Server hardware failure |

---

## Service Status Quick Reference

### How to Check If It's Just You or Everyone

1. **Ask other family members** — Can they access it?
2. **Check from a different device** — Phone vs computer
3. **Check the status page**: [Uptime Kuma](https://uptime.themillertribe-int.org) (if accessible)

### Status Page Legend

| Status | What It Means | What to Do |
|--------|--------------|------------|
| 🟢 Operational | Everything working | Not a problem |
| 🟡 Degraded | Something slow or partial | Monitor, may fix itself |
| 🔴 Down | Service not accessible | Call Todd if it affects you |
| ⚫ Maintenance | Planned maintenance | Wait for it to complete |

---

## Quick Diagnosis Flowchart

```
Something's Not Working
        │
        ▼
Is it just one service?
   │         │
  YES        NO
   │         │
   ▼         ▼
Check    Is internet
status   working?
page        │
   │     │      │
  YES    YES   NO
   │     │      │
   ▼     ▼      ▼
Wait   Check  Check
for    if it's Wi-Fi
fix    your   or router
       device
```

---

## Important Information

### Where Passwords Are Stored
- **Todd's password manager**: 1Password (master password known only to Todd)
- **Family-shared passwords**: In 1Password family vault
- **Emergency access**: Contact backup contact if Todd is unavailable

### Hardware Location
- **Main servers**: Home office, server closet
- **Network equipment**: Entryway closet
- **UPS (battery backup)**: Same locations as equipment

### What Todd Needs to Know
When calling Todd about an issue, have this information ready:
1. **What service** isn't working
2. **When it started** (just now? this morning?)
3. **What you tried** (restarted app, restarted device)
4. **Error messages** (exact text if possible)
5. **Who else is affected** (just you? whole family?)

---

## External Services (If We Need Them)

| Service | Contact | Notes |
|---------|---------|-------|
| Internet Provider | [ISP Phone] | For internet outages only |
| Dell Support | 1-800-xxx-xxxx | For server hardware (if under warranty) |
| NVIDIA Support | [If applicable] | For GPU issues (rare) |

---

## Internal Documentation Links

If you're technical and need more info:

- [Full Family Guide](family-guide.md)
- [Disaster Recovery Procedures](../disaster-recovery/recovery-procedures/overview.md)
- [Operations Runbooks](../operations/runbooks/overview.md)
- [Infrastructure Overview](../infrastructure/hosts.md)

---

## Post-Incident Checklist

After any major incident, Todd should:

- [ ] Document what happened in incident report
- [ ] Update runbooks if new procedure was learned
- [ ] Notify family when resolved
- [ ] Schedule post-mortem if significant outage

---

*Last updated: 2026-03-11*
*Next review: Quarterly (or after any major incident)*
