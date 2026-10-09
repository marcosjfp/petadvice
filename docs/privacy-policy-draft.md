# PETAdvice privacy policy — unpublished draft

**Do not publish this draft as a completed policy.** Operator, contact, hosting/email providers, jurisdiction, legal bases, transfer arrangements, account inactivity and backup retention have not been chosen. This document describes the implemented beta and marks decisions still required.

Policy version: `beta-2026-10-09`. Effective date: **[SET WHEN PUBLISHED]**.

## Who operates PETAdvice

Controller/business name: **[OPERATOR NAME AND ADDRESS]**.
Privacy contact: **[PRIVACY EMAIL]**.
Website: **[DOMAIN]**.
Hosting provider and storage region: **[PROVIDER / REGION]**.
Email provider and processing region: **[PROVIDER / REGION]**.

## Information the application processes

- Account email, password hash, account creation date, email verification date, and the date/version of your acknowledgement of the privacy notice. Passwords are hashed using Argon2id; the application does not store plaintext passwords.
- Pet profiles: name, species, optional breed/size, birth date, sex, neuter status, weight and environment/known-condition fields where supported. Avoid putting personal or sensitive information in pet names.
- Symptom checks: selected symptom, question/answer history, timing and educational urgency guidance.
- Security records: revocable sessions and authentication timestamps; hashed, expiring verification/recovery tokens. Pending email bodies are encrypted until delivery or expiry.
- Necessary browser session cookies. The guest access token is held in page memory, not persistent browser storage. Closing or refreshing the page loses access to that guest check.
- Connection addresses are used transiently for abuse prevention. Redis rate-limit keys contain keyed digests, rather than raw addresses/emails. Application request logs contain a random request ID, route template, method, response status and duration; they exclude request bodies, raw URLs, account/check IDs, cookies, addresses and reset links. **[DESCRIBE ANY ADDITIONAL HOSTING/CDN LOGS AND THEIR RETENTION]**.

The frontend now serves font files itself. The provided application does not include advertising or third-party analytics. Source links are external websites only if you choose to open them. **[DISCLOSE ANY SERVICES THE OPERATOR ADDS]**.

## Purpose and legal basis

The information supports accounts, saved pet profiles, educational symptom checks, security, recovery and data controls. **[SELECT AND DOCUMENT THE APPROPRIATE LEGAL BASIS FOR EACH PURPOSE UNDER ARTICLE 6, AND ANY REQUIRED ADDITIONAL CONDITIONS]**.

The signup checkbox records that you read the notice. It is not automatically a valid legal basis for every form of processing. Any future optional analytics/marketing consent needs its own choice and withdrawal process.

## Retention and deletion

| Data | Current application behavior | Operator decision still needed |
| --- | --- | --- |
| Guest checks and guest pet wrapper | Access expires after 24 hours by default; configurable with `GUEST_RETENTION_HOURS`. A healthy maintenance worker deletes expired records on its 30-second loop. Checks can also be downloaded/deleted while the page is open. | Confirm the chosen duration and worker monitoring before publishing. |
| Account, saved profiles and checks | Retained until account deletion. Deletion removes associated application records, sessions, action tokens and queued mail. | Set any inactivity/closure retention and support process; indefinite retention has not been approved. |
| Sessions | One-hour maximum access; logout/password reset revoke them. Expired/revoked records are removed after an additional day. | Confirm security-record retention. |
| Verification/recovery links | Verification: 24 hours. Recovery: 30 minutes. Single use; resends supersede earlier links. Used/expired records are cleared by maintenance. | Confirm security-record retention. |
| Pending email | Encrypted, retried with backoff, removed after delivery or expiry. Superseded links are not sent. Local development mailbox files are private and purged after 24 hours. | Document production provider retention and deletion. |
| Backups and operational logs | Backup tools exist, including encryption and safe restoration into empty databases. No production backup/log expiry schedule is installed yet. | **[BACKUP PERIOD, LOG PERIOD, ENCRYPTION/ACCESS CONTROLS AND AUTOMATED EXPIRY]**. |

Deletion from the live application does not erase independently retained backups immediately. **[SPECIFY HOW SOON BACKUP COPIES EXPIRE AND HOW DELETIONS ARE REAPPLIED AFTER A RESTORE]**. A restore must not bring deleted accounts back into active service.

## Providers, transfers and disclosure

Hosting/database and email providers will process information necessary to operate the service. **[LIST PROVIDERS, CONTRACTS, REGIONS, INTERNATIONAL TRANSFERS AND SAFEGUARDS]**. **[DESCRIBE ANY OTHER RECIPIENTS OR LEGALLY REQUIRED DISCLOSURES]**.

## Your choices and rights

Account controls allow JSON export and account deletion after password confirmation. Guest controls allow JSON download and deletion while the check is accessible. **[DESCRIBE CONTACT-BASED ACCESS/CORRECTION/OBJECTION/RESTRICTION REQUESTS, IDENTITY VERIFICATION, RESPONSE PROCESS AND APPLICABLE RIGHTS]**.

**[IDENTIFY THE APPROPRIATE SUPERVISORY AUTHORITY AND COMPLAINT ROUTE FOR THE OPERATOR'S JURISDICTION]**. **[SET ELIGIBILITY/CHILDREN'S POLICY AND ANY REQUIRED GUARDIAN PROCESS]**.

## Updates and publication

Publish an operator-approved policy at the configured HTTPS `PRIVACY_POLICY_URL`. Set `PRIVACY_OPERATOR`, `PRIVACY_EMAIL` and a new `PRIVACY_POLICY_VERSION`; notify users of material changes as applicable. Production startup requires these details, but configuration alone is not a legal review or compliance certification.

Source for the decisions this draft leaves open: [GDPR, especially Articles 5, 6, 13–22 and 32](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679). The operator must determine applicability and the final wording.
