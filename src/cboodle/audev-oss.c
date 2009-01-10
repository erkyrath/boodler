/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_oss extension is distributed under the LGPL.
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
#include <sys/ioctl.h>
#include <fcntl.h>
#include <sys/soundcard.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_DEVNAME "/dev/dsp"
#define DEFAULT_SOUNDRATE (44100)

static char *format_names[] = {
  "8-bit log mu-law",
  "8-bit log A-law",
  "4-bit ADPCM/IMA",
  "8-bit unsigned",
  "16-bit signed little-end",
  "16-bit signed big-end",
  "8-bit signed",
  "16-bit unsigned little-end",
  "16-bit unsigned big-end",
  "MPEG",
  /* Where are S32_LE and S32_BE in this? */
  NULL
};

static int device = -1; /* file descriptor */
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* AFMT_* */
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static struct timeval timeperbuf;
static char *rawbuffer = NULL;
static long *valbuffer = NULL;

/* Some versions of the sound header don't have the _NE constants. We
   don't even try to figure out the endianness. Sorry. */
#ifndef AFMT_S16_NE
#define AFMT_S16_NE (AFMT_S16_LE)
#endif

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ix;
  long lx;
  unsigned int formatlist, tmpflist;
  int channels, format, rate;
  int fragsize;

  if (verbose) {
    printf("Boodler: OSS sound driver.\n");
  }

  if (device >= 0) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  if (!devname)
    devname = DEFAULT_DEVNAME;
  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;

  device = open(devname, O_WRONLY);
  if (device < 0) {
    fprintf(stderr, "Unable to open %s: %s\n", 
      devname, strerror(errno));
    return FALSE;
  }

  if (verbose) {
    printf("Opened %s.\n", devname);
  }

  if (verbose) {
    int versnum = 0;
    printf("Sound header version 0x%lx.\n", (long)SOUND_VERSION);
#ifdef OSS_GETVERSION
    if (ioctl(device, OSS_GETVERSION, &versnum) < 0) {
      printf("Unable to get sound driver version number.\n");
    }
    else {
      printf("Sound driver version 0x%lx.\n", (long)versnum);
    }
#else
    printf("Sound header does not support sound driver version number.\n");
#endif
  }

  if (ioctl(device, SNDCTL_DSP_GETFMTS, &formatlist) < 0) {
    fprintf(stderr, "Unable to query sound-sample formats for %s: %s\n", 
      devname, strerror(errno));
    close(device);
    device = -1;
    return FALSE;
  }

  if (verbose) {
    printf("Sound-sample formats supported in hardware:\n");
    for (ix=0, tmpflist=formatlist; 
	 tmpflist && format_names[ix]; 
	 tmpflist >>= 1, ix++) {
      if (tmpflist & 1)
	printf("  %s\n", format_names[ix]);
    }
  }

  format = 0;
  if (formatlist & AFMT_S16_NE) {
    format = AFMT_S16_NE;
  }
  else if (formatlist & AFMT_S16_BE) {
    format = AFMT_S16_BE;
  }
  else if (formatlist & AFMT_S16_LE) {
    format = AFMT_S16_LE;
  }

  if (format == 0) {
    if (verbose) {
      printf("No 16-bit signed sound format supported in hardware; using an emulated mode.\n");
    }
    format = AFMT_S16_NE;
  }
  
  if (ioctl(device, SNDCTL_DSP_SETFMT, &format) < 0) {
    fprintf(stderr, "Unable to set sound format for %s: %s\n", 
      devname, strerror(errno));
    close(device);
    device = -1;
    return FALSE;
  }

  if (format != AFMT_S16_BE && format != AFMT_S16_LE) {
    fprintf(stderr,
      "Unable to set any 16-bit signed sound format; aborting.\n");
    close(device);
    device = -1;
    return FALSE;
  }

  if (verbose) {
    printf("Set sound format to %s.\n", 
      format_names[(format==AFMT_S16_BE) ? 5 : 4]);
  }

  channels = 2;
  if (ioctl(device, SNDCTL_DSP_CHANNELS, &channels) < 0) {
    fprintf(stderr, "Unable to set channel count for %s: %s\n", 
      devname, strerror(errno));
    close(device);
    device = -1;
    return FALSE;
  }

  if (channels == 2) {
    if (verbose)
      printf("Set stereo mode.\n");
  }
  else if (channels == 1) {
    fprintf(stderr, "Stereo mode not supported; aborting.\n");
    close(device);
    device = -1;
    return FALSE;
    /* 
    if (verbose)
      printf("Stero mode not supported; reverting to mono.\n");
    */
  }
  else {
    fprintf(stderr, "Neither stereo nor mono mode is supported; aborting.\n");
    close(device);
    device = -1;
    return FALSE;
  }

  rate = ratewanted;
  if (ioctl(device, SNDCTL_DSP_SPEED, &rate) < 0) {
    fprintf(stderr, "Unable to set sampling rate for %s: %s\n", 
      devname, strerror(errno));
    close(device);
    device = -1;
    return FALSE;
  }

  if (rate < ratewanted*0.90 || rate > ratewanted*1.10) {
    fprintf(stderr, 
      "Sampling rate fixed at %d fps, which is not close enough to %ld; aborting.\n", 
      rate, ratewanted);
    close(device);
    device = -1;
    return FALSE;
  }

  if (verbose) {
    printf("Set sampling rate to %d fps.\n", rate);
  }

  if (ioctl(device, SNDCTL_DSP_GETBLKSIZE, &fragsize) < 0) {
    fprintf(stderr, "Unable to read buffer measurement for %s: %s\n", 
      devname, strerror(errno));
    close(device);
    device = -1;
    return FALSE;
  }

  if (verbose) {
    printf("Buffer size is %d.\n", fragsize);
  }

  if (verbose) {
    audio_buf_info info;
    if (ioctl(device, SNDCTL_DSP_GETOSPACE, &info) < 0) {
      fprintf(stderr, "Unable to get buffer measurements for %s: %s\n", 
	devname, strerror(errno));
    }
    else {
      printf("%d buffers of %d bytes each; %d buffers available.\n",
	info.fragstotal, info.fragsize, info.fragments);
    }
  }

  sound_rate = rate;
  sound_channels = channels;
  sound_format = format;
  sound_buffersize = fragsize;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);
  timeperbuf.tv_sec = framesperbuf / sound_rate;
  lx = framesperbuf - (timeperbuf.tv_sec * sound_rate);
  timeperbuf.tv_usec = lx * (1 + (1000000 / sound_rate));
  while (timeperbuf.tv_usec >= 1000000) {
    timeperbuf.tv_usec -= 1000000;
    timeperbuf.tv_sec += 1;
  }

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

  if (verbose) {
    printf("Framesperbuf = %ld; timeperbuf = %d.%06d\n",
      framesperbuf, 
      (int)timeperbuf.tv_sec, (int)timeperbuf.tv_usec);
  }

  return TRUE;
}

void audev_close_device()
{
  if (device < 0) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  close(device);
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
  /* struct timeval tv; */
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

    if (sound_format == AFMT_S16_BE) {
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

    /*
    while (1) {
      if (ioctl(device, SNDCTL_DSP_GETOSPACE, &info) < 0) {
	fprintf(stderr, "Unable to get buffer measurements: %s\n", 
	  strerror(errno));
	return FALSE;
      }
      if (info.fragments > min_buffers) {
	break;
      }
      tv = timeperbuf;
      select(0, NULL, NULL, NULL, &tv);
    }
    */

    write(device, rawbuffer, sound_buffersize);    
  }
}

