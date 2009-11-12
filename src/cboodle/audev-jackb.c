/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_jackb extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/*
   For information about Bio2Jack, see <http://bio2jack.sourceforge.net/>.
   For information about the JACK Audio Connection Kit, see
   <http://jackaudio.org/>.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#include <bio2jack.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define DEFAULT_CLIENTNAME ("boodler")

static int deviceid = 0;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static long sound_buffersize = 0; /* bytes */
static int sound_format = 0; /* 0 small-end, 1 big-end */
static enum JACK_PORT_CONNECTION_MODE connect_mode = CONNECT_NONE;

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

struct timeval sleeptime;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  extraopt_t *opt;
  int channels;
  unsigned long rate;
  int fragsize, format;
  long jbufframes, jbufsize;
  int res;

  if (verbose) {
    printf("Boodler: JackBIO sound driver.\n");
  }

  if (deviceid) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;
  if (!devname) 
    devname = DEFAULT_CLIENTNAME;

  rate = ratewanted;
  channels = 2;
  fragsize = 32768;
  format = 0; /* default to little-endian */

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "end") && opt->val) {
      if (!strcmp(opt->val, "big"))
        format = 1;
      else if (!strcmp(opt->val, "little"))
        format = 0;
    }
    else if (!strcmp(opt->key, "connect") && opt->val) {
      if (!strcmp(opt->val, "none"))
        connect_mode = CONNECT_NONE;
      else if (!strcmp(opt->val, "output"))
        connect_mode = CONNECT_OUTPUT;
      else if (!strcmp(opt->val, "all"))
        connect_mode = CONNECT_ALL;
      else
        printf("JackB connect parameter must be none, output, or all.\n");
    }
    else if (!strcmp(opt->key, "buffersize") && opt->val) {
      fragsize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("JackB driver is unable to list devices.\n");
    }
  }

  JACK_Init();
  JACK_SetPortConnectionMode(connect_mode);
  JACK_SetClientName(devname);

  res = JACK_Open(&deviceid, 16, &rate, 2);
  if (res) {
    fprintf(stderr, "Unable to open JACK connection: error %d\n", res);
    return FALSE;
  }

  jbufsize = JACK_GetBytesFreeSpace(deviceid);
  jbufframes = jbufsize / JACK_GetBytesPerOutputFrame(deviceid);
  if (jbufframes/2 >= rate) {
    sleeptime.tv_sec = 1;
    sleeptime.tv_usec = 0;
  }
  else {
    sleeptime.tv_sec = 0;
    sleeptime.tv_usec = (jbufframes/2) * 1000000 / rate;
  }

  if (verbose) {
    printf("Jack client name is \"%s_...\"\n", devname);
    printf("Sample format is %s-endian.\n", (format ? "big" : "little"));
    printf("Sample rate is %ld fps.\n", rate);
    printf("Boodler buffer size is %d.\n", fragsize);
    printf("Bio2Jack buffer size is %ld (%ld frames).\n", jbufsize, jbufframes);
    switch (connect_mode) {
    case CONNECT_NONE:
      printf("Bio2Jack connect_mode=CONNECT_NONE.\n");
      break;
    case CONNECT_OUTPUT:
      printf("Bio2Jack connect_mode=CONNECT_OUTPUT.\n");
      break;
    case CONNECT_ALL:
      printf("Bio2Jack connect_mode=CONNECT_ALL.\n");
      break;
    default:
      printf("Bio2Jack connect_mode=???.\n");
      break;
    }
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
    JACK_Close(deviceid);
    deviceid = 0;
    return FALSE;     
  }
  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(valbuffer);
    JACK_Close(deviceid);
    deviceid = 0;
    return FALSE;    
  }

  return TRUE;
}

void audev_close_device()
{
  int res;

  res = JACK_Close(deviceid);
  deviceid = 0;

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
  long pos;

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

    pos = 0;

    while (pos < sound_buffersize) {
      long written;
      long towrite = JACK_GetBytesFreeSpace(deviceid);

      if (towrite <= 0) {
        struct timeval tv = sleeptime;
        select(0, 0, 0, 0, &tv);
        continue;
      }

      if (towrite > sound_buffersize-pos)
        towrite = sound_buffersize-pos;

      written = JACK_Write(deviceid, (unsigned char *)rawbuffer + pos, towrite);
      if (written != towrite) {
        fprintf(stderr, "Device write incomplete: %ld of %ld\n", written, towrite);
        return FALSE;
      }

      pos += written;
    }

  }
}

