/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/

struct stereo_struct {
  double scalex;
  double shiftx;
  double scaley;
  double shifty;
};

struct note_struct {
  sample_t *sample;
  long starttime; /* frame time */
  double pitch; /* 1.0 means the sample's natural pitch */
  double volume; /* 0.0 is mute; 1.0 is full volume; higher to overdrive */
  stereo_t pan; /* see above */
  int repetitions; /* number of times through loop section */
  PyObject *channel; /* Python channel object */
  PyObject *removefunc; /* Python object to call when note is removed */

  long framepos; /* position in sample */
  long framefrac; /* ...and fraction, in 0.16 fixed-pt */
  int repsleft;

  note_t *next;
};

extern int noteq_init(void);
extern int noteq_generate(long *buffer, 
  generate_func_t genfunc, void *rock);
extern void note_destroy_by_channel(PyObject *channel);
extern void noteq_adjust_timebase(long offset);

extern long note_create(sample_t *samp, double pitch, double volume,
  stereo_t *pan,
  long starttime, PyObject *channel, PyObject *removefunc);
extern long note_create_reps(sample_t *samp, double pitch, double volume,
  stereo_t *pan,
  long starttime, int reps, PyObject *channel, PyObject *removefunc);
extern long note_create_duration(sample_t *samp, double pitch, double volume,
  stereo_t *pan,
  long starttime, long duration, PyObject *channel, PyObject *removefunc);
extern void note_destroy(note_t **noteptr);


