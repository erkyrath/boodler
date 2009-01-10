/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/

#include <stdio.h>
#include <stdlib.h>

#include "common.h"
#include "audev.h"
#include "sample.h"

sample_t *sample_create()
{
  sample_t *samp;

  samp = (sample_t *)malloc(sizeof(sample_t));
  if (!samp)
    return NULL;

  samp->error = FALSE;
  samp->loaded = FALSE;
  samp->numframes = 0;
  samp->data = NULL;

  return samp;
}

void sample_destroy(sample_t *samp)
{
  if (samp->data) {
    free(samp->data);
    samp->data = NULL;
    samp->loaded = FALSE;
  }

  samp->error = TRUE;

  free(samp);
}

void sample_unload(sample_t *samp)
{
  if (samp->error)
    return;

  if (samp->data) {
    free(samp->data);
    samp->data = NULL;
  }
  samp->loaded = FALSE;
}

int sample_load(sample_t *samp, int framerate,
  long numframes, void *data, long loopstart, long loopend,
  int numchannels, int samplebits,
  int issigned, int isbigend)
{
  value_t *snd;
  value_t *sptr;
  int val;
  int numchanout;
  long fx;
  int bval, bval2;

  if (samp->error)
    return FALSE;
  if (samp->loaded)
    return TRUE;

  if (samplebits != 8 && samplebits != 16) {
    fprintf(stderr, 
      "Unable to load sound data at %d bits per sample (only 8 and 16 supported)\n", 
      samplebits);
    samp->error = TRUE;
    return FALSE;
  }

  if (numchannels == 1)
    numchanout = 1;
  else
    numchanout = 2;

  snd = (value_t *)malloc(sizeof(value_t) * numchanout * numframes);
  if (!snd) {
    fprintf(stderr, "Unable to allocate memory for sound data\n");
    samp->error = TRUE;
    return FALSE;
  }

  sptr = snd;

  if (samplebits == 8) {
    char *bdat = (char *)data;
    for (fx=0; fx<numframes; fx++) {
      bval = (*bdat++) & 0xFF;
      if (!issigned)
	bval ^= 0x80;
      if (bval & 0x80)
	val = (-0x80 + (bval & 0x7F)) * 0x100;
      else
	val = bval * 0x100;
      *sptr++ = val;
      if (numchannels == 1) {
	/* nothing */
      }
      else {
	bval = (*bdat++) & 0xFF;
	if (!issigned)
	  bval ^= 0x80;
	if (bval & 0x80)
	  val = (-0x80 + (bval & 0x7F)) * 0x100;
	else
	  val = bval * 0x100;
	*sptr++ = val;
	if (numchannels > 2) {
	  bdat += (numchannels-2);
	}
      }
    }
  }
  else {
    char *bdat = (char *)data;
    for (fx=0; fx<numframes; fx++) {
      if (isbigend) {
	bval = (*bdat++) & 0xFF;
	bval2 = (*bdat++) & 0xFF;
      }
      else {
	bval2 = (*bdat++) & 0xFF;
	bval = (*bdat++) & 0xFF;
      }
      if (!issigned)
	bval ^= 0x80;
      if (bval & 0x80)
	val = (-0x80 + (bval & 0x7F)) * 0x100;
      else
	val = bval * 0x100;	
      val |= bval2;
      *sptr++ = val;
      if (numchannels == 1) {
	/* nothing */
      }
      else {
	if (isbigend) {
	  bval = (*bdat++) & 0xFF;
	  bval2 = (*bdat++) & 0xFF;
	}
	else {
	  bval2 = (*bdat++) & 0xFF;
	  bval = (*bdat++) & 0xFF;
	}
	if (!issigned)
	  bval ^= 0x80;
	if (bval & 0x80)
	  val = (-0x80 + (bval & 0x7F)) * 0x100;
	else
	  val = bval * 0x100;	
	val |= bval2;
	*sptr++ = val;
	if (numchannels > 2) {
	  bdat += (2 * (numchannels-2));
	}
      }
    }
  }

  if (snd+(numchanout*numframes) != sptr) {
    fprintf(stderr, "Wrong number of samples in data\n");
    samp->error = TRUE;
    return FALSE;
  }

  samp->data = snd;
  samp->numframes = numframes;
  samp->numchannels = numchanout;
  samp->framerate = (double)framerate / (double)audev_get_soundrate();

  if (loopstart >= loopend || loopstart < 0 || loopend < 0) {
    samp->hasloop = FALSE;
    samp->loopstart = 0;
    samp->loopend = 0;
  }
  else {
    samp->hasloop = TRUE;
    samp->loopstart = loopstart;
    samp->loopend = loopend;
  }
  samp->looplen = samp->loopend - samp->loopstart;

  samp->loaded = TRUE;

  return TRUE;
}

