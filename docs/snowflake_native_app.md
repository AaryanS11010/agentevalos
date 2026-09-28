# Snowflake Native App packaging notes

## Why a native app, not just a service that connects to Snowflake

`services/eval-engine` connects *out* to a customer's Snowflake account with
credentials the customer provisions — fine for customers comfortable granting an
external service read access to labeled datasets. Some finance/healthcare customers
won't do that. The [`snowflake-native-app/`](../snowflake-native-app) package installs
*inside* their account instead: the scoring stored procedure and Streamlit UI run on
the customer's own compute, and no prediction data or model output ever crosses the
account boundary. This is the same product, offered as two deployment shapes.

## Current duplication (tracked, not yet resolved)

[`snowflake-native-app/app/python/udfs/run_eval.py`](../snowflake-native-app/app/python/udfs/run_eval.py)
duplicates the scoring math in
[`services/eval-engine/app/snowflake/udf_scoring.py`](../services/eval-engine/app/snowflake/udf_scoring.py)
rather than importing it, because native app Python handlers run in Snowflake's
sandboxed runtime without access to arbitrary local packages (no `agentevalos-sdk`
import, no relative imports outside the app's own files).

Options to de-duplicate, in order of effort:

1. **Vendor a minimal scoring module** into `snowflake-native-app/app/python/` that
   both the native app and `eval-engine` import from a shared location via a build
   step (copy at CI time, not at runtime).
2. **Publish `agentevalos-sdk`'s pure-Python scoring functions as a Snowflake-hosted
   package** on the Snowflake Anaconda channel, once the scoring logic stabilizes —
   then both sides `import` the same versioned package.

Not resolved in this scaffold — pick an approach once the scoring logic itself is
locked down; duplicating a few functions is cheaper than premature sharing infra
while the math is still changing.

## Deployment

```bash
cd snowflake-native-app
snow app run              # local dev: creates app package + application
snow app version create   # cut a version for listing / cross-account testing
```

See [`snowflake-native-app/README.md`](../snowflake-native-app/README.md) for the
consumer-facing install + data-grant instructions.

## Marketplace listing (future)

Once the app is stable, list it on the Snowflake Marketplace so customers can install
it with zero infrastructure of their own — this is the natural distribution channel
for the "which foundational tabular model is most impactful for my industry" use case,
since the answer is only valuable if a compliance/risk team can self-serve it without
provisioning a new service.
