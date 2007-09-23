/* Boodler: a programmable soundscape tool
   Copyright 2002-7 by Andrew Plotkin <erkyrath@eblong.com>
   <http://eblong.com/zarf/boodler/>
   The cboodle_alsa extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/* This version of the file is written to version 0.5 of the ALSA API.
   (That's old -- circa 2001.)
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <sys/asoundlib.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)

static snd_pcm_t *device = NULL;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* SND_PCM_SFMT_* */
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ix, res;
  int alsacard, alsadevice;
  long lx;
  unsigned int formatlist, tmpflist;
  int channels, format, rate;
  int fragsize;

  if (verbose) {
    printf("Boodler: ALSA sound driver.\n");
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;

  /* Grab card/device info from devname? */

  alsacard = snd_defaults_pcm_card();
  alsadevice = snd_defaults_pcm_device();

  res = snd_pcm_open(&device, alsacard, alsadevice, 
    SND_PCM_OPEN_PLAYBACK);
  if (res) {
    fprintf(stderr, "Error opening ALSA device: %s\n", snd_strerror(res));
    return FALSE;
  }

  if (verbose) {
    printf("Opened ALSA card %d, device %d.\n", alsacard, alsadevice);
  }

  if (verbose) {
    snd_pcm_info_t info;
    printf("ALSA header version %s.\n", SND_LIB_VERSION_STR);
    res = snd_pcm_info(device, &info);
    if (res) {
      printf("Unable to get PCM device info.\n");
    }
    else {
      printf("PCM device \"%s\", name \"%s\"\n", info.id, info.name);
    }
  }

  format = -1;
  channels = 2;

  {
    snd_pcm_channel_info_t info;

    info.channel = SND_PCM_CHANNEL_PLAYBACK;

    res = snd_pcm_channel_info(device, &info);
    if (res) {
      fprintf(stderr, "Error getting channel info: %s\n", snd_strerror(res));
      return FALSE;
    }

    if (verbose) {
      printf("Native channel info:\n");
      printf("  formats = 0x%x, rates = 0x%x, min_rate = %d, max_rate = %d\n",
        info.formats, info.rates, info.min_rate, info.max_rate);
      printf("  min_fragment = %d, max_fragment = %d\n", 
        info.min_fragment_size, info.max_fragment_size);
    }

    fragsize = info.max_fragment_size;
    if (verbose) {
      printf("Choosing fragment size %d.\n", fragsize);
    }

    if (info.formats & SND_PCM_FMT_S16_BE) {
      format = SND_PCM_SFMT_S16_BE;
    }
    else if (info.formats & SND_PCM_FMT_S16_LE) {
      format = SND_PCM_SFMT_S16_LE;
    }
    if (verbose) {
      if (format == -1) 
        printf("No 16-bit signed format supported natively...\n");
      else
        printf("Native support for %s\n", snd_pcm_get_format_name(format));
    }
  }

  {
    snd_pcm_channel_info_t info;

    info.channel = SND_PCM_CHANNEL_PLAYBACK;

    res = snd_pcm_plugin_info(device, &info);
    if (res) {
      fprintf(stderr, "Error getting channel plugin info: %s\n", snd_strerror(res));
      return FALSE;
    }

    if (verbose) {
      printf("Plugin channel info:\n");
      printf("  formats = 0x%x, rates = 0x%x, min_rate = %d, max_rate = %d\n",
        info.formats, info.rates, info.min_rate, info.max_rate);
      printf("  min_fragment = %d, max_fragment = %d\n", 
        info.min_fragment_size, info.max_fragment_size);
    }

    if (format == -1) {
      if (info.formats & SND_PCM_FMT_S16_BE) {
        format = SND_PCM_SFMT_S16_BE;
      }
      else if (info.formats & SND_PCM_FMT_S16_LE) {
        format = SND_PCM_SFMT_S16_LE;
      }
      if (verbose) {
        if (format == -1) 
          printf("No 16-bit signed format supported in plugin...\n");
        else
          printf("Plugin support for %s\n", snd_pcm_get_format_name(format));
      }
    }

    if (ratewanted < info.min_rate) {
      rate = info.min_rate;
    }
    else if (ratewanted > info.max_rate) {
      rate = info.max_rate;
    }
    else {
      rate = ratewanted;
    }

    if (verbose) {
      printf("Choosing rate %d.\n", rate);
    }
  }

  if (format == -1) {
    fprintf(stderr, "Unable find acceptable sample format.\n");
    return FALSE;
  }

  {
    snd_pcm_channel_params_t params;

    memset(&params, 0, sizeof(params));
    params.channel = SND_PCM_CHANNEL_PLAYBACK;
    params.mode = SND_PCM_MODE_BLOCK;
    params.format.interleave = 1;
    params.format.format = format;
    params.format.rate = rate;
    params.format.voices = 2;
    params.start_mode = SND_PCM_START_DATA;
    params.stop_mode = SND_PCM_STOP_STOP;
    params.buf.block.frag_size = fragsize;
    params.buf.block.frags_min = 1;
    /*params.buf.block.frags_max = ###;*/

    res = snd_pcm_plugin_params(device, &params);
    if (res) {
      fprintf(stderr, "Error setting plugin parameters: %s\n", snd_strerror(res));
      return FALSE;
    }
  }

  res = snd_pcm_plugin_prepare(device, SND_PCM_CHANNEL_PLAYBACK);
  if (res) {
    fprintf(stderr, "Error preparing plugin: %s\n", snd_strerror(res));
    return FALSE;
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

  return TRUE;
}

void audev_close_device()
{
  int res;

  if (device == NULL) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  res = snd_pcm_channel_flush(device, SND_PCM_CHANNEL_PLAYBACK);
  if (res) {
    fprintf(stderr, "Error flushing device: %s\n", snd_strerror(res));
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
  ssize_t written;

  if (!device) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    if (sound_format == SND_PCM_SFMT_S16_BE) {
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

    written = snd_pcm_plugin_write(device, rawbuffer, sound_buffersize); 
    if (written != sound_buffersize) {
      if (written < 0) {
        fprintf(stderr, "Error writing sound: %s\n", snd_strerror(written));
      }
      else {
        fprintf(stderr, "Incomplete sound write: %ld bytes short\n",
          sound_buffersize - (long)written);
      }
    }
  }
}

