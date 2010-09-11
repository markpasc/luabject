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
        lua_State* L = (lua_State*) PyCObject_AsVoidPtr(capsule);

        int status = luaL_loadstring(L, script);
        if (status)
            return raise_lua_error(status, L);

        // TODO: even this script load is potentially unsafe, so it should be run as a pumped thread too.
        status = lua_pcall(L, 0, 0, 0);
        if (status)
            return raise_lua_error(status, L);

        // TODO: Lock the global table after the initial run
        // so it can't be mutated by others.

        //lua_sethook(state, carp, LUA_MASKCOUNT, 10);  // TODO: should we set up stoppage here, or does it need to happen somewhere the thread can be continued?
        Py_RETURN_NONE;
    }

    static void end_thread_step(lua_State* l, lua_Debug* ar) {
        lua_yield(l, 0);
    }

    static PyObject* start_function(PyObject* self, PyObject* args) {
        PyObject* capsule;
        char* funcname;

        if (!PyArg_ParseTuple(args, "Os", &capsule, &funcname))
            return NULL;
        lua_State* L = (lua_State*) PyCObject_AsVoidPtr(capsule);

        lua_State* thread = lua_newthread(L);
        lua_sethook(thread, end_thread_step, LUA_MASKCOUNT, 10);

        lua_getglobal(thread, funcname);
        if (!lua_isfunction(thread, lua_gettop(thread))) {
            lua_pop(L, 1);
            PyErr_SetString(PyExc_ValueError, "Uh that function you asked for is not a function");
            return NULL;
        }

        PyObject* threadcapsule = PyCObject_FromVoidPtr((void*) thread, NULL);
        return Py_BuildValue("O", threadcapsule);
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
        {"load_script", load_script, METH_VARARGS, "Load a script into a Luabject."},
        {"start_function", start_function, METH_VARARGS, "Call one of the Luabject's functions."},
        {"thread_status", thread_status, METH_VARARGS, "Query the status of a Luabject thread."},
        {"pump_thread", pump_thread, METH_VARARGS, "Resume the thread for one Luabject execution step."},
        {NULL, NULL, 0, NULL}  // sentinel
    };

    PyMODINIT_FUNC init_luabject(void) {
        PyObject* m;

        m = Py_InitModule("village._luabject", LuabjectMethods);
        if (m == NULL)
            return;

        PyExc_LuaErrors[LUA_ERRRUN] = PyErr_NewException("village._luabject.LuaRuntimeError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRRUN]);
        PyModule_AddObject(m, "LuaRuntimeError", PyExc_LuaErrors[LUA_ERRRUN]);

        PyExc_LuaErrors[LUA_ERRSYNTAX] = PyErr_NewException("village._luabject.LuaSyntaxError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRSYNTAX]);
        PyModule_AddObject(m, "LuaSyntaxError", PyExc_LuaErrors[LUA_ERRSYNTAX]);

        PyExc_LuaErrors[LUA_ERRMEM] = PyErr_NewException("village._luabject.LuaMemoryError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRMEM]);
        PyModule_AddObject(m, "LuaMemoryError", PyExc_LuaErrors[LUA_ERRMEM]);

        PyExc_LuaErrors[LUA_ERRERR] = PyErr_NewException("village._luabject.LuaErrorError", NULL, NULL);
        Py_INCREF(PyExc_LuaErrors[LUA_ERRRUN]);
        PyModule_AddObject(m, "LuaErrorError", PyExc_LuaErrors[LUA_ERRRUN]);
    }

}
