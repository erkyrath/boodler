/* Boodler: a programmable soundscape tool
   Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_lame extension is distributed under the GPL.
   See the GPL document, or the above URL, for details.
*/

/*
   Developed with LAME library version 3.93.
   For information about the LAME encoding library, see
   <http://lame.sourceforge.net/>.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <lame/lame.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define DEFAULT_FILENAME "boosound.mp3"

static FILE *device = NULL;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static long maxtime = 0, curtime = 0;

static long samplesperbuf = 0;
static long framesperbuf = 0;
static long outbuffersize = 0;

static short *rawbuffer = NULL;
static long *valbuffer = NULL;
static unsigned char *outbuffer = NULL;

static lame_global_flags *lame = NULL;

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ret;
  int channels, rate;
  int fragsize;
  extraopt_t *opt;
  double maxsecs = 5.0;
  char *title = NULL;

  int vbr_fast = FALSE;
  int vbr_quality = 2;
  int abr_rate = 0;
  int haste = -1;

  if (verbose) {
    printf("Boodler: LAME sound driver.\n");
    printf("LAME library version: %s\n", get_lame_version());
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "time") && opt->val) {
      maxsecs = atof(opt->val);
    }
    else if (!strcmp(opt->key, "fast")) {
      vbr_fast = TRUE;
    }
    else if (!strcmp(opt->key, "haste") && opt->val) {
      haste = atoi(opt->val);
    }
    else if (!strcmp(opt->key, "quality") && opt->val) {
      vbr_quality = atoi(opt->val);
    }
    else if (!strcmp(opt->key, "abr") && !opt->val) {
      abr_rate = 160;
    }
    else if (!strcmp(opt->key, "abr") && opt->val) {
      abr_rate = atoi(opt->val);
      if (abr_rate < 8)
	abr_rate = 8;
      if (abr_rate > 320)
	abr_rate = 320;
    }
    else if (!strcmp(opt->key, "title") && opt->val) {
      title = opt->val;
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("Device list: give any writable file as a device name.\n");
    }
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
  fragsize = 16384; /* in samples */

  if (verbose) {
    printf("%d channels, %d frames per second, 16-bit samples (signed)\n",
      channels, rate);
  }

  maxtime = (long)(maxsecs * (double)rate);
  curtime = 0;
  if (verbose) {
    printf("%g seconds of output (%ld frames)\n", maxsecs, maxtime);
  }

  sound_rate = rate;
  sound_channels = channels;

  samplesperbuf = fragsize;
  framesperbuf = fragsize / (sound_channels);

  /* rawbuffer is not actually organized in frames -- it's not
     interleaved. So framesperbuf is really samplesperchannel. (Which
     is the same number, anyhow.) */

  rawbuffer = (short *)malloc(samplesperbuf * sizeof(short));
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

  outbuffersize = framesperbuf * 2 + 7200;
  outbuffer = (unsigned char *)malloc(outbuffersize);
  if (!outbuffer) {
    fprintf(stderr, "Unable to allocate output buffer.\n");
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }
  
  lame = lame_init();
  if (!lame) {
    fprintf(stderr, "Unable to initialize LAME.\n");
    free(outbuffer);
    outbuffer = NULL;
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }
  
  ret = lame_set_in_samplerate(lame, sound_rate);
  if (ret) {
    fprintf(stderr, "Unable to set sample rate.\n");
    lame_close(lame);
    lame = NULL;
    free(outbuffer);
    outbuffer = NULL;
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }

  if (!abr_rate) {
    vbr_mode mode = vbr_rh;
    if (vbr_fast)
      mode = vbr_mtrh;

    ret = lame_set_VBR(lame, mode);
    if (ret) {
      fprintf(stderr, "Unable to set VBR mode.\n");
      lame_close(lame);
      lame = NULL;
      free(outbuffer);
      outbuffer = NULL;
      free(valbuffer);
      valbuffer = NULL;
      free(rawbuffer);
      rawbuffer = NULL;
      fclose(device);
      device = NULL;
      return FALSE;
    }

    ret = lame_set_VBR_q(lame, vbr_quality);
    if (ret) {
      fprintf(stderr, "Unable to set VBR quality.\n");
      lame_close(lame);
      lame = NULL;
      free(outbuffer);
      outbuffer = NULL;
      free(valbuffer);
      valbuffer = NULL;
      free(rawbuffer);
      rawbuffer = NULL;
      fclose(device);
      device = NULL;
      return FALSE;
    }
  }
  else {
    ret = lame_set_VBR(lame, vbr_abr);
    if (ret) {
      fprintf(stderr, "Unable to set ABR mode.\n");
      lame_close(lame);
      lame = NULL;
      free(outbuffer);
      outbuffer = NULL;
      free(valbuffer);
      valbuffer = NULL;
      free(rawbuffer);
      rawbuffer = NULL;
      fclose(device);
      device = NULL;
      return FALSE;
    }

    ret = lame_set_VBR_mean_bitrate_kbps(lame, abr_rate);
    if (ret) {
      fprintf(stderr, "Unable to set ABR rate.\n");
      lame_close(lame);
      lame = NULL;
      free(outbuffer);
      outbuffer = NULL;
      free(valbuffer);
      valbuffer = NULL;
      free(rawbuffer);
      rawbuffer = NULL;
      fclose(device);
      device = NULL;
      return FALSE;
    }
  }

  if (haste >= 0) {
    ret = lame_set_quality(lame, haste);
    if (ret) {
      fprintf(stderr, "Unable to set encoding haste.\n");
      lame_close(lame);
      lame = NULL;
      free(outbuffer);
      outbuffer = NULL;
      free(valbuffer);
      valbuffer = NULL;
      free(rawbuffer);
      rawbuffer = NULL;
      fclose(device);
      device = NULL;
      return FALSE;
    }
  }

  {
    char commentbuf[256];
    id3tag_v2_only(lame);

    id3tag_set_comment(lame, "Generated by Boodler.");

    if (title) {
      strcpy(commentbuf, "Boodler: ");
      strncat(commentbuf, title, 255-strlen(commentbuf));
      id3tag_set_title(lame, commentbuf);
    }

    id3tag_set_genre(lame, "12");
  }

  ret = lame_init_params(lame);
  if (ret) {
    fprintf(stderr, "Unable to initialize parameters.\n");
    lame_close(lame);
    lame = NULL;
    free(outbuffer);
    outbuffer = NULL;
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }

  if (verbose) {
    vbr_mode mode;

    printf("LAME settings: rate %d, encoding haste %d, %d channels, ratio %f\n", 
      lame_get_in_samplerate(lame),
      lame_get_quality(lame),
      lame_get_num_channels(lame),
      lame_get_compression_ratio(lame));

    mode = lame_get_VBR(lame);
    switch (mode) {
      case vbr_rh: 
	printf("VBR, quality %d\n", lame_get_VBR_q(lame));
	break;
      case vbr_mtrh: 
	printf("VBR (fast), quality %d\n", lame_get_VBR_q(lame));
	break;
      case vbr_abr: 
	printf("ABR, %d kbps\n", lame_get_VBR_mean_bitrate_kbps(lame));
	break;
      case vbr_off: 
	printf("CBR, %d kbps\n", lame_get_brate(lame));
	break;
      default: printf("Unknown compression mode\n");
    }
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

  res = lame_encode_flush(lame, outbuffer, outbuffersize);
  if (res < 0) {
    fprintf(stderr, "Encoding error on flush: %d\n", res);
  }
  else {
    if (res > 0)
      fwrite(outbuffer, 1, res, device);
  }

  fclose(device);
  device = NULL;

  res = lame_close(lame);
  lame = NULL;
  if (res) {
    fprintf(stderr, "Unable to close LAME\n");
  }

  if (rawbuffer) {
    free(rawbuffer);
    rawbuffer = NULL;
  }
  if (valbuffer) {
    free(valbuffer);
    valbuffer = NULL;
  }
  if (outbuffer) {
    free(outbuffer);
    outbuffer = NULL;
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
  short *ptrleft, *ptrright;
  int ix, res;

  if (!device) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    ptrleft = rawbuffer;
    ptrright = rawbuffer + framesperbuf;

    for (ix=0; ix<samplesperbuf; ix+=2) {
      long samp;

      samp = valbuffer[ix];
      if (samp > 0x7FFF)
	samp = 0x7FFF;
      else if (samp < -0x7FFF)
	samp = -0x7FFF;
      *ptrleft++ = samp;

      samp = valbuffer[ix+1];
      if (samp > 0x7FFF)
	samp = 0x7FFF;
      else if (samp < -0x7FFF)
	samp = -0x7FFF;
      *ptrright++ = samp;
    }

    res = lame_encode_buffer(lame, rawbuffer, rawbuffer + framesperbuf,
      framesperbuf, outbuffer, outbuffersize);
    if (res < 0) {
      fprintf(stderr, "Encoding error: %d\n", res);
      return FALSE;
    }

    if (res > 0)
      fwrite(outbuffer, 1, res, device);
    
    curtime += framesperbuf;
    if (curtime >= maxtime)
      return FALSE;
  }
}
