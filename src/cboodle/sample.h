/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/

struct sample_struct {
  int loaded;
  int error;

  long numframes;
  int numchannels;
  int hasloop;
  long loopstart, loopend; /* frame time */
  long looplen;

  value_t *data; /* numchannels*numframes values, [-0x7FFF..0x7FFF] */
  double framerate; /* 1.0 means SOUNDRATE fps */
};

extern sample_t *sample_create(void);
extern void sample_destroy(sample_t *samp);

extern int sample_load(sample_t *samp, int framerate,
  long numframes, void *data, long loopstart, long loopend,
  int numchannels, int samplebits,
  int issigned, int isbigend);
extern void sample_unload(sample_t *samp);

