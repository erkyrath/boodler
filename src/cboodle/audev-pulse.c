/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_pulse extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/*
   For information about the PulseAudio sound server, see
   <http://www.pulseaudio.org/>.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#include <pulse/simple.h>
#include <pulse/version.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)

static pa_simple *device = NULL;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static pa_sample_format_t sound_format = PA_SAMPLE_S16NE;
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  extraopt_t *opt;
  int channels, rate;
  pa_sample_format_t format;
  int fragsize;
  pa_sample_spec spec;

  if (verbose) {
    printf("Boodler: PulseAudio sound driver.\n");
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;

  rate = ratewanted;
  channels = 2;
  format = PA_SAMPLE_S16NE;
  fragsize = 32768;

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "end") && opt->val) {
      if (!strcmp(opt->val, "big"))
        format = PA_SAMPLE_S16BE;
      else if (!strcmp(opt->val, "little"))
        format = PA_SAMPLE_S16LE;
    }
    else if (!strcmp(opt->key, "buffersize") && opt->val) {
      fragsize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("PULSE driver is unable to list devices.\n");
    }
  }

  bzero(&spec, sizeof(spec));
  spec.format = format;
  spec.channels = channels;
  spec.rate = rate;

  device = pa_simple_new(
    NULL,               /* Use the default server. */
    "Boodler",          /* Our application's name. */
    PA_STREAM_PLAYBACK,
    devname,            /* Pick a device (sink). */
    "Soundscape",       /* Description of our stream. */
    &spec,              /* Our sample format. */
    NULL,               /* Use default channel map. */
    NULL,               /* Use default buffering attributes. */
    NULL                /* Ignore error code. */
  );

  if (!device) {
    fprintf(stderr, "Unable to open Pulse server\n");
    return FALSE;
  }

  if (verbose) {
    printf("PulseAudio library: %s.\n", pa_get_library_version());
    printf("Sample rate is %d fps.\n", (int)spec.rate);
    if (format == PA_SAMPLE_S16BE)
      printf("Samples are 16-bit big-endian.\n");
    else if (format == PA_SAMPLE_S16LE)
      printf("Samples are 16-bit little-endian.\n");
    else
      printf("Samples are unknown-endian.\n");
    printf("Buffer size is %d.\n", fragsize);
  }

  sound_rate = rate;
  sound_channels = channels;
  sound_format = format;
  sound_buffersize = fragsize;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    pa_simple_free(device);
    device = NULL;
    return FALSE;     
  }
  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(valbuffer);
    pa_simple_free(device);
    device = NULL;
    return FALSE;    
  }

  return TRUE;
}

void audev_close_device()
{
  int res;

  if (!device) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  if (pa_simple_drain(device, &res) < 0) {
    fprintf(stderr, "Device drain failed: %d\n", res);
  }

  pa_simple_free(device);
  device = NULL;

  if (valbuffer) {
    free(valbuffer);
    valbuffer = NULL;
  }
  if (rawbuffer) {
    free(rawbuffer);
    rawbuffer = NULL;
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

    if (sound_format == PA_SAMPLE_S16BE) {
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

    if (pa_simple_write(device, rawbuffer, sound_buffersize, &res) < 0) {
      fprintf(stderr, "Device write failed: %d\n", res);
      return FALSE;
    }
  }
}

