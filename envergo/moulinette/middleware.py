from django.db import connection


class CountQueriesMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)
        content = response.content

        raise 0

        return response
