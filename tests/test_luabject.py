try:
    import unittest2 as unittest
except ImportError:
    import unittest


import eventlet

from village import _luabject
from village import luabject


class TestDirect(unittest.TestCase):

    def test_new(self):
        state = _luabject.new()
        # PyCObject isn't available to assertIsInstance, so:
        self.assertEqual(type(state).__name__, 'PyCObject')

    def load_script_to_completion(self, state, script):
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, script)
        _luabject.pump_thread(thread)
        while _luabject.thread_status(thread) == 1:
            _luabject.pump_thread(thread)

    def test_load_script(self):
        state = _luabject.new()
        self.load_script_to_completion(state, "")

        # Can load multiple scripts in one state.
        self.load_script_to_completion(state, "")

        # Can load a syntactically correct script.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() prant() end")

        # Can load multiple syntactically correct scripts in one state.
        thread = _luabject.new_thread(state)
        self.load_script_to_completion(state, "function bar() prant() end")

        # Loading a syntactically incorrect script raises an exception.
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        with self.assertRaises(_luabject.LuaSyntaxError):
            _luabject.load_script(thread, "1+1")

        # Can load a syntactically correct script even after a load_script() exception.
        self.load_script_to_completion(state, "function foo() prant() end")

        # Loading a syntactically correct script that causes an error works until we evaluate it.
        state = _luabject.new()
        thread = _luabject.new_thread(state)
        _luabject.load_script(thread, "hi()")
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.pump_thread(thread)
            while _luabject.thread_status(thread) == 1:
                _luabject.pump_thread(thread)

        # Can load a syntactically correct script even after a load_script() exception.
        self.load_script_to_completion(state, "function foo() prant() end")

    def test_load_function(self):
        # Trying to load an unknown function raises an exception.
        state = _luabject.new()
        self.load_script_to_completion(state, "bar = 1")

        thread = _luabject.new_thread(state)
        with self.assertRaises(ValueError):
            _luabject.load_function(thread, "foo")  # nil
        with self.assertRaises(ValueError):
            _luabject.load_function(thread, "bar")  # not a function

        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() bar = 1 end")

        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))

        # Functions that throw runtime errors can still be loaded without error.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() prant() end")
        _luabject.load_function(thread, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))

    def test_pump_thread(self):
        # Errors in the script are raised as exceptions when run.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() prant() end")
        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        with self.assertRaises(_luabject.LuaRuntimeError):
            _luabject.pump_thread(thread)

        # A short error-free script runs to completion.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() bar = 1 end")
        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(0, _luabject.thread_status(thread))

        # A long error-free script will take more than one pump to run.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() for v = 1, 10000 do bar = 1 end end")
        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))

        # An infinite loop can be pumped without raising an exception.
        state = _luabject.new()
        self.load_script_to_completion(state, "function foo() while true do bar = 1 end end")
        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        self.assertEqual(0, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))
        _luabject.pump_thread(thread)
        self.assertEqual(1, _luabject.thread_status(thread))

    def test_register_global(self):
        state = _luabject.new()

        class Test(object):
            def __init__(self):
                self.ran = False
            def __call__(self):
                self.ran = True

        tester = Test()
        _luabject.register_global(state, "hi", tester)

        self.load_script_to_completion(state, "function foo() hi() end")
        thread = _luabject.new_thread(state)
        _luabject.load_function(thread, "foo")
        _luabject.pump_thread(thread)
        while 1 == _luabject.thread_status(thread):
            _luabject.pump_thread(thread)

        self.assertTrue(tester.ran)


class TestPyject(unittest.TestCase):

    def test_basic(self):
        l = luabject.Luabject()
        l.load_script("function foo() bar = 1 end")
        l.run('foo')

    def test_cooperative(self):
        l = luabject.Luabject()
        l.load_script("function foo() for x = 1, 20 do bar = 1 end end")

        luab_thread = eventlet.spawn(l.run, 'foo')
        other_thread = eventlet.spawn(lambda: None)

        results = list()
        def linked_append(gt, arg):
            results.append(arg)

        other_thread.link(linked_append, 'other')
        luab_thread.link(linked_append, 'luab')

        # The other thread finishes before the luabject thread, even though the luabject thread starts first.
        luab_thread.wait()
        self.assertEqual(['other', 'luab'], results)
