/* Boodler: a programmable soundscape tool
   Copyright 2007-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_shout extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.

   Shout driver contributed by Aaron Griffith.
*/

/*
   Developed with ShoutLib library version 2.2.2.
   For information about the Vorbis encoding library, see
   <http://xiph.org/>.
   For information about LibShout, see
   <http://www.icecast.org/>.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <math.h>
#include <vorbis/vorbisenc.h>
#include <shout/shout.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)

#define DEFAULT_SERVER "127.0.0.1"
#define DEFAULT_PORT 8000
#define DEFAULT_PROTOCOL SHOUT_PROTOCOL_HTTP
#define DEFAULT_MOUNT "/boodler.ogg"
#define DEFAULT_USER "source"
#define DEFAULT_PASSWORD "hackme"

static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* TRUE for big-endian, FALSE for little */
static long sound_buffersize = 0; /* bytes */

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

static shout_t *shout = NULL;

static void audev_vorbis_flush(void);

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ret;
  int channels, format, rate;
  int fragsize;
  extraopt_t *opt;
  double quality = 0.5;
  
  char* server = DEFAULT_SERVER;
  int port = DEFAULT_PORT;
  int protocol = DEFAULT_PROTOCOL;
  char* mount = DEFAULT_MOUNT;
  char* user = DEFAULT_USER;
  char* password = DEFAULT_PASSWORD;

  if (verbose) {
    printf("Boodler: SHOUT sound driver.\n");
    printf("ShoutLib version: %s\n", shout_version(NULL,NULL,NULL));
  }

  if (shout) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  format = FALSE; /* always little-endian */

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "end") && opt->val) {
      if (!strcmp(opt->val, "big"))
	format = TRUE;
      else if (!strcmp(opt->val, "little"))
	format = FALSE;
    }
    else if (!strcmp(opt->key, "shout-server") && opt->val) {
      server = opt->val;
    }
    else if (!strcmp(opt->key, "shout-port") && opt->val) {
      port = atoi(opt->val);
    }
    else if (!strcmp(opt->key, "shout-mount") && opt->val) {
      mount = opt->val;
    }
    else if (!strcmp(opt->key, "shout-protocol") && !strcmp(opt->val, "http")) {
      protocol = SHOUT_PROTOCOL_HTTP;
    }
    else if (!strcmp(opt->key, "shout-protocol") && !strcmp(opt->val, "xaudiocast")) {
      protocol = SHOUT_PROTOCOL_XAUDIOCAST;
    }
    else if (!strcmp(opt->key, "shout-protocol") && !strcmp(opt->val, "icy")) {
      protocol = SHOUT_PROTOCOL_ICY;
    }
    else if (!strcmp(opt->key, "shout-user") && opt->val) {
      user = opt->val;
    }
    else if (!strcmp(opt->key, "shout-password") && opt->val) {
      password = opt->val;
    }
    else if (!strcmp(opt->key, "quality") && opt->val) {
      quality = atof(opt->val);
    }
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;
  rate = ratewanted;

  channels = 2;
  fragsize = 16384;

  if (verbose) {
    printf("%d channels, %d frames per second, 16-bit samples (signed, %s)\n",
      channels, rate, (format?"big-endian":"little-endian"));
    printf("vorbis VBR encoding quality %f\n", quality);
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
    return FALSE;    
  }

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
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
    return FALSE;
  }
  
  shout_init();
  
  if (!(shout = shout_new())) {
    fprintf(stderr, "Could not allocate shout_t\n");
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_host(shout, server) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting hostname: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_protocol(shout, protocol) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting protocol: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_port(shout, port) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting port: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_password(shout, password) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting password: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_mount(shout, mount) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting mount: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_set_user(shout, user) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting user: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }

  if (shout_set_format(shout, SHOUT_FORMAT_OGG) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting format: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  if (shout_open(shout) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error connecting to server: %s\n", shout_get_error(shout));
    free(valbuffer);
    valbuffer = NULL;
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;
  }
  
  vorbis_comment_init(&vc);
  vorbis_comment_add_tag(&vc, "ENCODER", "Boodler");
  //vorbis_comment_add_tag(&vc, "SERVER_NAME", "Boodler");
  //vorbis_comment_add_tag(&vc, "SERVER_DESCRIPTION", "BoodlerDDD");
  
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
      shout_send(shout, og.header, og.header_len);
      shout_send(shout, og.body, og.body_len);
    }
  }

  return TRUE;
}

void audev_close_device()
{
  if (!shout) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  shout_close(shout);
  shout_free(shout);
  shout = NULL;
  shout_shutdown();
  
  vorbis_analysis_wrote(&vd, 0);
  audev_vorbis_flush();
  
  ogg_stream_clear(&os);
  vorbis_block_clear(&vb);
  vorbis_dsp_clear(&vd);
  vorbis_comment_clear(&vc);
  vorbis_info_clear(&vi);

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

  if (!shout) {
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
        shout_send(shout, og.header, og.header_len);
        shout_send(shout, og.body, og.body_len);
        if (ogg_page_eos(&og)) eos=1;
      }
      shout_sync(shout);
    }
  }
}

