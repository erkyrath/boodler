/* Boodler: a programmable soundscape tool
   Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   This program is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.

   Vorbis driver contributed by Aaron Griffith.
*/

/*
   For information about the Vorbis encoding library, see
   <http://xiph.org/>.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <math.h>
#include <vorbis/vorbisenc.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define DEFAULT_FILENAME "boosound.ogg"

static FILE *device = NULL;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* TRUE for big-endian, FALSE for little */
static long sound_buffersize = 0; /* bytes */
static long maxtime = 0, curtime = 0;

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

static ogg_stream_state os;
static ogg_page         og;
static ogg_packet       op;
static vorbis_info      vi;
static vorbis_comment   vc;
static vorbis_dsp_state vd;
static vorbis_block     vb;
static int eos=0;

static void audev_vorbis_flush(void);

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ret;
  int channels, format, rate;
  int fragsize;
  extraopt_t *opt;
  double maxsecs = 5.0;
  double quality = 0.5;
  char *title = NULL;

  if (verbose) {
    printf("Boodler: VORBIS sound driver.\n");
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  format = FALSE; /* always little-endian */

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "time") && opt->val) {
      maxsecs = atof(opt->val);
    }
    else if (!strcmp(opt->key, "quality") && opt->val) {
      quality = atof(opt->val);
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
  fragsize = 16384;

  if (verbose) {
    printf("%d channels, %d frames per second, 16-bit samples (signed, %s)\n",
      channels, rate, (format?"big-endian":"little-endian"));
    printf("vorbis VBR encoding quality %f\n", quality);
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
  
  vorbis_info_init(&vi);
  ret = vorbis_encode_init_vbr(&vi, 2, sound_rate, quality);
  if (ret) {
    fprintf(stderr, "Unable to initialize Vorbis encoder.\n");
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }

  /* See <http://xiph.org/vorbis/doc/v-comment.html> */  
  vorbis_comment_init(&vc);
  {
    char commentbuf[256];
    time_t nowtime;
    struct tm *now;

    if (title) {
      strcpy(commentbuf, "Boodler: ");
      strncat(commentbuf, title, 255-strlen(commentbuf));
      vorbis_comment_add_tag(&vc, "TITLE", commentbuf);
    }

    nowtime = time(NULL);
    now = localtime(&nowtime);
    strftime(commentbuf, 255, "%Y-%m-%d (generated)", now);
    vorbis_comment_add_tag(&vc, "DATE", commentbuf);

    vorbis_comment_add_tag(&vc, "ENCODER", "Boodler");
  }
  
  vorbis_analysis_init(&vd, &vi);
  vorbis_block_init(&vd, &vb);
  
  srand(time(NULL));
  ret = ogg_stream_init(&os, rand());
  if (ret) {
    fprintf(stderr, "Unable to initialize Ogg stream.\n");
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    fclose(device);
    device = NULL;
    return FALSE;
  }
  
  {
    ogg_packet header;
    ogg_packet header_comm;
    ogg_packet header_code;

    vorbis_analysis_headerout(&vd, &vc, &header, &header_comm, &header_code);
    ogg_stream_packetin(&os, &header);
    ogg_stream_packetin(&os, &header_comm);
    ogg_stream_packetin(&os, &header_code);
    while (!eos) {
      int result = ogg_stream_flush(&os, &og);
      if (result==0) break;
      fwrite(og.header, 1, og.header_len, device);
      fwrite(og.body, 1, og.body_len, device);
    }
  }

  return TRUE;
}

void audev_close_device()
{
  if (device == NULL) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  vorbis_analysis_wrote(&vd, 0);
  audev_vorbis_flush();
  
  ogg_stream_clear(&os);
  vorbis_block_clear(&vb);
  vorbis_dsp_clear(&vd);
  vorbis_comment_clear(&vc);
  vorbis_info_clear(&vi);

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
  int i, ix, res;

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

    float **buffer = vorbis_analysis_buffer(&vd, sound_buffersize / 4);
    
    for (i = 0; i < sound_buffersize / 4; i++) {
        buffer[0][i] = ((rawbuffer[i*4+1]<<8)|
            (0x00ff&(int)rawbuffer[i*4]))/32768.f;
        buffer[1][i] = ((rawbuffer[i*4+3]<<8)|
            (0x00ff&(int)rawbuffer[i*4+2]))/32768.f;
    }
    
    vorbis_analysis_wrote(&vd,i);
    audev_vorbis_flush();
    
    curtime += framesperbuf;
    if (curtime >= maxtime)
      return FALSE;
  }
}

static void audev_vorbis_flush(void)
{
  while (vorbis_analysis_blockout(&vd, &vb) == 1) {
    vorbis_analysis(&vb, NULL);
    vorbis_bitrate_addblock(&vb);
    
    while (vorbis_bitrate_flushpacket(&vd, &op)) {
      ogg_stream_packetin(&os, &op);
      
      while (!eos) {
        int result = ogg_stream_pageout(&os, &og);
        if (result == 0) break;
        fwrite(og.header, 1, og.header_len, device);
        fwrite(og.body, 1, og.body_len, device);
        if (ogg_page_eos(&og)) eos=1;
      }
    }
  }
}

