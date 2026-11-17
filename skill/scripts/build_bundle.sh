#!/usr/bin/env bash
# Build a ready-to-import bundle from a vpn-list output directory.
#
# usage: build_bundle.sh [OUT_DIR] [BUNDLE_DIR]
#   OUT_DIR     directory produced by run.py  (default ~/Desktop/vpn-list)
#   BUNDLE_DIR  where to assemble the bundle  (default ~/Desktop/vpn-ready)
set -euo pipefail

OUT="${1:-$HOME/Desktop/vpn-list}"
BUNDLE="${2:-$HOME/Desktop/vpn-ready}"
if [ ! -d "$OUT" ]; then
  echo "no such output dir: $OUT" >&2
  exit 1
fi

stable_n=$([ -s "$OUT/working_stable_unique.txt" ] && wc -l < "$OUT/working_stable_unique.txt" || echo 0)
uniq_n=$([ -s "$OUT/working_unique.txt" ] && wc -l < "$OUT/working_unique.txt" || echo 0)
if [ "$stable_n" -eq 0 ] && [ "$uniq_n" -eq 0 ]; then
  echo "refusing to build an EMPTY bundle: no working servers in $OUT" >&2
  exit 2
fi

# Rebuild the bundle from scratch so leftovers from earlier runs can never
# linger (build only ever writes the files below plus README.txt).
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE"
copy_if() { if [ -f "$1" ]; then cp -f "$1" "$BUNDLE/$2"; fi; }
copy_if "$OUT/working_stable_unique.txt" "1-working_stable_unique.txt"
copy_if "$OUT/working_stable_base64.txt" "2-subscription-base64.txt"
copy_if "$OUT/clash.yaml"                "3-clash.yaml"
copy_if "$OUT/working_unique.txt"        "4-more_servers.txt"

cat > "$BUNDLE/README.txt" <<EOF
VPN Working List — حزمة استيراد
==============================
تاريخ البناء: $(date -Is)

الملفات:
  1-working_stable_unique.txt   القائمة الأساسية ($stable_n سيرفراً مستقرّاً) — استوردها مباشرة
  2-subscription-base64.txt     نفس القائمة بصيغة base64 (اشتراك) — الصق محتواها في "استيراد من الحافظة"
  3-clash.yaml                  لعملاء Clash/Mihomo
  4-more_servers.txt            قائمة أوسع ($uniq_n سيرفراً نجح ≥2/3)

الاستخدام:
  - v2rayNG / Hiddify / NekoBox / Streisand (أندرويد):
      استيراد من ملف -> 1-working_stable_unique.txt
      أو انسخ 2-subscription-base64.txt والصقه في "استيراد من الحافظة".
  - v2rayN / Nekoray / Hiddify (ويندوز/لينكس): ملف أو حافظة.
  - Clash / Mihomo / Clash Verge / OpenWrt: استخدم 3-clash.yaml.

ملاحظة: السيرفرات المجانية تتغيّر؛ شغّل المهارة أو انتظر المهمة اليومية للحصول على قائمة أحدث.
EOF

PARENT="$(dirname "$BUNDLE")"
BASE="$(basename "$BUNDLE")"
tar -czf "$PARENT/$BASE.tar.gz" -C "$PARENT" "$BASE"
echo "bundle:   $BUNDLE"
echo "archive:  $PARENT/$BASE.tar.gz"
echo "servers:  stable=$stable_n more=$uniq_n"
