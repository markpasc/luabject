import eventlet

from village import _luabject


class Luabject(object):

    def __init__(self):
        self._state = _luabject.new()

    def load_script(self, script):
        thread = _luabject.new_thread(self._state)
        _luabject.load_script(thread, script)
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            eventlet.sleep()
            _luabject.pump_thread(thread)

    def run(self, funcname, args=None, kwargs=None):
        thread = _luabject.new_thread(self._state)
        _luabject.load_function(thread, funcname)
        # TODO: put args on the stack after the function
        # TODO: do the first pump with the number of args too
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            eventlet.sleep()
            _luabject.pump_thread(thread)
