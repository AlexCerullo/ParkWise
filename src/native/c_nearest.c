#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdlib.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    double lat;
    double lng;
    double distance;
    double avg_fine;
    long violation_count;
    long violation_types;
    PyObject *location;
    double risk_score;
} nearest_result_t;

static nearest_result_t *result_buffer = NULL;
static Py_ssize_t result_capacity = 0;
static long hot_path_allocs_last = 0;
static long hot_path_allocs_total = 0;

static double to_radians(double degrees) {
    return degrees * (M_PI / 180.0);
}

static double haversine_miles(double lat1, double lng1, double lat2, double lng2) {
    const double radius_miles = 3959.0;
    double dlat = to_radians(lat2 - lat1);
    double dlng = to_radians(lng2 - lng1);

    double a = pow(sin(dlat / 2.0), 2.0) +
               cos(to_radians(lat1)) * cos(to_radians(lat2)) * pow(sin(dlng / 2.0), 2.0);
    double c = 2.0 * asin(fmin(1.0, sqrt(a)));
    return radius_miles * c;
}

static int compare_results(const void *a, const void *b) {
    const nearest_result_t *ra = (const nearest_result_t *)a;
    const nearest_result_t *rb = (const nearest_result_t *)b;

    if (ra->risk_score < rb->risk_score) {
        return -1;
    }
    if (ra->risk_score > rb->risk_score) {
        return 1;
    }
    if (ra->distance < rb->distance) {
        return -1;
    }
    if (ra->distance > rb->distance) {
        return 1;
    }
    return 0;
}

static PyObject *build_python_result(const nearest_result_t *result) {
    PyObject *entry = PyDict_New();
    if (!entry) {
        return NULL;
    }

    PyObject *location_str = result->location ? result->location : PyUnicode_FromString("");
    if (!location_str) {
        Py_DECREF(entry);
        return NULL;
    }

    PyDict_SetItemString(entry, "location", location_str);
    PyDict_SetItemString(entry, "lat", PyFloat_FromDouble(result->lat));
    PyDict_SetItemString(entry, "lng", PyFloat_FromDouble(result->lng));
    PyDict_SetItemString(entry, "distance", PyFloat_FromDouble(result->distance));
    PyDict_SetItemString(entry, "violationCount", PyLong_FromLong(result->violation_count));
    PyDict_SetItemString(entry, "avgFine", PyFloat_FromDouble(result->avg_fine));
    PyDict_SetItemString(entry, "violationTypes", PyLong_FromLong(result->violation_types));
    PyDict_SetItemString(entry, "riskScore", PyFloat_FromDouble(result->risk_score));

    const char *risk_level = "Low";
    if (result->risk_score > 0.66) {
        risk_level = "High";
    } else if (result->risk_score > 0.33) {
        risk_level = "Medium";
    }
    PyDict_SetItemString(entry, "riskLevel", PyUnicode_FromString(risk_level));

    if (!result->location) {
        Py_DECREF(location_str);
    }

    return entry;
}

static void release_locations(Py_ssize_t count) {
    if (!result_buffer) {
        return;
    }

    for (Py_ssize_t i = 0; i < count; ++i) {
        if (result_buffer[i].location) {
            Py_DECREF(result_buffer[i].location);
            result_buffer[i].location = NULL;
        }
    }
}

static int ensure_capacity(Py_ssize_t needed) {
    if (needed <= result_capacity) {
        return 0;
    }

    Py_ssize_t new_capacity = result_capacity > 0 ? result_capacity : 1024;
    while (new_capacity < needed) {
        new_capacity *= 2;
    }

    nearest_result_t *new_buffer = PyMem_Realloc(result_buffer, sizeof(nearest_result_t) * new_capacity);
    if (!new_buffer) {
        return -1;
    }

    result_buffer = new_buffer;
    result_capacity = new_capacity;
    hot_path_allocs_last += 1;
    hot_path_allocs_total += 1;
    return 0;
}

static PyObject *filter_rank(PyObject *self, PyObject *args) {
    double user_lat, user_lng, radius;
    PyObject *candidates_obj;
    Py_ssize_t limit;

    if (!PyArg_ParseTuple(args, "dddOn", &user_lat, &user_lng, &radius, &candidates_obj, &limit)) {
        return NULL;
    }

    if (limit < 1) {
        limit = 1;
    }

    hot_path_allocs_last = 0;

    PyObject *seq = PySequence_Fast(candidates_obj, "candidates must be a sequence");
    if (!seq) {
        return NULL;
    }

    Py_ssize_t candidate_count = PySequence_Fast_GET_SIZE(seq);
    if (candidate_count == 0) {
        Py_DECREF(seq);
        return PyList_New(0);
    }

    if (ensure_capacity(candidate_count) != 0) {
        Py_DECREF(seq);
        return PyErr_NoMemory();
    }
    nearest_result_t *results = result_buffer;

    Py_ssize_t kept = 0;
    for (Py_ssize_t i = 0; i < candidate_count; ++i) {
        PyObject *item = PySequence_Fast_GET_ITEM(seq, i);
        if (!PyTuple_Check(item) || PyTuple_GET_SIZE(item) != 6) {
            Py_DECREF(seq);
            release_locations(kept);
            PyErr_SetString(PyExc_TypeError, "candidate entries must be 6-tuples");
            return NULL;
        }

        PyObject *lat_obj = PyTuple_GET_ITEM(item, 0);
        PyObject *lng_obj = PyTuple_GET_ITEM(item, 1);
        PyObject *count_obj = PyTuple_GET_ITEM(item, 2);
        PyObject *avg_obj = PyTuple_GET_ITEM(item, 3);
        PyObject *types_obj = PyTuple_GET_ITEM(item, 4);
        PyObject *location_obj = PyTuple_GET_ITEM(item, 5);

        double lat = PyFloat_AsDouble(lat_obj);
        double lng = PyFloat_AsDouble(lng_obj);
        long violation_count = PyLong_AsLong(count_obj);
        double avg_fine = PyFloat_AsDouble(avg_obj);
        long violation_types = PyLong_AsLong(types_obj);

        if (PyErr_Occurred()) {
            Py_DECREF(seq);
            release_locations(kept);
            return NULL;
        }

        double distance = haversine_miles(user_lat, user_lng, lat, lng);
        if (distance > radius) {
            continue;
        }

        nearest_result_t *slot = &results[kept];
        slot->lat = lat;
        slot->lng = lng;
        slot->distance = distance;
        slot->avg_fine = avg_fine;
        slot->violation_count = violation_count;
        slot->violation_types = violation_types;

        if (PyUnicode_Check(location_obj)) {
            Py_INCREF(location_obj);
            slot->location = location_obj;
        } else {
            slot->location = NULL;
        }

        kept++;
    }

    Py_DECREF(seq);
    if (kept == 0) {
        release_locations(kept);
        return PyList_New(0);
    }

    long min_count = results[0].violation_count;
    long max_count = results[0].violation_count;
    for (Py_ssize_t i = 1; i < kept; ++i) {
        if (results[i].violation_count < min_count) {
            min_count = results[i].violation_count;
        }
        if (results[i].violation_count > max_count) {
            max_count = results[i].violation_count;
        }
    }

    double span = (double)(max_count - min_count);
    if (span < 1e-9) {
        span = 1.0;
    }

    for (Py_ssize_t i = 0; i < kept; ++i) {
        results[i].risk_score = (results[i].violation_count - min_count) / span;
    }

    qsort(results, kept, sizeof(nearest_result_t), compare_results);
    Py_ssize_t final_count = kept < limit ? kept : limit;

    PyObject *out_list = PyList_New(final_count);
    if (!out_list) {
        release_locations(kept);
        return NULL;
    }

    for (Py_ssize_t i = 0; i < final_count; ++i) {
        PyObject *entry = build_python_result(&results[i]);
        if (!entry) {
            Py_DECREF(out_list);
            release_locations(kept);
            return NULL;
        }
        PyList_SET_ITEM(out_list, i, entry);
    }

    release_locations(kept);
    return out_list;
}

static PyObject *get_hot_path_stats(PyObject *self, PyObject *Py_UNUSED(args)) {
    PyObject *stats = PyDict_New();
    if (!stats) {
        return NULL;
    }

    PyDict_SetItemString(stats, "allocations_last_call", PyLong_FromLong(hot_path_allocs_last));
    PyDict_SetItemString(stats, "total_reallocations", PyLong_FromLong(hot_path_allocs_total));
    PyDict_SetItemString(stats, "buffer_capacity", PyLong_FromSsize_t(result_capacity));
    return stats;
}

static PyMethodDef module_methods[] = {
    {"filter_rank", filter_rank, METH_VARARGS, "Filter and rank nearest parking violations."},
    {"hot_path_stats", (PyCFunction)get_hot_path_stats, METH_NOARGS, "Get allocation stats for the native hot path."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT,
    "c_nearest",
    "Native helpers for nearest-violation calculations.",
    -1,
    module_methods
};

PyMODINIT_FUNC PyInit_c_nearest(void) {
    return PyModule_Create(&module_definition);
}
