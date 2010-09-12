try:
    import unittest2 as unittest
except ImportError:
    import unittest


from village import _luabject


class TestDirect(unittest.TestCase):

    def test_new(self):
        state = _luabject.new()
        # PyCObject isn't available to assertIsInstance, so:
        self.assertEqual(type(state).__name__, 'PyCObject')

    def test_load_script(self):
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

        # Can load multiple scripts in one state.
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

        # Can load a syntactically correct script.
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "function foo() prant() end")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

        # Can load multiple syntactically correct scripts in one state.
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "function bar() prant() end")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

        # Loading a syntactically incorrect script raises an exception.
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        with self.assertRaises(_luabject.LuaSyntaxError):
            _luabject.load_script(thread, "1+1")

        # Can load a syntactically correct script even after a load_script() exception.
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "function foo() prant() end")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

        # Loading a syntactically correct script that causes an error works until we evaluate it.
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "hi()")
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.pump_thread(thread)
            while _luabject.thread_status(thread) == 1:
                _luabject.pump_thread(thread)

        # Can load a syntactically correct script even after a load_script() exception.
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "function foo() prant() end")
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

    def test_start_function(self):
        raise unittest.SkipTest()

        # Trying to start an unknown function raises an exception.
        state = _luabject.new()
        _luabject.load_script(state, "bar = 1")
        with self.assertRaises(ValueError):
            _luabject.start_function(state, "foo")
        with self.assertRaises(ValueError):
            _luabject.start_function(state, "bar")

        state = _luabject.new()
        _luabject.load_script(state, "function foo() bar = 1 end")
        thread = _luabject.start_function(state, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))

        # Functions that throw runtime errors can still be started without error.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() prant() end")
        thread = _luabject.start_function(state, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))

    def test_pump_thread(self):
        raise unittest.SkipTest()

        # Errors in the script are raised as exceptions when run.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() prant() end")
        thread = _luabject.start_function(state, "foo")
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.pump_thread(thread)

        # A short error-free script runs to completion.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() bar = 1 end")
        thread = _luabject.start_function(state, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(0, _luabject.thread_status(thread))

        # A long error-free script will take more than one pump to run.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() for v = 1, 10000 do bar = 1 end end")
        thread = _luabject.start_function(state, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))

        # An infinite loop can be pumped without raising an exception.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() while true do bar = 1 end end")
        thread = _luabject.start_function(state, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))