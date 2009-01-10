/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_esd extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <esd.h>

#include "common.h"
#include "audev.h"

static int device = -1; /* file descriptor */
static int sound_big_endian = 0;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

static void print_esd_format(FILE *out, esd_format_t format);

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int rate, format;
  char endtest[sizeof(unsigned int)];
  esd_server_info_t *info;

  if (verbose) {
    printf("Boodler: ESD sound driver.\n");
  }

  if (device >= 0) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  *((unsigned int *)endtest) = ESD_ENDIAN_KEY;
  if (endtest[0] == 'N' && endtest[1] == 'D' && endtest[2] == 'N' && endtest[3] == 'E') {
    sound_big_endian = FALSE;
  }
  else if (endtest[sizeof(unsigned int)-1] == 'N' && endtest[sizeof(unsigned int)-2] == 'D' && endtest[sizeof(unsigned int)-3] == 'N' && endtest[sizeof(unsigned int)-4] == 'E') {
    sound_big_endian = TRUE;
  }
  else {
    fprintf(stderr, "Cannot determine endianness.\n");
    return FALSE;
  }

  rate = ratewanted;
  if (!rate)
    rate = ESD_DEFAULT_RATE;

  format = (ESD_BITS16 | ESD_STEREO | ESD_STREAM | ESD_PLAY);

  device = esd_play_stream_fallback(format, rate, devname, "boodler");

  if (device <= 0) {
    device = -1;
    fprintf(stderr, "Unable to open ESD connection.\n");
    return FALSE;
  }

  if (verbose) {
    printf("Opened ESD connection to %s.\n", (devname ? devname : "localhost"));
    printf("Connection rate %d, format ", rate);
    print_esd_format(stdout, format);
    printf("\n");
  }

  /* This freezes up for some reason. Bah. */
  if (verbose && FALSE) {
    info = esd_get_server_info(device);
    printf("ESD server version %d, format %d, rate %d\n", info->version, info->format, info->rate);
    esd_free_server_info(info);
  }

  sound_rate = rate;
  sound_channels = 2;
  sound_buffersize = ESD_BUF_SIZE / 4;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);

  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    close(device);
    device = -1;
    return FALSE;    
  }

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    close(device);
    device = -1;
    return FALSE;     
  }

  return TRUE;
}

static void print_esd_format(FILE *out, esd_format_t format)
{
  int val;
  int isstream = FALSE;
  int issample = FALSE;

  val = (format & ESD_MASK_BITS);
  switch (val) {
  case ESD_BITS8:
    fprintf(out, "8-bit");
    break;
  case ESD_BITS16:
    fprintf(out, "16-bit");
    break;
  default:
    fprintf(out, "?-bit");
    break;
  }

  fprintf(out, " ");

  val = (format & ESD_MASK_CHAN);
  switch (val) {
  case ESD_MONO:
    fprintf(out, "mono");
    break;
  case ESD_STEREO:
    fprintf(out, "stereo");
    break;
  default:
    fprintf(out, "?-channel");
    break;
  }

  fprintf(out, " ");

  val = (format & ESD_MASK_MODE);
  switch (val) {
  case ESD_STREAM:
    fprintf(out, "stream");
    isstream = TRUE;
    break;
  case ESD_SAMPLE:
    fprintf(out, "sample");
    issample = TRUE;
    break;
  case ESD_ADPCM:
    fprintf(out, "adpcm");
    break;
  default:
    fprintf(out, "?-mode");
    break;
  }

  fprintf(out, " ");

  val = (format & ESD_MASK_FUNC);
  if (isstream) {
    switch (val) {
    case ESD_PLAY:
      fprintf(out, "play");
      break;
    case ESD_MONITOR:
      fprintf(out, "monitor");
      break;
    case ESD_RECORD:
      fprintf(out, "record");
      break;
    default:
      fprintf(out, "?-func");
      break;
    }
  }
  if (issample) {
    switch (val) {
    case ESD_PLAY:
      fprintf(out, "play");
      break;
    case ESD_STOP:
      fprintf(out, "stop");
      break;
    case ESD_LOOP:
      fprintf(out, "loop");
      break;
    default:
      fprintf(out, "?-func");
      break;
    }
  }

  fprintf(out, " [0x%04x]", (int)format);
}

void audev_close_device()
{
  if (device < 0) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  esd_close(device);
  device = -1;

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

  if (device < 0) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    if (sound_big_endian) {
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

    write(device, rawbuffer, sound_buffersize);    
  }
}

