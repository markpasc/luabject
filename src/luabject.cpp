#include <Python.h>
#include <sys/cdefs.h>
#include <stdio.h>

extern "C" {

    #include "lua.h"
    #include "lauxlib.h"

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

    static PyObject* raise_lua_error(PyObject* errortype, lua_State* L) {
        int top = lua_gettop(L);
        assert(lua_isstring(L, top));
        PyErr_SetString(errortype, lua_tostring(L, top));
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
            return raise_lua_error(PyExc_ValueError, L);

        status = lua_pcall(L, 0, 0, 0);
        if (status)
            return raise_lua_error(PyExc_ValueError, L);

        // TODO: Lock the global table after the initial run
        // so it can't be mutated by others.

        //lua_sethook(state, carp, LUA_MASKCOUNT, 10);  // TODO: should we set up stoppage here, or does it need to happen somewhere the thread can be continued?
        Py_RETURN_NONE;
    }

    static PyMethodDef LuabjectMethods[] = {
        {"new", new_luabject, METH_VARARGS, "Create a new Luabject with a stack and everything."},
        {"load_script", load_script, METH_VARARGS, "Load a script into a Luabject."},
        {NULL, NULL, 0, NULL}  // sentinel
    };

    PyMODINIT_FUNC init_luabject(void) {
        PyObject* m;

        m = Py_InitModule("village._luabject", LuabjectMethods);
        if (m == NULL)
            return;
    }

}
