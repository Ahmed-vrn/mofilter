#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# ============================================================
#  إصلاح شامل لمشروع "مفلتر السيرفرات" — الإصدار 1.4.1
#
#  يعمل من أي مكان: يكتشف مجلد المشروع تلقائيًا (بجانب السكربت،
#  أو ~/Desktop/desktop app، أو ~/Desktop/desktop app/mofilter-main).
#
#  يقوم بـ:
#   0) نسخة احتياطية كاملة قبل أي تعديل
#   1) توحيد الإصدار إلى 1.4.1 في التطبيق والمهارة والحزمة والتوثيق
#   2) إصلاح سطر --version الخاطئ في اقرأني.txt
#   3) دمج _pump() مع _stream() وحذف التكرار
#   4) إضافة تعليق «عقد» على STAGE_RE
#   5) تحسين cancel() مع waitpid WNOHANG (لا يعتبر الإيقاف نجاحًا)
#   6) إضافة READY_DIR إلى resolve_result
#   7) التأكد من اختبارات الوحدة (test_selftest.py)
#   8) إضافة FAQ إلى README.md
#   9) تحذير الحد=0 في الواجهة
#  10) إشعار عند تعطيل زر GitHub
#  11) شرح --single و --no-confirm في التوثيق
#  12) تشغيل الاختبارات وبناء حزمة النقل إن وُجد build_package.sh
#
#  الخيارات:
#    --no-backup   بلا نسخة احتياطية (غير مستحسن)
#    --no-build    لا تعِد بناء حزمة «مفلتر السيرفرات»
#    --no-test     لا تشغّل الاختبارات
#    --version X   وحّد إلى إصدار آخر (افتراضي 1.4.1)
#    --help
# ============================================================

set -euo pipefail

VERSION="1.4.1"
DO_BACKUP=1
DO_BUILD=1
DO_TEST=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-backup) DO_BACKUP=0 ;;
    --no-build)  DO_BUILD=0 ;;
    --no-test)   DO_TEST=0 ;;
    --version)   [ $# -ge 2 ] || { echo "--version يحتاج رقمًا" >&2; exit 2; }; VERSION="$2"; shift ;;
    --version=*) VERSION="${1#*=}" ;;
    -h|--help)
      awk 'NR==1 {next} /^# =+$/ { if (started) exit; started=1; next } started { sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) echo "خيار غير معروف: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${MOFILTER_PROJECT:-}"

if [ -z "$PROJECT" ]; then
  for cand in \
    "$SCRIPT_DIR" \
    "$SCRIPT_DIR/mofilter-main" \
    "$HOME/Desktop/desktop app" \
    "$HOME/Desktop/desktop app/mofilter-main" \
    "$PWD" \
    "$PWD/mofilter-main"; do
    if [ -f "$cand/vpn-web-app.py" ] && [ -f "$cand/README.md" ]; then
      PROJECT="$cand"
      break
    fi
  done
fi

[ -n "$PROJECT" ] || { echo "✘ لم أجد مجلد المشروع (vpn-web-app.py + README.md)" >&2; exit 1; }
[ -f "$PROJECT/vpn-web-app.py" ] || { echo "✘ vpn-web-app.py غير موجود في $PROJECT" >&2; exit 1; }
[ -f "$PROJECT/اقرأني.txt" ] || { echo "✘ اقرأني.txt غير موجود" >&2; exit 1; }
[ -f "$PROJECT/README.md" ] || { echo "✘ README.md غير موجود" >&2; exit 1; }

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'
say()  { printf "${C}▸${N} %s\n" "$*"; }
ok()   { printf "${G}✔${N} %s\n" "$*"; }
warn() { printf "${Y}⚠${N} %s\n" "$*"; }
die()  { printf "${R}✘${N} %s\n" "$*" >&2; exit 1; }

say "المشروع: $PROJECT"

# ---------- نسخة احتياطية ----------
if [ "$DO_BACKUP" = "1" ]; then
  BACKUP_ROOT="${MOFILTER_BACKUP_DIR:-$HOME/Desktop}"
  STAMP="$(date +%Y%m%d-%H%M%S)"
  BACKUP="$BACKUP_ROOT/mofilter-backup-$STAMP"
  mkdir -p "$BACKUP_ROOT"
  say "نسخة احتياطية: $BACKUP"
  cp -a "$PROJECT" "$BACKUP"
  ok "تم النسخ الاحتياطي"
else
  warn "تخطّيت النسخة الاحتياطية (--no-backup)"
fi

# ============================================================
#  1) توحيد الإصدار
# ============================================================
say "توحيد الإصدار إلى $VERSION"

python3 - "$PROJECT" "$VERSION" <<'PYEOF'
import os, re, sys, pathlib

root = pathlib.Path(sys.argv[1])
version = sys.argv[2]
changed = []


def edit(name, fn):
    path = root / name
    if not path.is_file():
        return
    src = path.read_text(encoding="utf-8")
    new = fn(src)
    if new != src:
        path.write_text(new, encoding="utf-8")
        changed.append(name)


def app_version(src):
    return re.sub(r'^APP_VERSION = "[^"]*"', 'APP_VERSION = "%s"' % version, src, count=1, flags=re.M)


edit("vpn-web-app.py", app_version)
edit("skill/.version", lambda src: version + "\n")
edit("desktop/mofilter-desktop.py",
     lambda src: re.sub(r'^VERSION = "[^"]*"', 'VERSION = "%s"' % version, src, count=1, flags=re.M))
edit("اقرأني.txt", lambda src: re.sub(r'الإصدار \d+\.\d+\.\d+  ·  التطبيق \d+\.\d+\.\d+',
                                      'الإصدار %s  ·  التطبيق %s' % (version, version), src, count=1))
edit("اقرأني.txt", lambda src: src.replace(
    "# المتوقع: مفلتر السيرفرات 1.3.0", "# المتوقع: مفلتر السيرفرات " + version))
for name in ("README.md", "README.ar.md", "اقرأني.txt"):
    edit(name, lambda src: re.sub(r'gh release download v\d+\.\d+\.\d+',
                                  'gh release download v' + version, src))

# رأس الحزمة المولّد (إن كانت لم تُبنَ بعد)
edit("مفلتر السيرفرات", lambda src: re.sub(r'^VERSION="[^"]*"', 'VERSION="%s"' % version,
                                            src, count=1, flags=re.M))
edit("مفلتر السيرفرات", lambda src: re.sub(r'^#  الإصدار \d+\.\d+\.\d+  ·  التطبيق \d+\.\d+\.\d+',
                                            '#  الإصدار %s  ·  التطبيق %s' % (version, version),
                                            src, count=1, flags=re.M))

print("  الملفات المعدّلة: " + (", ".join(changed) if changed else "لا شيء — كانت موحّدة"))
PYEOF

ok "تم توحيد الإصدار"

# ============================================================
#  2) إصلاحات الكود (آمنة وقابلة للتكرار)
# ============================================================
say "إصلاحات الكود: _pump / STAGE_RE / cancel / resolve_result"

python3 - "$PROJECT/vpn-web-app.py" <<'PYEOF'
import re, sys, pathlib

path = pathlib.Path(sys.argv[1])
src = path.read_text(encoding="utf-8")
notes = []

# 2أ) احذف _pump() المكررة إن وُجدت
pump_re = re.compile(r'\n    def _pump\(self, proc\):.*?\n(?=    def _restore_links\()', re.DOTALL)
if pump_re.search(src):
    src = pump_re.sub('\n', src)
    notes.append("حُذفت _pump")
else:
    notes.append("_pump غير موجودة")

# 2ب) تعليق العقد على STAGE_RE (مرة واحدة)
if "عقد مع سكربت المهارة run.py" not in src:
    contract = (
        '# عقد مع سكربت المهارة run.py: يجب أن يطبع مراحل بصيغة "== n/6"\n'
        '# وإلا انكسر شريط التقدم صامتًا. لا تغيّر هذا التنسيق في run.py\n'
        '# دون تحديث STAGE_RE هنا.\n'
    )
    src2 = re.sub(r'(STAGE_RE = re\.compile\(r"==\\s\*\(\\d\)\\s\*/\\s\*6"\))',
                  contract + r'\1', src, count=1)
    if src2 != src:
        src = src2
        notes.append("أُضيف تعليق STAGE_RE")
else:
    notes.append("تعليق STAGE_RE موجود")

# 2ج) cancel(): إن كانت النسخة القديمة (poll فقط) موجودة، استبدلها
old_cancel = '''        for _ in range(20):
            if proc.poll() is not None:
                break
            time.sleep(0.25)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                try:
                    proc.kill()
                except OSError:
                    pass
        return True, ""'''
new_cancel = '''        # انتظر حتى 5 ثوانٍ باستخدام waitpid(WNOHANG) — أدق من poll()
        import errno
        reaped = False
        for _ in range(20):
            try:
                pid, _status = os.waitpid(proc.pid, os.WNOHANG)
            except ChildProcessError:
                reaped = True
                break
            except OSError as exc:
                if exc.errno != errno.ECHILD:
                    raise
                reaped = True
                break
            if pid == proc.pid:
                reaped = True
                break
            time.sleep(0.25)
        if reaped:
            proc.returncode = -signal.SIGTERM  # الإيقاف ليس نجاحًا
        if not reaped:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                os.waitpid(proc.pid, 0)
            except OSError:
                pass
            proc.returncode = -signal.SIGKILL
        return True, ""'''
if old_cancel in src:
    src = src.replace(old_cancel, new_cancel, 1)
    notes.append("حُسّنت cancel")
elif "waitpid(proc.pid, os.WNOHANG)" in src:
    notes.append("cancel محسّنة مسبقًا")
else:
    notes.append("! لم أعثر على cancel القديمة — تخطيت")

# 2د) READY_DIR ضمن resolve_result
if "os.path.join(READY_DIR, name)" not in src:
    old_resolve = '    candidates = [os.path.join(RESULTS_DIR, name), os.path.join(DATA_DIR, name)]'
    new_resolve = '''    candidates = [
        os.path.join(RESULTS_DIR, name),
        os.path.join(DATA_DIR, name),
        os.path.join(READY_DIR, name),
    ]'''
    if old_resolve in src:
        src = src.replace(old_resolve, new_resolve, 1)
        notes.append("أُضيف READY_DIR")
    else:
        notes.append("! لم أعثر على resolve_result — تخطيت")
else:
    notes.append("READY_DIR موجود")

path.write_text(src, encoding="utf-8")
print("  " + " · ".join(notes))
PYEOF

ok "تمت إصلاحات الكود"

# ============================================================
#  3) الاختبارات
# ============================================================
if [ ! -f "$PROJECT/test_selftest.py" ]; then
  warn "test_selftest.py غير موجود — أنشئه عبر build_package.sh أو استعده من نسخة احتياطية"
else
  ok "test_selftest.py موجود"
fi

# ============================================================
#  4) FAQ + توثيق الخيارات + واجهة الويب
# ============================================================
say "تحديث README.md / اقرأني.txt / واجهة الويب"

python3 - "$PROJECT" <<'PYEOF'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
readme = root / "README.md"
guide = root / "اقرأني.txt"
app_path = root / "vpn-web-app.py"

# 4أ) FAQ في README
if readme.is_file():
    src = readme.read_text(encoding="utf-8")
    if "## FAQ" not in src:
        faq = """## FAQ

**Why is the test slow?**
A full run tests every link with real cores (sing-box/Xray), 3 passes each.
1500+ links can take hours. Set the **limit** field (e.g. 200–300) for a
quick trial — links with a Russian whitelist SNI are tested first, so a
limited run tests the useful subset.

**Can I run it on Windows or macOS?**
No — the installer, desktop entry and core downloads target Linux. The
Python app itself is portable, but the desktop integration is Linux-only.

**Do I need OpenCode or DeepSeek Harness?**
No. The app is fully standalone (Python stdlib only). The skill is copied
to `~/.config/opencode/skills/vpn-list` as a conventional path, but no
agent is required.

**Where is the GitHub token stored?**
In `~/.config/vpn-list/github.json` (mode `600`), never in the repo.
Without it, the publish button is disabled and auto-sync is skipped.

**How do I reset everything?**
See the **Uninstall** section, then re-run the installer.

"""
        if "## License" in src:
            src = src.replace("## License", faq + "## License", 1)
        else:
            src = src.rstrip() + "\n\n" + faq
        readme.write_text(src, encoding="utf-8")
        print("  README.md: أُضيف FAQ")
    else:
        print("  README.md: FAQ موجود")

    # 4ب) توثيق --single / --no-confirm
    src = readme.read_text(encoding="utf-8")
    if "### About `--single` and `--no-confirm`" not in src:
        doc = """### About `--single` and `--no-confirm`

Both flags are passed internally by the web UI when it spawns `run.py`:

- `--single` — run one test pass and write the result immediately
  (instead of the default multi-phase batch mode).
- `--no-confirm` — never prompt on stdin; assume "yes" for any
  confirmation. Required because the UI runs with `stdin=DEVNULL`.

From a terminal you can use them directly:

```bash
python3 $S/run.py --single --no-confirm
```

"""
        marker = "Useful environment variables:"
        if marker in src:
            src = src.replace(marker, doc + marker, 1)
        elif "## Security" in src:
            src = src.replace("## Security", doc + "## Security", 1)
        else:
            src = src.rstrip() + "\n\n" + doc
        readme.write_text(src, encoding="utf-8")
        print("  README.md: أُضيف شرح --single")
    else:
        print("  README.md: شرح --single موجود")

# 4ج) الشرح العربي في اقرأني.txt
if guide.is_file():
    src = guide.read_text(encoding="utf-8")
    if "خيارات --single و --no-confirm" not in src:
        doc = """
خيارات --single و --no-confirm
------------------------------
هذان الخياران تمرّرهما الواجهة تلقائيًا عند تشغيل run.py:

  - --single       ينفّذ دورة فحص واحدة ويكتب النتيجة فورًا
                   (بدلًا من الوضع الافتراضي متعدد المراحل).
  - --no-confirm   لا يسأل أبدًا على stdin ويعتبر أي تأكيد «نعم».
                   ضروري لأن الواجهة تشغّل العملية بـ stdin=DEVNULL،
                   فأي سؤال انتظارًا لإدخال سيجعل التشغيل يتوقف.

من الطرفية يمكن استخدامهما مباشرة:

    python3 ~/.config/opencode/skills/vpn-list/scripts/run.py --single --no-confirm
"""
        marker = "\n\nماذا يفعل التطبيق"
        if marker in src:
            src = src.replace(marker, doc + marker, 1)
        else:
            src = src.rstrip() + "\n" + doc
        guide.write_text(src, encoding="utf-8")
        print("  اقرأني.txt: أُضيف شرح --single")
    else:
        print("  اقرأني.txt: شرح --single موجود")

# 4د) واجهة الويب: تحذير الحد=0 + إشعار GitHub
if app_path.is_file():
    src = app_path.read_text(encoding="utf-8")

    if "الحد = 0 يعني فحص كل الروابط" not in src:
        old = '''  function startRun(mode){
    var src = $("srcInput").value.trim();'''
        new = '''  function startRun(mode){
    var src = $("srcInput").value.trim();
    // تحذير: الحد=0 يعني فحص كل الروابط — قد يستغرق ساعات
    if(mode === "russia"){
      var limNow = parseInt($("rusLimit").value, 10);
      if(isNaN(limNow) || limNow === 0){
        if(!confirm("الحد = 0 يعني فحص كل الروابط (قد يستغرق ساعات).\\nهل تريد المتابعة؟")){
          return;
        }
      }
    }'''
        if old in src:
            src = src.replace(old, new, 1)
            print("  الواجهة: أُضيف تحذير الحد=0")
        else:
            print("  ! startRun لم يطابق — تخطيت تحذير الحد")
    else:
        print("  الواجهة: تحذير الحد=0 موجود")

    if "GitHub غير مضبوط — انسخ github.json" not in src:
        old2 = '''    var sb = $("btnSync");
    if(sb){
      sb.disabled = state.running || s.running || window.__gh === false;
      sb.title = (window.__gh === false) ? "GitHub غير مضبوط على هذا الجهاز" : "";
    }'''
        new2 = '''    var sb = $("btnSync");
    if(sb){
      // لا نستخدم disabled: الزر المعطّل لا يُطلق حدث النقر فلا يظهر السبب
      sb.disabled = state.running || s.running;
      sb.classList.toggle("gh-off", window.__gh === false);
      sb.setAttribute("aria-disabled", window.__gh === false ? "true" : "false");
      sb.title = (window.__gh === false) ? "GitHub غير مضبوط — انسخ github.json إلى ~/.config/vpn-list/" : "";
    }
    if(sb && !sb._ghNotice){
      sb._ghNotice = true;
      sb.addEventListener("click", function(ev){
        if(window.__gh === false){
          ev.preventDefault();
          ev.stopImmediatePropagation();
          toast("GitHub غير مضبوط: انسخ github.json إلى ~/.config/vpn-list/ ثم أعد التشغيل");
        }
      }, true);
    }'''
        if old2 in src:
            src = src.replace(old2, new2, 1)
            print("  الواجهة: أُضيف إشعار GitHub")
        else:
            print("  ! كتلة renderSync القديمة غير موجودة — تخطيت إشعار GitHub")
    else:
        print("  الواجهة: إشعار GitHub موجود")

    app_path.write_text(src, encoding="utf-8")
PYEOF

ok "تم تحديث التوثيق والواجهة"

# ============================================================
#  5) التحقق + الاختبارات + الحزمة
# ============================================================
say "التحقق من النتيجة"

APP_VER="$(grep -m1 '^APP_VERSION = ' "$PROJECT/vpn-web-app.py" | sed -E 's/.*"([^"]+)".*/\1/')"
SKILL_VER="$(tr -d '[:space:]' < "$PROJECT/skill/.version" 2>/dev/null || true)"
DESK_VER="$(grep -m1 '^VERSION = ' "$PROJECT/desktop/mofilter-desktop.py" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/' || true)"
[ "$APP_VER" = "$VERSION" ] || die "إصدار التطبيق $APP_VER ≠ $VERSION"
[ -z "$SKILL_VER" ] || [ "$SKILL_VER" = "$VERSION" ] || die "إصدار المهارة $SKILL_VER ≠ $VERSION"
[ -z "$DESK_VER" ] || [ "$DESK_VER" = "$VERSION" ] || die "إصدار سطح المكتب $DESK_VER ≠ $VERSION"
ok "الإصدارات متطابقة: $VERSION"

python3 -m py_compile "$PROJECT/vpn-web-app.py"
if [ -f "$PROJECT/desktop/mofilter-desktop.py" ]; then
  python3 -m py_compile "$PROJECT/desktop/mofilter-desktop.py"
fi
bash -n "$PROJECT/build_package.sh" 2>/dev/null || true
ok "فحص الصيغة ناجح"

if [ "$DO_TEST" = "1" ] && [ -f "$PROJECT/test_selftest.py" ]; then
  say "تشغيل الاختبارات"
  ( cd "$PROJECT" && python3 test_selftest.py )
  ok "الاختبارات ناجحة"
fi

if [ "$DO_BUILD" = "1" ] && [ -f "$PROJECT/build_package.sh" ]; then
  say "إعادة بناء حزمة النقل"
  ( cd "$PROJECT" && bash build_package.sh )
  ok "تم بناء الحزمة"
fi

printf '\n%s\n' "────────────────────────────────────────────"
ok "اكتمل الإصلاح — الإصدار $VERSION"
printf '  المشروع: %s\n' "$PROJECT"
