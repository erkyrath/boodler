/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_alsa extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/*
   Developed with ALSA library version 1.0.14a.
   For information about ALSA, see <http://alsa-project.org/>.
   Documentation: <http://alsa-project.org/alsa-doc/alsa-lib/>
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <alsa/asoundlib.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define DEFAULT_DEVICENAME "default"

static snd_pcm_t *device = NULL;
static unsigned int sound_rate = 0; /* frames per second */
static snd_pcm_format_t sound_format = 0; /* SND_PCM_FORMAT_* */
static long sound_buffersize = 16384; /* bytes */
static snd_pcm_uframes_t sound_periodsize = 0; /* frames */
static snd_pcm_uframes_t sound_hwbuffersize = 16384; /* frames */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int res, count;
  int native_big_endian = 0;
  int channels, format;
  extraopt_t *opt;
  char endtest[sizeof(unsigned int)];

  snd_pcm_hw_params_t *params = NULL;

  if (verbose) {
    printf("Boodler: ALSA sound driver.\n");
    printf("ALSA header version %s, library version %s\n",
      SND_LIB_VERSION_STR, snd_asoundlib_version());
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  *((unsigned int *)endtest) = ( (unsigned int) ( ('E' << 24) + ('N' << 16) + ('D' << 8) + ('I') ) );
  if (endtest[0] == 'I' && endtest[1] == 'D' && endtest[2] == 'N' && endtest[3] == 'E') {
    native_big_endian = FALSE;
  }
  else if (endtest[sizeof(unsigned int)-1] == 'I' && endtest[sizeof(unsigned int)-2] == 'D' && endtest[sizeof(unsigned int)-3] == 'N' && endtest[sizeof(unsigned int)-4] == 'E') {
    native_big_endian = TRUE;
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
    else if (!strcmp(opt->key, "periodsize") && opt->val) {
      sound_periodsize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "hwbuffer") && opt->val) {
      sound_hwbuffersize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "buffersize") && opt->val) {
      sound_buffersize = atol(opt->val) * 4;
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("ALSA driver is unable to list devices.\n");
      /* Check aplay.c: snd_device_name_hint(), snd_device_name_get_hint() */
    }
  }

  if (format == -1) {
    format = native_big_endian;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;
  if (!devname) 
    devname = DEFAULT_DEVICENAME;

  if (format)
    sound_format = SND_PCM_FORMAT_S16_BE;
  else
    sound_format = SND_PCM_FORMAT_S16_LE;

  /* open in blocking mode */
  res = snd_pcm_open(&device, devname, SND_PCM_STREAM_PLAYBACK, 0);
  if (res) {
    fprintf(stderr, "Error opening ALSA device: %s\n", snd_strerror(res));
    return FALSE;
  }

  if (verbose) {
    snd_pcm_info_t *info = NULL;

    res = snd_pcm_info_malloc(&info);
    if (!res) {
      res = snd_pcm_info(device, info);
      if (!res) {
	printf("PCM device \"%s\", name \"%s\"\n", 
	  snd_pcm_info_get_id(info), snd_pcm_info_get_name(info));
      }
      snd_pcm_info_free(info);
    }

    if (res) {
      printf("Unable to get PCM device info: %s\n", snd_strerror(res));
    }
  }

  channels = 2;

  res = snd_pcm_hw_params_malloc(&params);
  if (res) {
    fprintf(stderr, "Error allocating hardware parameters: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_any(device, params);
  if (res) {
    fprintf(stderr, "Error setting up hardware parameters: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_set_access(device, params, SND_PCM_ACCESS_RW_INTERLEAVED);
  if (res) {
    fprintf(stderr, "Error setting write-interleaved access: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_set_format(device, params, sound_format);
  if (res) {
    fprintf(stderr, "Error setting sample format: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_set_channels(device, params, channels);
  if (res) {
    fprintf(stderr, "Error setting two channels: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  sound_rate = ratewanted;

  res = snd_pcm_hw_params_set_rate_near(device, params, &sound_rate, NULL);
  if (res) {
    fprintf(stderr, "Error setting sample rate: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  if (sound_periodsize != 0) {
    res = snd_pcm_hw_params_set_period_size_near(device, params, &sound_periodsize, NULL);
    if (res) {
      fprintf(stderr, "Error setting sample period size: %s\n",
	snd_strerror(res));
      snd_pcm_close(device);
      device = NULL;
      return FALSE;
    }
  }

  if (sound_hwbuffersize != 0) {
    res = snd_pcm_hw_params_set_buffer_size_near(device, params, &sound_hwbuffersize);
    if (res) {
      fprintf(stderr, "Error setting hardware buffer size: %s\n",
	snd_strerror(res));
      snd_pcm_close(device);
      device = NULL;
      return FALSE;
    }
  }

  /* Set up the parameters. */

  res = snd_pcm_hw_params(device, params);
  if (res) {
    fprintf(stderr, "Error using hardware parameters: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  /* Now read them back in, just to be sure. */

  res = snd_pcm_hw_params_current(device, params);
  if (res) {
    fprintf(stderr, "Error fetching hardware parameters: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_get_rate(params, &sound_rate, NULL);
  if (res) {
    fprintf(stderr, "Error fetching hardware rate: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_get_period_size(params, &sound_periodsize, NULL);
  if (res) {
    fprintf(stderr, "Error fetching hardware period size: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  res = snd_pcm_hw_params_get_buffer_size(params, &sound_hwbuffersize);
  if (res) {
    fprintf(stderr, "Error fetching hardware buffer size: %s\n",
      snd_strerror(res));
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  /* Ensure that sound_buffersize is a multiple of the periodsize*4.
     (Because we have 4 bytes to a frame, and sound_buffersize is in
     bytes.)
  */

  count = sound_buffersize / (4*sound_periodsize);
  if (count <= 0)
    count = 1;
  sound_buffersize = count * (4*sound_periodsize);

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * channels);

  if (verbose) {
    printf("Sample rate %d\n", sound_rate);
    printf("Sample format %s (16-bit signed %s-endian)\n", 
      snd_pcm_format_name(sound_format),
      ((sound_format==SND_PCM_FORMAT_S16_BE) ? "big" : "little"));
    printf("Boodler buffer %ld frames\n", framesperbuf);
    printf("Hardware buffer %ld frames (period %ld frames)\n",
      (long)sound_hwbuffersize, (long)sound_periodsize);
  }

  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    snd_pcm_close(device);
    device = NULL;
    return FALSE;    
  }

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    snd_pcm_close(device);
    device = NULL;
    return FALSE;     
  }

  res = snd_pcm_prepare(device);
  if (res) {
    fprintf(stderr, "Error preparing device: %s\n",
      snd_strerror(res));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  snd_pcm_hw_params_free(params);

  return TRUE;
}

void audev_close_device()
{
  int res;

  if (device == NULL) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  res = snd_pcm_drain(device);
  if (res) {
    fprintf(stderr, "Error draining device: %s\n", snd_strerror(res));
  }

  res = snd_pcm_close(device);
  if (res) {
    fprintf(stderr, "Error closing device: %s\n", snd_strerror(res));
  }
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
  return (long)sound_rate;
}

long audev_get_framesperbuf()
{
  return framesperbuf;
}

int audev_loop(mix_func_t mixfunc, generate_func_t genfunc, void *rock)
{
  char *ptr;
  int ix;
  snd_pcm_sframes_t res;
  snd_pcm_uframes_t written, towrite;

  if (!device) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    if (sound_format == SND_PCM_FORMAT_S16_BE) {
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

    /* Now write out the rawbuffer, in chunks of (at most) periodsize
       frames. */

    written = 0; /* frames */

    while (written < framesperbuf) {
      towrite = framesperbuf - written;
      if (towrite > sound_periodsize)
	towrite = sound_periodsize;

      ptr = rawbuffer + (4*written); /* 4 bytes per frame */

      res = snd_pcm_writei(device, ptr, towrite);
      if (res > 0) {
	if (res != towrite) {
	  fprintf(stderr, "Incomplete sound write: %ld frames short\n",
	    (long)towrite - (long)res);
	}
	written += res;
	continue;
      }
      if (res == 0) {
	fprintf(stderr, "Error: no frames written!\n");
	return FALSE;
      }

      /* (res < 0) */

      if (res == -EPIPE) {
	/* When an underflow occurs, we have to call prepare() again. */
	res = snd_pcm_prepare(device);
	if (res) {
	  fprintf(stderr, "Error repreparing: %s\n", snd_strerror(res));
	  return FALSE;
	}

	/* We also re-do the writei(), with the same data as before,
	   although I haven't seen a clear explanation of why this
	   makes sense. To accomplish this, just continue without
	   incrementing written. */
	continue;
      }

      fprintf(stderr, "Error writing sound: %s\n", snd_strerror(res));
      return FALSE;
    }
  }
}

