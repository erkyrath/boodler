/* Boodler: a programmable soundscape tool
   Copyright 2001-2011 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/

/* This source file does not get compiled directly. It must first be
   preprocessed by replacing the token esd with one of the
   extension module keys (file, oss, and so on).

   This is handled by the command
      python setup.py generate_source
   ...which generates the source files cboodle-file.c, cboodle-oss.c, 
   and so on. The source package is distributed with these files already
   generated.
*/


#include <Python.h>

#include "common.h"
#include "audev.h"
#include "sample.h"
#include "noteq.h"

typedef struct run_agents_rock_struct {
  PyObject *runagents;
  PyObject *generator;
} run_agents_rock_t;

extern void initcboodle_esd(void);
static int run_python_agents(long curtime, void *rock);

static PyObject *cboodle_init(PyObject *self, PyObject *args)
{
  char *devname = NULL;
  int ratewanted = 0;
  int verbose = 0;
  int ix, res;
  PyObject *extras = NULL;
  extraopt_t *opts = NULL;
  extraopt_t dummyopt = {NULL, NULL};

  if (!PyArg_ParseTuple(args, "|ziiO:init", &devname, &ratewanted, &verbose, &extras))
    return NULL;

  res = noteq_init();
  if (!res) {
    PyErr_SetString(PyExc_IOError, "unable to initialize note queue");
    return NULL;
  }

  if (extras && PyList_Check(extras)) {
    int count = PyList_Size(extras);

    opts = (extraopt_t *)malloc(sizeof(extraopt_t) * (count+1));
    if (!opts) {
      PyErr_SetString(PyExc_IOError, "unable to initialize extra options");
      return NULL;
    }

    for (ix=0; ix<count; ix++) {
      PyObject *tup = PyList_GetItem(extras, ix);
      PyObject *tkey, *tval;
      if (!tup)
	return NULL;
      if (!PyTuple_Check(tup) || PyTuple_Size(tup) != 2) {
	PyErr_SetString(PyExc_TypeError, "extraopts must be a list of 2-tuples");
	return NULL;
      }

      tkey = PyTuple_GetItem(tup, 0);
      if (!tkey)
	return NULL;
      tval = PyTuple_GetItem(tup, 1);
      if (!tval)
	return NULL;
      if (!PyString_Check(tkey) 
	|| !(tval == Py_None || PyString_Check(tval))) {
	PyErr_SetString(PyExc_TypeError, "extraopts must be (string, string) or (string, None)");
	return NULL;
      }

      opts[ix].key = PyString_AsString(tkey);
      if (tval == Py_None)
	opts[ix].val = NULL;
      else
	opts[ix].val = PyString_AsString(tval);
    }

    opts[count].key = NULL;
    opts[count].val = NULL;
  }

  res = audev_init_device(devname, ratewanted, (verbose!=0),
    (opts?opts:(&dummyopt)));
  if (!res) {
    PyErr_SetString(PyExc_IOError, "unable to initialize audio device");
    if (opts) {
      free(opts);
    }
    return NULL;
  }

  if (opts) {
    free(opts);
  }

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *cboodle_final(PyObject *self, PyObject *args)
{
  if (!PyArg_ParseTuple(args, ":final"))
    return NULL;

  audev_close_device();

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *cboodle_loop(PyObject *self, PyObject *args)
{
  run_agents_rock_t dat = {NULL, NULL};
  int res;

  if (!PyArg_ParseTuple(args, "OO:loop", &dat.runagents, &dat.generator))
    return NULL;
  
  if (!PyCallable_Check(dat.runagents)) {
    PyErr_SetString(PyExc_TypeError, "loop: argument 1 must be callable");
    return NULL;
  }

  res = audev_loop(noteq_generate, run_python_agents, &dat);
  if (res) {
    /* run_python_agents() returned TRUE, meaning that a Python
       exception occurred in runagents. */
    return NULL;
  }

  /* An error occurred in the C core, and a message has been printed. */
  Py_INCREF(Py_None);
  return Py_None;
}

static int run_python_agents(long curtime, void *rock)
{
  run_agents_rock_t *dat = rock;
  PyObject *arglist;
  PyObject *result;

  arglist = Py_BuildValue("(iO)", curtime, dat->generator);
  if (!arglist) {
    return TRUE;
  }

  result = PyEval_CallObject(dat->runagents, arglist);
  Py_DECREF(arglist);

  if (!result) {
    return TRUE;
  }

  Py_DECREF(result);

  return FALSE;
}

static PyObject *cboodle_framesperbuf(PyObject *self, PyObject *args)
{
  long framesperbuf;

  if (!PyArg_ParseTuple(args, ":framesperbuf"))
    return NULL;

  framesperbuf = audev_get_framesperbuf();
  return Py_BuildValue("i", framesperbuf);
}

static PyObject *cboodle_framespersec(PyObject *self, PyObject *args)
{
  long framespersec;

  if (!PyArg_ParseTuple(args, ":framespersec"))
    return NULL;

  framespersec = audev_get_soundrate();
  return Py_BuildValue("i", framespersec);
}

static PyObject *cboodle_new_sample(PyObject *self, PyObject *args)
{
  sample_t *samp;

  if (!PyArg_ParseTuple(args, ":new_sample"))
    return NULL;

  samp = sample_create();
  
  return Py_BuildValue("s#", (void *)&samp, sizeof(sample_t *));
}

static PyObject *cboodle_delete_sample(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;

  /* ### use CObject instead of sampstr/samplen? */

  if (!PyArg_ParseTuple(args, "s#:delete_sample", &sampstr, &samplen))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "delete_sample: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  sample_destroy(samp);

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *cboodle_unload_sample(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;

  if (!PyArg_ParseTuple(args, "s#:unload_sample", &sampstr, &samplen))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "unload_sample: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  sample_unload(samp);

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *cboodle_is_sample_error(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  int retval;

  if (!PyArg_ParseTuple(args, "s#:is_sample_error", &sampstr, &samplen))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "is_sample_error: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  retval = (samp->error != FALSE);
  
  return Py_BuildValue("i", retval);
}

static PyObject *cboodle_is_sample_loaded(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  int retval;

  if (!PyArg_ParseTuple(args, "s#:is_sample_loaded", &sampstr, &samplen))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "is_sample_loaded: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  retval = (samp->loaded != FALSE);
  
  return Py_BuildValue("i", retval);
}

static PyObject *cboodle_sample_info(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  PyObject *result;

  if (!PyArg_ParseTuple(args, "s#:sample_info", &sampstr, &samplen))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "sample_info: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  
  if (!samp->hasloop) {
    result = Py_BuildValue("(fl)", samp->framerate, samp->numframes);
  }
  else {
    result = Py_BuildValue("(flll)", samp->framerate, samp->numframes, samp->loopstart, samp->loopend);
  }
  return result;
}

static PyObject *cboodle_load_sample(PyObject *self, PyObject *args)
{
  int retval;
  sample_t *samp;
  char *sampstr;
  int samplen;

  int framerate;
  long numframes;
  void *data;
  int datalen;
  long loopstart, loopend;
  int numchannels;
  int samplebits;
  int issigned, isbigend;

  if (!PyArg_ParseTuple(args, "s#(ils#lliiii):load_sample", 
    &sampstr, &samplen, &framerate, &numframes,
    &data, &datalen, &loopstart, &loopend,
    &numchannels, &samplebits, &issigned, &isbigend)) {
    return NULL;
  }

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "load_sample: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);

  if (!data || datalen != numframes * numchannels * (samplebits/8)) {
    PyErr_SetString(PyExc_ValueError, 
      "load_sample: data length does not match frame count and frame size");
    return NULL;
  }

  /*
  printf("load_sample(samp %p, framerate %d, numframes %ld,"
    " data %p (len %d), loop %ld...%ld, numchannels %d, samplebits %d,"
    " issigned %d, isbigend %d\n",
    samp, framerate, numframes, data, datalen, loopstart, loopend,
    numchannels, samplebits, issigned, isbigend);
  */

  retval = sample_load(samp, framerate, numframes, data,
    loopstart, loopend, numchannels, samplebits,
    issigned, isbigend);

  return Py_BuildValue("i", retval);
}

static PyObject *cboodle_create_note(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  double pitch;
  double volume;
  stereo_t pan;
  long starttime;
  long retval;
  PyObject *channel, *removefunc;

  if (!PyArg_ParseTuple(args, "s#ddddddlOO:create_note", 
    &sampstr, &samplen,
    &pitch, &volume, 
    &pan.scalex, &pan.shiftx, &pan.scaley, &pan.shifty,
    &starttime, &channel, &removefunc))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "create_note: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  retval = note_create(samp, pitch, volume, &pan, starttime, channel, removefunc);

  return Py_BuildValue("l", retval);
}

static PyObject *cboodle_create_note_reps(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  double pitch;
  double volume;
  stereo_t pan;
  long starttime;
  int reps;
  long retval;
  PyObject *channel, *removefunc;

  if (!PyArg_ParseTuple(args, "s#ddddddliOO:create_note",
    &sampstr, &samplen,
    &pitch, &volume,
    &pan.scalex, &pan.shiftx, &pan.scaley, &pan.shifty,
    &starttime, &reps, &channel, &removefunc))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "create_note: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  retval = note_create_reps(samp, pitch, volume, &pan, starttime, reps, channel, removefunc);

  return Py_BuildValue("l", retval);
}

static PyObject *cboodle_create_note_duration(PyObject *self, PyObject *args)
{
  sample_t *samp;
  char *sampstr;
  int samplen;
  double pitch;
  double volume;
  stereo_t pan;
  long starttime;
  long duration;
  long retval;
  PyObject *channel, *removefunc;

  if (!PyArg_ParseTuple(args, "s#ddddddllOO:create_note",
    &sampstr, &samplen,
    &pitch, &volume,
    &pan.scalex, &pan.shiftx, &pan.scaley, &pan.shifty,
    &starttime, &duration, &channel, &removefunc))
    return NULL;

  if (!sampstr || samplen != sizeof(sample_t *)) {
    PyErr_SetString(PyExc_TypeError, 
      "create_note: argument must be a string returned by new_sample");
    return NULL;
  }

  samp = *((sample_t **)sampstr);
  retval = note_create_duration(samp, pitch, volume, &pan, starttime, duration, channel, removefunc);

  return Py_BuildValue("l", retval);
}

static PyObject *cboodle_stop_notes(PyObject *self, PyObject *args)
{
  PyObject *channel;

  if (!PyArg_ParseTuple(args, "O:stop_notes", &channel))
    return NULL;

  note_destroy_by_channel(channel);

  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *cboodle_adjust_timebase(PyObject *self, PyObject *args)
{
  long offset;

  if (!PyArg_ParseTuple(args, "l:adjust_timebase", &offset))
    return NULL;

  noteq_adjust_timebase(offset);

  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef methods[] = {
  {"init", cboodle_init, METH_VARARGS},
  {"loop", cboodle_loop, METH_VARARGS},
  {"final", cboodle_final, METH_VARARGS},
  {"framesperbuf", cboodle_framesperbuf, METH_VARARGS},
  {"framespersec", cboodle_framespersec, METH_VARARGS},
  {"new_sample", cboodle_new_sample, METH_VARARGS},
  {"delete_sample", cboodle_delete_sample, METH_VARARGS},
  {"load_sample", cboodle_load_sample, METH_VARARGS},
  {"unload_sample", cboodle_unload_sample, METH_VARARGS},
  {"is_sample_error", cboodle_is_sample_error, METH_VARARGS},
  {"is_sample_loaded", cboodle_is_sample_loaded, METH_VARARGS},
  {"sample_info", cboodle_sample_info, METH_VARARGS},
  {"create_note", cboodle_create_note, METH_VARARGS},
  {"create_note_reps", cboodle_create_note_reps, METH_VARARGS},
  {"create_note_duration", cboodle_create_note_duration, METH_VARARGS},
  {"stop_notes", cboodle_stop_notes, METH_VARARGS},
  {"adjust_timebase", cboodle_adjust_timebase, METH_VARARGS},
  {NULL, NULL}
};

void initcboodle_esd(void)
{
  Py_InitModule("cboodle_esd", methods);
}

