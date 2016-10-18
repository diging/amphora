from redis.exceptions import ConnectionError


class StatusException(Exception):
    def __init__(self, response):
        self.message = 'Encountered status %i' % response.status_code
        self.response = response
        self.status_code = response.status_code

    def __str__(self):
        return repr(self.message)
