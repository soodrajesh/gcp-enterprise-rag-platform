# Engineering Handbook

## Deployments

All production changes ship through the CI/CD pipeline. Direct console changes are blocked except
during a declared incident. Every service deploys with a canary at 10% for 15 minutes before full
rollout, and rolls back automatically if the error-rate SLO burn alert fires.

## On-call

On-call rotations are one week long. Engineers are compensated with time off in lieu equal to 1 day
per on-call week. Handover happens Monday 10:00 with a written summary of open issues.

## Service level objectives

Tier-1 services target 99.9% monthly availability. Tier-2 services target 99.5%. Error budgets are
reviewed in the monthly reliability meeting; if a budget is exhausted, feature work pauses until
reliability work restores it.
