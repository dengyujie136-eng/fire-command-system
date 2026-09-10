# Dixie Fire ForeFire input preparation

The JSON manifest in this directory is the data-side input contract for member C. It records the selected ignition candidate, raster inputs, NASA POWER hourly weather, paths, coordinate reference systems, file sizes, and SHA-256 hashes.

This directory does not contain a completed `final_input.nc` or a verified ForeFire result yet. Member C must use the manifest to prepare the case-specific NetCDF and ForeFire case file.

The selected ignition rule is deterministic: the first candidate returned by the ordered Dixie Fire candidate-hotspot API. Its coordinate is an approximately 375 m VIIRS thermal-anomaly pixel center, not a surveyed ignition point.

Original hourly and daily weather data remain in their original `raw` and `processed/weather` locations. Any later resampling or interpolation must be written as a separate product and marked `is_interpolated=true`.
