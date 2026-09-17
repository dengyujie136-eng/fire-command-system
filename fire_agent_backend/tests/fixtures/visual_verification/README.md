# Visual verification fixtures

These files are deterministic development and test fixtures for member B's module.
They are not observations of the simulated Cresta Dam event. The coordinates and
event identifiers in the JSON files are synthetic, and every fixture record is
marked with `is_simulated: true`.

`candidate_input.json` follows member A's agreed HTTP/MQTT batch contract
`fire.hotspot.candidate.v0.1`. `member_a_historical_candidate.json` preserves the
provided FIRMS example and verifies that a real historical observation can be
replayed with `is_simulated: false` and `replay.is_replay: true`. JSON files remain
development fixtures rather than a production synchronization mechanism.

## Image provenance

| File | Test role | Source page | Usage note |
| --- | --- | --- | --- |
| `wildfire_smoke_nasa.jpg` | visible smoke and wildfire | NASA Earth Observatory, “New Fires Scorch the Hills of Southern California” | Retain NASA/USGS attribution and review NASA media-use guidance before redistribution. |
| `wildfire_false_color_nasa.jpg` | active fire and burn-scar context | Same NASA Earth Observatory article | Retain NASA/USGS attribution and review NASA media-use guidance before redistribution. |
| `bare_ground_usgs.jpg` | non-fire bare-ground negative | USGS, “Sunset over the desert” | Source page labels the image Public Domain. |
| `cloud_cover_noaa.jpg` | cloud/low-quality uncertain case | NOAA/NESDIS/STAR GOES-West Full Disk | U.S. Government imagery; retain NOAA attribution and verify dataset-specific terms before redistribution. |

The SHA-256 values frozen in `imagery_assets.json` detect accidental fixture
replacement. Replace these reference assets with event-specific imagery once the
upstream data interface and actual data rights are confirmed.
