/* Boodler: a programmable soundscape tool
   Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
   <http://eblong.com/zarf/boodler/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/

#include <stdio.h>
#include <stdlib.h>
#include <Python.h>

#include "common.h"
#include "noteq.h"
#include "audev.h"
#include "sample.h"

typedef struct volrange_struct {
  long start, end;
#ifdef BOODLER_INTMATH
  long istartvol, iendvol;
#else
  double startvol, endvol;
#endif
} volrange_t;

/* A queue of notes, ordered by starting time, past to future. */
static note_t *queue = NULL;

static long current_time = 0; /* frame time */

static volrange_t *ranges = NULL;
int maxranges = 0;

static note_t *last_added = NULL;

int noteq_init()
{
  last_added = NULL;

  maxranges = 2;
  ranges = (volrange_t *)malloc(sizeof(volrange_t) * maxranges);
  if (!ranges)
    return FALSE;

  return TRUE;
}

static void noteq_add(note_t *note)
{
  long starttime = note->starttime;
  note_t **nptr;

  if (last_added && starttime >= last_added->starttime) {
    nptr = &(last_added->next);
  }
  else {
    nptr = &queue;
  }

  while ((*nptr) && starttime > (*nptr)->starttime) {
    nptr = &((*nptr)->next);
  }

  note->next = (*nptr);
  (*nptr) = note;
  last_added = note;
}

static void noteq_remove(note_t **noteptr)
{
  note_t *note = (*noteptr);
  (*noteptr) = note->next;
  note->next = NULL;

  last_added = NULL;
}

long note_create(sample_t *samp, double pitch, double volume,
  double panscale, double panshift,
  long starttime, PyObject *channel, PyObject *removefunc)
{
  return note_create_reps(samp, pitch, volume, panscale, panshift, starttime, 1, channel, removefunc);
}

long note_create_duration(sample_t *samp, double pitch, double volume,
  double panscale, double panshift,
  long starttime, long duration, PyObject *channel, PyObject *removefunc)
{
  int reps;

  if (!samp->hasloop) {
    reps = 1;
  }
  else {
    long looplen = samp->looplen;
    long margins = samp->numframes - looplen;
    duration = (long)((double)duration * (samp->framerate * pitch));
    reps = (duration - margins + (looplen-1)) / looplen;
  }

  return note_create_reps(samp, pitch, volume, panscale, panshift, starttime, reps, channel, removefunc);
}

long note_create_reps(sample_t *samp, double pitch, double volume,
  double panscale, double panshift,
  long starttime, int reps, PyObject *channel, PyObject *removefunc)
{
  note_t *note;
  long duration;
  double ratio;

  note = (note_t *)malloc(sizeof(note_t));
  if (!note)
    return 0;
  
  ratio = (samp->framerate * pitch);
  if (!samp->hasloop || reps <= 1) {
    reps = 1;
    duration = (double)(samp->numframes) / ratio;
  }
  else {
    duration = (double)(samp->numframes + samp->looplen * (reps-1)) / ratio;
  }

  note->sample = samp;
  note->pitch = pitch;
  note->volume = volume;
  note->panscale = panscale;
  note->panshift = panshift;
  note->starttime = starttime;
  note->repetitions = reps;
  note->channel = channel;
  if (note->channel) {
    Py_INCREF(note->channel);
  }
  note->removefunc = removefunc;
  if (note->removefunc) {
    Py_INCREF(note->removefunc);
  }

  note->framepos = 0;
  note->framefrac = 0;
  note->repsleft = reps-1;
  note->next = NULL;

  noteq_add(note);

  /* printf("Added note %p, samp %p, pitch %g, vol %g, starttime %ld, reps %d, duration %ld\n",
     note, samp, pitch, volume, starttime, reps, duration); */

  return duration;
}

void note_destroy(note_t **noteptr)
{
  note_t *note = (*noteptr);
  /* printf("Removed note %p (samp %p)\n", note, note->sample); */

  noteq_remove(noteptr);

  if (note->removefunc && PyCallable_Check(note->removefunc)) {
    PyObject *result;
    result = PyObject_CallFunction(note->removefunc, NULL);
    if (result) {
      Py_DECREF(result);
    }
    else {
      fprintf(stderr, "exception calling note remover\n");
      PyErr_Clear();
    }
  }

  if (note->channel) {
    Py_DECREF(note->channel);
    note->channel = NULL;
  }
  if (note->removefunc) {
    Py_DECREF(note->removefunc);
    note->removefunc = NULL;
  }

  note->sample = NULL;
  note->starttime = 0;
  free(note);
}

int noteq_generate(long *buffer, generate_func_t genfunc, void *rock)
{
  int ranx;
  long lx;
  note_t **nptr;
  long framesperbuf = audev_get_framesperbuf();
  long end_time;

  /* This can become invalid, since we're deleting notes */
  last_added = NULL;

  if (genfunc) {
    int res = (*genfunc)(current_time, rock);
    if (res)
      return TRUE;
  }
  /* Remember, genfunc might have called noteq_adjust_timebase() to
     change the current_time */

  end_time = current_time + framesperbuf;

  memset(buffer, 0, sizeof(long) * 2 * framesperbuf);

  nptr = &queue;
  while (1) {
    note_t *note = (*nptr);
    sample_t *samp;
    int willdelete = FALSE;
    long notestart;
    double pitch;
    long lpitch;
    double volume;
    double stereoshift, stereoscale;
    int numranges;
    long *valptr;
    value_t *sampdata;
    long framepos, framefrac;
    long numframes;

    if (!note || (note->starttime >= end_time)) {
      break;
    }

    samp = note->sample;

    stereoscale = note->panscale;
    stereoshift = note->panshift;

    volume = note->volume;
    numranges = 0;

    if (note->channel) {
      PyObject *chan = note->channel;
      Py_INCREF(chan);

      while (1) {
	PyObject *newchan;
	PyObject *stereo;
	PyObject *vol = PyObject_GetAttrString(chan, "volume");
	if (vol) {
	  if (PyTuple_Check(vol) && PyTuple_Size(vol) == 4) {
	    long endtm;
	    double endvol;
	    endtm = PyInt_AsLong(PyTuple_GET_ITEM(vol, 1));
	    endvol = PyFloat_AsDouble(PyTuple_GET_ITEM(vol, 3));

	    if (current_time >= endtm) {
	      volume *= endvol;
	    }
	    else {
	      long starttm;
	      double startvol;
	      starttm = PyInt_AsLong(PyTuple_GET_ITEM(vol, 0));
	      startvol = PyFloat_AsDouble(PyTuple_GET_ITEM(vol, 2));
	      if (starttm >= end_time) {
		volume *= startvol;
	      }
	      else {
		if (numranges >= maxranges) {
		  maxranges *= 2;
		  ranges = (volrange_t *)realloc(ranges, 
		    sizeof(volrange_t) * maxranges);
		}
		ranges[numranges].start = starttm;
		ranges[numranges].end = endtm;
#ifdef BOODLER_INTMATH
		ranges[numranges].istartvol = (long)(startvol * 65536.0);
		ranges[numranges].iendvol = (long)(endvol * 65536.0);
#else
		ranges[numranges].startvol = startvol;
		ranges[numranges].endvol = endvol;
#endif
		numranges++;
	      }
	    }

	  }
	  Py_DECREF(vol);
	}
	vol = NULL;

	stereo = PyObject_GetAttrString(chan, "stereo");
	if (stereo) {
	  if (PyTuple_Check(stereo) && PyTuple_Size(stereo) == 2) {
	    double chshift, chscale;
	    chscale = PyFloat_AsDouble(PyTuple_GET_ITEM(stereo, 0));
	    chshift = PyFloat_AsDouble(PyTuple_GET_ITEM(stereo, 1));
	    stereoscale = stereoscale * chscale;
	    stereoshift = (stereoshift * chscale) + chshift;
	  }

	  Py_DECREF(stereo);
	}
	stereo = NULL;

	newchan = PyObject_GetAttrString(chan, "parent");
	Py_DECREF(chan);
	chan = NULL;
	if (!newchan) {
	  break;
	}
	if (newchan == Py_None) {
	  Py_DECREF(newchan);
	  break;
	}
	chan = newchan;
      }
    }

    pitch = samp->framerate * note->pitch;
    lpitch = (long)(pitch * (double)0x10000);
    if (lpitch < 1)
      lpitch = 1;
    else if (lpitch > 0x10000000)
      lpitch = 0x10000000;

    framepos = note->framepos;
    framefrac = note->framefrac;
    numframes = samp->numframes;
    sampdata = samp->data;

    if (note->starttime >= current_time) {
      notestart = note->starttime - current_time;
    }
    else {
      notestart = 0;
    }
    
    valptr = &buffer[notestart*2];

    if (samp->numchannels == 1) {
      double vollft, volrgt;
      long ivollft, ivolrgt;
#ifdef BOODLER_INTMATH
      long ivollftbase, ivolrgtbase;
#endif      
      if (stereoshift < 0.0) {
	vollft = 1.0;
	volrgt = 1.0 + (stereoshift);
	if (volrgt < 0.0)
	  volrgt = 0.0;
      }
      else {
	volrgt = 1.0;
	vollft = 1.0 - (stereoshift);
	if (vollft < 0.0)
	  vollft = 0.0;
      }
      ivollft = (long)(volume * vollft * 65536.0);
      ivolrgt = (long)(volume * volrgt * 65536.0);
#ifdef BOODLER_INTMATH
      ivollftbase = ivollft;
      ivolrgtbase = ivolrgt;
#endif

      for (lx=notestart; lx<framesperbuf; lx++) {
	long cursamp, nextsamp;
	long val0, val1;
	long result, reslef, resrgt;

	cursamp = framepos;
	if (framepos+1 == samp->loopend && note->repsleft > 0) {
	  nextsamp = (framepos + 1 - samp->looplen);
	}
	else {
	  nextsamp = cursamp+1;
	}

	val0 = (long)sampdata[cursamp];
	val1 = (long)sampdata[nextsamp];
	result = (val0 * (0x10000-framefrac)) + (val1 * framefrac);

	if (numranges) {
	  long curtime = current_time + lx;
#ifdef BOODLER_INTMATH
	  long ivarvols = 0x4000;
#else
	  double varvols = 1.0;
#endif
	  for (ranx=0; ranx<numranges; ranx++) {
	    if (curtime >= ranges[ranx].end) {
#ifdef BOODLER_INTMATH
	      ivarvols = ((ivarvols * ranges[ranx].iendvol) >> 16);
#else
	      varvols *= ranges[ranx].endvol;
#endif
	    }
	    else if (curtime <= ranges[ranx].start) {
#ifdef BOODLER_INTMATH
	      ivarvols = ((ivarvols * ranges[ranx].istartvol) >> 16);
#else
	      varvols *= ranges[ranx].startvol;
#endif
	    }
	    else {
#ifdef BOODLER_INTMATH
	      long intermed = ((curtime-ranges[ranx].start)
		/ (((ranges[ranx].end-ranges[ranx].start) >> 8) | (long)1));
	      intermed = ((intermed * (ranges[ranx].iendvol - ranges[ranx].istartvol)) >> 8);
	      intermed = intermed + ranges[ranx].istartvol;
	      ivarvols = ((ivarvols * intermed) >> 16);
#else
	      varvols *= ((double)(curtime-ranges[ranx].start) 
		/ (double)(ranges[ranx].end-ranges[ranx].start) 
		* (ranges[ranx].endvol - ranges[ranx].startvol) 
		+ ranges[ranx].startvol);
#endif
	    }
	  }
#ifdef BOODLER_INTMATH
	  ivollft = ((ivarvols * ivollftbase) >> 14);
	  ivolrgt = ((ivarvols * ivolrgtbase) >> 14);
#else
	  ivollft = (long)(volume * varvols * vollft * 65536.0);
	  ivolrgt = (long)(volume * varvols * volrgt * 65536.0);
#endif
	}

	reslef = ((result >> 16) * ivollft) >> 16;
	resrgt = ((result >> 16) * ivolrgt) >> 16;
	
	*valptr += reslef;
	valptr++;
	*valptr += resrgt;
	valptr++;

	framefrac += lpitch;
	framepos += (framefrac >> 16);
	framefrac &= 0xFFFF;

	while (note->repsleft > 0 && framepos >= samp->loopend) {
	  framepos -= samp->looplen;
	  note->repsleft--;
	}

	if (framepos+1 >= numframes && note->repsleft == 0) {
	  willdelete = TRUE;
	  break;
	}
      }
    }
    else {
      double panch0, panch1;
      double vol0lft, vol0rgt, vol1lft, vol1rgt;
      double normfac;
      long ivol0lft, ivol0rgt, ivol1lft, ivol1rgt;
#ifdef BOODLER_INTMATH
      long ivol0lftbase, ivol0rgtbase;
      long ivol1lftbase, ivol1rgtbase;
#endif      

      panch0 = (stereoshift - stereoscale);
      panch1 = (stereoshift + stereoscale);

      if (panch0 < 0.0) {
	vol0lft = 1.0;
	vol0rgt = 1.0 + (panch0);
	if (vol0rgt < 0.0)
	  vol0rgt = 0.0;
      }
      else {
	vol0rgt = 1.0;
	vol0lft = 1.0 - (panch0);
	if (vol0lft < 0.0)
	  vol0lft = 0.0;
      }
      if (panch1 < 0.0) {
	vol1lft = 1.0;
	vol1rgt = 1.0 + (panch1);
	if (vol1rgt < 0.0)
	  vol1rgt = 0.0;
      }
      else {
	vol1rgt = 1.0;
	vol1lft = 1.0 - (panch1);
	if (vol1lft < 0.0)
	  vol1lft = 0.0;
      }

      normfac = vol0lft + vol1lft;
      if (normfac < 0.001) {
	/* nothing */
      }
      else {
	double scale0, scale1;
	normfac = 1.0 / normfac;
	scale0 = vol0lft * normfac;
	scale1 = vol1lft * normfac;
	vol0lft *= scale0;
	vol1lft *= scale1;
      }
      normfac = vol0rgt + vol1rgt;
      if (normfac < 0.001) {
	/* nothing */
      }
      else {
	double scale0, scale1;
	normfac = 1.0 / normfac;
	scale0 = vol0rgt * normfac;
	scale1 = vol1rgt * normfac;
	vol0rgt *= scale0;
	vol1rgt *= scale1;
      }

      /* printf("(%gA+%gB , %gA+%gB)\n", vol0lft, vol1lft, vol0rgt, vol1rgt); */

      ivol0lft = (long)(volume * vol0lft * 65536.0);
      ivol0rgt = (long)(volume * vol0rgt * 65536.0);
      ivol1lft = (long)(volume * vol1lft * 65536.0);
      ivol1rgt = (long)(volume * vol1rgt * 65536.0);
#ifdef BOODLER_INTMATH
      ivol0lftbase = ivol0lft;
      ivol0rgtbase = ivol0rgt;
      ivol1lftbase = ivol1lft;
      ivol1rgtbase = ivol1rgt;
#endif
      
      for (lx=notestart; lx<framesperbuf; lx++) {
	long cursamp, nextsamp;
	long val0, val1;
	long resch0, resch1;
	long res0lef, res0rgt, res1lef, res1rgt;

	cursamp = framepos*2;
	if (framepos+1 == samp->loopend && note->repsleft > 0) {
	  nextsamp = (framepos + 1 - samp->looplen)*2;
	}
	else {
	  nextsamp = cursamp+2;
	}

	val0 = (long)sampdata[cursamp];
	val1 = (long)sampdata[nextsamp];
	resch0 = (val0 * (0x10000-framefrac)) + (val1 * framefrac);
	val0 = (long)sampdata[cursamp+1];
	val1 = (long)sampdata[nextsamp+1];
	resch1 = (val0 * (0x10000-framefrac)) + (val1 * framefrac);

	if (numranges) {
	  long curtime = current_time + lx;
#ifdef BOODLER_INTMATH
	  long ivarvols = 0x4000;
#else
	  double varvols = 1.0;
#endif
	  for (ranx=0; ranx<numranges; ranx++) {
	    if (curtime >= ranges[ranx].end) {
#ifdef BOODLER_INTMATH
	      ivarvols = ((ivarvols * ranges[ranx].iendvol) >> 16);
#else
	      varvols *= ranges[ranx].endvol;
#endif
	    }
	    else if (curtime <= ranges[ranx].start) {
#ifdef BOODLER_INTMATH
	      ivarvols = ((ivarvols * ranges[ranx].istartvol) >> 16);
#else
	      varvols *= ranges[ranx].startvol;
#endif
	    }
	    else {
#ifdef BOODLER_INTMATH
	      long intermed = ((curtime-ranges[ranx].start)
		/ (((ranges[ranx].end-ranges[ranx].start) >> 8) | (long)1));
	      intermed = ((intermed * (ranges[ranx].iendvol - ranges[ranx].istartvol)) >> 8);
	      intermed = intermed + ranges[ranx].istartvol;
	      ivarvols = ((ivarvols * intermed) >> 16);
#else
	      varvols *= ((double)(curtime-ranges[ranx].start) 
		/ (double)(ranges[ranx].end-ranges[ranx].start) 
		* (ranges[ranx].endvol - ranges[ranx].startvol) 
		+ ranges[ranx].startvol);
#endif
	    }
	  }
#ifdef BOODLER_INTMATH
	  ivol0lft = ((ivarvols * ivol0lftbase) >> 14);
	  ivol0rgt = ((ivarvols * ivol0rgtbase) >> 14);
	  ivol1lft = ((ivarvols * ivol1lftbase) >> 14);
	  ivol1rgt = ((ivarvols * ivol1rgtbase) >> 14);
#else
	  ivol0lft = (long)(volume * vol0lft * varvols * 65536.0);
	  ivol0rgt = (long)(volume * vol0rgt * varvols * 65536.0);
	  ivol1lft = (long)(volume * vol1lft * varvols * 65536.0);
	  ivol1rgt = (long)(volume * vol1rgt * varvols * 65536.0);
#endif
	}

	res0lef = ((resch0 >> 16) * ivol0lft) >> 16;
	res0rgt = ((resch0 >> 16) * ivol0rgt) >> 16;
	res1lef = ((resch1 >> 16) * ivol1lft) >> 16;
	res1rgt = ((resch1 >> 16) * ivol1rgt) >> 16;
      
	*valptr += (res0lef+res1lef);
	valptr++;
	*valptr += (res0rgt+res1rgt);
	valptr++;

	framefrac += lpitch;
	framepos += (framefrac >> 16);
	framefrac &= 0xFFFF;

	while (note->repsleft > 0 && framepos >= samp->loopend) {
	  framepos -= samp->looplen;
	  note->repsleft--;
	}

	if (framepos+1 >= numframes && note->repsleft == 0) {
	  willdelete = TRUE;
	  break;
	}
      }
    }

    note->framepos = framepos;
    note->framefrac = framefrac;

    if (!willdelete) {
      nptr = &((*nptr)->next);
    }
    else {
      note_destroy(nptr);
    }
  }

  current_time = end_time;
  return FALSE;
}

void note_destroy_by_channel(PyObject *channel)
{
  note_t **nptr;

  nptr = &queue;
  while (1) {
    note_t *note = (*nptr);
    int willdelete = FALSE;

    if (!note) {
      break;
    }

    if (note->channel == channel) {
      willdelete = TRUE;
    }
    else {
      if (note->channel && channel) {
	PyObject *ancs = PyObject_GetAttrString(note->channel, "ancestors");
	if (ancs) {
	  if (PyMapping_HasKey(ancs, channel))
	    willdelete = TRUE;
	  Py_DECREF(ancs);
	}
      }
    }

    if (!willdelete) {
      nptr = &((*nptr)->next);
    }
    else {
      note_destroy(nptr);
    }
  }
}

void noteq_adjust_timebase(long offset)
{
  note_t *note;

  current_time -= offset;

  for (note = queue; note; note = note->next) {
    note->starttime -= offset;
  }  
}

