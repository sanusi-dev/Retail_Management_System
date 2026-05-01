import json
from django.contrib.messages import get_messages
from django.contrib.messages.storage.base import LEVEL_TAGS
from django.utils.deprecation import MiddlewareMixin


class HtmxMessageMiddleware(MiddlewareMixin):
    """
    For HTMX requests: intercepts pending Django messages and serialises them
    into the HX-Trigger response header as a 'showMessages' event payload.

    The client's app.js listens for the 'showMessages' event and calls SweetAlert2.

    For non-HTMX requests: messages render normally in the base template.

    This replaces the old system that appended OOB toast HTML to response bodies.
    """

    # Map Django message level tags to SweetAlert2 icon names
    ICON_MAP = {
        'debug':   'info',
        'info':    'info',
        'success': 'success',
        'warning': 'warning',
        'error':   'error',
    }

    def process_response(self, request, response):
        # Only intercept HTMX requests
        if not request.headers.get('HX-Request'):
            return response

        # Only intercept HTML responses (not JSON, not redirects)
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response

        # Read and consume all pending messages
        storage = get_messages(request)
        message_list = list(storage)

        if not message_list:
            return response

        # Serialise messages
        messages_data = []
        for message in message_list:
            tag = message.tags.split()[-1] if message.tags else 'info'
            messages_data.append({
                'text':  str(message),
                'icon':  self.ICON_MAP.get(tag, 'info'),
                'level': tag,
            })

        # Read any existing HX-Trigger header — must merge, not overwrite
        existing_trigger = response.get('HX-Trigger', None)

        if existing_trigger:
            try:
                trigger_data = json.loads(existing_trigger)
            except (json.JSONDecodeError, ValueError):
                # Existing header is a plain event name string, not JSON
                trigger_data = {existing_trigger: True}
        else:
            trigger_data = {}

        # Add our showMessages event to the trigger payload
        trigger_data['showMessages'] = messages_data

        response['HX-Trigger'] = json.dumps(trigger_data)

        return response
