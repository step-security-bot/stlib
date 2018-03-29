/*
/ Lara Maia <dev@lara.click> 2015 ~ 2018
/
/ The stlib is free software: you can redistribute it and/or
/ modify it under the terms of the GNU General Public License as
/ published by the Free Software Foundation, either version 3 of
/ the License, or (at your option) any later version.
/
/ The stlib is distributed in the hope that it will be useful,
/ but WITHOUT ANY WARRANTY; without even the implied warranty of
/ MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
/ See the GNU General Public License for more details.
/
/ You should have received a copy of the GNU General Public License
/ along with this program. If not, see http://www.gnu.org/licenses/.
*/

#include <Python.h>
#include <steam_api.h>
#include <utils.h>

typedef struct {
    PyObject_HEAD
} SteamUtils_Object;

static PyObject *SteamUtils_get_server_real_time(SteamUtils_Object *self) {
    unsigned int result = SteamUtils()->GetServerRealTime();

    return PyLong_FromUnsignedLong(result);
}

static int SteamUtils_init(SteamUtils_Object *self, PyObject *args, PyObject *kwds) {
    if (!SteamAPI_IsSteamRunning()) {
        PyErr_SetString(PyExc_ProcessLookupError, "Steam is not running");
        return -1;
    }

    setenv("SteamAppId", "480", 1);
    bool result = SteamAPI_Init();

    if (!result) {
        PyErr_SetString(PyExc_ValueError, "Unable to initialize SteamAPI (Invalid game id?)");
        return -1;
    }

    return 0;
}

static PyMethodDef SteamUtils_methods[] = {
        {"get_server_time", (PyCFunction) SteamUtils_get_server_real_time, METH_NOARGS, NULL},
        {NULL},
};

static PyTypeObject SteamUtilsType = {
        PyObject_HEAD_INIT(NULL)
        "steam_api.SteamUtils",
        sizeof(SteamUtils_Object),
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
        0, 0, 0, 0, 0, 0, 0,
        SteamUtils_methods,
        0, 0, 0, 0, 0, 0, 0,
        (initproc)SteamUtils_init,
        0,
        PyType_GenericNew,
};
