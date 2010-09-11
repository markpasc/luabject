#include <Python.h>
#include <sys/cdefs.h>
#include <stdio.h>

extern "C" {

    #include "lua.h"
    #include "lauxlib.h"

    static PyObject* new_luabject(PyObject* self, PyObject* args) {
        PyObject* capsule;
        lua_State* L;

        char* script;

        if (!PyArg_ParseTuple(args, "s", &script))
            return NULL;

        L = luaL_newstate();  // TODO: should there already be a lua state to fork from?
        int status = luaL_loadstring(L, script);
        if (status) {
            // FIXME: Actually surface the real Lua error here.
            PyErr_SetString(PyExc_RuntimeError, "Error while loading the script");
            lua_close(L);
            return NULL;
        }
        status = lua_pcall(L, 0, 0, 0);
        if (status) {
            // FIXME: Actually surface the real Lua error here.
            PyErr_SetString(PyExc_RuntimeError, "Error while running the script");
            lua_close(L);
            return NULL;
        }
        // TODO: Lock the global table after the initial run
        // so it can't be mutated by others.

        //luaL_openlibs(state);  // TODO: sandbox
        //lua_sethook(state, carp, LUA_MASKCOUNT, 10);  // TODO: should we set up stoppage here, or does it need to happen somewhere the thread can be continued?

        // Return the state out to Python land.
        capsule = PyCObject_FromVoidPtr((void*) capsule, NULL);
        return Py_BuildValue("O", capsule);
    }

    static PyMethodDef LuabjectMethods[] = {
        {"new", new_luabject, METH_VARARGS, "Create a new Lua stack for the object."},
        {NULL, NULL, 0, NULL}  // sentinel
    };

    PyMODINIT_FUNC init_luabject(void) {
        PyObject* m;

        m = Py_InitModule("village._luabject", LuabjectMethods);
        if (m == NULL)
            return;
    }

}
