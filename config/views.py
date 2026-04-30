from django.http import HttpResponse
from django.template.loader import render_to_string


def ratelimit_handler(request, exception):
    html = render_to_string("429.html", request=request)
    return HttpResponse(html, status=429)
