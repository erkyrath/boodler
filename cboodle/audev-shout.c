/* Boodler: a programmable soundscape tool
   Copyright 2002 by Andrew Plotkin <erkyrath@eblong.com>
   <http://www.eblong.com/zarf/boodler/>
   This program is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
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

static FILE* device = NULL;
static int sound_big_endian = 0;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* TRUE for big-endian, FALSE for little */
static long sound_buffersize = 0; /* bytes */
static long maxtime = 0, curtime = 0;

static long samplesperbuf = 0;
static long framesperbuf = 0;

static char *rawbuffer = NULL;
static long *valbuffer = NULL;

ogg_stream_state os;
ogg_page         og;
ogg_packet       op;
vorbis_info      vi;
vorbis_comment   vc;
vorbis_dsp_state vd;
vorbis_block     vb;
int eos=0,ret;
int i, founddata;

shout_t *shout;

void audev_vorbis_flush(void);

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ix, res;
  long lx;
  unsigned int formatlist, tmpflist;
  int channels, format, rate;
  int fragsize;
  extraopt_t *opt;
  char endtest[sizeof(unsigned int)];
  
  char* server = DEFAULT_SERVER;
  int port = DEFAULT_PORT;
  int protocol = DEFAULT_PROTOCOL;
  char* mount = DEFAULT_MOUNT;
  char* user = DEFAULT_USER;
  char* password = DEFAULT_PASSWORD;

  if (verbose) {
    printf("Boodler: SHOUT sound driver.\n");
  }

  if (device) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  *((unsigned int *)endtest) = ( (unsigned int) ( ('E' << 24) + ('N' << 16) + ('D' << 8) + ('I') ) );
  if (endtest[0] == 'I' && endtest[1] == 'D' && endtest[2] == 'N' && endtest[3] == 'E') {
    sound_big_endian = FALSE;
  }
  else if (endtest[sizeof(unsigned int)-1] == 'I' && endtest[sizeof(unsigned int)-2] == 'D' && endtest[sizeof(unsigned int)-3] == 'N' && endtest[sizeof(unsigned int)-4] == 'E') {
    sound_big_endian = TRUE;
  }
  else {
    fprintf(stderr, "Cannot determine endianness.\n");
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
  }

  if (format == -1) {
    format = sound_big_endian;
  }

  if (!ratewanted)
    ratewanted = DEFAULT_SOUNDRATE;
  //if (!devname) 
    //devname = DEFAULT_FILENAME;

  device = (FILE*)1; //fopen(devname, "wb");
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
  }

  maxtime = 0; //(long)(maxsecs * (double)rate);
  curtime = 0;
  /*if (verbose) {
    printf("%g seconds of output (%ld frames)\n", maxsecs, maxtime);
  }*/

  sound_rate = rate;
  sound_channels = channels;
  sound_format = format;
  sound_buffersize = fragsize;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);

  rawbuffer = (char *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    //fclose(device);
    device = NULL;
    return FALSE;    
  }

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;     
  }
  
  vorbis_info_init(&vi);
  ret = vorbis_encode_init_vbr(&vi , 2, sound_rate, 0.1);
  if (ret) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  shout_init();
  
  if (!(shout = shout_new())) {
    fprintf(stderr, "Could not allocate shout_t\n");
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_host(shout, server) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting hostname: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_protocol(shout, protocol) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting protocol: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_port(shout, port) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting port: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_password(shout, password) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting password: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_mount(shout, mount) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting mount: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_set_user(shout, user) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting user: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }

  if (shout_set_format(shout, SHOUT_FORMAT_OGG) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error setting format: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  if (shout_open(shout) != SHOUTERR_SUCCESS) {
    fprintf(stderr, "Error connecting to server: %s\n", shout_get_error(shout));
    free(rawbuffer);
    rawbuffer = NULL;
    //fclose(device);
    device = NULL;
    return FALSE;
  }
  
  vorbis_comment_init(&vc);
  vorbis_comment_add_tag(&vc, "ENCODER","Boodler");
  //vorbis_comment_add_tag(&vc, "SERVER_NAME","Boodler");
  //vorbis_comment_add_tag(&vc, "SERVER_DESCRIPTION","BoodlerDDD");
  
  vorbis_analysis_init(&vd, &vi);
  vorbis_block_init(&vd, &vb);
  
  srand(time(NULL));
  ogg_stream_init(&os, rand());
  
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
      //fwrite(og.header, 1, og.header_len, device);
      //fwrite(og.body, 1, og.body_len, device);
      shout_send(shout, og.header, og.header_len);
      shout_send(shout, og.body, og.body_len);
    }
  }

  return TRUE;
}

void audev_close_device()
{
  int res;
  
  shout_close(shout);
  shout_shutdown();
  
  vorbis_analysis_wrote(&vd, 0);
  audev_vorbis_flush();
  
  ogg_stream_clear(&os);
  vorbis_block_clear(&vb);
  vorbis_dsp_clear(&vd);
  vorbis_comment_clear(&vc);
  vorbis_info_clear(&vi);

  if (device == NULL) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  //fclose(device);
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

  if (device == 0) {
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

    //fwrite(rawbuffer, 1, sound_buffersize, device);
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
    //if (curtime >= maxtime)
      //return FALSE;
  }
}

void audev_vorbis_flush(void)
{
  while (vorbis_analysis_blockout(&vd, &vb) == 1) {
    vorbis_analysis(&vb, NULL);
    vorbis_bitrate_addblock(&vb);
    
    while (vorbis_bitrate_flushpacket(&vd, &op)) {
      ogg_stream_packetin(&os, &op);
      
      while (!eos) {
        int result = ogg_stream_pageout(&os, &og);
        if (result == 0) break;
        //fwrite(og.header, 1, og.header_len, device);
        //fwrite(og.body, 1, og.body_len, device);
        shout_send(shout, og.header, og.header_len);
        shout_send(shout, og.body, og.body_len);
        if (ogg_page_eos(&og)) eos=1;
      }
      shout_sync(shout);
    }
  }
}

