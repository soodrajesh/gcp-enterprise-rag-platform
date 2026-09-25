# Incident Response Runbook

## Severity levels

Sev-1 means customer-facing outage or confirmed data exposure. Sev-2 is significant degradation
with a workaround. Sev-3 is minor impact. Anything ambiguous is treated as one level higher until
proven otherwise.

## Handling a Sev-1

The first responder pages the on-call Incident Commander (IC) within 5 minutes. The IC opens a
dedicated incident channel, assigns a Communications Lead and a Scribe, and posts a status page
update within 15 minutes. Updates repeat every 30 minutes until mitigation. The IC owns decisions;
nobody else changes production during a Sev-1 without the IC's approval.

Escalation contact for the on-call rota: oncall-lead@northwind.example, phone +353 1 555 0142.

## Post-incident review

A blameless post-incident review is held within 5 working days of every Sev-1 and Sev-2. It must
produce corrective actions with owners and due dates, tracked to completion.
