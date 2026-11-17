# Carrier Profiles (Russian Mobile Networks)

Selected with `--carrier <name>` (or `VPN_CARRIER`). The profile sets the
throttling threshold and the SNI whitelist that is used to filter links.

## megafon
- Reality: viable, degrading
- xhttp: viable (packet-up)
- SNI: strict — must be a RU whitelist domain
- Throttle threshold: 80 KB/s
- SNI: `rutube.ru`, `vkvideo.ru`, `ozon.ru`, `kinopoisk.ru`, `wildberries.ru`
  plus the full universal Russian whitelist (see `whitelist-sni.md`).

## mts
- Reality: best option
- xhttp: blocked
- SNI: soft — foreign may work, RU more stable
- Throttle threshold: 50 KB/s
- SNI: `sun6-21.userapi.com`, `web.max.ru`, `download.max.ru`, `calls.max.ru`
  plus the full universal Russian whitelist. This is wider than before: a
  strict four-domain list threw away most working links.

## beeline
- Reality: unstable
- xhttp: preferred
- UDP: blocked (do not use Hysteria2 / WireGuard)
- Throttle threshold: 50 KB/s
- SNI: `yandex.ru`, `yandex.net`, `vk.com`, `mail.ru`

## tele2
- Reality: viable
- xhttp: viable
- SNI: lenient (foreign ok)
- Throttle threshold: 50 KB/s

## auto
- No SNI filtering on a normal (blacklist) environment.
- On a whitelist-only environment (VK reachable, Google not) it requires that a
  link carries an SNI, and drops the ones without one.

## Notes

All profiles accept any SNI that matches a domain in
`common.RU_SNI_HINTS` (suffix match), so subdomains such as
`sub.yandex.ru` are accepted too. Filtering never overrides the live test:
a link that passes the filter is still dropped if it cannot connect.

When `--limit` is used, links with a Russian whitelist SNI are tested first
(`retest.rank_links`), so a short trial tests the useful links rather than an
alphabetical slice. Malformed links (missing host/port/uuid) are dropped
before any network work (`retest.usable_links`).
