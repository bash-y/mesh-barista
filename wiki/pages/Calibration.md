# Calibration

The water level sensors and pump flow rates are what every pour and safety stop is based on. Current
values are in [[Configuration Reference]] (`LEVEL_RAW`, `CUP_RAW`, `FLOW_ML_PER_S`).

<!-- include: HANDOFF.md#Calibration -->

## Flow rate

`FLOW_ML_PER_S` in Node 1 is still the default 20 mL/s for every pump, so each timed pour is an estimate.
To measure it, run each pump 10 s into a measuring cup and divide the mL by 10, then measure the error on
a 60 mL pour. The work is tracked in [[Sprint Status]] (*Every pour is based on a measured flow rate*).
