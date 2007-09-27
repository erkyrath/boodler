/* Boodler: a programmable soundscape tool
   Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
   <http://eblong.com/zarf/boodler/>
   The cboodle_alsa extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/*
   Developed with ALSA library version 1.0.14a.
   For information about ALSA, see <http://alsa-project.org/>.
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
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int res;
  int native_big_endian = 0;
  int channels, format;
  extraopt_t *opt;
  char endtest[sizeof(unsigned int)];

  snd_pcm_hw_params_t *params = NULL;

  if (verbose) {
    printf("Boodler: ALSA sound driver.\n");
    printf("ALSA header version: %s\n", SND_LIB_VERSION_STR);
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
    else if (!strcmp(opt->key, "listdevices")) {
      printf("ALSA driver is unable to list devices.\n");
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

  if (verbose) {
    printf("Sample rate %d\n", sound_rate);
    printf("Sample format %s (16-bit signed %s-endian)\n", 
      snd_pcm_format_name(sound_format),
      ((sound_format==SND_PCM_FORMAT_S16_BE) ? "big" : "little"));
  }

  sound_buffersize = 32768; /* bytes */

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * channels);

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

  res = snd_pcm_hw_params(device, params);
  if (res) {
    fprintf(stderr, "Error using hardware parameters: %s\n",
      snd_strerror(res));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    snd_pcm_close(device);
    device = NULL;
    return FALSE;
  }

  //### read and check all the values?
  printf("Framesperbuf: %ld\n", framesperbuf);

  res = snd_pcm_hw_params_current(device, params);
  if (res) {
    fprintf(stderr, "Error fetching hardware parameters: %s\n",
      snd_strerror(res));
  }
  else {
    unsigned int gotrate;
    snd_pcm_uframes_t gotframes;
    unsigned int gotcount;

    res = snd_pcm_hw_params_get_rate(params, &gotrate, NULL);
    if (res)
      fprintf(stderr, "Error fetching rate: %s\n",
	snd_strerror(res));
    else
      printf("Found rate: %d\n", gotrate);

    res = snd_pcm_hw_params_get_period_size(params, &gotframes, NULL);
    if (res)
      fprintf(stderr, "Error fetching frames: %s\n",
	snd_strerror(res));
    else
      printf("Found frames: %d\n", (int)gotframes);

    res = snd_pcm_hw_params_get_periods(params, &gotcount, NULL);
    if (res)
      fprintf(stderr, "Error fetching count: %s\n",
	snd_strerror(res));
    else
      printf("Found count: %d\n", gotcount);
  }
  //###

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
  int ix, res;
  snd_pcm_sframes_t written;

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

    written = snd_pcm_writei(device, rawbuffer, framesperbuf); 
    if (written < 0) {
      if (written == -EPIPE) {
	fprintf(stderr, "### Underflow!\n");
	res = snd_pcm_prepare(device);
	if (res) {
	  fprintf(stderr, "Error repreparing: %s\n", snd_strerror(res));
	  return FALSE;
	}
	written = snd_pcm_writei(device, rawbuffer, framesperbuf);
	if (written < 0) {
	  fprintf(stderr, "Error re-writing: %s\n", snd_strerror(written));
	  return FALSE;
	}
      }
      else {
	fprintf(stderr, "Error writing sound: %s\n", snd_strerror(written));
	return FALSE;
      }
    }
    else if (written != framesperbuf) {
      fprintf(stderr, "Incomplete sound write: %ld frames short\n",
        framesperbuf - (long)written);
    }
  }
}

