import json
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin


class HtmxMessageMiddleware(MiddlewareMixin):
    """
    If the request is HTMX, automatically render any pending Django messages
    into the OOB toast template and append it to the response.
    """

    def process_response(self, request, response):
        # Check if it is an HTMX request and the response is HTML
        if (
            request.headers.get("HX-Request")
            and "text/html" in response["Content-Type"]
        ):

            # Get messages from the storage
            storage = list(request._messages)

            if storage:
                # Render the toast template with the messages
                # We reuse your OOB template logic here
                toast_html = render_to_string(
                    "partials/toasts_oob.html", {"messages": storage}
                )

                # Decode content, append toast, re-encode
                content = response.content.decode("utf-8")
                response.content = (content + toast_html).encode("utf-8")

        return response
