#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <stdint.h>
#include <string.h>

#if PY_VERSION_HEX < 0x030D0000
static inline int
compat_dict_get_item_ref(PyObject *mp, PyObject *key, PyObject **result)
{
    PyObject *item = PyDict_GetItemWithError(mp, key);
    if (item != NULL) {
        *result = Py_NewRef(item);
        return 1;
    }
    *result = NULL;
    return PyErr_Occurred() ? -1 : 0;
}

static inline int
compat_dict_pop_ignore(PyObject *mp, PyObject *key)
{
    int has = PyDict_Contains(mp, key);
    if (has <= 0) {
        return has;
    }
    return PyDict_DelItem(mp, key);
}
#define DICT_GET_REF(mp, key, out) compat_dict_get_item_ref((mp), (key), (out))
#define DICT_POP_DISCARD(mp, key) compat_dict_pop_ignore((mp), (key))
#else
#define DICT_GET_REF(mp, key, out) PyDict_GetItemRef((mp), (key), (out))
#define DICT_POP_DISCARD(mp, key) PyDict_Pop((mp), (key), NULL)
#endif

#define COMPACT_HIGH 32749U
#define COMPACT_LOW 32719U
#define COMPACT_ROOT ((1U << 15) | 1U)

#define INITIAL_STACK_CAP 128
#define CACHE_SIZE 1024
#define CACHE_MASK (CACHE_SIZE - 1)
#define PROBE_LIMIT 4

typedef struct {
    uint32_t parent;
    uint32_t counter;
    PyObject *name_obj;
    uint32_t code;
    PyObject *code_obj;
} CacheEntry;

typedef struct {
    PyObject_HEAD
    PyObject *node_id;
    PyObject *sensors;
    PyObject *outputs;
    PyObject *str_position;
    PyObject *str_time;
    PyObject *str_get;
} NativeNodeContextObject;

typedef struct {
    PyObject_HEAD
    PyObject *node_context;
    PyObject *state_trace;
    PyObject *reads;
    PyObject *to_send;
    PyObject *messages;
    PyObject *scratch_inbox;
    PyObject *root_key;
    uint32_t *stack_codes;
    PyObject **stack_keys;
    uint32_t *count_stack;
    Py_ssize_t depth;
    Py_ssize_t stack_cap;
    uint32_t inline_codes[INITIAL_STACK_CAP];
    PyObject *inline_keys[INITIAL_STACK_CAP];
    uint32_t inline_counts[INITIAL_STACK_CAP];
    CacheEntry cache[CACHE_SIZE];
} NativeEngineObject;

static PyTypeObject NativeNodeContextType;
static PyTypeObject NativeEngineType;

/* --- NativeNodeContext ---------------------------------------------------- */

static PyObject *
lookup_sensor(NativeNodeContextObject *self, PyObject *key)
{
    if (self->sensors == NULL || self->sensors == Py_None) {
        Py_RETURN_NONE;
    }
    if (PyDict_CheckExact(self->sensors)) {
        PyObject *val = NULL;
        int rc = DICT_GET_REF(self->sensors, key, &val);
        if (rc < 0) {
            return NULL;
        }
        if (rc == 0) {
            Py_RETURN_NONE;
        }
        return val;
    }
    return PyObject_CallMethodOneArg(self->sensors, self->str_get, key);
}

static void
NativeNodeContext_dealloc(NativeNodeContextObject *self)
{
    Py_XDECREF(self->node_id);
    Py_XDECREF(self->sensors);
    Py_XDECREF(self->outputs);
    Py_XDECREF(self->str_position);
    Py_XDECREF(self->str_time);
    Py_XDECREF(self->str_get);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
NativeNodeContext_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    (void)args;
    (void)kwds;
    NativeNodeContextObject *self = (NativeNodeContextObject *)type->tp_alloc(type, 0);
    if (self == NULL) {
        return NULL;
    }
    self->node_id = Py_NewRef(Py_None);
    self->sensors = Py_NewRef(Py_None);
    self->outputs = NULL;
    self->str_position = PyUnicode_InternFromString("position");
    self->str_time = PyUnicode_InternFromString("time");
    self->str_get = PyUnicode_InternFromString("get");
    if (!self->str_position || !self->str_time || !self->str_get) {
        Py_DECREF(self);
        return NULL;
    }
    return (PyObject *)self;
}

static int
NativeNodeContext_init(NativeNodeContextObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"node_id", "sensors", "outputs", NULL};
    PyObject *node_id = NULL;
    PyObject *sensors = Py_None;
    PyObject *outputs = Py_None;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|OO", kwlist, &node_id, &sensors, &outputs)) {
        return -1;
    }
    Py_INCREF(node_id);
    Py_SETREF(self->node_id, node_id);
    Py_INCREF(sensors);
    Py_SETREF(self->sensors, sensors);
    Py_CLEAR(self->outputs);
    if (outputs != Py_None) {
        self->outputs = Py_NewRef(outputs);
    }
    return 0;
}

static PyObject *
NativeNodeContext_sense(NativeNodeContextObject *self, PyObject *sensor_name)
{
    return lookup_sensor(self, sensor_name);
}

static PyObject *
NativeNodeContext_store(NativeNodeContextObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 2) {
        PyErr_SetString(PyExc_TypeError, "store() takes exactly 2 positional arguments");
        return NULL;
    }
    if (self->outputs == NULL) {
        self->outputs = PyDict_New();
        if (self->outputs == NULL) {
            return NULL;
        }
    }
    if (PyDict_SetItem(self->outputs, args[0], args[1]) < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeNodeContext_position(NativeNodeContextObject *self, PyObject *Py_UNUSED(ignored))
{
    return lookup_sensor(self, self->str_position);
}

static PyObject *
NativeNodeContext_time(NativeNodeContextObject *self, PyObject *Py_UNUSED(ignored))
{
    return lookup_sensor(self, self->str_time);
}

static PyObject *
NativeNodeContext_get_outputs(NativeNodeContextObject *self, void *Py_UNUSED(closure))
{
    if (self->outputs == NULL) {
        self->outputs = PyDict_New();
        if (self->outputs == NULL) {
            return NULL;
        }
    }
    return Py_NewRef(self->outputs);
}

static int
NativeNodeContext_set_outputs(NativeNodeContextObject *self, PyObject *value, void *Py_UNUSED(closure))
{
    if (value == NULL || value == Py_None) {
        Py_CLEAR(self->outputs);
        return 0;
    }
    if (!PyDict_Check(value)) {
        PyErr_SetString(PyExc_TypeError, "outputs must be a dict or None");
        return -1;
    }
    Py_INCREF(value);
    Py_XSETREF(self->outputs, value);
    return 0;
}

static PyMemberDef NativeNodeContext_members[] = {
    {"node_id", Py_T_OBJECT_EX, offsetof(NativeNodeContextObject, node_id), 0, "Device ID"},
    {"sensors", Py_T_OBJECT_EX, offsetof(NativeNodeContextObject, sensors), 0, "Device sensors"},
    {NULL, 0, 0, 0, NULL}
};

static PyGetSetDef NativeNodeContext_getset[] = {
    {"outputs", (getter)NativeNodeContext_get_outputs, (setter)NativeNodeContext_set_outputs,
     "Stored device outputs", NULL},
    {NULL, NULL, NULL, NULL, NULL}
};

static PyMethodDef NativeNodeContext_methods[] = {
    {"sense", (PyCFunction)NativeNodeContext_sense, METH_O, "Read a sensor value."},
    {"store", (PyCFunction)(void (*)(void))NativeNodeContext_store, METH_FASTCALL,
     "Store an actuation output."},
    {"position", (PyCFunction)NativeNodeContext_position, METH_NOARGS, "Read position sensor."},
    {"time", (PyCFunction)NativeNodeContext_time, METH_NOARGS, "Read time sensor."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject NativeNodeContextType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "phyelds.accel._engine.NativeNodeContext",
    .tp_basicsize = sizeof(NativeNodeContextObject),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_doc = "C-backed device context.",
    .tp_new = NativeNodeContext_new,
    .tp_init = (initproc)NativeNodeContext_init,
    .tp_dealloc = (destructor)NativeNodeContext_dealloc,
    .tp_members = NativeNodeContext_members,
    .tp_getset = NativeNodeContext_getset,
    .tp_methods = NativeNodeContext_methods,
};

/* --- CompactPaths hash & cache -------------------------------------------- */

static int
compute_compact_code(uint32_t parent, PyObject *name, uint32_t counter, uint32_t *out_code)
{
    PyObject *as_str = NULL;
    if (PyUnicode_Check(name)) {
        as_str = Py_NewRef(name);
    } else {
        as_str = PyObject_Str(name);
        if (as_str == NULL) {
            return -1;
        }
    }
    Py_ssize_t size = 0;
    const char *bytes = PyUnicode_AsUTF8AndSize(as_str, &size);
    if (bytes == NULL) {
        Py_DECREF(as_str);
        return -1;
    }
    uint32_t high = parent >> 15;
    uint32_t low = parent & 0x7FFFU;
    for (Py_ssize_t i = 0; i < size; i++) {
        uint32_t byte = (unsigned char)bytes[i];
        high = (high * 31U + byte) % COMPACT_HIGH;
        low = (low * 37U + byte) % COMPACT_LOW;
    }
    Py_DECREF(as_str);
    high = (high * 31U + 256U + counter) % COMPACT_HIGH;
    low = (low * 37U + 256U + counter) % COMPACT_LOW;
    *out_code = (high << 15) | low;
    return 0;
}

static int
ascii_equal(PyObject *a, PyObject *b)
{
    if (!PyUnicode_CheckExact(a) || !PyUnicode_CheckExact(b)) {
        return 0;
    }
    if (PyUnicode_IS_COMPACT_ASCII(a) && PyUnicode_IS_COMPACT_ASCII(b)) {
        Py_ssize_t len = PyUnicode_GET_LENGTH(a);
        if (len != PyUnicode_GET_LENGTH(b)) {
            return 0;
        }
        return memcmp(PyUnicode_1BYTE_DATA(a), PyUnicode_1BYTE_DATA(b), (size_t)len) == 0;
    }
    return 0;
}

static PyObject *
resolve_segment(NativeEngineObject *self, uint32_t parent, PyObject *name, uint32_t counter,
                uint32_t *out_code)
{
    uint32_t ptr_mix = (uint32_t)((uintptr_t)name >> 4);
    uint32_t base = ((parent * 2654435761U) ^ ptr_mix ^ (counter * 40503U)) & CACHE_MASK;

    for (uint32_t step = 0; step < PROBE_LIMIT; step++) {
        CacheEntry *entry = &self->cache[(base + step) & CACHE_MASK];
        if (entry->name_obj == NULL) {
            break;
        }
        if (entry->parent == parent && entry->counter == counter) {
            if (entry->name_obj == name || ascii_equal(entry->name_obj, name)) {
                *out_code = entry->code;
                return entry->code_obj;
            }
        }
    }

    uint32_t code = 0;
    if (compute_compact_code(parent, name, counter, &code) < 0) {
        return NULL;
    }
    PyObject *code_obj = PyLong_FromUnsignedLong(code);
    if (code_obj == NULL) {
        return NULL;
    }
    if (PyObject_Hash(code_obj) == -1 && PyErr_Occurred()) {
        Py_DECREF(code_obj);
        return NULL;
    }

    /* Find an empty slot within PROBE_LIMIT, otherwise overwrite base slot. */
    CacheEntry *target = &self->cache[base];
    for (uint32_t step = 0; step < PROBE_LIMIT; step++) {
        CacheEntry *candidate = &self->cache[(base + step) & CACHE_MASK];
        if (candidate->name_obj == NULL) {
            target = candidate;
            break;
        }
    }
    Py_XDECREF(target->name_obj);
    Py_XDECREF(target->code_obj);
    target->parent = parent;
    target->counter = counter;
    target->name_obj = Py_NewRef(name);
    target->code = code;
    target->code_obj = code_obj;
    *out_code = code;
    return code_obj; /* borrowed from cache while entry lives; stack also INCREFs */
}

/* --- NativeEngine helpers ------------------------------------------------- */

static int
ensure_stack_capacity(NativeEngineObject *self, Py_ssize_t needed)
{
    if (needed <= self->stack_cap) {
        return 0;
    }
    Py_ssize_t new_cap = self->stack_cap * 2;
    while (new_cap < needed) {
        new_cap *= 2;
    }
    uint32_t *new_codes = PyMem_Malloc((size_t)new_cap * sizeof(uint32_t));
    PyObject **new_keys = PyMem_Malloc((size_t)new_cap * sizeof(PyObject *));
    uint32_t *new_counts = PyMem_Malloc((size_t)(new_cap + 1) * sizeof(uint32_t));
    if (!new_codes || !new_keys || !new_counts) {
        PyMem_Free(new_codes);
        PyMem_Free(new_keys);
        PyMem_Free(new_counts);
        PyErr_NoMemory();
        return -1;
    }
    memcpy(new_codes, self->stack_codes, (size_t)self->depth * sizeof(uint32_t));
    memcpy(new_keys, self->stack_keys, (size_t)self->depth * sizeof(PyObject *));
    memcpy(new_counts, self->count_stack, (size_t)(self->depth + 1) * sizeof(uint32_t));
    if (self->stack_codes != self->inline_codes) {
        PyMem_Free(self->stack_codes);
        PyMem_Free(self->stack_keys);
        PyMem_Free(self->count_stack);
    }
    self->stack_codes = new_codes;
    self->stack_keys = new_keys;
    self->count_stack = new_counts;
    self->stack_cap = new_cap;
    return 0;
}

static void
clear_stack(NativeEngineObject *self)
{
    for (Py_ssize_t i = 0; i < self->depth; i++) {
        Py_DECREF(self->stack_keys[i]);
    }
    self->depth = 0;
    self->count_stack[0] = 0;
}

static PyObject *
extract_key_newref(NativeEngineObject *self, PyObject *path)
{
    if (path == NULL || path == Py_None) {
        PyObject *k = self->depth > 0 ? self->stack_keys[self->depth - 1] : self->root_key;
        return Py_NewRef(k);
    }
    if (PyList_CheckExact(path)) {
        Py_ssize_t n = PyList_GET_SIZE(path);
        PyObject *k = n > 0 ? PyList_GET_ITEM(path, n - 1) : self->root_key;
        return Py_NewRef(k);
    }
    Py_ssize_t n = PySequence_Size(path);
    if (n < 0) {
        return NULL;
    }
    if (n == 0) {
        return Py_NewRef(self->root_key);
    }
    return PySequence_GetItem(path, n - 1);
}

static int
engine_reset_round(NativeEngineObject *self, PyObject *node_context, PyObject *messages,
                   PyObject *state)
{
    clear_stack(self);
    Py_INCREF(node_context);
    Py_XSETREF(self->node_context, node_context);

    PyObject *new_state = NULL;
    if (state == NULL || state == Py_None) {
        new_state = PyDict_New();
    } else if (PyDict_CheckExact(state)) {
        new_state = PyDict_Copy(state);
    } else {
        new_state = PyDict_New();
        if (new_state && PyDict_Merge(new_state, state, 1) < 0) {
            Py_DECREF(new_state);
            return -1;
        }
    }
    if (new_state == NULL) {
        return -1;
    }
    Py_XSETREF(self->state_trace, new_state);

    if (self->reads == NULL) {
        self->reads = PySet_New(NULL);
        if (self->reads == NULL) {
            return -1;
        }
    } else if (PySet_Clear(self->reads) < 0) {
        return -1;
    }

    PyObject *new_to_send = PyDict_New();
    if (new_to_send == NULL) {
        return -1;
    }
    Py_XSETREF(self->to_send, new_to_send);

    if (messages == NULL || messages == Py_None) {
        PyObject *empty_msgs = PyDict_New();
        if (empty_msgs == NULL) {
            return -1;
        }
        Py_XSETREF(self->messages, empty_msgs);
    } else {
        Py_INCREF(messages);
        Py_XSETREF(self->messages, messages);
    }
    return 0;
}

static PyObject *
engine_finish_cooldown(NativeEngineObject *self)
{
    if (self->state_trace == NULL || self->to_send == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "cooldown() called before setup()");
        return NULL;
    }
    /* Prune unread keys from state_trace. */
    Py_ssize_t state_len = PyDict_Size(self->state_trace);
    if (state_len > 0) {
        PyObject *stack_dead[32];
        PyObject **dead = stack_dead;
        Py_ssize_t dead_cap = 32;
        Py_ssize_t dead_count = 0;

        Py_ssize_t pos = 0;
        PyObject *k = NULL;
        PyObject *v = NULL;
        while (PyDict_Next(self->state_trace, &pos, &k, &v)) {
            int seen = PySet_Contains(self->reads, k);
            if (seen < 0) {
                if (dead != stack_dead) {
                    PyMem_Free(dead);
                }
                return NULL;
            }
            if (seen == 0) {
                if (dead_count == dead_cap) {
                    Py_ssize_t next_cap = dead_cap * 2;
                    PyObject **grown = PyMem_Malloc((size_t)next_cap * sizeof(PyObject *));
                    if (!grown) {
                        if (dead != stack_dead) {
                            PyMem_Free(dead);
                        }
                        return PyErr_NoMemory();
                    }
                    memcpy(grown, dead, (size_t)dead_count * sizeof(PyObject *));
                    if (dead != stack_dead) {
                        PyMem_Free(dead);
                    }
                    dead = grown;
                    dead_cap = next_cap;
                }
                dead[dead_count++] = k;
            }
        }
        for (Py_ssize_t i = 0; i < dead_count; i++) {
            if (PyDict_DelItem(self->state_trace, dead[i]) < 0) {
                if (dead != stack_dead) {
                    PyMem_Free(dead);
                }
                return NULL;
            }
        }
        if (dead != stack_dead) {
            PyMem_Free(dead);
        }
    }

    PyObject *outbox = self->to_send;
    self->to_send = PyDict_New();
    if (self->to_send == NULL) {
        Py_DECREF(outbox);
        return NULL;
    }
    clear_stack(self);
    Py_CLEAR(self->messages);
    return outbox;
}

/* --- NativeEngine Python methods ------------------------------------------ */

static void
NativeEngine_dealloc(NativeEngineObject *self)
{
    clear_stack(self);
    if (self->stack_codes != self->inline_codes) {
        PyMem_Free(self->stack_codes);
        PyMem_Free(self->stack_keys);
        PyMem_Free(self->count_stack);
    }
    for (size_t i = 0; i < CACHE_SIZE; i++) {
        Py_XDECREF(self->cache[i].name_obj);
        Py_XDECREF(self->cache[i].code_obj);
    }
    Py_XDECREF(self->node_context);
    Py_XDECREF(self->state_trace);
    Py_XDECREF(self->reads);
    Py_XDECREF(self->to_send);
    Py_XDECREF(self->messages);
    Py_XDECREF(self->scratch_inbox);
    Py_XDECREF(self->root_key);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *
NativeEngine_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    (void)args;
    (void)kwds;
    NativeEngineObject *self = (NativeEngineObject *)type->tp_alloc(type, 0);
    if (self == NULL) {
        return NULL;
    }
    self->stack_codes = self->inline_codes;
    self->stack_keys = self->inline_keys;
    self->count_stack = self->inline_counts;
    self->stack_cap = INITIAL_STACK_CAP;
    self->depth = 0;
    self->count_stack[0] = 0;
    memset(self->cache, 0, sizeof(self->cache));

    self->root_key = PyLong_FromUnsignedLong(COMPACT_ROOT);
    if (self->root_key == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    if (PyObject_Hash(self->root_key) == -1 && PyErr_Occurred()) {
        Py_DECREF(self);
        return NULL;
    }
    return (PyObject *)self;
}

static PyObject *
NativeEngine_setup(NativeEngineObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"node_context", "messages", "state", NULL};
    PyObject *node_context = NULL;
    PyObject *messages = Py_None;
    PyObject *state = Py_None;
    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "O|OO", kwlist, &node_context, &messages, &state)) {
        return NULL;
    }
    if (engine_reset_round(self, node_context, messages, state) < 0) {
        return NULL;
    }
    return Py_NewRef((PyObject *)self);
}

static PyObject *
NativeEngine_enter(NativeEngineObject *self, PyObject *name)
{
    if (ensure_stack_capacity(self, self->depth + 1) < 0) {
        return NULL;
    }
    uint32_t counter = self->count_stack[self->depth];
    uint32_t parent = self->depth > 0 ? self->stack_codes[self->depth - 1] : COMPACT_ROOT;
    uint32_t code = 0;
    PyObject *key_obj = resolve_segment(self, parent, name, counter, &code);
    if (key_obj == NULL) {
        return NULL;
    }
    self->count_stack[self->depth] = counter + 1;
    self->stack_codes[self->depth] = code;
    self->stack_keys[self->depth] = Py_NewRef(key_obj);
    self->depth++;
    self->count_stack[self->depth] = 0;
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_exit(NativeEngineObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->depth > 0) {
        self->depth--;
        Py_DECREF(self->stack_keys[self->depth]);
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_current_path(NativeEngineObject *self, PyObject *Py_UNUSED(ignored))
{
    PyObject *list = PyList_New(self->depth);
    if (list == NULL) {
        return NULL;
    }
    for (Py_ssize_t i = 0; i < self->depth; i++) {
        PyList_SET_ITEM(list, i, Py_NewRef(self->stack_keys[i]));
    }
    return list;
}

static PyObject *
NativeEngine_key(NativeEngineObject *self, PyObject *path)
{
    return extract_key_newref(self, path);
}

static PyObject *
NativeEngine_write_state(NativeEngineObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs < 1 || nargs > 2) {
        PyErr_SetString(PyExc_TypeError, "write_state() takes 1 or 2 positional arguments");
        return NULL;
    }
    PyObject *key = extract_key_newref(self, nargs == 2 ? args[1] : NULL);
    if (key == NULL) {
        return NULL;
    }
    int rc = PyDict_SetItem(self->state_trace, key, args[0]);
    Py_DECREF(key);
    if (rc < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_read_state(NativeEngineObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs > 1) {
        PyErr_SetString(PyExc_TypeError, "read_state() takes at most 1 positional argument");
        return NULL;
    }
    PyObject *key = extract_key_newref(self, nargs == 1 ? args[0] : NULL);
    if (key == NULL) {
        return NULL;
    }
    if (PySet_Add(self->reads, key) < 0) {
        Py_DECREF(key);
        return NULL;
    }
    PyObject *val = NULL;
    int rc = DICT_GET_REF(self->state_trace, key, &val);
    Py_DECREF(key);
    if (rc < 0) {
        return NULL;
    }
    if (rc == 0) {
        Py_RETURN_NONE;
    }
    return val;
}

static PyObject *
NativeEngine_forget(NativeEngineObject *self, PyObject *stack)
{
    PyObject *key = extract_key_newref(self, stack);
    if (key == NULL) {
        return NULL;
    }
    int rc = DICT_POP_DISCARD(self->state_trace, key);
    Py_DECREF(key);
    if (rc < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_send(NativeEngineObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs < 1 || nargs > 2) {
        PyErr_SetString(PyExc_TypeError, "send() takes 1 or 2 positional arguments");
        return NULL;
    }
    PyObject *key = extract_key_newref(self, nargs == 2 ? args[1] : NULL);
    if (key == NULL) {
        return NULL;
    }
    int rc = PyDict_SetItem(self->to_send, key, args[0]);
    Py_DECREF(key);
    if (rc < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_aligned(NativeEngineObject *self, PyObject *Py_UNUSED(ignored))
{
    PyObject *current_key = self->depth > 0 ? self->stack_keys[self->depth - 1] : self->root_key;
    PyObject *out = PyList_New(0);
    if (out == NULL) {
        return NULL;
    }
    if (self->messages == NULL || !PyDict_CheckExact(self->messages)) {
        return out;
    }
    Py_ssize_t pos = 0;
    PyObject *nid = NULL;
    PyObject *peer_msgs = NULL;
    while (PyDict_Next(self->messages, &pos, &nid, &peer_msgs)) {
        int has = PyDict_CheckExact(peer_msgs)
            ? PyDict_Contains(peer_msgs, current_key)
            : PySequence_Contains(peer_msgs, current_key);
        if (has < 0) {
            Py_DECREF(out);
            return NULL;
        }
        if (has && PyList_Append(out, nid) < 0) {
            Py_DECREF(out);
            return NULL;
        }
    }
    return out;
}

static PyObject *
NativeEngine_aligned_values(NativeEngineObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs > 1) {
        PyErr_SetString(PyExc_TypeError, "aligned_values() takes at most 1 positional argument");
        return NULL;
    }
    PyObject *current_key = self->depth > 0 ? self->stack_keys[self->depth - 1] : self->root_key;
    PyObject *target_key = extract_key_newref(self, nargs == 1 ? args[0] : NULL);
    if (target_key == NULL) {
        return NULL;
    }
    int same_key = (target_key == current_key);
    if (!same_key && PyLong_CheckExact(target_key)) {
        int eq = PyObject_RichCompareBool(target_key, current_key, Py_EQ);
        if (eq < 0) {
            Py_DECREF(target_key);
            return NULL;
        }
        same_key = eq;
    }

    PyObject *result = PyDict_New();
    if (result == NULL) {
        Py_DECREF(target_key);
        return NULL;
    }
    if (self->messages != NULL && PyDict_CheckExact(self->messages)) {
        Py_ssize_t pos = 0;
        PyObject *nid = NULL;
        PyObject *peer_msgs = NULL;
        while (PyDict_Next(self->messages, &pos, &nid, &peer_msgs)) {
            if (PyDict_CheckExact(peer_msgs)) {
                if (!same_key) {
                    int aligned = PyDict_Contains(peer_msgs, current_key);
                    if (aligned < 0) {
                        Py_DECREF(target_key);
                        Py_DECREF(result);
                        return NULL;
                    }
                    if (!aligned) {
                        continue;
                    }
                }
                PyObject *val = NULL;
                int rc = DICT_GET_REF(peer_msgs, target_key, &val);
                if (rc < 0) {
                    Py_DECREF(target_key);
                    Py_DECREF(result);
                    return NULL;
                }
                if (rc > 0) {
                    int set_rc = PyDict_SetItem(result, nid, val);
                    Py_DECREF(val);
                    if (set_rc < 0) {
                        Py_DECREF(target_key);
                        Py_DECREF(result);
                        return NULL;
                    }
                }
            }
        }
    }
    Py_DECREF(target_key);
    return result;
}

static PyObject *
NativeEngine_begin_process(NativeEngineObject *self, PyObject *name)
{
    PyObject *saved_send = PyDict_Copy(self->to_send);
    PyObject *saved_state = PyDict_Copy(self->state_trace);
    PyObject *saved_reads = PySet_New(self->reads);
    if (!saved_send || !saved_state || !saved_reads) {
        Py_XDECREF(saved_send);
        Py_XDECREF(saved_state);
        Py_XDECREF(saved_reads);
        return NULL;
    }
    uint32_t saved_counter = self->count_stack[self->depth];
    self->count_stack[self->depth] = 0;
    PyObject *entered = NativeEngine_enter(self, name);
    if (entered == NULL) {
        self->count_stack[self->depth] = saved_counter;
        Py_DECREF(saved_send);
        Py_DECREF(saved_state);
        Py_DECREF(saved_reads);
        return NULL;
    }
    Py_DECREF(entered);
    self->count_stack[self->depth - 1] = saved_counter;

    PyObject *token = PyTuple_New(3);
    if (token == NULL) {
        Py_DECREF(saved_send);
        Py_DECREF(saved_state);
        Py_DECREF(saved_reads);
        return NULL;
    }
    PyTuple_SET_ITEM(token, 0, saved_send);
    PyTuple_SET_ITEM(token, 1, saved_state);
    PyTuple_SET_ITEM(token, 2, saved_reads);
    return token;
}

static PyObject *
NativeEngine_end_process(NativeEngineObject *self, PyObject *const *args, Py_ssize_t nargs)
{
    if (nargs != 2 || !PyTuple_CheckExact(args[0]) || PyTuple_GET_SIZE(args[0]) != 3) {
        PyErr_SetString(PyExc_TypeError, "end_process(token, commit) expects a 3-tuple token");
        return NULL;
    }
    PyObject *exited = NativeEngine_exit(self, NULL);
    Py_DECREF(exited);
    int commit = PyObject_IsTrue(args[1]);
    if (commit < 0) {
        return NULL;
    }
    if (!commit) {
        PyObject *saved_send = PyTuple_GET_ITEM(args[0], 0);
        PyObject *saved_state = PyTuple_GET_ITEM(args[0], 1);
        PyObject *saved_reads = PyTuple_GET_ITEM(args[0], 2);
        Py_INCREF(saved_send);
        Py_XSETREF(self->to_send, saved_send);
        Py_INCREF(saved_state);
        Py_XSETREF(self->state_trace, saved_state);
        Py_INCREF(saved_reads);
        Py_XSETREF(self->reads, saved_reads);
    }
    Py_RETURN_NONE;
}

static PyObject *
NativeEngine_state_trace(NativeEngineObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->state_trace == NULL) {
        return PyDict_New();
    }
    return PyDict_Copy(self->state_trace);
}

static PyObject *
NativeEngine_cooldown(NativeEngineObject *self, PyObject *Py_UNUSED(ignored))
{
    return engine_finish_cooldown(self);
}

static PyMemberDef NativeEngine_members[] = {
    {"node_context", Py_T_OBJECT_EX, offsetof(NativeEngineObject, node_context), 0,
     "Active NodeContext"},
    {NULL, 0, 0, 0, NULL}
};

static PyMethodDef NativeEngine_methods[] = {
    {"setup", (PyCFunction)(void (*)(void))NativeEngine_setup, METH_VARARGS | METH_KEYWORDS,
     "Prepare engine for a round."},
    {"enter", (PyCFunction)NativeEngine_enter, METH_O, "Enter an alignment point."},
    {"exit", (PyCFunction)NativeEngine_exit, METH_NOARGS, "Leave current alignment point."},
    {"current_path", (PyCFunction)NativeEngine_current_path, METH_NOARGS,
     "Return copy of current alignment path."},
    {"key", (PyCFunction)NativeEngine_key, METH_O, "Return key of alignment path."},
    {"write_state", (PyCFunction)(void (*)(void))NativeEngine_write_state, METH_FASTCALL,
     "Write state at path."},
    {"read_state", (PyCFunction)(void (*)(void))NativeEngine_read_state, METH_FASTCALL,
     "Read state at path."},
    {"forget", (PyCFunction)NativeEngine_forget, METH_O, "Delete state at path."},
    {"send", (PyCFunction)(void (*)(void))NativeEngine_send, METH_FASTCALL,
     "Queue outgoing message."},
    {"aligned", (PyCFunction)NativeEngine_aligned, METH_NOARGS, "List aligned neighbor IDs."},
    {"aligned_values", (PyCFunction)(void (*)(void))NativeEngine_aligned_values, METH_FASTCALL,
     "Return values received from aligned neighbors."},
    {"begin_process", (PyCFunction)NativeEngine_begin_process, METH_O,
     "Start a process transaction."},
    {"end_process", (PyCFunction)(void (*)(void))NativeEngine_end_process, METH_FASTCALL,
     "Finish a process transaction."},
    {"state_trace", (PyCFunction)NativeEngine_state_trace, METH_NOARGS,
     "Return copy of current state dictionary."},
    {"cooldown", (PyCFunction)NativeEngine_cooldown, METH_NOARGS,
     "End round, prune unread state and return outgoing messages."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject NativeEngineType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "phyelds.accel._engine.NativeEngine",
    .tp_basicsize = sizeof(NativeEngineObject),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_doc = "C-backed aggregate engine using 30-bit compact alignment keys.",
    .tp_new = NativeEngine_new,
    .tp_dealloc = (destructor)NativeEngine_dealloc,
    .tp_members = NativeEngine_members,
    .tp_methods = NativeEngine_methods,
};

/* --- Module-level batch round loop ---------------------------------------- */

static int
populate_inbox(PyObject *inbox, PyObject *neighbor_iter_or_seq, PyObject *prev_outboxes)
{
    PyDict_Clear(inbox);
    if (neighbor_iter_or_seq == NULL || neighbor_iter_or_seq == Py_None) {
        return 0;
    }
    if (PyList_CheckExact(neighbor_iter_or_seq)) {
        Py_ssize_t n = PyList_GET_SIZE(neighbor_iter_or_seq);
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *other = PyList_GET_ITEM(neighbor_iter_or_seq, i);
            PyObject *outbox = NULL;
            int rc = DICT_GET_REF(prev_outboxes, other, &outbox);
            if (rc < 0) {
                return -1;
            }
            if (rc > 0) {
                int set_rc = PyDict_SetItem(inbox, other, outbox);
                Py_DECREF(outbox);
                if (set_rc < 0) {
                    return -1;
                }
            }
        }
        return 0;
    }
    PyObject *iter = PyObject_GetIter(neighbor_iter_or_seq);
    if (iter == NULL) {
        return -1;
    }
    PyObject *other = NULL;
    while ((other = PyIter_Next(iter)) != NULL) {
        PyObject *outbox = NULL;
        int rc = PyDict_GetItemRef(prev_outboxes, other, &outbox);
        if (rc < 0) {
            Py_DECREF(other);
            Py_DECREF(iter);
            return -1;
        }
        if (rc > 0) {
            int set_rc = PyDict_SetItem(inbox, other, outbox);
            Py_DECREF(outbox);
            if (set_rc < 0) {
                Py_DECREF(other);
                Py_DECREF(iter);
                return -1;
            }
        }
        Py_DECREF(other);
    }
    Py_DECREF(iter);
    return PyErr_Occurred() ? -1 : 0;
}

static PyObject *
run_chunk(PyObject *Py_UNUSED(module), PyObject *const *args, Py_ssize_t nargs)
{
    /*
     * Args: (engine, context, context_var, program, devices, sensors, neighbors,
     *        prev_outboxes, prev_states)
     */
    if (nargs != 9) {
        PyErr_SetString(PyExc_TypeError, "run_chunk expects 9 arguments");
        return NULL;
    }
    if (!PyObject_TypeCheck(args[0], &NativeEngineType) ||
        !PyObject_TypeCheck(args[1], &NativeNodeContextType)) {
        PyErr_SetString(PyExc_TypeError, "run_chunk requires NativeEngine and NativeNodeContext");
        return NULL;
    }
    NativeEngineObject *eng = (NativeEngineObject *)args[0];
    NativeNodeContextObject *ctx = (NativeNodeContextObject *)args[1];
    PyObject *context_var = args[2];
    PyObject *program = args[3];
    PyObject *devices = args[4];
    PyObject *sensors_map = args[5];
    PyObject *neighbors_map = args[6];
    PyObject *prev_outboxes = args[7];
    PyObject *prev_states = args[8];

    if (eng->scratch_inbox == NULL) {
        eng->scratch_inbox = PyDict_New();
        if (eng->scratch_inbox == NULL) {
            return NULL;
        }
    }

    PyObject *states = PyDict_New();
    PyObject *outboxes = PyDict_New();
    PyObject *outputs = PyDict_New();
    PyObject *results = PyDict_New();
    if (!states || !outboxes || !outputs || !results) {
        Py_XDECREF(states);
        Py_XDECREF(outboxes);
        Py_XDECREF(outputs);
        Py_XDECREF(results);
        return NULL;
    }

    PyObject *token = PyContextVar_Set(context_var, (PyObject *)eng);
    if (token == NULL) {
        goto fail;
    }

    PyObject *seq = PySequence_Fast(devices, "devices must be a sequence");
    if (seq == NULL) {
        PyContextVar_Reset(context_var, token);
        Py_DECREF(token);
        goto fail;
    }
    Py_ssize_t count = PySequence_Fast_GET_SIZE(seq);
    PyObject **items = PySequence_Fast_ITEMS(seq);

    for (Py_ssize_t i = 0; i < count; i++) {
        PyObject *device = items[i];
        PyObject *dev_sensors = PyObject_GetItem(sensors_map, device);
        if (dev_sensors == NULL) {
            goto loop_fail;
        }

        PyObject *nbrs = NULL;
        if (PyDict_CheckExact(neighbors_map)) {
            if (DICT_GET_REF(neighbors_map, device, &nbrs) < 0) {
                Py_DECREF(dev_sensors);
                goto loop_fail;
            }
        } else {
            nbrs = PyObject_GetItem(neighbors_map, device);
            if (nbrs == NULL && PyErr_ExceptionMatches(PyExc_KeyError)) {
                PyErr_Clear();
            } else if (nbrs == NULL) {
                Py_DECREF(dev_sensors);
                goto loop_fail;
            }
        }

        int inbox_rc = populate_inbox(eng->scratch_inbox, nbrs, prev_outboxes);
        Py_XDECREF(nbrs);
        if (inbox_rc < 0) {
            Py_DECREF(dev_sensors);
            goto loop_fail;
        }

        PyObject *prev_state = NULL;
        if (DICT_GET_REF(prev_states, device, &prev_state) < 0) {
            Py_DECREF(dev_sensors);
            goto loop_fail;
        }

        Py_INCREF(device);
        Py_SETREF(ctx->node_id, device);
        Py_SETREF(ctx->sensors, dev_sensors); /* steals dev_sensors */
        Py_CLEAR(ctx->outputs);

        int setup_rc = engine_reset_round(eng, (PyObject *)ctx, eng->scratch_inbox, prev_state);
        Py_XDECREF(prev_state);
        if (setup_rc < 0) {
            goto loop_fail;
        }

        PyObject *res = PyObject_CallNoArgs(program);
        if (res == NULL) {
            goto loop_fail;
        }
        PyObject *outbox = engine_finish_cooldown(eng);
        if (outbox == NULL) {
            Py_DECREF(res);
            goto loop_fail;
        }

        /* Steal state_trace directly instead of copying it a second time. */
        PyObject *new_state = eng->state_trace;
        eng->state_trace = NULL;

        PyObject *dev_outputs = ctx->outputs ? Py_NewRef(ctx->outputs) : PyDict_New();
        Py_CLEAR(ctx->outputs);
        if (dev_outputs == NULL) {
            Py_DECREF(new_state);
            Py_DECREF(outbox);
            Py_DECREF(res);
            goto loop_fail;
        }

        int ok = (PyDict_SetItem(results, device, res) == 0 &&
                  PyDict_SetItem(outboxes, device, outbox) == 0 &&
                  PyDict_SetItem(states, device, new_state) == 0 &&
                  PyDict_SetItem(outputs, device, dev_outputs) == 0);
        Py_DECREF(res);
        Py_DECREF(outbox);
        Py_DECREF(new_state);
        Py_DECREF(dev_outputs);
        if (!ok) {
            goto loop_fail;
        }
        continue;

    loop_fail:
        Py_DECREF(seq);
        PyContextVar_Reset(context_var, token);
        Py_DECREF(token);
        goto fail;
    }

    Py_DECREF(seq);
    if (PyContextVar_Reset(context_var, token) < 0) {
        Py_DECREF(token);
        goto fail;
    }
    Py_DECREF(token);

    PyObject *ret = PyTuple_New(4);
    if (ret == NULL) {
        goto fail;
    }
    PyTuple_SET_ITEM(ret, 0, states);
    PyTuple_SET_ITEM(ret, 1, outboxes);
    PyTuple_SET_ITEM(ret, 2, outputs);
    PyTuple_SET_ITEM(ret, 3, results);
    return ret;

fail:
    Py_DECREF(states);
    Py_DECREF(outboxes);
    Py_DECREF(outputs);
    Py_DECREF(results);
    return NULL;
}

static PyMethodDef module_methods[] = {
    {"run_chunk", (PyCFunction)(void (*)(void))run_chunk, METH_FASTCALL,
     "Run one synchronous round chunk over a sequence of device IDs in C."},
    {NULL, NULL, 0, NULL}
};

static int
engine_mod_exec(PyObject *module)
{
    if (PyType_Ready(&NativeNodeContextType) < 0) {
        return -1;
    }
    if (PyType_Ready(&NativeEngineType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(module, "NativeNodeContext", (PyObject *)&NativeNodeContextType) < 0) {
        return -1;
    }
    if (PyModule_AddObjectRef(module, "NativeEngine", (PyObject *)&NativeEngineType) < 0) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot engine_slots[] = {
    {Py_mod_exec, engine_mod_exec},
#ifdef Py_GIL_DISABLED
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}
};

static struct PyModuleDef engine_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "phyelds.accel._engine",
    .m_doc = "C-backed aggregate computing engine and batch loop.",
    .m_size = 0,
    .m_methods = module_methods,
    .m_slots = engine_slots,
};

PyMODINIT_FUNC
PyInit__engine(void)
{
    return PyModuleDef_Init(&engine_module);
}
