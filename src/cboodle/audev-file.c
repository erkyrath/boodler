/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_file extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define DEFAULT_FILENAME "boosound.raw"

static FILE *device = NULL;
static int sound_big_endian = 0;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* TRUE for big-endian, FALSE for little */
static long sound_buffersize = 0; /* bytes */
static long maxtime = 0, curtime = 0;

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int channels, format, rate;
  int fragsize;
  extraopt_t *opt;
  double maxsecs = 5.0;
  char endtest[sizeof(unsigned int)];

  if (verbose) {
    printf("Boodler: FILE sound driver.\n");
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  *((unsigned int *)endtest) = ( (unsigned int) ( ('E' << 24) + ('N' << 16) + ('D' << 8) + ('I') ) );
  if (endtest[0] == 'I' && endtest[1] == 'D' && endtest[2] == 'N' && endtest[3] == 'E') {
    sound_big_endian = FALSE;
  }
  else if (endtest[sizeof(unsigned int)-1] == 'I' && endtest[sizeof(unsigned int)-2] == 'D' && endtest[sizeof(unsigned int)-3] == 'N' && endtest[sizeof(unsigned int)-4] == 'E') {
    sound_big_endian = TRUE;
  }
  else {
    fprintf(stderr, "Cannot determine native endianness.\n");
    return FALSE;
  }

  format = -1;

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "end") && opt->val) {
      if (!strcmp(opt->val, "big"))
	format = TRUE;
      else if (!strcmp(opt->val, "little"))
	format = FALSE;
    }
    else if (!strcmp(opt->key, "time") && opt->val) {
      maxsecs = atof(opt->val);
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("Device list: give any writable file as a device name.\n");
    }
  }

  if (format == -1) {
    format = sound_big_endian;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;
  if (!devname) 
    devname = DEFAULT_FILENAME;

  device = fopen(devname, "wb");
  if (!device) {
    fprintf(stderr, "Error opening file %s\n", devname);
    return FALSE;
  }

  if (verbose) {
    printf("Opened file %s.\n", devname);
  }

  rate = ratewanted;
  channels = 2;
  fragsize = 16384;

  if (verbose) {
    printf("%d channels, %d frames per second, 16-bit samples (signed, %s)\n",
      channels, rate, (format?"big-endian":"little-endian"));
  }

  maxtime = (long)(maxsecs * (double)rate);
  curtime = 0;
  if (verbose) {
    printf("%g seconds of output (%ld frames)\n", maxsecs, maxtime);
  }

  sound_rate = rate;
  sound_channels = channels;
  sound_format = format;
  sound_buffersize = fragsize;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);

  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    fclose(device);
    device = NULL;
    return FALSE;    
  }

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;     
  }

  return TRUE;
}

void audev_close_device()
{
  if (device == NULL) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  fclose(device);
  device = NULL;

  if (rawbuffer) {
    free(rawbuffer);
    rawbuffer = NULL;
  }
  if (valbuffer) {
    free(valbuffer);
    valbuffer = NULL;
  }
}

long audev_get_soundrate()
{
  return sound_rate;
}

long audev_get_framesperbuf()
{
  return framesperbuf;
}

int audev_loop(mix_func_t mixfunc, generate_func_t genfunc, void *rock)
{
  char *ptr;
  int ix, res;

  if (!device) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    if (sound_format) {
      for (ix=0, ptr=rawbuffer; ix<samplesperbuf; ix++) {
	long samp = valbuffer[ix];
	if (samp > 0x7FFF)
	  samp = 0x7FFF;
	else if (samp < -0x7FFF)
	  samp = -0x7FFF;
	*ptr++ = ((samp >> 8) & 0xFF);
	*ptr++ = ((samp) & 0xFF);
      }
    }
    else {
      for (ix=0, ptr=rawbuffer; ix<samplesperbuf; ix++) {
	long samp = valbuffer[ix];
	if (samp > 0x7FFF)
	  samp = 0x7FFF;
	else if (samp < -0x7FFF)
	  samp = -0x7FFF;
	*ptr++ = ((samp) & 0xFF);
	*ptr++ = ((samp >> 8) & 0xFF);
      }
    }

    fwrite(rawbuffer, 1, sound_buffersize, device);
    curtime += framesperbuf;
    if (curtime >= maxtime)
      return FALSE;
  }
}

