#include <Python.h>
#include <sys/cdefs.h>
#include <stdio.h>

extern "C" {

    #include "lua.h"
    #include "lauxlib.h"

    static PyObject* PyExc_LuaErrors[6];

    static void close_lua_state(void* state) {
        lua_State* L = (lua_State*) state;
        lua_close(L);
    }

    static PyObject* new_luabject(PyObject* self, PyObject* args) {
        PyObject* capsule;
        lua_State* L;

        if (!PyArg_ParseTuple(args, ""))
            return NULL;

        L = luaL_newstate();  // TODO: should there already be a lua state to fork from?
        //luaL_openlibs(state);  // TODO: sandbox

        // Return the state out to Python land.
        capsule = PyCObject_FromVoidPtr((void*) L, close_lua_state);
        return Py_BuildValue("O", capsule);
    }

    int invoke_python_callable(lua_State* L) {
        PyObject* callable = (PyObject*) lua_touserdata(L, lua_upvalueindex(1));
        assert(PyCallable_Check(callable));

        // TODO: Convert the stacked args to py args.

        // TODO: Why does this segfault on bound instance methods?
        PyObject* ret = PyObject_CallObject(callable, NULL);

        // TODO: Convert the return value to stacked return values.

        return 0;
    }

    static PyObject* register_global(PyObject* self, PyObject* args) {
        PyObject* capsule;
        char* name;
        PyObject* callable;

        if (!PyArg_ParseTuple(args, "OsO", &capsule, &name, &callable))
            return NULL;
        lua_State* L = (lua_State*) PyCObject_AsVoidPtr(capsule);

        lua_pushlightuserdata(L, (void*) callable);
        lua_pushcclosure(L, invoke_python_callable, 1);
        lua_setglobal(L, name);

        Py_RETURN_NONE;
    }

    static PyObject* raise_lua_error(int status, lua_State* L) {
        int top = lua_gettop(L);
        assert(lua_isstring(L, top));
        PyErr_SetString(PyExc_LuaErrors[status], lua_tostring(L, top));
        return NULL;
    }

    static PyObject* load_script(PyObject* self, PyObject* args) {
        PyObject* capsule;
        char* script;

        if (!PyArg_ParseTuple(args, "Os", &capsule, &script))
            return NULL;
        lua_State* thread = (lua_State*) PyCObject_AsVoidPtr(capsule);

        int status = luaL_loadstring(thread, script);
        if (status)
            return raise_lua_error(status, thread);

        // TODO: Lock the global table after the initial run
        // so it can't be mutated by others.

        Py_RETURN_NONE;
    }

    static void end_thread_step(lua_State* l, lua_Debug* ar) {
        lua_yield(l, 0);
    }

    static PyObject* new_thread(PyObject* self, PyObject* args) {
        PyObject* capsule;

        if (!PyArg_ParseTuple(args, "O", &capsule))
            return NULL;
        lua_State* L = (lua_State*) PyCObject_AsVoidPtr(capsule);

        lua_State* thread = lua_newthread(L);
        lua_sethook(thread, end_thread_step, LUA_MASKCOUNT, 10);

        PyObject* threadcapsule = PyCObject_FromVoidPtr((void*) thread, NULL);
        return Py_BuildValue("O", threadcapsule);
    }

    static PyObject* load_function(PyObject* self, PyObject* args) {
        PyObject* capsule;
        char* funcname;

        if (!PyArg_ParseTuple(args, "Os", &capsule, &funcname))
            return NULL;
        lua_State* thread = (lua_State*) PyCObject_AsVoidPtr(capsule);

        lua_getglobal(thread, funcname);
        if (!lua_isfunction(thread, lua_gettop(thread))) {
            lua_pop(thread, 1);
            PyErr_SetString(PyExc_ValueError, "Uh that function you asked for is not a function");
            return NULL;
        }

        Py_RETURN_NONE;
    }

    static PyObject* thread_status(PyObject* self, PyObject* args) {
        PyObject* capsule;

        if (!PyArg_ParseTuple(args, "O", &capsule))
            return NULL;
        lua_State* thread = (lua_State*) PyCObject_AsVoidPtr(capsule);

        int status = lua_status(thread);
        return Py_BuildValue("i", status);
    }

    static PyObject* pump_thread(PyObject* self, PyObject* args) {
        PyObject* capsule;

        if (!PyArg_ParseTuple(args, "O", &capsule))
            return NULL;
        lua_State* thread = (lua_State*) PyCObject_AsVoidPtr(capsule);

        int status = lua_resume(thread, 0);
        if (status && status != LUA_YIELD)
            return raise_lua_error(status, thread);

        return Py_BuildValue("i", status);
    }

    static PyMethodDef LuabjectMethods[] = {
        {"new", new_luabject, METH_VARARGS, "Create a new Luabject with a stack and everything."},
        {"register_global", register_global, METH_VARARGS, "Register a Python callable as a global function in the Luabject."},
        {"load_script", load_script, METH_VARARGS, "Load a script into a Luabject."},
        {"new_thread", new_thread, METH_VARARGS, "Create a new thread for the Luabject."},
        {"load_function", load_function, METH_VARARGS, "Prepare to call one of the Luabject's functions."},
        {"thread_status", thread_status, METH_VARARGS, "Query the status of a Luabject thread."},
        {"pump_thread", pump_thread, METH_VARARGS, "Resume the thread for one Luabject execution step."},
        {NULL, NULL, 0, NULL}
    };

    PyMODINIT_FUNC init_luabject(void) {
        PyObject* m;

        m = Py_InitModule("luabject._luabject", LuabjectMethods);
        if (m == NULL)
            return;

        PyExc_LuaErrors[LUA_ERRRUN] = PyErr_NewException("luabject._luabject.LuaRuntimeError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRRUN]);
        PyModule_AddObject(m, "LuaRuntimeError", PyExc_LuaErrors[LUA_ERRRUN]);

        PyExc_LuaErrors[LUA_ERRSYNTAX] = PyErr_NewException("luabject._luabject.LuaSyntaxError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRSYNTAX]);
        PyModule_AddObject(m, "LuaSyntaxError", PyExc_LuaErrors[LUA_ERRSYNTAX]);

        PyExc_LuaErrors[LUA_ERRMEM] = PyErr_NewException("luabject._luabject.LuaMemoryError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRMEM]);
        PyModule_AddObject(m, "LuaMemoryError", PyExc_LuaErrors[LUA_ERRMEM]);

        PyExc_LuaErrors[LUA_ERRERR] = PyErr_NewException("luabject._luabject.LuaErrorError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRRUN]);
        PyModule_AddObject(m, "LuaErrorError", PyExc_LuaErrors[LUA_ERRRUN]);

        PyModule_AddIntConstant(m, "LUA_YIELD", LUA_YIELD);
        PyModule_AddIntConstant(m, "LUA_ERRSYNTAX", LUA_ERRSYNTAX);
        PyModule_AddIntConstant(m, "LUA_ERRMEM", LUA_ERRMEM);
        PyModule_AddIntConstant(m, "LUA_ERRRUN", LUA_ERRRUN);
    }

}
