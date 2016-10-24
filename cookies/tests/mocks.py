class MockFile(object):
    pass


class MockIngester(object):
    def __init__(self, stream):
        self.data = stream.read()

    def next(self):
        if len(self.data) == 0:
            raise StopIteration()
        return self.data.pop()
