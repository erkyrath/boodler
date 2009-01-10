/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
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

/* This represents a linear volume fade, starting and ending at
   particular times. */
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

static void leftright_volumes(double shiftx, double shifty,
  double *outlft, double *outrgt);

/* A quick introduction to Python reference-counting:
   (See <http://docs.python.org/api/api.html> for full docs.)

   C code embedded in Python is responsible for incrementing and
   decrementing the reference counts of the objects it uses. We only
   use a couple of idioms:

   PyObject_GetAttrString() -- returns a new reference. The caller
   must call Py_DECREF when finished with the value.

   PyTuple_GET_ITEM() -- returns a "borrowed" reference. The caller
   doesn't have to release the reference. But once the tuple is
   released, items borrowed from the tuple may vanish too.

   Python objects stored in a C object (for example, note->channel) --
   we must call Py_INCREF for as long as the object is in use, and
   Py_DECREF when we release it.
 */

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
  stereo_t *pan,
  long starttime, PyObject *channel, PyObject *removefunc)
{
  return note_create_reps(samp, pitch, volume, pan, starttime, 1, channel, removefunc);
}

long note_create_duration(sample_t *samp, double pitch, double volume,
  stereo_t *pan,
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

  return note_create_reps(samp, pitch, volume, pan, starttime, reps, channel, removefunc);
}

long note_create_reps(sample_t *samp, double pitch, double volume,
  stereo_t *pan,
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
  /* Must copy the pan struct that was passed in, because it is 
     stack-allocated. */
  note->pan = *pan;
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

/* The following macro breaks every rule of C style and moral
   rectitude. It's a bunch of lines, it doesn't paren-protect its
   arguments, and it doesn't act like an expression.

   But it's the operation I need, and I need it inline.

   The goal is to multiply FVOL by a factor taken from the
   linear-interpolation range RANGE. CURTIME indicates the position in
   RANGE to look at.

   In integer-math mode, this operates on IVOL instead of FVOL. The
   unused parameter is never touched, so it doesn't have to exist at
   all. (I use two different variable names for the int and float
   cases, to be absolutely sure no mistakes get covered up by magical
   typecasting.)
*/

#ifdef BOODLER_INTMATH

#define APPLY_RANGE(RANGE, CURTIME, FVOL, IVOL)    \
    if (CURTIME >= RANGE.end) {                    \
      IVOL = ((IVOL * RANGE.iendvol) >> 16);       \
    }                                              \
    else if (CURTIME <= RANGE.start) {             \
      IVOL = ((IVOL * RANGE.istartvol) >> 16);     \
    }                                              \
    else {                                         \
      long intermed = ((CURTIME-RANGE.start)       \
	/ (((RANGE.end-RANGE.start) >> 8) | (long)1));                   \
      intermed = ((intermed * (RANGE.iendvol - RANGE.istartvol)) >> 8);  \
      intermed = intermed + RANGE.istartvol;       \
      IVOL = ((IVOL * intermed) >> 16);            \
    }

#else /* BOODLER_INTMATH */

#define APPLY_RANGE(RANGE, CURTIME, FVOL, IVOL)    \
    if (CURTIME >= RANGE.end) {                    \
      FVOL *= RANGE.endvol;                        \
    }                                              \
    else if (CURTIME <= RANGE.start) {             \
      FVOL *= RANGE.startvol;                      \
    }                                              \
    else {                                         \
      FVOL *= ((double)(CURTIME-RANGE.start)       \
	/ (double)(RANGE.end-RANGE.start)          \
	* (RANGE.endvol - RANGE.startvol)          \
	+ RANGE.startvol);                         \
    }

#endif /* BOODLER_INTMATH */

int noteq_generate(long *buffer, generate_func_t genfunc, void *rock)
{
  note_t **nptr;
  long framesperbuf = audev_get_framesperbuf();
  long end_time;

  /* These could be declared inside the loop, but if I put them
     outside I can initialize them early, which squashes some stupid
     compiler warnings. */
  stereo_t pan0, pan1;
  volrange_t range0lft, range0rgt, range1lft, range1rgt;

  if (genfunc) {
    int res = (*genfunc)(current_time, rock);
    if (res)
      return TRUE;
  }
  /* Remember, genfunc might have called noteq_adjust_timebase() to
     change the current_time */

  end_time = current_time + framesperbuf;

  /* Squash stupid compiler warnings. */
  memset(&pan1, 0, sizeof(pan1));
  memset(&range0lft, 0, sizeof(range0lft));
  range0rgt = range1lft = range1rgt = range0lft;

  /* The following code is unapologetically long, repetitive, and nasty.
     This is the bottom loop for mixing sound, so we don't trade off
     cycles for anything. */

  memset(buffer, 0, sizeof(long) * 2 * framesperbuf);

  /* Loop through all the notes in the queue. (At least up to the
     point where they're past the current buffer. For each note, add
     its contribution into the buffer. */
  nptr = &queue;
  while (1) {
    note_t *note = (*nptr);
    sample_t *samp;
    int willdelete = FALSE;
    long notestart;
    double pitch;
    long lpitch;
    double volume;
    int bothpans;
    int numranges;
    long *valptr;
    value_t *sampdata;
    long framepos, framefrac;
    long numframes;

    if (!note || (note->starttime >= end_time)) {
      break;
    }

    samp = note->sample;

    pan0 = note->pan;
    bothpans = FALSE;
    volume = note->volume;
    numranges = 0;

    /* We must compute a total volume, by multiplying the note's
       volume by the volume factor of every channel it's in. We do
       this by iterating up the channel tree. 

       The tricky part is that some channels might be in the middle of
       a volume change, which means we can't just multiply in a
       constant factor. Those channels (only) go onto the ranges list.
       (The ranges list will be consulted once per frame, as we
       generate the note.)

       While we're at it, we compose all the stereo pans. As with the
       volumes, we have to worry about channels that are in the middle
       of a pan change. However, the solution is different. Once a pan
       change appears, we keep track of two pan positions: that at the
       beginning of the buffer, and that at the end. (Before the first
       change appears, these are identical. The bothpans flag
       indicates whether we've hit that first change yet.) */

    if (note->channel) {
      PyObject *chan = note->channel;
      Py_INCREF(chan);

      while (1) {
	PyObject *newchan;
	PyObject *stereo;
	PyObject *vol = PyObject_GetAttrString(chan, "volume");
	if (vol) {
	  if (PyTuple_Check(vol) && PyTuple_Size(vol) == 4) {
	    /* A channel's volume is a 4-tuple: 

	       (int starttime, int endtime, float startvol, float endvol)

	       This is the general case: the volume fades from
	       startvol to endvol over an interval. Before starttime,
	       we assume the volume is flat at startvol; after
	       endtime, we assume endvol. 

	       If the volume is completely constant, endtime will be
	       zero, or perhaps just before current_time. (This fits
	       nicely into the general case.) */

	    long endtm;
	    double endvol;
	    endtm = PyInt_AsLong(PyTuple_GET_ITEM(vol, 1));
	    endvol = PyFloat_AsDouble(PyTuple_GET_ITEM(vol, 3));

	    if (current_time >= endtm) {
	      /* Channel volume is constant across the buffer. */
	      volume *= endvol;
	    }
	    else {
	      long starttm;
	      double startvol;
	      starttm = PyInt_AsLong(PyTuple_GET_ITEM(vol, 0));
	      startvol = PyFloat_AsDouble(PyTuple_GET_ITEM(vol, 2));
	      if (starttm >= end_time) {
		/* Channel volume is constant across the buffer. */
		volume *= startvol;
	      }
	      else {
		/* This is the nasty case; we're in the middle of a
		   fade. Rather than multiplying volume, we create a
		   new range in the ranges list. */

		if (numranges >= maxranges) {
		  maxranges *= 2;
		  ranges = (volrange_t *)realloc(ranges, 
		    sizeof(volrange_t) * maxranges);
		  if (!ranges)
		    return TRUE;
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
	  if (PyTuple_Check(stereo) && PyTuple_Size(stereo) == 4) {
	    /* A channel's stereo value is a 4-tuple:
	       (int starttime, int endtime, tuple startpan, tuple endpan)

	       Like the volume tuple, this is the general case. The
	       startpan and endpan values are stereo objects. 

	       A stereo object is a 0-, 2-, or 4-tuple. In full form:
	       (xscale, xshift, yscale, yshift)
	       Missing entries are presumed to be (1,0,1,0) in that order. */

	    PyObject *usepan = NULL;

	    long starttm = 0;
	    PyObject *startpan = NULL;
	    long endtm = PyInt_AsLong(PyTuple_GET_ITEM(stereo, 1));
	    PyObject *endpan = PyTuple_GET_ITEM(stereo, 3);

	    if (current_time >= endtm) {
	      /* Stereo is constant across the buffer. */
	      usepan = endpan;
	    }
	    else {
	      starttm = PyInt_AsLong(PyTuple_GET_ITEM(stereo, 0));
	      startpan = PyTuple_GET_ITEM(stereo, 2);

	      if (starttm >= end_time) {
		/* Stereo is constant across the buffer. */
		usepan = startpan;
	      }
	      else {
		/* Nasty case: we're in the middle of a stereo swoop. */
		usepan = NULL;
	      }
	    }

	    /* The value in usepan is now NULL if we're in a swoop, or
	       a stereo object if we're in the constant case. */

	    if (usepan) {
	      /* Apply constant transform to the pan value. (If we're
		 already keeping track of two pan values, apply it to
		 both of them.) */
	      int tuplesize = 0;
	      if (PyTuple_Check(usepan))
		tuplesize = PyTuple_Size(usepan);
	      if (tuplesize >= 2) {
		double chshift, chscale;
		chscale = PyFloat_AsDouble(PyTuple_GET_ITEM(usepan, 0));
		chshift = PyFloat_AsDouble(PyTuple_GET_ITEM(usepan, 1));
		pan0.scalex = pan0.scalex * chscale;
		pan0.shiftx = (pan0.shiftx * chscale) + chshift;
		if (bothpans) {
		  pan1.scalex = pan1.scalex * chscale;
		  pan1.shiftx = (pan1.shiftx * chscale) + chshift;
		}
	      }
	      if (tuplesize >= 4) {
		double chshift, chscale;
		chscale = PyFloat_AsDouble(PyTuple_GET_ITEM(usepan, 2));
		chshift = PyFloat_AsDouble(PyTuple_GET_ITEM(usepan, 3));
		pan0.scaley = pan0.scaley * chscale;
		pan0.shifty = (pan0.shifty * chscale) + chshift;
		if (bothpans) {
		  pan1.scaley = pan1.scaley * chscale;
		  pan1.shifty = (pan1.shifty * chscale) + chshift;
		}
	      }
	    }
	    else {
	      /* Record the pan positions at the start and end of the 
		 buffer (current_time and end_time). */
	      if (!bothpans) {
		/* This is the first non-constant pan we've hit. Set
		   up pan1 to be the same as what we've computed so
		   far. */
		pan1 = pan0;
		bothpans = TRUE;
	      }
	      /* Extract the stereo object values into stereo_t structs. */
	      stereo_t tuplestart, tupleend;
	      int tuplesizestart = 0;
	      int tuplesizeend = 0;
	      if (PyTuple_Check(startpan))
		tuplesizestart = PyTuple_Size(startpan);
	      if (tuplesizestart >= 2) {
		tuplestart.scalex = PyFloat_AsDouble(PyTuple_GET_ITEM(startpan, 0));
		tuplestart.shiftx = PyFloat_AsDouble(PyTuple_GET_ITEM(startpan, 1));
	      }
	      else {
		tuplestart.scalex = 1.0;
		tuplestart.shiftx = 0.0;
	      }
	      if (tuplesizestart >= 4) {
		tuplestart.scaley = PyFloat_AsDouble(PyTuple_GET_ITEM(startpan, 2));
		tuplestart.shifty = PyFloat_AsDouble(PyTuple_GET_ITEM(startpan, 3));
	      }
	      else {
		tuplestart.scaley = 1.0;
		tuplestart.shifty = 0.0;
	      }
	      if (PyTuple_Check(endpan))
		tuplesizeend = PyTuple_Size(endpan);
	      if (tuplesizeend >= 2) {
		tupleend.scalex = PyFloat_AsDouble(PyTuple_GET_ITEM(endpan, 0));
		tupleend.shiftx = PyFloat_AsDouble(PyTuple_GET_ITEM(endpan, 1));
	      }
	      else {
		tupleend.scalex = 1.0;
		tupleend.shiftx = 0.0;
	      }
	      if (tuplesizeend >= 4) {
		tupleend.scaley = PyFloat_AsDouble(PyTuple_GET_ITEM(endpan, 2));
		tupleend.shifty = PyFloat_AsDouble(PyTuple_GET_ITEM(endpan, 3));
	      }
	      else {
		tupleend.scaley = 1.0;
		tupleend.shifty = 0.0;
	      }

	      /* Interpolate for current_time, into pan0. */
	      stereo_t usetuple;
	      if (current_time >= endtm) {
		usetuple = tupleend;
	      }
	      else if (current_time >= starttm) {
		double ratio = ((double)(current_time - starttm)) / ((double)(endtm - starttm));
		usetuple.scalex = ratio * (tupleend.scalex - tuplestart.scalex) + tuplestart.scalex;
		usetuple.shiftx = ratio * (tupleend.shiftx - tuplestart.shiftx) + tuplestart.shiftx;
		usetuple.scaley = ratio * (tupleend.scaley - tuplestart.scaley) + tuplestart.scaley;
		usetuple.shifty = ratio * (tupleend.shifty - tuplestart.shifty) + tuplestart.shifty;
	      }
	      else {
		usetuple = tuplestart;
	      }
	      pan0.scalex = pan0.scalex * usetuple.scalex;
	      pan0.shiftx = (pan0.shiftx * usetuple.scalex) + usetuple.shiftx;
	      pan0.scaley = pan0.scaley * usetuple.scaley;
	      pan0.shifty = (pan0.shifty * usetuple.scaley) + usetuple.shifty;

	      /* Interpolate for end_time, into pan1. */
	      if (end_time >= endtm) {
		usetuple = tupleend;
	      }
	      else if (end_time >= starttm) {
		double ratio = ((double)(end_time - starttm)) / ((double)(endtm - starttm));
		usetuple.scalex = ratio * (tupleend.scalex - tuplestart.scalex) + tuplestart.scalex;
		usetuple.shiftx = ratio * (tupleend.shiftx - tuplestart.shiftx) + tuplestart.shiftx;
		usetuple.scaley = ratio * (tupleend.scaley - tuplestart.scaley) + tuplestart.scaley;
		usetuple.shifty = ratio * (tupleend.shifty - tuplestart.shifty) + tuplestart.shifty;
	      }
	      else {
		usetuple = tuplestart;
	      }
	      pan1.scalex = pan1.scalex * usetuple.scalex;
	      pan1.shiftx = (pan1.shiftx * usetuple.scalex) + usetuple.shiftx;
	      pan1.scaley = pan1.scaley * usetuple.scaley;
	      pan1.shifty = (pan1.shifty * usetuple.scaley) + usetuple.shifty;
	    }
	  }

	  Py_DECREF(stereo);
	}
	stereo = NULL;

	/*
	printf("pan0: %.3f %.3f %.3f %.3f. pan1: %.3f %.3f %.3f %.3f.\n",
	  pan0.scalex, pan0.shiftx, pan0.scaley, pan0.shifty,
	  pan1.scalex, pan1.shiftx, pan1.scaley, pan1.shifty); */

	/* Point chan at chan.parent, and continue the loop (unless
	   we've reached the top of the tree). */

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
      long lx;

      /* Compute the volume adjustment for the left and right output
	 channels, based on the pan position. */
      double vollft, volrgt;

      if (!bothpans) {
	leftright_volumes(pan0.shiftx, pan0.shifty, &vollft, &volrgt);
      }
      else {
	/* The pan position is changing, so don't put anything in
	   vollft/volrgt. Instead, work out the left and right volume
	   ranges. */
	double tmp0lft, tmp0rgt;
	double tmp1lft, tmp1rgt;

	vollft = 1.0;
	volrgt = 1.0;
	range0lft.start = current_time;
	range0rgt.start = current_time;
	range0lft.end = end_time;
	range0rgt.end = end_time;

	leftright_volumes(pan0.shiftx, pan0.shifty, &tmp0lft, &tmp0rgt);
	leftright_volumes(pan1.shiftx, pan1.shifty, &tmp1lft, &tmp1rgt);
#ifdef BOODLER_INTMATH
	range0lft.istartvol = (long)(tmp0lft * 65536.0);
	range0lft.iendvol = (long)(tmp1lft * 65536.0);
	range0rgt.istartvol = (long)(tmp0rgt * 65536.0);
	range0rgt.iendvol = (long)(tmp1rgt * 65536.0);
#else
	range0lft.startvol = tmp0lft;
	range0lft.endvol = tmp1lft;
	range0rgt.startvol = tmp0rgt;
	range0rgt.endvol = tmp1rgt;
#endif
      }

      long ivollft, ivolrgt;
#ifdef BOODLER_INTMATH
      long ivollftbase, ivolrgtbase;
#endif
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

	if (numranges || bothpans) {
	  int ranx;
	  long curtime = current_time + lx;
#ifdef BOODLER_INTMATH
	  /* Start with 0x4000, instead of 0x10000, to allow some
	     headroom when we multiply by values over 0x10000. We'll
	     compensate later by downshifting >>14 instead of >>16. */
	  long ivarvols = 0x4000;
#else
	  double varvols = 1.0;
#endif
	  for (ranx=0; ranx<numranges; ranx++) {
	    APPLY_RANGE(ranges[ranx], curtime, varvols, ivarvols);
	  }

	  if (!bothpans) {
	    /* Done. */
#ifdef BOODLER_INTMATH
	    ivollft = ((ivarvols * ivollftbase) >> 14);
	    ivolrgt = ((ivarvols * ivolrgtbase) >> 14);
#else
	    ivollft = (long)(volume * varvols * vollft * 65536.0);
	    ivolrgt = (long)(volume * varvols * volrgt * 65536.0);
#endif
	  }
	  else {
	    /* More to do -- we need to throw range0lft/range0rgt into
	       the mix. */
#ifdef BOODLER_INTMATH
	    long ivarvolslft = ivarvols;
	    long ivarvolsrgt = ivarvols;
#else
	    double varvolslft = varvols;
	    double varvolsrgt = varvols;
#endif
	    APPLY_RANGE(range0lft, curtime, varvolslft, ivarvolslft);
	    APPLY_RANGE(range0rgt, curtime, varvolsrgt, ivarvolsrgt);

#ifdef BOODLER_INTMATH
	    ivollft = ((ivarvolslft * ivollftbase) >> 14);
	    ivolrgt = ((ivarvolsrgt * ivolrgtbase) >> 14);
#else
	    ivollft = (long)(volume * varvolslft * vollft * 65536.0);
	    ivolrgt = (long)(volume * varvolsrgt * volrgt * 65536.0);
#endif
	  }
	}

	/* All of the volume and pan information has been boiled down
	   into ivollft/ivolrgt. Apply it to the sample. */

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
    else { /* samp->numchannels == 2 */
      long lx;

      /* Compute the volume adjustment for the left and right output
	 channels, based on the pan position. We have to do this
	 twice: for input channel 0 and for input channel 1. */
      double vol0lft, vol0rgt, vol1lft, vol1rgt;

      if (!bothpans) {
	leftright_volumes(pan0.shiftx - pan0.scalex, pan0.shifty,
	  &vol0lft, &vol0rgt); 
	leftright_volumes(pan0.shiftx + pan0.scalex, pan0.shifty,
	  &vol1lft, &vol1rgt);
      }
      else {
	/* The pan position is changing, so don't put anything in
	   vol#lft/vol#rgt. Instead, work out the left and right volume
	   ranges for each channel. */
	double tmp0lft, tmp0rgt;
	double tmp1lft, tmp1rgt;

	vol0lft = 1.0;
	vol0rgt = 1.0;
	range0lft.start = current_time;
	range0rgt.start = current_time;
	range0lft.end = end_time;
	range0rgt.end = end_time;

	leftright_volumes(pan0.shiftx - pan0.scalex, pan0.shifty,
	  &tmp0lft, &tmp0rgt);
	leftright_volumes(pan1.shiftx - pan1.scalex, pan1.shifty,
	  &tmp1lft, &tmp1rgt);
#ifdef BOODLER_INTMATH
	range0lft.istartvol = (long)(tmp0lft * 65536.0);
	range0lft.iendvol = (long)(tmp1lft * 65536.0);
	range0rgt.istartvol = (long)(tmp0rgt * 65536.0);
	range0rgt.iendvol = (long)(tmp1rgt * 65536.0);
#else
	range0lft.startvol = tmp0lft;
	range0lft.endvol = tmp1lft;
	range0rgt.startvol = tmp0rgt;
	range0rgt.endvol = tmp1rgt;
#endif

	vol1lft = 1.0;
	vol1rgt = 1.0;
	range1lft.start = current_time;
	range1rgt.start = current_time;
	range1lft.end = end_time;
	range1rgt.end = end_time;

	leftright_volumes(pan0.shiftx + pan0.scalex, pan0.shifty,
	  &tmp0lft, &tmp0rgt);
	leftright_volumes(pan1.shiftx + pan1.scalex, pan1.shifty,
	  &tmp1lft, &tmp1rgt);
#ifdef BOODLER_INTMATH
	range1lft.istartvol = (long)(tmp0lft * 65536.0);
	range1lft.iendvol = (long)(tmp1lft * 65536.0);
	range1rgt.istartvol = (long)(tmp0rgt * 65536.0);
	range1rgt.iendvol = (long)(tmp1rgt * 65536.0);
#else
	range1lft.startvol = tmp0lft;
	range1lft.endvol = tmp1lft;
	range1rgt.startvol = tmp0rgt;
	range1rgt.endvol = tmp1rgt;
#endif
      }

      /* printf("(%gA+%gB , %gA+%gB)\n", vol0lft, vol1lft, vol0rgt, vol1rgt); */

      long ivol0lft, ivol0rgt, ivol1lft, ivol1rgt;
#ifdef BOODLER_INTMATH
      long ivol0lftbase, ivol0rgtbase;
      long ivol1lftbase, ivol1rgtbase;
#endif      
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

	if (numranges || bothpans) {
	  int ranx;
	  long curtime = current_time + lx;
#ifdef BOODLER_INTMATH
	  long ivarvols = 0x4000;
#else
	  double varvols = 1.0;
#endif
	  for (ranx=0; ranx<numranges; ranx++) {
	    APPLY_RANGE(ranges[ranx], curtime, varvols, ivarvols);
	  }

	  if (!bothpans) {
	    /* Done. */
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
	  else {
	    /* More to do -- we need to throw range*lft/range*rgt into
	       the mix. */
#ifdef BOODLER_INTMATH
	    long ivarvolslft0 = ivarvols;
	    long ivarvolsrgt0 = ivarvols;
	    long ivarvolslft1 = ivarvols;
	    long ivarvolsrgt1 = ivarvols;
#else
	    double varvolslft0 = varvols;
	    double varvolsrgt0 = varvols;
	    double varvolslft1 = varvols;
	    double varvolsrgt1 = varvols;
#endif
	    APPLY_RANGE(range0lft, curtime, varvolslft0, ivarvolslft0);
	    APPLY_RANGE(range0rgt, curtime, varvolsrgt0, ivarvolsrgt0);
	    APPLY_RANGE(range1lft, curtime, varvolslft1, ivarvolslft1);
	    APPLY_RANGE(range1rgt, curtime, varvolsrgt1, ivarvolsrgt1);

#ifdef BOODLER_INTMATH
	    ivol0lft = ((ivarvolslft0 * ivol0lftbase) >> 14);
	    ivol0rgt = ((ivarvolsrgt0 * ivol0rgtbase) >> 14);
	    ivol1lft = ((ivarvolslft1 * ivol1lftbase) >> 14);
	    ivol1rgt = ((ivarvolsrgt1 * ivol1rgtbase) >> 14);
#else
	    ivol0lft = (long)(volume * vol0lft * varvolslft0 * 65536.0);
	    ivol0rgt = (long)(volume * vol0rgt * varvolsrgt0 * 65536.0);
	    ivol1lft = (long)(volume * vol1lft * varvolslft1 * 65536.0);
	    ivol1rgt = (long)(volume * vol1rgt * varvolsrgt1 * 65536.0);
#endif
	  }
	}

	/* All of the volume and pan information has been boiled down
	   into ivol#lft/ivol#rgt. Apply it to the sample. */

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

/* Given a point-source of sound at (shiftx, shifty), determine the
   volume levels it produces in the left and right output channels.
   These values will be between 0 and 1.
*/
static void leftright_volumes(double shiftx, double shifty,
  double *outlft, double *outrgt)
{
  double vollft, volrgt;
  double dist; 

  /* compute dist = max(abs(shiftx), abs(shifty)) */

  if (shiftx >= 0.0)
    dist = shiftx;
  else
    dist = -shiftx;
  if (shifty >= 0.0) {
    if (shifty > dist)
      dist = shifty;
  }
  else {
    if (-shifty > dist)
      dist = -shifty;
  }

  /* Normalize shiftx, shifty by dist. Distances < 1 are considered to be 1. */

  if (dist > 1.0) {
    shiftx /= dist;
    shifty /= dist;
  }

  /* Now shiftx, shifty are in the range [-1, 1] */
      
  /* Compute the volume levels, based on shiftx. (The Y value has no
     effect inside the [-1, 1] range.) */

  if (shiftx < 0.0) {
    vollft = 1.0;
    volrgt = 1.0 + shiftx;
  }
  else {
    volrgt = 1.0;
    vollft = 1.0 - shiftx;
  }

  /* Now scale down the volumes, using the inverse square of the distance. */

  if (dist > 1.0) {
    dist = dist*dist;
    vollft /= dist;
    volrgt /= dist;
  }

  *outlft = vollft;
  *outrgt = volrgt;
}
