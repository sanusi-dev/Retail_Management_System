from livereload.middleware import LiveReloadScriptMiddleware

class CustomLiveReloadMiddleware(LiveReloadScriptMiddleware):
    """Livereload middleware that skips HTMX requests"""
    def process_response(self, request, response):
        print(f"Request: {'HTMX' if 'HX-Request' in request.headers else 'Normal'}")
        if request.headers.get('HX-Request') == 'true':
            return response
            
        return super().process_response(request, response)