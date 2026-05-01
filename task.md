Do the following tasks in the customer list
 view:

1. **Upgrade Django** — upgrade Django to the latest stable version. After upgrading, remove any explicit installation or registration of `django-template-partials` from `requirements.txt`, `settings.py`, and `apps.py`, since Django 6+ ships with template partials built in. Also remove any `{% load partials %}` tags from templates if they are no longer needed.

2. **Search bar width** — the search input is too narrow. Make it the same width as the filter and sort selects.

3. **Table header alignment** — the `<thead>` columns are not aligning correctly with the `<tbody>` rows. Investigate and fix the table layout so headers and cells line up properly.

4. **Customer count and total balance on HTMX requests** — currently when the user searches, filters, or sorts, only the table rows are swapped. The subtitle showing customer count and total deposited balance in the page header does not update. Fix this so both values reflect the current filtered/sorted queryset on every HTMX request.

Do not change any other behaviour or layout. Keep all existing HTMX attributes (`hx-get`, `hx-target`, `hx-push-url`, `hx-include`) as they are.