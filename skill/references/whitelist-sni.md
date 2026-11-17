# Whitelist SNI Domains (Russia)

Using an SNI from a Russian whitelisted domain significantly increases the
chance of passing TSPU. Domains are matched by suffix, so `sub.yandex.ru`
matches `yandex.ru`.

## Universal
- `yandex.ru`, `yandex.net`, `yastatic.net`
- `vk.com`, `userapi.com`, `vkvideo.ru`
- `mail.ru`, `ok.ru`, `max.ru`
- `gosuslugi.ru`, `mos.ru`, `rt.ru`, `rbc.ru`
- `ozon.ru`, `wildberries.ru`, `avito.ru`, `2gis.ru`, `dzen.ru`, `rutube.ru`
- `sberbank.ru`, `tinkoff.ru`, `vtb.ru`
- `x5.ru`, `5post-gate.x5.ru`

The full hint list lives in `scripts/common.py` (`RU_SNI_HINTS`). It is used
for **ranking** (which links to test first) and as the carrier allow-list.

## MTS-specific (strictest)
- `sun6-21.userapi.com`, `web.max.ru`, `download.max.ru`, `calls.max.ru`
- plus the universal list above

## Megafon-specific
- `rutube.ru`, `vkvideo.ru`, `ozon.ru`, `kinopoisk.ru`, `wildberries.ru`
- plus the universal list above

## Beeline-specific
- `yandex.ru`, `yandex.net`, `vk.com`, `mail.ru`
- plus the universal list above

## Tele2
- lenient: any SNI is accepted.

Links are filtered by `retest.filter_links()` before testing. A profile only
filters when `requires_ru_sni` is set (Megafon and MTS). Beeline/Tele2 keep any
SNI, and `auto` filters only when a whitelist environment is detected.

The lists are best-effort guidance from public Russian whitelist profiles, not
a guarantee: the live connectivity test always makes the final decision.
