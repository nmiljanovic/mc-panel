class SetRemoteAddrFromForwardedFor:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Nginx appends the client IP to X-Forwarded-For
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Client IP is ALWAYS the first element in the comma-separated list
            real_ip = x_forwarded_for.split(',')[0].strip()
            request.META['REMOTE_ADDR'] = real_ip

        return self.get_response(request)
