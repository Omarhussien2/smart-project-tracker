# Changelog — سجل التغييرات

<!--
تعليمات صيانة هذا الملف:
━━━━━━━━━━━━━━━━━━━━━
- هذا الملف MUST يتم تحديثه مع كل تغيير
- آخر مهمة دائمة في أي task: تحديث CHANGELOG.md + DEVLOG.md
- لو لقيت الملف قديم أو ناقص → حدّثه فوراً
- صيغة كل entry: `[#commit_hash] وصف التغيير`
- التصنيفات: Added | Changed | Fixed | Removed | Security
- الترتيب: من الأحدث للأقدم
-->

## [v1.1] — 2026-04-10 → 2026-04-21

### Review & Bug Fix Session

#### Fixed
- [`6513ede`] غلّف الكود كامل بـ try/except — التطبيق لا يتعطل أبداً، يعرض رسالة خطأ واضحة بدل صفحة فارغة
- [`de79253`] أزال ALL Streamlit decorators (@st.cache_resource, @st.cache_data) واستبدلها بـ manual session_state caching — الـ decorators كانت تخزن حالات فاشلة دائماً
- [`3bb62ad`] read_functions ترجع empty data عند أي API error بدل ما تكسر الصفحة
- [`c1d3bd6`] خفض API calls من ~13 لكل تحميل صفحة إلى ~2 باستخدام caching ثلاثي الطبقات
- [`bd477f1`] أضاف Google Sheets connection test مع تشخيص واضح للمشاكل (Share sheet, Enable APIs)
- [`8b7b92d`] رقم النسخة "v1.0" → "v1.1"، ضيّق `*.json` في .gitignore لمنع تجاهل ملفات مشروعة
- [`d581dcc`] استبدل `time.sleep(0.5)` بـ retry loop (3 محاولات) — الـ sleep كان يعمل block للـ Streamlit server
- [`5c0f6f0`] أضاف `uuid.uuid4().hex[:6]` لـ project IDs — كان ممكن يتكرر لو مشروعين اتنشأوا بنفس الثانية

#### Changed
- [`5c0f6f0`] `flush_writes()` يعيد استخدام gspread client بدل ما يفتح واحد جديد لكل مجموعة
- [`c1d3bd6`] `append_timestamp()` يبني batch updates بدل 3 API calls منفصلة

#### Removed
- [`5c0f6f0`] أزال `.planning/` من git tracking (كان متتبع بالغلط رغم وجوده في .gitignore)
- [`c1d3bd6`] أزال dead debounce buffer code (`debounced_write`, `force_flush`) — ما كان يُستعمل أبداً
- [`de79253`] أزال `test_connection()` من startup — كان يستهلك API calls إضافية

#### Security
- [`8b7b92d`] ضيّق `.gitignore` pattern: `*.json` → أسماء ملفات محددة (credentials.json, smart-project-tracker*.json, service-account*.json)

---

## [v1.0] — 2026-04-09 → 2026-04-10

### Phase 09: Docker Deployment

#### Added
- [`ec512de`] Dockerfile مع python:3.11-slim + health check + STREAMLIT_LOGGER_LEVEL=error
- [`5f192ad`] docker-compose.yml مع tracker + nginx services + log rotation + health checks
- [`928428d`] nginx.conf مع SSE support + blocking لـ credentials.json, .env, secrets.toml, .key, .pem
- [`91b997d`] .dockerignore + pinned versions في requirements.txt

#### Fixed
- [`c4ae109`] config.toml: headless=true, enableCORS=false, showErrorDetails=false, enableXsrfProtection=true

### Phase 08: Live Timer

#### Added
- [`8537666`] `components/live_timer.py` — `@st.fragment(run_every=1s)` يعرض الوقت الحي
- [`11a4a10`] دمج live timer في project cards — يظهر فقط لو فيه time tracked أو status=running
- [`32ba6cd`] auto-refresh fragment في workspace — يعمل rerun كل 30s لو فيه tasks شغالة

### Phase 07: State Persistence

#### Added
- [`837a445`] debounced write wrapper + DEBOUNCE_INTERVAL_SECONDS constant
- [`3da8149`] `rebuild_session_from_sheets()` — يعيد بناء session state من Sheets data (source of truth)
- [`7981e17`] ربط workspace.py بـ rebuild + flush, و project_card.py بـ force_flush بعد الكتابة

### Phase 06: Secrets Management

#### Added
- [`48b0ee4`] `config.py` credential helpers: `get_google_credentials()`, `has_google_credentials()`
- [`af1f61a`] demo mode detection باستخدام `st.secrets` try/except
- [`4aa7b77`] secrets.toml template بـ placeholder credentials

#### Changed
- [`bcde0c6`] أعادة كتابة `google_sheets.py` لاستخدام `service_account_from_dict` بدل `oauth2client`

#### Removed
- [`bcde0c6`] أزال `oauth2client` من requirements.txt

### Deployment Preparation

#### Fixed
- [`02bf67d`] استخدام named args لـ `ws.update(range_name=, values=)` — gspread 6.x compatibility
- [`dc129ea`] استخدام Sheet ID بدل Sheet name للنشر الموثوق على Cloud

#### Security
- [`d844c4d`] تحديث .gitignore + إيقاف tracking لـ secrets.toml

---

## القادم (Planned)

### Phase 10: Team Sheet Sync (Bi-directional)
- قراءة مشاريع الفريق من شيت الفريق (فلتر: Manager = "عمر")
- عرضها في workspace سماوة مع علامة 🔗 "متزامن مع الفريق"
- كتابة الحالة ثنائياً: تحديث → شيت التركر + شيت الفريق
- راجع DEVLOG.md للتصميم التفصيلي
