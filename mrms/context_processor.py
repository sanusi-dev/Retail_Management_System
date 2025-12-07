from urllib.parse import urlparse


def browser_url(request):
    current_url = request.headers.get("HX-Current-URL")

    if not current_url:
        # fallback to referer if it's an HTMX fragment without HX-Current-URL
        current_url = request.META.get("HTTP_REFERER")

    if current_url:
        parsed = urlparse(current_url)
        path = parsed.path
        if parsed.query:
            path += "?" + parsed.query
    else:
        path = request.path

    return {"next": path}
