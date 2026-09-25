# Information Security Policy

## Passwords and authentication

Passwords must be at least 14 characters. Password rotation is not required on a schedule; it is
required immediately after suspected compromise. All staff must use phishing-resistant MFA
(hardware security keys or passkeys). SMS codes are not permitted for privileged accounts.

## Logging and retention

Audit logs for production systems are retained for 400 days: 30 days hot in the logging platform
and the remainder in write-once cold storage. Application debug logs are retained for 30 days.
Access to audit logs is limited to the Security team and requires a ticket.

## Cloud access

Engineers use short-lived credentials via workload identity or SSO. Long-lived service account keys
are prohibited by organisation policy. Break-glass access is time-boxed to 60 minutes and reviewed
weekly.
