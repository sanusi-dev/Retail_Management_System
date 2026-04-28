# THE CORE RULE

**The application must remain fully functional after every single task is completed.**

Not "mostly working." Not "working except for X." Fully working. If a task cannot be completed
without leaving the app broken, the agent must complete a safe intermediate step first, then
finish the task. Never leave the codebase in a half-migrated state.

---

## HOW TO HANDLE TASKS THAT WOULD BREAK THE APP

Before executing any task, the agent must:

### Step 1 — Impact scan
Search the codebase for everything the task would remove or change.
Ask: "If I remove or change this right now, what breaks?"

### Step 2 — Check the reconstruction brief for the approved replacement
The file `reconstruction_document.md` documents the approved
alternative for every package or pattern being removed. The agent must find and read that
alternative **before writing any code**.

If the brief does not specify a replacement, **stop and ask the developer** before proceeding.
Do not invent a replacement.

### Step 3 — Replace before removing
Always implement the replacement first, migrate all usages to it, verify nothing is broken,
then remove the old dependency.

**Never remove first. Always replace first.**

### Step 4 — Verify after every change
After completing the task (or any intermediate step), run:
```bash
python manage.py check
python manage.py migrate --check
python manage.py runserver  # confirm it starts without errors
```
Report the result before declaring the task done.

---

## APPROVED REPLACEMENT MAP

This table tells the agent exactly what to substitute for each thing being removed.
These replacements are pre-approved — no need to ask the developer.

| Being Removed | Approved Replacement | Migration Notes |
|---|---|---|
| `django-render-block` (`render_block_to_string`) | `django-template-partials` (`{% partialdef %}` + `render_partial`) | See migration guide below |
| `django-tailwind` (the package + `theme` app) | Tailwind CSS **standalone CLI** binary | See migration guide below |
| `django-easy-audit` | Custom `AuditLog` model in `core/models.py` | See migration guide below |
| `django-browser-reload` | Remove entirely — no replacement needed in production | Check `INSTALLED_APPS` and `urls.py` |
| `django-environ` | `python-decouple` (`from decouple import config`) | Replace all `env(...)` calls with `config(...)` |
| `django-extensions` | Remove entirely — check if any management command depends on it first | Run `grep -r "django_extensions" .` |
| `Faker` | Move to `requirements-dev.txt` only | Remove from `requirements.txt`, keep in dev |
| `honcho` | Remove entirely — not used for this deployment model | Check `Procfile` and `manage.py` |
| `binaryornot`, `chardet`, `click`, `EditorConfig`, `cookiecutter` | Remove entirely — scaffolding tools | These are transitive deps, will auto-remove |
| `django-stubs`, `django-stubs-ext` | Move to `requirements-dev.txt` only | Type checking only, not runtime |
| `djlint` | Move to `requirements-dev.txt` only | Linter, not runtime |

---

## MIGRATION GUIDES (READ BEFORE EXECUTING)

### A. django-render-block → django-template-partials

**The problem:** Every view that returns an HTMX partial currently does this:
```python
from django_render_block import render_block_to_string

def my_view(request):
    if request.htmx:
        html = render_block_to_string("mytemplate.html", "content", context)
        return HttpResponse(html)
    return render(request, "mytemplate.html", context)
```

**The replacement:** `django-template-partials` uses `{% partialdef %}` blocks in templates
and a `render_partial` helper in views.

**Step-by-step migration (do this file by file, not all at once):**


1. In the template, wrap the partial block:
   ```html
   <!-- BEFORE (django-render-block style) -->
   {% block content %}
     <div>...your partial html...</div>
   {% endblock %}

   <!-- AFTER (django-template-partials style) -->
   {% partialdef content inline=True %}
     <div>...your partial html...</div>
   {% endpartialdef %}
   ```
   Note: `inline=True` means the partial renders as part of the full page too.
   No change needed to how the full page renders.

3. In the view, replace the import and call:
   ```python
   # BEFORE
   from django_render_block import render_block_to_string
   html = render_block_to_string("mytemplate.html", "content", context, request)

   # AFTER
    # use template#partial_name syntax:
    return render(request, "mytemplate.html#content", context)

   ```

4. Verify the page and its HTMX partial swap both work before moving to the next template.

5. After ALL templates are migrated, remove `django_render_block` from `INSTALLED_APPS`
   and `requirements.txt`.

**Do not remove `django-render-block` until every single view has been migrated.**

---

### B. django-tailwind → Tailwind CSS Standalone CLI

**The problem:** `django-tailwind` adds a `theme` Django app, a Node.js dependency,
and requires `python manage.py tailwind start` to compile CSS during development.

**The replacement:** Tailwind CSS standalone CLI — a single binary that watches and
compiles with no Node.js required.

**Step-by-step migration:**

## Before You Start

Make a note of the following in your current project:

- Where your base template is (e.g. `templates/main.html`)
- The line that loads Tailwind CSS (`{% tailwind_css %}` or equivalent)
- Your current `INSTALLED_APPS` entries related to tailwind
- Your `TAILWIND_APP_NAME` setting in `settings.py`

Do **not** delete the `theme` app until Step 6 is verified working.

---

## Step 1 — Download the Tailwind Standalone CLI

Go to the latest release page and download the Linux binary:

```
https://github.com/tailwindlabs/tailwindcss/releases/latest
→ tailwindcss-linux-x64
```

You can also do this directly from the terminal:

```bash
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64
mv tailwindcss-linux-x64 tailwindcss
```

Place the binary in in the **project root** (same level as `manage.py`).

---

## Step 2 — Add the Binary to `.gitignore`

The binary is large and platform-specific — don't commit it:

```
# .gitignore

# Tailwind standalone CLI binary
tailwindcss

# Tailwind compiled output (generated artifact)
static/css/tailwind.css
```

---

## Step 3 — Create `tailwind.config.js`

In your project root, create `tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./**/templates/**/*.html",
    "./**/templates/**/*.djhtml",
    "./static/**/*.js",
  ],
  theme: { extend: {} },
  plugins: [],
}
```

The `content` array tells Tailwind which files to scan for class names. Only
classes found in those files are included in the compiled CSS — everything else
is stripped out.

---

## Step 4 — Create the Source CSS File

Create the directory and file if they don't already exist:

```bash
mkdir -p static/css
```

Create `static/css/input.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

You can add your own custom CSS below those three directives if needed.

---

## Step 5 — Verify the Build Works

Run a one-shot build to confirm everything is wired up correctly:

```bash
./tailwindcss -c tailwind.config.js -i static/css/input.css -o static/css/tailwind.css
```

You should see `static/css/tailwind.css` created. Open it and confirm it contains
compiled CSS (not empty, not an error message).

---

## Step 6 — Update the Base Template

Open your base template (e.g. `templates/main.html`) and replace the
`django-tailwind` tag with a standard static file link:

```html
<!-- BEFORE -->
{% load tailwind_tags %}
{% tailwind_css %}

<!-- AFTER -->
{% load static %}
<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
```

> **Important:** Keep `{% load static %}` at the top of your template if it isn't
> already there. If another `{% load static %}` already exists, you don't need a
> second one.

---

## Step 7 — Clean Up `settings.py`

Remove the following from `INSTALLED_APPS`:

```python
# Remove these:
"tailwind",
"theme",                  # the generated app django-tailwind created
"django_browser_reload",  # if it was added alongside django-tailwind
```

Remove the Tailwind-specific settings:

```python
# Remove this:
TAILWIND_APP_NAME = "theme"

# Also remove if present:
INTERNAL_IPS = ["127.0.0.1"]  # only if it was added solely for browser reload
```

Remove the browser reload URL from `urls.py` if it was added:

```python
# Remove this from urls.py:
path("__reload__/", include("django_browser_reload.urls")),
```

---

## Step 8 — Delete the `theme` App

Once you've confirmed styles works, delete the `theme` directory:

```bash
rm -rf theme/
```

---

## Step 9 — Update `requirements.txt`

Remove these lines:

```
django-tailwind
django-browser-reload   # if present
```

Then sync the environment:

```bash
pip uninstall django-tailwind django-browser-reload
```

---

## Step 10 — Verify Everything

11. Run `python manage.py check` and verify CSS still loads correctly.

**Do not delete the `theme` app until step 6 is verified working.**

---

### C. django-easy-audit → Custom AuditLog model

**The problem:** `django-easy-audit` is installed but all three watch flags are `False`
in settings, so it is recording nothing. It is a dead dependency.

**The replacement:** A simple `AuditLog` model with explicit calls in service functions.

**Step-by-step migration:**

1. Add the `AuditLog` model to `core/models.py`:
   ```python
   import logging
   logger = logging.getLogger(__name__)

   class AuditLog(models.Model):
       user = models.ForeignKey(
           'account.CustomUser', on_delete=models.SET_NULL,
           null=True, blank=True
       )
       action = models.CharField(max_length=100)
       object_type = models.CharField(max_length=100)
       object_id = models.CharField(max_length=100)
       object_repr = models.CharField(max_length=255)
       detail = models.JSONField(default=dict)
       timestamp = models.DateTimeField(auto_now_add=True)
       ip_address = models.GenericIPAddressField(null=True, blank=True)

       class Meta:
           ordering = ['-timestamp']
           verbose_name = 'Audit Log'
           verbose_name_plural = 'Audit Logs'

       def __str__(self):
           return f"{self.timestamp:%Y-%m-%d %H:%M} · {self.user} · {self.action} · {self.object_repr}"
   ```

2. Add a helper to `core/utils.py`:
   ```python
   from core.models import AuditLog

   def audit(user, action, obj, detail=None, request=None):
       """
       Call this explicitly inside service functions for auditable actions.
       Never call from signals.
       """
       try:
           ip = None
           if request:
               x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
               ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
           AuditLog.objects.create(
               user=user,
               action=action,
               object_type=type(obj).__name__,
               object_id=str(obj.pk),
               object_repr=str(obj),
               detail=detail or {},
               ip_address=ip,
           )
       except Exception:
           import logging
           logging.getLogger('core.audit').error(
               f"AuditLog failed: action={action}", exc_info=True
           )
   ```

3. Run `python manage.py makemigrations core && python manage.py migrate`

4. Remove `easyaudit` from `INSTALLED_APPS` in `settings.py`.
   Remove the three `DJANGO_EASY_AUDIT_*` settings.

5. Remove `django-easy-audit` from `requirements.txt`.

6. Run `python manage.py check` — confirm no errors.

7. Add `audit()` calls inside service functions for the following actions (do this
   incrementally as each service function is built in Phase 2):
   - `void_sale()`
   - `void_receipt()`
   - `void_supplier_payment()`
   - `cancel_agreement()`
   - `void_cfa_fulfillment()`
   - `void_deposit()`
   - `void_transformation()`

**The audit calls are added during Phase 2 (service layer), not Phase 1.**
Phase 1 only removes the dead package and adds the empty model.

---

## TASK EXECUTION FORMAT

When the developer says "execute task N", the agent must respond with this structure:

```
TASK N — [Task name]

IMPACT SCAN:
- Files affected: [list]
- Packages/functions being replaced: [list]
- Risk of breakage if done naively: [describe]

REPLACEMENT PLAN:
- Step 1: [what gets built/added first]
- Step 2: [migration of existing code]
- Step 3: [removal of old code]
- Step 4: [verification]

PROCEEDING WITH STEP 1...
[code]

STEP 1 COMPLETE. Proceeding to step 2...
[code]

... and so on until:

VERIFICATION:
[output of python manage.py check]
[confirmation app starts]

TASK N COMPLETE. Summary of what changed:
- [change 1]
- [change 2]
```

If at any step the agent encounters something not covered by the approved replacement map
or the reconstruction brief, it must stop and say:

```
BLOCKED — Need developer input.
[Describe what was found and what decision is needed]
Do not proceed until developer responds.
```

---

## TASK LIST (PHASE 1 — in recommended order)

Execute these one at a time. Do not start the next until the previous is verified working.

**Task 1 — Fix the `Payment.can_void` duplicate bug**
- File: `supply_chain/models.py`
- Risk: Low — isolated fix, no dependencies
- No replacement needed — just remove the duplicate definition

**Task 2 — Fix the `Loan.__str__` bug**
- File: `loan/models.py`
- Risk: Low — one-line fix
- Change `return self.loan_id` to `return str(self.loan_id)`

**Task 3 — Remove django-easy-audit, add AuditLog model**
- Follow Migration Guide C above exactly
- Risk: Low — package is already disabled (all watch flags are False)
- Deliverable: AuditLog model exists, easy-audit is gone, app still starts

**Task 4 — Add `select_for_update()` to `Transaction.clean()`**
- File: `customer/models.py`
- Risk: Low — isolated model change
- Wrap the available balance read in `select_for_update()` inside `transaction.atomic()`

**Task 5 — Fix balance cache exception swallowing**
- File: `customer/signals.py`
- Risk: Low — change `except Exception: print(...)` to proper logging
- Import `logging`, replace print with `logger.error(..., exc_info=True)`
- Wrap cache update in same `transaction.atomic()` as the parent save

**Task 6 — Replace django-render-block with django-template-partials**
- Follow Migration Guide A above exactly
- Risk: HIGH if done wrong — follow the file-by-file approach
- Deliverable: every view works, every HTMX partial works, old package gone

**Task 7 — Replace django-tailwind with Tailwind standalone CLI**
- Follow Migration Guide B above exactly
- Risk: MEDIUM — CSS must be compiled and static files verified before removing theme app
- Deliverable: app looks identical, no Node.js dependency, theme app deleted

**Task 8 — Clean up remaining dead dependencies**
- Remove: `django-browser-reload`, `django-environ`, `django-extensions`, `honcho`
- Move to dev: `Faker`, `django-stubs`, `django-stubs-ext`, `djlint`
- Risk: Low — run `grep -r` for each before removing to confirm not used
- Deliverable: clean `requirements.txt` and `requirements-dev.txt`

**Task 9 — Add `void_reason` field to `Sale`**
- File: `customer/models.py`
- Add `void_reason = models.TextField(blank=True)`
- Run `makemigrations` + `migrate`
- Risk: Low

**Task 10 — Add `email` and `address` fields to `Customer`**
- File: `customer/models.py`
- Add both as optional (`blank=True`)
- Run `makemigrations` + `migrate`
- Risk: Low

---















# RMS Renovation — Agent Task Execution Protocol

> Give this document to the agent **alongside the handoff system prompt** at the start of every
> session. This governs HOW the agent executes tasks, not what the tasks are.

---

## THE CORE RULE

**The application must remain fully functional after every single task is completed.**

Not "mostly working." Not "working except for X." Fully working. If a task cannot be completed
without leaving the app broken, the agent must complete a safe intermediate step first, then
finish the task. Never leave the codebase in a half-migrated state.

---

## HOW TO HANDLE TASKS THAT WOULD BREAK THE APP

Before executing any task, the agent must:

### Step 1 — Impact scan
Search the codebase for everything the task would remove or change.
Ask: "If I remove or change this right now, what breaks?"

### Step 2 — Check the reconstruction brief for the approved replacement
The file `rms_reconstruction_v2.md` (or the handoff system prompt) documents the approved
alternative for every package or pattern being removed. The agent must find and read that
alternative **before writing any code**.

If the brief does not specify a replacement, **stop and ask the developer** before proceeding.
Do not invent a replacement.

### Step 3 — Replace before removing
Always implement the replacement first, migrate all usages to it, verify nothing is broken,
then remove the old dependency.

**Never remove first. Always replace first.**

### Step 4 — Verify after every change
After completing the task (or any intermediate step), run:
```bash
python manage.py check
python manage.py migrate --check
python manage.py runserver  # confirm it starts without errors
```
Report the result before declaring the task done.

---

## APPROVED REPLACEMENT MAP

This table tells the agent exactly what to substitute for each thing being removed.
These replacements are pre-approved — no need to ask the developer.

| Being Removed | Approved Replacement | Migration Notes |
|---|---|---|
| `django-render-block` (`render_block_to_string`) | `django-template-partials` (`{% partialdef %}` + `render_partial`) | See migration guide below |
| `django-tailwind` (the package + `theme` app) | Tailwind CSS **standalone CLI** binary | See migration guide below |
| `django-easy-audit` | Custom `AuditLog` model in `core/models.py` | See migration guide below |
| `django-browser-reload` | Remove entirely — no replacement needed in production | Check `INSTALLED_APPS` and `urls.py` |
| `django-environ` | `python-decouple` (`from decouple import config`) | Replace all `env(...)` calls with `config(...)` |
| `django-extensions` | Remove entirely — check if any management command depends on it first | Run `grep -r "django_extensions" .` |
| `Faker` | Move to `requirements-dev.txt` only | Remove from `requirements.txt`, keep in dev |
| `honcho` | Remove entirely — not used for this deployment model | Check `Procfile` and `manage.py` |
| `binaryornot`, `chardet`, `click`, `EditorConfig`, `cookiecutter` | Remove entirely — scaffolding tools | These are transitive deps, will auto-remove |
| `django-stubs`, `django-stubs-ext` | Move to `requirements-dev.txt` only | Type checking only, not runtime |
| `djlint` | Move to `requirements-dev.txt` only | Linter, not runtime |

---

## MIGRATION GUIDES (READ BEFORE EXECUTING)

### A. django-render-block → django-template-partials

**The problem:** Every view that returns an HTMX partial currently does this:
```python
from django_render_block import render_block_to_string

def my_view(request):
    if request.htmx:
        html = render_block_to_string("mytemplate.html", "content", context)
        return HttpResponse(html)
    return render(request, "mytemplate.html", context)
```

**The replacement:** `django-template-partials` uses `{% partialdef %}` blocks in templates
and a `render_partial` helper in views.

**Step-by-step migration (do this file by file, not all at once):**

1. Add `template_partials` to `INSTALLED_APPS` in `settings.py`

2. In the template, wrap the partial block:
   ```html
   <!-- BEFORE (django-render-block style) -->
   {% block content %}
     <div>...your partial html...</div>
   {% endblock %}

   <!-- AFTER (django-template-partials style) -->
   {% partialdef content inline=True %}
     <div>...your partial html...</div>
   {% endpartialdef %}
   ```
   Note: `inline=True` means the partial renders as part of the full page too.
   No change needed to how the full page renders.

3. In the view, replace the import and call:
   ```python
   # BEFORE
   from django_render_block import render_block_to_string
   html = render_block_to_string("mytemplate.html", "content", context, request)

   # AFTER
   from template_partials.views import render_partial
   # OR use the shortcut:
   from django.template.loader import render_to_string
   # django-template-partials patches the loader — use template#partial_name syntax:
   html = render_to_string("mytemplate.html#content", context, request=request)
   return HttpResponse(html)
   ```

4. Verify the page and its HTMX partial swap both work before moving to the next template.

5. After ALL templates are migrated, remove `django_render_block` from `INSTALLED_APPS`
   and `requirements.txt`.

**Do not remove `django-render-block` until every single view has been migrated.**

---

### B. django-tailwind → Tailwind CSS Standalone CLI

**The problem:** `django-tailwind` adds a `theme` Django app, a Node.js dependency,
and requires `python manage.py tailwind start` to compile CSS during development.

**The replacement:** Tailwind CSS standalone CLI — a single binary that watches and
compiles with no Node.js required.

**Step-by-step migration:**

1. Download the Tailwind standalone CLI for Windows:
   ```
   https://github.com/tailwindlabs/tailwindcss/releases/latest
   → tailwindcss-windows-x64.exe
   ```
   Place it in the project root as `tailwindcss.exe` (add to `.gitignore`).

2. Create `tailwind.config.js` in the project root (if not already there):
   ```javascript
   module.exports = {
     content: [
       "./**/templates/**/*.html",
       "./**/templates/**/*.djhtml",
     ],
     theme: { extend: {} },
     plugins: [],
   }
   ```

3. Create `static/css/input.css`:
   ```css
   @tailwind base;
   @tailwind components;
   @tailwind utilities;
   ```

4. Build command (development — add to a `Makefile` or `README`):
   ```bash
   ./tailwindcss.exe -i static/css/input.css -o static/css/tailwind.css --watch
   ```

5. Build command (production):
   ```bash
   ./tailwindcss.exe -i static/css/input.css -o static/css/tailwind.css --minify
   ```

6. In `base.html`, replace the tailwind CSS link with the compiled output:
   ```html
   <!-- BEFORE (django-tailwind managed this) -->
   {% load tailwind_tags %}
   {% tailwind_css %}

   <!-- AFTER -->
   <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
   ```

7. Remove from `INSTALLED_APPS`:
   - `tailwind`
   - `theme` (the generated app)
   - `django_browser_reload` (if it was added alongside tailwind)

8. Remove `TAILWIND_APP_NAME` from `settings.py`.

9. Remove the `theme` app directory entirely.

10. Remove `django-tailwind` and `django-browser-reload` from `requirements.txt`.

11. Run `python manage.py check` and verify CSS still loads correctly.

**Do not delete the `theme` app until step 6 is verified working.**

---

### C. django-easy-audit → Custom AuditLog model

**The problem:** `django-easy-audit` is installed but all three watch flags are `False`
in settings, so it is recording nothing. It is a dead dependency.

**The replacement:** A simple `AuditLog` model with explicit calls in service functions.

**Step-by-step migration:**

1. Add the `AuditLog` model to `core/models.py`:
   ```python
   import logging
   logger = logging.getLogger(__name__)

   class AuditLog(models.Model):
       user = models.ForeignKey(
           'account.CustomUser', on_delete=models.SET_NULL,
           null=True, blank=True
       )
       action = models.CharField(max_length=100)
       object_type = models.CharField(max_length=100)
       object_id = models.CharField(max_length=100)
       object_repr = models.CharField(max_length=255)
       detail = models.JSONField(default=dict)
       timestamp = models.DateTimeField(auto_now_add=True)
       ip_address = models.GenericIPAddressField(null=True, blank=True)

       class Meta:
           ordering = ['-timestamp']
           verbose_name = 'Audit Log'
           verbose_name_plural = 'Audit Logs'

       def __str__(self):
           return f"{self.timestamp:%Y-%m-%d %H:%M} · {self.user} · {self.action} · {self.object_repr}"
   ```

2. Add a helper to `core/utils.py`:
   ```python
   from core.models import AuditLog

   def audit(user, action, obj, detail=None, request=None):
       """
       Call this explicitly inside service functions for auditable actions.
       Never call from signals.
       """
       try:
           ip = None
           if request:
               x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
               ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
           AuditLog.objects.create(
               user=user,
               action=action,
               object_type=type(obj).__name__,
               object_id=str(obj.pk),
               object_repr=str(obj),
               detail=detail or {},
               ip_address=ip,
           )
       except Exception:
           import logging
           logging.getLogger('core.audit').error(
               f"AuditLog failed: action={action}", exc_info=True
           )
   ```

3. Run `python manage.py makemigrations core && python manage.py migrate`

4. Remove `easyaudit` from `INSTALLED_APPS` in `settings.py`.
   Remove the three `DJANGO_EASY_AUDIT_*` settings.

5. Remove `django-easy-audit` from `requirements.txt`.

6. Run `python manage.py check` — confirm no errors.

7. Add `audit()` calls inside service functions for the following actions (do this
   incrementally as each service function is built in Phase 2):
   - `void_sale()`
   - `void_receipt()`
   - `void_supplier_payment()`
   - `cancel_agreement()`
   - `void_cfa_fulfillment()`
   - `void_deposit()`
   - `void_transformation()`

**The audit calls are added during Phase 2 (service layer), not Phase 1.**
Phase 1 only removes the dead package and adds the empty model.

---

## TASK EXECUTION FORMAT

When the developer says "execute task N", the agent must respond with this structure:

```
TASK N — [Task name]

IMPACT SCAN:
- Files affected: [list]
- Packages/functions being replaced: [list]
- Risk of breakage if done naively: [describe]

REPLACEMENT PLAN:
- Step 1: [what gets built/added first]
- Step 2: [migration of existing code]
- Step 3: [removal of old code]
- Step 4: [verification]

PROCEEDING WITH STEP 1...
[code]

STEP 1 COMPLETE. Proceeding to step 2...
[code]

... and so on until:

VERIFICATION:
[output of python manage.py check]
[confirmation app starts]

TASK N COMPLETE. Summary of what changed:
- [change 1]
- [change 2]
```

If at any step the agent encounters something not covered by the approved replacement map
or the reconstruction brief, it must stop and say:

```
BLOCKED — Need developer input.
[Describe what was found and what decision is needed]
Do not proceed until developer responds.
```

---

## TASK LIST (PHASE 1 — in recommended order)

Execute these one at a time. Do not start the next until the previous is verified working.

**Task 1 — Fix the `Payment.can_void` duplicate bug**
- File: `supply_chain/models.py`
- Risk: Low — isolated fix, no dependencies
- No replacement needed — just remove the duplicate definition

**Task 2 — Fix the `Loan.__str__` bug**
- File: `loan/models.py`
- Risk: Low — one-line fix
- Change `return self.loan_id` to `return str(self.loan_id)`

**Task 3 — Remove django-easy-audit, add AuditLog model**
- Follow Migration Guide C above exactly
- Risk: Low — package is already disabled (all watch flags are False)
- Deliverable: AuditLog model exists, easy-audit is gone, app still starts

**Task 4 — Add `select_for_update()` to `Transaction.clean()`**
- File: `customer/models.py`
- Risk: Low — isolated model change
- Wrap the available balance read in `select_for_update()` inside `transaction.atomic()`

**Task 5 — Fix balance cache exception swallowing**
- File: `customer/signals.py`
- Risk: Low — change `except Exception: print(...)` to proper logging
- Import `logging`, replace print with `logger.error(..., exc_info=True)`
- Wrap cache update in same `transaction.atomic()` as the parent save

**Task 6 — Replace django-render-block with django-template-partials**
- Follow Migration Guide A above exactly
- Risk: HIGH if done wrong — follow the file-by-file approach
- Deliverable: every view works, every HTMX partial works, old package gone

**Task 7 — Replace django-tailwind with Tailwind standalone CLI**
- Follow Migration Guide B above exactly
- Risk: MEDIUM — CSS must be compiled and static files verified before removing theme app
- Deliverable: app looks identical, no Node.js dependency, theme app deleted

**Task 8 — Clean up remaining dead dependencies**
- Remove: `django-browser-reload`, `django-environ`, `django-extensions`, `honcho`
- Move to dev: `Faker`, `django-stubs`, `django-stubs-ext`, `djlint`
- Risk: Low — run `grep -r` for each before removing to confirm not used
- Deliverable: clean `requirements.txt` and `requirements-dev.txt`

**Task 9 — Add `void_reason` field to `Sale`**
- File: `customer/models.py`
- Add `void_reason = models.TextField(blank=True)`
- Run `makemigrations` + `migrate`
- Risk: Low

**Task 10 — Add `email` and `address` fields to `Customer`**
- File: `customer/models.py`
- Add both as optional (`blank=True`)
- Run `makemigrations` + `migrate`
- Risk: Low

---

## TASK LIST (PHASE 2 — SERVICE LAYER REFACTOR)

> Start Phase 2 only after all Phase 1 tasks are verified complete and the app is clean.

### Why this phase is the most dangerous

The current codebase uses Django signals for almost all business side effects:
- Inventory decrements happen in signals
- Balance cache updates happen in signals
- Status propagations happen in signals
- Financial reversals on void happen in signals

The risk of this phase is **double execution** — if you create a service function that
does the work AND leave the signal in place, both fire. The result is inventory going
down twice, balances deducted twice, or statuses updated in conflicting directions.

The rule for this phase is stricter than Phase 1:

**Build the service → wire the view to call the service → disable the signal →
verify nothing fires twice → only then delete the signal.**

---

### The Signal Inventory (what currently exists and what replaces it)

Read these before any Phase 2 task. These are ALL the signals in the codebase and
their exact replacement destinations.

#### `inventory/signals.py`

| Signal | Trigger | What it does | Move to |
|---|---|---|---|
| `create_coupled_product` | `Product` post_save (created=True, category=motorcycle, type=boxed) | Auto-creates the Coupled counterpart product | **Keep as signal** — simple, no business logic, correct as-is |
| `create_product_inventory` | `Product` post_save (created=True) | Auto-creates `Inventory` record at qty=0 | **Keep as signal** — simple, correct as-is |
| `update_inventory` | `GoodsReceiptItem` post_save (created=True) | Recalculates WAC, updates `Inventory.quantity`, creates `InventoryTransaction` | Move to `supply_chain/services.process_goods_receipt()` |
| `reverse_inventory_on_receipt_void` | `GoodsReceiptItem` post_save (reversal items) | Restores inventory, creates reversal `InventoryTransaction` | Move to `supply_chain/services.void_receipt()` — already partially there |
| `update_inventory_on_transformation` | `TransformationItem` post_save (created=True) | Decrements source Boxed inventory with `select_for_update()`, creates `InventoryTransaction` | Move to `inventory/services.process_transformation()` — already partially there |
| `reverse_inventory_on_transformation_void` | `TransformationItem` post_save (status=voided) | Restores source inventory | Move to `inventory/services.void_transformation()` — already partially there |
| `update_inventory_on_sale` | `BoxedSale` post_save (created=True) | Decrements Boxed inventory, creates `InventoryTransaction` | Move to `customer/services.create_sale()` |
| `reverse_inventory_on_sale_void` | `BoxedSale` post_delete or status signal | Restores inventory | Move to `customer/services.void_sale()` |

#### `supply_chain/signals.py`

| Signal | Trigger | What it does | Move to |
|---|---|---|---|
| `update_po_payment_status` | `Payment` post_save + post_delete | Recalculates PO `payment_status` | Move to `supply_chain/services.record_supplier_payment()` and `void_supplier_payment()` |
| `update_po_delivery_status` | `GoodsReceiptItem` post_save + post_delete | Recalculates PO `delivery_status` | Move to `supply_chain/services.process_goods_receipt()` and `void_receipt()` |
| `close_po_if_complete` | `PurchaseOrder` post_save | Auto-closes PO when fully paid AND fully received | Move to a `_update_po_status()` private helper called at the end of both services above |

#### `customer/signals.py`

| Signal | Trigger | What it does | Move to |
|---|---|---|---|
| `create_deposit_account` | `Customer` post_save (created=True) | Auto-creates `DepositAccount` | **Keep as signal** — simple, correct as-is |
| `update_cached_balances` | `Transaction`, `PurchaseAgreement`, `PurchaseAgreementLineItem`, `CfaAgreement`, `CfaFulfillment`, `BoxedSale`, `CoupledSale` post_save + post_delete (8 triggers total) | Recalculates all three cached balance fields | Move to a `_refresh_balances(account)` private helper called explicitly at the end of each relevant service function |
| `process_sale_void_effects` | `Sale` post_save (status changed to VOIDED) | Restores inventory, resets TransformationItem statuses, creates refund Transaction | Move entirely to `customer/services.void_sale()` |
| `update_agreement_status` | `BoxedSale`, `CoupledSale` post_save + post_delete | Recalculates `PurchaseAgreement.status` | Move to `customer/services.create_sale()` and `void_sale()` |
| `create_fulfillment_transaction` | `Sale` post_save (created, payment=from_deposit) | Creates the FULFILLMENT `Transaction` | Move to `customer/services.create_sale()` |
| `void_fulfillment_transaction` | `Sale` post_save (status=VOIDED, payment=from_deposit) | Voids the FULFILLMENT transaction, creates REFUND | Move to `customer/services.void_sale()` |

---

### The Three Signals That STAY as Signals

These are simple auto-creation hooks with no financial or inventory logic. Leave them alone:

1. `create_coupled_product` — creates a Coupled product when a Boxed motorcycle is created
2. `create_product_inventory` — creates an Inventory record when any product is created
3. `create_deposit_account` — creates a DepositAccount when a customer is created

Do not touch these in Phase 2.

---

### Migration Guide D — Signals → Services (the safe pattern)

Every Phase 2 task follows this exact sequence. Do not deviate from it.

**Step 1 — Write the service function (signals still active)**

Create or update the service function. For now, it duplicates what the signal does.
The signal is still connected. Do NOT call the service from views yet.

```python
# customer/services.py

from django.db import transaction as db_transaction
from core.utils import audit

def void_sale(sale_id: int, void_reason: str, user) -> None:
    """
    Void a sale and reverse all its side effects.
    Called explicitly from views. Replaces process_sale_void_effects signal.
    """
    from customer.models import Sale, BoxedSale, CoupledSale, Transaction

    with db_transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale_id)

        if sale.status == Sale.Status.VOIDED:
            raise BusinessRuleViolation("Sale is already voided.")

        # 1. Restore inventory for boxed sales
        for item in sale.boxedsale_set.all():
            item.product.inventory.quantity = (
                F('quantity') + item.quantity
            )
            item.product.inventory.save(update_fields=['quantity'])
            InventoryTransaction.objects.create(
                transaction_type='sale_reversal',
                product=item.product,
                quantity_change=item.quantity,
                cost_impact=item.quantity * item.product.inventory.weighted_average_cost,
                source=item,
            )

        # 2. Restore coupled items to AVAILABLE
        for item in sale.coupledsale_set.all():
            item.transformation_item.status = TransformationItem.Status.AVAILABLE
            item.transformation_item.save(update_fields=['status'])

        # 3. Void the fulfillment transaction and create refund (deposit sales only)
        if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            fulfillment_txn = Transaction.objects.filter(
                source_content_type=ContentType.objects.get_for_model(Sale),
                source_object_id=sale.pk,
                transaction_type=Transaction.TransactionType.FULFILLMENT,
                status=Transaction.Status.ACTIVE,
            ).first()
            if fulfillment_txn:
                fulfillment_txn.status = Transaction.Status.VOIDED
                fulfillment_txn.save(update_fields=['status'])
            Transaction.objects.create(
                deposit_account=sale.customer.depositaccount,
                transaction_type=Transaction.TransactionType.REFUND,
                amount=sale.sales_total,
            )

        # 4. Mark sale voided
        sale.status = Sale.Status.VOIDED
        sale.void_reason = void_reason
        sale.updated_by = user
        sale.save(update_fields=['status', 'void_reason', 'updated_by'])

        # 5. Update agreement status if applicable
        if sale.agreement:
            sale.agreement.update_status()

        # 6. Refresh balance cache
        _refresh_balances(sale.customer.depositaccount)

        # 7. Audit
        audit(user, 'void_sale', sale, detail={
            'void_reason': void_reason,
            'total': str(sale.sales_total),
            'payment_method': sale.payment_method,
        })
```

**Step 2 — Write a test for the service function**

Before wiring the view, write at least one test that:
- Calls the service function directly
- Asserts the inventory was restored
- Asserts the balance was updated correctly
- Asserts the sale status is VOIDED

```python
# customer/tests/test_services.py
from django.test import TestCase
from customer.services import void_sale

class VoidSaleServiceTest(TestCase):
    def test_void_sale_restores_inventory(self):
        # setup: create a sale with a boxed item
        # call void_sale()
        # assert inventory restored
        # assert sale.status == VOIDED
        pass  # implement fully
```

**Step 3 — Wire the view to call the service**

Find the view that currently handles the void action (likely a POST to a void endpoint).
Replace whatever it currently does with a call to the service function.

```python
# BEFORE (view directly manipulates the model or relies on signal)
def void_sale_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    sale.status = Sale.Status.VOIDED
    sale.save()  # signal fires here
    messages.success(request, "Sale voided.")
    return redirect(...)

# AFTER (view calls service, signal is about to be disconnected)
def void_sale_view(request, pk):
    void_reason = request.POST.get('void_reason', '')
    try:
        void_sale(pk, void_reason, request.user)
        messages.success(request, f"Sale voided. {void_reason}")
    except BusinessRuleViolation as e:
        messages.error(request, str(e))
    return redirect(...)
```

**Step 4 — Disconnect the signal (CRITICAL STEP)**

This is where double execution is prevented. The signal must be disconnected NOW,
before any real traffic hits the view.

```python
# In the signals.py file, comment out or delete the receiver decorator:

# BEFORE
@receiver(post_save, sender=Sale)
def process_sale_void_effects(sender, instance, **kwargs):
    ...

# AFTER — disconnect by removing the decorator and renaming
# (do not just delete the function body — keep the code for reference until verified)
# OLD_SIGNAL_process_sale_void_effects — REPLACED BY customer/services.void_sale()
def OLD_process_sale_void_effects(sender, instance, **kwargs):
    ...  # keep for reference, will delete in cleanup step
```

**Step 5 — Verify no double execution**

Run the test suite. Manually test the void flow end to end:
- Void a sale
- Check inventory count — must have gone up by exactly the right amount
- Check deposit balance — must have been refunded exactly once
- Check AuditLog — must have exactly one entry
- Check sale status — must be VOIDED

If anything happened twice, the signal is still connected somewhere. Find it.

**Step 6 — Delete the old signal function**

Once verified, delete the `OLD_` prefixed function entirely. Clean up imports.

---

### Phase 2 Task List (in recommended order)

Execute these one at a time. Each task is one signal group → one service function.
Do not start the next task until the current one is verified with tests.

---

**Task 11 — Create `customer/services.py` scaffold**

Before migrating any signals, create the services file with empty function stubs and
the custom exception classes. This establishes the pattern without breaking anything.

```python
# customer/services.py

import logging
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BusinessRuleViolation(Exception):
    """Raised when a service call violates a business rule."""
    pass


class InsufficientFundsError(BusinessRuleViolation):
    pass


class InsufficientStockError(BusinessRuleViolation):
    pass


def record_deposit(account, amount, note, user, request=None):
    raise NotImplementedError


def void_deposit(transaction_id, void_reason, user, request=None):
    raise NotImplementedError


def create_purchase_agreement(account, line_items, user, request=None):
    raise NotImplementedError


def cancel_agreement(agreement_id, user, request=None):
    raise NotImplementedError


def create_cfa_agreement(account, amount_naira, exchange_rate, user, request=None):
    raise NotImplementedError


def record_cfa_fulfillment(agreement_id, cfa_amount, notes, user, request=None):
    raise NotImplementedError


def void_cfa_fulfillment(fulfillment_id, void_reason, user, request=None):
    raise NotImplementedError


def create_sale(customer, payment_method, agreement, items, user, request=None):
    raise NotImplementedError


def void_sale(sale_id, void_reason, user, request=None):
    raise NotImplementedError


def _refresh_balances(account):
    """
    Private helper. Recalculates and saves all three cached balance fields.
    Call at the end of any service that changes transactions, agreements, or sales.
    """
    try:
        with db_transaction.atomic():
            account_locked = account.__class__.objects.select_for_update().get(
                pk=account.pk
            )
            account_locked.cached_total_balance = account_locked._calculate_total_balance()
            account_locked.cached_allocated_balance = account_locked._calculate_allocated_balance()
            account_locked.cached_available_balance = (
                account_locked.cached_total_balance - account_locked.cached_allocated_balance
            )
            account_locked.save(update_fields=[
                'cached_total_balance',
                'cached_allocated_balance',
                'cached_available_balance',
            ])
    except Exception:
        logger.error(
            "Balance cache refresh failed for account %s", account.pk,
            exc_info=True
        )
        raise  # do not swallow — let the parent transaction fail
```

- Risk: Zero — nothing is connected yet, all functions raise NotImplementedError
- Deliverable: File exists, imports work, `python manage.py check` passes

---

**Task 12 — Do the same for `supply_chain/services.py` and `inventory/services.py`**

Check if these files already exist (they may have some content).
If they do, add the missing function stubs without overwriting existing code.
Add the same exception classes if not present.

- Risk: Zero — stubs only
- Deliverable: All three service files have complete stub signatures

---

**Task 13 — Implement and wire `void_sale()`**

This is the most complex service. Do it first because it's the highest-risk signal in
the codebase — `process_sale_void_effects` does three different things in one signal.

Follow Migration Guide D steps 1–6 exactly.

- Signal to disconnect: `process_sale_void_effects` in `customer/signals.py`
- Signals to disconnect: `void_fulfillment_transaction`, `create_fulfillment_transaction`
  (these are part of the same flow — all three fire on Sale save)
- Tests required: inventory restored, balance refunded exactly once, agreement status updated
- Deliverable: Void sale works end-to-end, signals disconnected, tests pass

---

**Task 14 — Implement and wire `create_sale()`**

- Signals to disconnect: `update_inventory_on_sale`, `update_agreement_status`,
  `create_fulfillment_transaction` (for new sales)
- Logic to move: inventory decrement with `select_for_update()`, agreement status update,
  fulfillment transaction creation for deposit sales
- Tests required: stock decremented exactly once, agreement status updated, balance
  deducted for deposit sales
- Deliverable: Sale creation works end-to-end, signals disconnected

---

**Task 15 — Implement and wire `record_deposit()` and `void_deposit()`**

- Signal to move: `update_cached_balances` (for Transaction post_save — deposit/withdrawal types)
- Logic: create Transaction, call `_refresh_balances()`
- Existing `clean()` validation stays on the model — do not move it to the service
- Tests required: balance increases correctly, void blocked when funds are allocated
- Deliverable: Deposit and void-deposit work, balance cache updated via service not signal

---

**Task 16 — Implement and wire `create_purchase_agreement()` and `cancel_agreement()`**

- Signal to move: `update_cached_balances` (for PurchaseAgreement and
  PurchaseAgreementLineItem post_save)
- Logic: validate `available_balance >= total_value`, create agreement + line items,
  call `_refresh_balances()`
- Tests required: balance allocated correctly, cancel releases allocation
- Deliverable: Agreement creation and cancellation work, balance updated via service

---

**Task 17 — Implement and wire `create_cfa_agreement()`, `record_cfa_fulfillment()`,
`void_cfa_fulfillment()`**

- Signal to move: `update_cached_balances` (for CfaAgreement and CfaFulfillment post_save)
- Tests required: Naira allocated correctly, fulfillment updates remaining XOF,
  void restores remaining XOF, epsilon tolerance for FULFILLED status
- Deliverable: Full CFA flow works via services

---

**Task 18 — Migrate `update_inventory` signal (goods receipt → inventory)**

- Service: `supply_chain/services.process_goods_receipt()` (may already exist — check first)
- Signal to disconnect: `update_inventory` in `inventory/signals.py`
- Logic: WAC recalculation, inventory quantity update, InventoryTransaction creation,
  PO delivery status update, PO auto-close check
- Tests required: WAC calculated correctly (verify formula), stock increased by correct amount
- Deliverable: Goods receipt processing works via service, signal disconnected

---

**Task 19 — Migrate `void_receipt()` signal chain**

- Service: `supply_chain/services.void_receipt()` (may already exist — check first)
- Signal to disconnect: `reverse_inventory_on_receipt_void` in `inventory/signals.py`
- Tests required: stock decreased by correct amount, WAC reversal correct,
  blocked when stock < received quantity
- Deliverable: Receipt void works via service

---

**Task 20 — Migrate supplier payment signals**

- Service: `supply_chain/services.record_supplier_payment()` and `void_supplier_payment()`
- Signals to disconnect: `update_po_payment_status`, `close_po_if_complete`
- Tests required: PO payment status updates correctly across partial payments,
  PO auto-closes when fully paid AND fully received
- Deliverable: Supplier payment flow works via service, bug in `can_void` already fixed
  (Task 1) so void should now work correctly

---

**Task 21 — Migrate transformation signals**

- Service: `inventory/services.process_transformation()` and `void_transformation()`
  (these likely already partially exist — check, then complete)
- Signals to disconnect: `update_inventory_on_transformation`,
  `reverse_inventory_on_transformation_void`
- Tests required: source inventory decremented, unit cost calculated correctly,
  void blocked if any item is sold
- Deliverable: Assembly flow works via service

---

**Task 22 — Clean up: delete all disconnected signal functions**

After all tasks 13–21 are verified:
1. Delete every signal function marked `OLD_` or that has been fully replaced
2. For signals that were kept (`create_coupled_product`, `create_product_inventory`,
   `create_deposit_account`) — leave them completely untouched
3. Run the full test suite
4. Run `python manage.py check`
5. Verify the app starts and all major flows work end-to-end

- Deliverable: `signals.py` files contain ONLY the three auto-creation signals.
  All business logic lives in service functions.

---

**Task 23 — Add `audit()` calls to all service functions**

Now that all services exist and work, add `audit()` calls to the auditable actions.
The `AuditLog` model was created in Task 3 — now it starts being used.

Add `audit()` to:
- `void_sale()`
- `void_receipt()`
- `void_supplier_payment()`
- `cancel_agreement()`
- `void_cfa_fulfillment()`
- `void_deposit()`
- `void_transformation()`

- Risk: Low — adding a write to a new table at the end of already-working transactions
- Deliverable: Audit log populates correctly for all void/cancel actions

---

**Task 24 — Write missing tests for financial logic**

Write tests for the following (currently zero coverage):
1. `_refresh_balances()` — correct total, allocated, available across all scenarios
2. `PurchaseAgreementLineItem.remaining_quantity` — verify cross-version counting
3. `CfaAgreement.update_status()` — verify epsilon tolerance for FULFILLED
4. `void_sale()` — all three side effects (inventory, balance, agreement)
5. `process_goods_receipt()` — WAC formula correctness

- Deliverable: Test suite exists, all tests pass, `python manage.py test` reports 0 failures

---

## IMPORTANT REMINDERS FOR THE AGENT

- Read the reconstruction brief (`rms_reconstruction_v2.md`) before every task, not just once.
  Relevant sections change depending on which task is being executed.

- When editing a file, always read the current state of the file first. Never edit from memory
  of a previous read — the file may have changed since the last task.

- After every file edit, run `python manage.py check` before declaring the step done.

- If `makemigrations` produces unexpected migrations (e.g., touching models you didn't intend
  to change), stop and report before applying them.

- Never run `git add .` or `git commit` — the developer manages version control.

- If the developer says "just do it" for something blocked, ask once more to confirm the
  specific decision needed. Do not interpret "just do it" as permission to invent a solution
  not in the reconstruction brief.

- The app must start and serve a page at the end of every task. That is the minimum
  definition of "not broken."