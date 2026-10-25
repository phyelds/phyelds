// The GIL must outlive every owned Python reference in its scope.
#pragma once
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <cmath>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>

namespace phyelds_argos {
struct PythonDeleter {
    void operator()(PyObject* value) const { Py_XDECREF(value); }
};
using Object = std::unique_ptr<PyObject, PythonDeleter>;

inline Object Checked(PyObject* value) {
    if (!value) {
        // Preserve the original traceback; the controller adds its ID and program.
        PyErr_Print();
        throw std::runtime_error("Python call failed (see traceback above)");
    }
    return Object(value);
}

inline void Check(int result) {
    if (result < 0) Checked(nullptr);
}

inline void InitializePython() {
    static std::once_flag once;
    std::call_once(once, [] {
        if (Py_IsInitialized()) return;
        PyConfig config;
        PyConfig_InitPythonConfig(&config);
        config.parse_argv = 0;
        config.install_signal_handlers = 0;
        PyStatus status = PyConfig_SetBytesString(&config, &config.program_name, PHYELDS_PYTHON_EXECUTABLE);
        if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
        std::string error;
        if (PyStatus_Exception(status))
            error = status.err_msg ? status.err_msg : "could not initialize Python";
        PyConfig_Clear(&config);
        if (!error.empty()) throw std::runtime_error(error);
        // ARGoS can dispatch controllers to worker threads. Each call takes the GIL.
        PyEval_SaveThread();
    });
}

class Gil {
public:
    Gil() : m_state(PyGILState_Ensure()) {}
    ~Gil() { PyGILState_Release(m_state); }
    Gil(Gil const&) = delete;
    Gil& operator=(Gil const&) = delete;
private:
    PyGILState_STATE m_state;
};

inline void Put(PyObject* dict, char const* name, Object value) {
    Check(PyDict_SetItemString(dict, name, value.get()));
}

inline double Number(PyObject* value) {
    double number = PyFloat_AsDouble(value);
    if (PyErr_Occurred()) Checked(nullptr);
    if (!std::isfinite(number)) throw std::runtime_error("actuator components must be finite");
    return number;
}
}
