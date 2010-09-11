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
        _luabject.load_script(state, "")

        # Can load multiple scripts in one state.
        _luabject.load_script(state, "")

        # Can load a syntactically correct script.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() prant() end")

        # Can load multiple syntactically correct scripts in one state.
        _luabject.load_script(state, "function bar() prant() end")

        # Loading a syntactically incorrect script raises an exception.
        state = _luabject.new()
        with self.assertRaises(_luabject.LuaSyntaxError):
            _luabject.load_script(state, "1+1")

        # Can load a syntactically correct script even after a load_script() exception.
        _luabject.load_script(state, "function foo() prant() end")

        # Loading a syntactically correct script that causes an error raises an exception.
        state = _luabject.new()
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.load_script(state, "hi()")

        # Can load a syntactically correct script even after a load_script() exception.
        _luabject.load_script(state, "function foo() prant() end")

    def test_start_function(self):
        # Trying to start an unknown function raises an exception.
        state = _luabject.new()
        _luabject.load_script(state, "bar = 1")
        with self.assertRaises(ValueError):
            _luabject.start_function(state, "foo")
        with self.assertRaises(ValueError):
            _luabject.start_function(state, "bar")

        # Errors in the script are raised as exceptions when run.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() prant() end")
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.start_function(state, "foo")

        # Otherwise a script will run just fine.
        state = _luabject.new()
        _luabject.load_script(state, "function foo() bar = 1 end")
        _luabject.start_function(state, "foo")
