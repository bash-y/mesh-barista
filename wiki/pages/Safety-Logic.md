# Safety Logic

The system's job is to never run a pump dry, never overflow the cup, and never keep pumping after it
loses contact with part of the system.

## Rules

| Rule | Threshold | What it protects |
| --- | --- | --- |
| Dry-run lock | below 10 %, unlock above 20 % | The pump; the gap stops relay chatter |
| Overflow stop | cup at 90 %, read by Node 3 | No spilled water |
| Stale data stop | no cup reading for 1.5 s | Never pour blind |
| Lost node | no heartbeat for 3 s | Pumps off, buzzer, zone flagged |
| Leave SAFE | operator acknowledge | A half-poured cup is an unknown state |
| Watchdog | Node 1's loop frozen for 3 s | Resets Node 1 with every pump off |

The exact values live in the sketches: see `LEVEL_LOCK_PCT`, `LEVEL_UNLOCK_PCT`, `CUP_FULL_PCT`,
`CUP_STALE_MS`, `LOST_MS` and `WATCHDOG_MS` in [[Configuration Reference]].

## States

| State | Meaning |
| --- | --- |
| **NORMAL** | All nodes alive. Pours allowed. |
| **DEGRADED** | A reservoir is low, or running without Node 2 (from the web dashboard). |
| **SAFE** | Pumps off, buzzers on, LED flashing red. Needs an operator acknowledge, and Node 3 back. |
