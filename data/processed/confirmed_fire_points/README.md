# Confirmed fire-point handoff

This directory contains small, versioned outputs produced by the visual fire-point
confirmation module for downstream spread-model development. Large source imagery
is not stored in Git.

Each JSON document preserves the event and source-candidate identity, the WGS84
ignition coordinate, confirmation evidence, and a flat `forefire_input` object.
Member C can read `forefire_input` directly while the live integration uses:

```text
GET /api/visual-verification/events/{event_id}/confirmed-fire-points
```

The Dixie Fire document is a real historical course-demo result and a concrete
integration fixture. It is not a hard-coded condition in the generic selection
algorithm.
