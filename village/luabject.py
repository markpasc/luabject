import village._luabject


class Luabject(object):

    def __init__(self):
        self._state = village._luabject.new_luabject()

    def start(self, funcname, args, callback=None):
        village._luabject.start(self._state, funcname, *args)

    def pump(self):
        village._luabject.pump(self._state)
