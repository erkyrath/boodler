/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_osxaq extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <AudioToolbox/AudioQueue.h>
/* "/System/Library/Frameworks/AudioToolbox.framework/Versions/A/Headers/AudioQueue.h" */
#include <pthread.h>

#include "common.h"
#include "audev.h"

#define DEFAULT_SOUNDRATE (44100)
#define NUM_BUFFERS (3)
#define SIZE_BUFFERS (65536)

static int sound_big_endian = 0;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static int sound_format = 0; /* TRUE for big-endian, FALSE for little */
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static long *valbuffer = NULL;

static int bufcount = NUM_BUFFERS;

typedef struct buffer_struct {
  pthread_mutex_t mutex;
  pthread_cond_t cond;
  AudioQueueBuffer *buffer;
  int full;
} buffer_t;

static AudioQueueRef aqueue = NULL;
static buffer_t *buffers = NULL; /* array, len bufcount */

static int device = FALSE; /* just a flag */
static int bailing = FALSE;
static int filling = 0;
static int started = FALSE;

static void playCallback(void *user, AudioQueueRef queue, 
  AudioQueueBuffer *qbuf);

int audev_init_device(char *devname, long ratewanted, int verbose, extraopt_t *extra)
{
  int channels, format, rate, ix, res;
  int fragsize;
  extraopt_t *opt;
  char endtest[sizeof(unsigned int)];
  AudioStreamBasicDescription formataq;
  OSStatus status;

  if (verbose) {
    printf("Boodler: OSX AudioQueue driver.\n");
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
    fprintf(stderr, "Cannot determine native endianness.\n");
    return FALSE;
  }

  format = -1;
  fragsize = SIZE_BUFFERS;

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "end") && opt->val) {
      if (!strcmp(opt->val, "big"))
        format = TRUE;
      else if (!strcmp(opt->val, "little"))
        format = FALSE;
    }
    else if (!strcmp(opt->key, "buffersize") && opt->val) {
      fragsize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "buffercount") && opt->val) {
      bufcount = atoi(opt->val);
    }
    else if (!strcmp(opt->key, "listdevices")) {
      printf("Device list: not yet supported.\n");
    }
  }

  if (bufcount < 2)
    bufcount = 2;

  /* ### device list */

  if (format == -1) {
    format = sound_big_endian;
  }

  if (!ratewanted) {
    ratewanted = DEFAULT_SOUNDRATE;
  }

  rate = ratewanted;
  channels = 2;

  sound_rate = rate;
  sound_channels = channels;
  sound_format = format;
  sound_buffersize = fragsize;

  samplesperbuf = sound_buffersize / 2;
  framesperbuf = sound_buffersize / (2 * sound_channels);
    
  if (verbose) {
    printf("%d channels, %d frames per second, 16-bit samples (signed, %s)\n",
      channels, rate, (sound_format?"big-endian":"little-endian"));
    printf("%d buffers, %ld bytes (%ld frames) per buffer\n",
      bufcount, sound_buffersize, framesperbuf);
  }

  bzero(&formataq, sizeof(formataq));
  formataq.mSampleRate = sound_rate;
  formataq.mFormatID = kAudioFormatLinearPCM;
  formataq.mFramesPerPacket = 1;
  formataq.mChannelsPerFrame = sound_channels;
  formataq.mBytesPerFrame = sound_channels * 2;
  formataq.mBytesPerPacket = sound_channels * 2;
  formataq.mBitsPerChannel = 16;
  formataq.mReserved = 0;
  formataq.mFormatFlags = kLinearPCMFormatFlagIsSignedInteger;
  if (sound_format)
    formataq.mFormatFlags |= kLinearPCMFormatFlagIsBigEndian;

  aqueue = NULL;
  status = AudioQueueNewOutput(&formataq, &playCallback, NULL, NULL, NULL, 0,
    &aqueue);
  if (status) {
    fprintf(stderr, "Unable to allocate AudioQueue: %d\n", (int)status);
    return FALSE;
  }
  
  { /*###*/
      UInt32 propsize = 0;
      CFStringRef propval;
      status = AudioQueueGetPropertySize(aqueue, kAudioQueueProperty_CurrentDevice, &propsize);
      fprintf(stderr, "### (%ld) device propsize %ld\n", status, propsize);
      status = AudioQueueGetProperty(aqueue, kAudioQueueProperty_CurrentDevice, &propval, &propsize);
      fprintf(stderr, "### (%ld) device property %lx (%ld)\n", status, propval, propsize);
  } /*###*/

  buffers = (buffer_t *)malloc(bufcount * sizeof(buffer_t));
  if (!buffers) {
    fprintf(stderr, "Unable to allocate buffer array\n");
    AudioQueueDispose(aqueue, TRUE);
    return FALSE;
  }

  for (ix = 0; ix < bufcount; ix++) {
    long lx;

    status = AudioQueueAllocateBuffer(aqueue, sound_buffersize, &buffers[ix].buffer);
    if (status) {
      fprintf(stderr, "Unable to allocate AudioQueueBuffer\n");
      AudioQueueDispose(aqueue, TRUE);
      return FALSE;
    }

    buffers[ix].full = FALSE;

    for (lx = 0; lx < samplesperbuf; lx++) {
      ((short*)(buffers[ix].buffer->mAudioData))[lx] = 0;
    }

    res = pthread_mutex_init(&buffers[ix].mutex, NULL);
    if (res) {
      fprintf(stderr, "Unable to init mutex.\n");
      /* free stuff */
      AudioQueueDispose(aqueue, TRUE);
      return FALSE;
    }

    res = pthread_cond_init(&buffers[ix].cond, NULL);
    if (res) {
      fprintf(stderr, "Unable to init cond.\n");
      /* free stuff */
      AudioQueueDispose(aqueue, TRUE);
      return FALSE;
    }
  }
  
  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    AudioQueueDispose(aqueue, TRUE);
    return FALSE;     
  }

  device = TRUE;
  started = FALSE;
  filling = 0;

  return TRUE;
}

void audev_close_device()
{
  int ix;
  long sleep;
  OSStatus status;

  if (!device) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }
  
  bailing = TRUE;

  if (!started) {
    /* We never got to the point of starting playback. Do it now. */
    started = TRUE;
    fprintf(stderr, "### late-starting\n");
    status = AudioQueueStart(aqueue, NULL);
    if (status) {
      fprintf(stderr, "Could not late-start audio device.\n");
      return;
    }
  }

  fprintf(stderr, "### flushing\n");

  status = AudioQueueFlush(aqueue);
  if (status) {
    fprintf(stderr, "Could not flush audio device; continuing.\n");
  }

  /* Wait on each buffer to make sure they're all drained. */
  for (ix = 0; ix < bufcount; ix++) {
    buffer_t *buffer = &buffers[ix];
    pthread_mutex_lock(&buffer->mutex);
    while (buffer->full)
      pthread_cond_wait(&buffer->cond, &buffer->mutex);
    pthread_mutex_unlock(&buffer->mutex);
  }

  /* And wait one more buffer-duration. I'm not sure why this is necessary
     with all the flushing and stopping, but it is. */
  sleep = 1000 * ((1000*framesperbuf) / sound_rate); 
  fprintf(stderr, "### final sleep is %ld microsec\n", sleep);
  usleep(sleep);

  fprintf(stderr, "### stopping queue non-immediate\n");

  status = AudioQueueStop(aqueue, FALSE);
  if (status) {
    fprintf(stderr, "Could not stop audio device; continuing.\n");
  }

  status = AudioQueueDispose(aqueue, FALSE);
  if (status) {
    fprintf(stderr, "Could not dispose audio device; continuing.\n");
  }

  device = FALSE;

  if (valbuffer) {
    free(valbuffer);
    valbuffer = NULL;
  }

  for (ix = 0; ix < bufcount; ix++) {
    pthread_mutex_destroy(&buffers[ix].mutex);
    pthread_cond_destroy(&buffers[ix].cond);
  }

  free(buffers);
  buffers = NULL;
}

long audev_get_soundrate()
{
  return sound_rate;
}

long audev_get_framesperbuf()
{
  return framesperbuf;
}


static void playCallback(void *user, AudioQueueRef queue, 
  AudioQueueBuffer *qbuf)
{
  int ix;
  buffer_t *buffer = NULL;

  for (ix = 0; ix < bufcount; ix++) {
    if (buffers[ix].buffer == qbuf) {
      buffer = &(buffers[ix]);
      break;
    }
  }

  fprintf(stderr, "### Buffer %d called back\n", ix);
  
  if (!buffer) {
    fprintf(stderr, "Unable to identify buffer in callback.\n");
    return;
  }

  pthread_mutex_lock(&buffer->mutex);

  if (!buffer->full)
    fprintf(stderr, "Buffer %d called back but not full.\n", ix);

  buffer->full = FALSE;

  pthread_mutex_unlock(&buffer->mutex);
  pthread_cond_signal(&buffer->cond);
}

int audev_loop(mix_func_t mixfunc, generate_func_t genfunc, void *rock)
{
  char *ptr;
  int res;

  if (!device) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }
  
  while (1) {
    OSStatus status;
    buffer_t *buffer;

    if (bailing)
      return FALSE;
    
    res = mixfunc(valbuffer, genfunc, rock);
    if (res) {
      fprintf(stderr, "### mixfunc says to stop.\n");
      bailing = TRUE;
      return TRUE;
    }

    buffer = &buffers[filling];
    fprintf(stderr, "### filling buffer %d\n", filling);

    pthread_mutex_lock(&buffer->mutex);
    
    while (buffer->full) {
      fprintf(stderr, "### but full, so blocking\n");
      pthread_cond_wait(&buffer->cond, &buffer->mutex);
      fprintf(stderr, "### ...unblocking\n");
    }
    
    if (sound_format) {
      long lx;
      for (lx=0, ptr=buffer->buffer->mAudioData; lx<samplesperbuf; lx++) {
        long samp = valbuffer[lx];
        if (samp > 0x7FFF)
          samp = 0x7FFF;
        else if (samp < -0x7FFF)
          samp = -0x7FFF;
        *ptr++ = ((samp >> 8) & 0xFF);
        *ptr++ = ((samp) & 0xFF);
      }
    }
    else {
      long lx;
      for (lx=0, ptr=buffer->buffer->mAudioData; lx<samplesperbuf; lx++) {
        long samp = valbuffer[lx];
        if (samp > 0x7FFF)
          samp = 0x7FFF;
        else if (samp < -0x7FFF)
          samp = -0x7FFF;
        *ptr++ = ((samp) & 0xFF);
        *ptr++ = ((samp >> 8) & 0xFF);
      }
    }
    
    buffer->buffer->mAudioDataByteSize = sound_buffersize;
    buffer->full = TRUE;

    status = AudioQueueEnqueueBuffer(aqueue, buffer->buffer, 0, NULL);
    if (status) {
      fprintf(stderr, "Could not enqueue buffer.\n");
      return FALSE;
    }
    
    filling += 1;
    if (filling >= bufcount) 
      filling = 0;

    pthread_mutex_unlock(&buffer->mutex);

    if (!started && filling == 0) {
      /* When all the buffers are filled for the first time, we can
         start the device playback. */
      started = TRUE;
      fprintf(stderr, "### starting device\n");
      status = AudioQueueStart(aqueue, NULL);
      if (status) {
        fprintf(stderr, "Could not start sound device.\n");
        return FALSE;
      }
    }
  }
}
