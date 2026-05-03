import json
from django.contrib.messages import get_messages


class HtmxMessageMiddleware:
    """
    Intercepts Django messages on HTMX responses and serialises them into
    HX-Trigger as a 'messages' event payload. The frontend showMessages listener
    (in app.js) picks this up and calls SweetAlert2.

    Skips redirects because the browser follows them transparently and
    HTMX never sees the headers — messages must stay in the session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if "HX-Request" not in request.headers:
            return response

        if 300 <= response.status_code < 400:
            return response

        storage = get_messages(request)
        message_list = [
            {"message": str(msg), "tags": msg.tags}
            for msg in storage
        ]

        if not message_list:
            return response

        existing = response.get("HX-Trigger")
        if existing:
            try:
                trigger_data = json.loads(existing)
            except (json.JSONDecodeError, ValueError):
                trigger_data = {existing: True}
        else:
            trigger_data = {}

        trigger_data["messages"] = message_list
        response["HX-Trigger"] = json.dumps(trigger_data)

        return response
