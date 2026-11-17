# Throttling Detection (TSPU Silent Throttling)

TSPU often allows the handshake and the 204 response, then throttles the stream
to a few Kbit/s after 30–60 seconds. A plain connectivity check does not catch
this, so the pipeline has a second stage.

## How it works

For each *candidate* that already passed the connectivity rounds:

1. A dedicated `sing-box` instance is started with **one local SOCKS inbound per
   candidate**, each routed to its own outbound
  (`{"inbound": ["iN"], "outbound": "tN"}` route rules).
2. Throughput: `curl` downloads `VPN_THROTTLE_TEST_SIZE` KB from
  `VPN_THROTTLE_URL` (default `speed.cloudflare.com`) through the candidate's
  SOCKS port; bytes / seconds → KB/s.
- Below the carrier threshold → the link is written to `working_throttled.txt`
  and excluded from the stable list.
- If the throughput cannot be measured at all, the link is **not** marked
  throttled (conservative — the network may simply be restricted).
5. Sustained test: 5 `generate_204` requests spread over
   `VPN_SUSTAINED_SECONDS`; any failure marks the link unstable
   (`working_unstable.txt`) and excludes it.

## Tuning

- `VPN_THROTTLE_KBPS` (default 50) — Megafon profile uses 80.
- `VPN_THROTTLE_TEST_SIZE` (default 100 KB).
- `VPN_SUSTAINED_SECONDS` (default 30).

## Enabling

- `--throttle` (force) / `--no-throttle` (disable).
- Enabled automatically when `--carrier` is a specific operator.
- `VPN_THROTTLE=1` in the environment.

Throttled and unstable links are listed separately and are **excluded** from
`working_stable_unique.txt`.
