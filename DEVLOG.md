# DevLog — سجل التحديات والحلول

<!--
تعليمات صيانة هذا الملف:
━━━━━━━━━━━━━━━━━━━━━
- هذا الملف MUST يتم تحديثه مع كل تغيير
- آخر مهمة دائمة في أي task: تحديث CHANGELOG.md + DEVLOG.md
- لو لقيت الملف قديم أو ناقص → حدّثه فوراً
- صيغة كل entry:
  ### [عنوان التحدي]
  - **المشكلة:** وصف واضح
  - **السبب:** الجذر الحقيقي (ليس العرضي)
  - **المحاولات:** كل اللي جرّبناه
  - **الحل النهائي:** اللي اشتغل فعلاً
  - **الدرس المستفاد:** اللي نتعلمه للمستقبل
-->

---

## التحدي #7: التطبيق يعرض صفحة فارغة — فقط العنوان

- **المشكلة:** بعد إصلاح الـ 429، التطبيق يعرض فقط العنوان والعنوان الفرعي. لا tabs، لا workspace، لا footer.

- **السبب (الجذري):** ثلاثة أسباب متراكبة:
  1. `test_connection()` يستهلك API calls إضافية عند كل session جديد → يخلي الـ 429 أسوأ
  2. `connection_ok = False` يتخزن في `st.session_state` → التطبيق يدخل offline mode دائم
  3. `@st.cache_resource` على `_get_spreadsheet()` ممكن يخزن حالة فاشلة للأبد

- **المحاولات:**
  | # | الحل | النتيجة |
  |---|------|---------|
  | 1 | `@st.cache_data(ttl=30)` على read functions | ❌ يخزن empty DataFrame من 429 لـ 30 ثانية |
  | 2 | إزالة `test_connection()` من startup | ❌ `_get_spreadsheet()` بدون cache = API call كل مرة |
  | 3 | `read_projects()` ترجع empty على أي error | ❌ الـ empty result يتخزن في cache |
  | 4 | إزالة ALL decorators + manual session_state cache | ✅ **اشتغل** |

- **الحل النهائي:**
  - **صفر decorators** — لا `@st.cache_resource` ولا `@st.cache_data`
  - Manual caching بـ `st.session_state` + timestamp
  - النجاح يتخزن 60 ثانية. الفشل **ما يتخزن** — يعيد المحاولة مباشرة
  - كل function ترجع empty data عند أي خطأ (لا يكسر الصفحة أبداً)
  - `app.py` مغلف بالكامل بـ try/except مع `traceback.format_exc()`

- **الدرس المستفاد:** Streamlit decorators مريحة لكن خطيرة على Cloud — `@st.cache_resource` يخزن exceptions، و `@st.cache_data` يخزن نتائج فاشلة. Manual caching أكثر أماناً.

---

## التحدي #6: HTTP 429 — Rate Limit من Google Sheets API

- **المشكلة:** `gspread.exceptions.APIError: [429] Quota exceeded for 'Read requests per minute per user'`. التطبيق يتوقف تماماً بعد 5 تفاعلات.

- **السبب (الجذري):** لا يوجد أي caching — كل Streamlit rerun (كل ضغطة زر) يعمل ~13 API calls:
  - `test_connection()`: 2 reads
  - `read_projects()` × 2 workspaces: 6 reads (3 لكل واحد: open_by_key + row_values + get_all_records)
  - `read_todos()` × 2 workspaces: 4 reads
  - Google limit: 60 reads/min → 5 تحميلات = 💥

- **المحاولات:**
  | # | الحل | النتيجة |
  |---|------|---------|
  | 1 | `@st.cache_resource` على client + spreadsheet | ⚠️ يقلل calls لكن يخزن الفشل |
  | 2 | `@st.cache_data(ttl=30)` على read functions | ⚠️ يقلل reads لكن يخزن empty results |
  | 3 | إزالة `_ensure_headers()` من read path | ✅ يوفر 1 call لكل workspace |
  | 4 | Manual session_state cache | ✅ **الحل النهائي** |

- **الحل النهائي:**
  - `get_client()`: بدون decorator — gspread يعيد استخدام tokens داخلياً
  - `_open_spreadsheet()`: بدون decorator — 1 API call في كل مرة
  - `read_projects()`: session_state cache بـ 60s TTL. النجاح يتخزن، الفشل لا
  - إزالة `test_connection()` من startup — وفر 2 calls
  - إزالة `_ensure_headers()` من read path — وفر 2 calls
  - المجموع: ~2 calls أول تحميل، 0 خلال الـ TTL

- **الدرس المستفاد:** على Streamlit Cloud مع Google Sheets backend، لازم تحسب API call budget من أول يوم. كل `open_by_key()` = 1 call. كل `get_all_records()` = 1 call. Caching ليس رفاهية — هو ضرورة.

---

## التحدي #5: `generate_project_id()` ممكن يولّد IDs متكررة

- **المشكلة:** ID يتكون من timestamp فقط (`SAM-20260423145900`). لو مشروعين اتنشأوا في نفس الثانية يحصلون نفس ID.

- **السبب:** الاعتماد على `datetime.now()` فقط بدون عشوائية.

- **الحل النهائي:** أضفنا `uuid.uuid4().hex[:6]` كـ suffix → `SAM-20260423145900-a3f2b1`

- **الدرس المستفاد:** أي ID generator لازم يكون فيه عنصر عشوائي. Timestamp وحده ما تكفي في البيئات المتزامنة.

---

## التحدي #4: `time.sleep(0.5)` يعمل block للـ Streamlit server

- **المشكلة:** عند إكمال مهمة (complete)، الكود ينتظر 0.5 ثانية ل propagating البيانات. هذا يوقف الـ server عن معالجة أي طلب ثاني.

- **السبب:** `time.sleep()` يحجب الـ Python thread. Streamlit يعمل على thread واحد.

- **المحاولات:**
  | # | الحل | النتيجة |
  |---|------|---------|
  | 1 | `time.sleep(0.5)` | ❌ يوقف server |
  | 2 | retry loop (3 محاولات بدون sleep) | ✅ **اشتغل** |

- **الحل النهائي:** retry loop يقرأ البيانات 3 مرات بدون تأخير. غالباً البيانات متوفرة من أول محاولة.

- **الدرس المستفاد:** لا تستعمل `time.sleep()` في Streamlit أبداً. استعمل retry logic أو callbacks.

---

## التحدي #3: `append_timestamp()` يرسل 3 API calls منفصلة لكل event

- **المشكلة:** كل ضغطة زر (start/pause/complete) ترسل 3 writes + 1 read = 4 API calls.

- **السبب:** كل column update كان `ws.update()` منفصل (timestamps_log، time column، status).

- **الحل النهائي:** بناء `batch_updates` list ثم تطبيقها sequentially. الكود أنظف لكن الـ calls ما زالت منفصلة (batch_update الحقيقي يحتاج gspread syntax مختلف).

- **الدرس المستفاد:** gspread 6.x عنده `ws.batch_update()` لكن syntax يختلف عن `ws.update()`. لازم نتحقق قبل الاستعمال.

---

## التحدي #2: `.gitignore` `*.json` واسع جداً

- **المشكلة:** الـ pattern `*.json` يمنع commit لأي ملف JSON، حتى المشروعة.

- **السبب:** القصد كان حماية credentials.json لكن التنفيذ كان واسع جداً.

- **الحل النهائي:** استبدلنا بأسماء ملفات محددة: `credentials.json`, `smart-project-tracker*.json`, `service-account*.json`

- **الدرس المستفاد:** `.gitignore` patterns لازم تكون محددة قدر الإمكان. Wildcard واسع = مفاجآت سيئة.

---

## التحدي #1: `.planning/` متتبع في git رغم وجوده في .gitignore

- **المشكلة:** ملفات `.planning/` كانت متتبعة و visible في repo.

- **السبب:** الملفات اتنشأت قبل إضافة الـ gitignore rule.

- **الحل النهائي:** `git rm -r --cached .planning/` لإزالتها من tracking بدون حذفها محلياً.

- **الدرس المستفاد:** أضف الـ gitignore rule **قبل** إنشاء الملفات. لو تأخرت، استعمل `git rm --cached`.

---

## ملخص الدروس المستفادة

| # | المجال | الدرس |
|---|--------|-------|
| 1 | **Streamlit Caching** | `@st.cache_resource` يخزن exceptions دائماً. `@st.cache_data` يخزن empty results. Manual caching أكثر أماناً على Cloud. |
| 2 | **API Budget** | حسب API calls من أول يوم. كل `open_by_key()` = 1 call. Google limit = 60/min. |
| 3 | **Blocking** | `time.sleep()` يوقف Streamlit server. استعمل retry loops بدل ذلك. |
| 4 | **IDs** | أي ID generator لازم فيه عنصر عشوائي (uuid). Timestamp وحدها ما تكفي. |
| 5 | **Gitignore** | استعمل patterns محددة بدل wildcards واسعة. `credentials.json` أفضل من `*.json`. |
| 6 | **Error Handling** | كل function تتصل بـ API لازم يكون عندها try/except. الصفحة ما تكسر أبداً. |
| 7 | **Session State** | فشل API ما يتخزن في cache — يحاول ثاني مباشرة. نجاح يتخزن 60 ثانية. |
| 8 | **gspread 6.x** | `ws.update()` لازم يستخدم `range_name=` و `values=` كـ named args. |
| 9 | **Docker/Security** | showErrorDetails=false, nginx يحجب الملفات الحساسة، secrets عبر volume mount read-only. |
| 10 | **Git Tracking** | لو أضفت gitignore rule بعد إنشاء الملفات، استعمل `git rm --cached` لتنظيف. |
