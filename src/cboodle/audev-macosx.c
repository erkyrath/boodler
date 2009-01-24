/* Boodler: a programmable soundscape tool
   Copyright 2002-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle_macosx extension is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
*/

/*
  For CoreAudio documentation, see:
  http://developer.apple.com/documentation/MusicAudio/Reference/CACoreAudioReference/AudioHardware/CompositePage.html
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <CoreAudio/CoreAudio.h>
/* "/System/Library/Frameworks/CoreAudio.framework/Versions/A/Headers/CoreAudio.h" */

#include "common.h"
#include "audev.h"

typedef struct buffer_struct {
  pthread_mutex_t mutex;
  pthread_cond_t cond;
  int full;
  float *buf;
} buffer_t;

static AudioDeviceID audevice = kAudioDeviceUnknown;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static long sound_buffersize = 0; /* bytes */

static int started = FALSE;
static int bufcount = 6;
static long samplesperbuf = 0;
static long framesperbuf = 0;

static int bailing;

static int filling, emptying;
static buffer_t *rawbuffer;
static long *valbuffer = NULL; /* samplesperbuf longs */

static OSStatus PlaybackIOProc(AudioDeviceID inDevice,
  const AudioTimeStamp *inNow,
  const AudioBufferList *inInputData,
  const AudioTimeStamp *inInputTime,
  AudioBufferList *outOutputData,
  const AudioTimeStamp *inOutputTime,
  void *inClientData);

int audev_init_device(char *wantdevname, long ratewanted, int verbose, extraopt_t *extra)
{
  int bx, res;
  OSStatus status;
  int channels;
  long rate;
  long fragsize;
  int listdevices = FALSE;
  AudioDeviceID wantdevid;
  AudioDeviceID wantedaudev;
  extraopt_t *opt;
  UInt32 propsize;
  UInt32 bytecount;
  struct AudioStreamBasicDescription streamdesc;
#define LEN_DEVICE_NAME 128
  char devicename[LEN_DEVICE_NAME];

  if (verbose) {
    printf("Boodler: OSX CoreAudio sound driver.\n");
  }

  fragsize = 32768;
  bufcount = 6;

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "buffersize") && opt->val) {
      fragsize = atol(opt->val);
    }
    else if (!strcmp(opt->key, "buffercount") && opt->val) {
      bufcount = atoi(opt->val);
    }
    else if (!strcmp(opt->key, "listdevices")) {
      listdevices = TRUE;
    }
  }

  if (bufcount < 2)
    bufcount = 2;

  if (audevice != kAudioDeviceUnknown) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  wantedaudev = kAudioDeviceUnknown;

  /* If the given device name is a string representation of an
     integer, work out the integer. */
  wantdevid = kAudioDeviceUnknown;
  if (wantdevname) {
    char *endptr = NULL;
    wantdevid = strtol(wantdevname, &endptr, 10);
    if (!endptr || endptr == wantdevname || (*endptr != '\0'))
      wantdevid = kAudioDeviceUnknown;
  }

  if (listdevices || wantdevname) {
    int ix, jx;
    int device_count;
#define LEN_DEVICE_LIST 16
    AudioDeviceID devicelist[LEN_DEVICE_LIST];  

    propsize = LEN_DEVICE_LIST * sizeof(AudioDeviceID);
    status = AudioHardwareGetProperty(kAudioHardwarePropertyDevices,
      &propsize, devicelist);
    if (status) {
      fprintf(stderr, "Could not get list of audio devices.\n");
      return FALSE;
    }
    device_count = propsize / sizeof(AudioDeviceID);

    for (ix=0; ix<device_count; ix++) {
      AudioDeviceID tmpaudev = devicelist[ix];

      /* Determine if this is an output device. */
      status = AudioDeviceGetPropertyInfo(tmpaudev, 0, 0, 
	kAudioDevicePropertyStreamConfiguration, &propsize, NULL);
      if (status) {
	fprintf(stderr, "Could not get audio property info.\n");
	return FALSE;
      }

      AudioBufferList *buflist = (AudioBufferList *)malloc(propsize);
      status = AudioDeviceGetProperty(tmpaudev, 0, 0, 
	kAudioDevicePropertyStreamConfiguration, &propsize, buflist);
      if (status) {
	fprintf(stderr, "Could not get audio property info.\n");
	return FALSE;
      }

      int hasoutput = FALSE;

      for (jx=0; jx<buflist->mNumberBuffers; jx++) {
	if (buflist->mBuffers[jx].mNumberChannels > 0) {
	  hasoutput = TRUE;
	}
      }

      free(buflist);
      buflist = NULL;

      if (!hasoutput) {
	/* skip this device. */
	continue;
      }

      /* Determine the device name. */

      propsize = LEN_DEVICE_NAME * sizeof(char);
      status = AudioDeviceGetProperty(tmpaudev, 1, 0,
	kAudioDevicePropertyDeviceName, &propsize, devicename);
      if (status) {
	fprintf(stderr, "Could not get audio device name.\n");
	return FALSE;
      }

      if (listdevices)
	printf("Found device ID %d: \"%s\".\n", (int)tmpaudev, devicename);

      /* Check if the desired name matches (a prefix of) the device name. */
      if (wantdevname && !strncmp(wantdevname, devicename, 
	    strlen(wantdevname))) {
	wantedaudev = tmpaudev;
      }

      /* Check if the int version of the desired name matches the device ID. */
      if (wantdevid != kAudioDeviceUnknown && wantdevid == tmpaudev) {
	wantedaudev = tmpaudev;
      }
    }
  }

  if (wantdevname) {
    audevice = wantedaudev;
  }
  else {
    propsize = sizeof(audevice);
    status = AudioHardwareGetProperty(kAudioHardwarePropertyDefaultOutputDevice,
      &propsize, &audevice);
    if (status) {
      fprintf(stderr, "Could not get audio default device.\n");
      return FALSE;
    }
  }

  if (audevice == kAudioDeviceUnknown) {
    fprintf(stderr, "Audio default device is unknown.\n");
    return FALSE;
  }

  propsize = LEN_DEVICE_NAME * sizeof(char);
  status = AudioDeviceGetProperty(audevice, 1, 0,
    kAudioDevicePropertyDeviceName, &propsize, devicename);
  if (status) {
    fprintf(stderr, "Could not get audio device name.\n");
    return FALSE;
  }

  if (verbose) {
    printf("Got device ID %d: \"%s\".\n", (int)audevice, devicename);
  }

  if (ratewanted) {
    memset(&streamdesc, 0, sizeof(streamdesc));
    streamdesc.mSampleRate = ratewanted;

    propsize = sizeof(streamdesc);

    status = AudioDeviceSetProperty(audevice, NULL, 0, 0,
      kAudioDevicePropertyStreamFormatMatch, propsize, &streamdesc);
    if (status) {
      fprintf(stderr, "Could not set sample rate; continuing.\n");
    }
  }

  {
    bytecount = fragsize;

    propsize = sizeof(bytecount);

    status = AudioDeviceSetProperty(audevice, NULL, 0, 0,
      kAudioDevicePropertyBufferSize, propsize, &bytecount);
    if (status) {
      fprintf(stderr, "Could not set buffer size; continuing.\n");
    }
  }

  propsize = sizeof(struct AudioStreamBasicDescription);
  status = AudioDeviceGetProperty(audevice, 1, 0,
    kAudioDevicePropertyStreamFormat, &propsize, &streamdesc);
  if (status) {
    fprintf(stderr, "Could not get audio device description.\n");
    return FALSE;
  }

  rate = streamdesc.mSampleRate;

  if (streamdesc.mFormatID != kAudioFormatLinearPCM) {
    fprintf(stderr, "Audio device format is not LinearPCM; exiting.\n");
    return FALSE;    
  }

  if (streamdesc.mChannelsPerFrame != 2) {
    fprintf(stderr, "Audio device is not stereo; exiting.\n");
    return FALSE;
  }
  channels = 2;

  if (!(streamdesc.mFormatFlags & kLinearPCMFormatFlagIsFloat)) {
    fprintf(stderr, "Audio device is not floating-point; exiting.\n");
    return FALSE;
  }

  propsize = sizeof(bytecount);
  status = AudioDeviceGetProperty(audevice, 1, 0,
    kAudioDevicePropertyBufferSize, &propsize, &bytecount);
  if (status) {
    fprintf(stderr, "Could not get audio device buffer size.\n");
    return FALSE;
  }

  fragsize = bytecount;
  if (verbose) {
    printf("%ld bytes per buffer.\n", fragsize);
  }

  if (verbose) {
    printf("%d buffers in queue.\n", bufcount);
  }

  /* Everything's figured out. */

  sound_rate = rate;
  sound_channels = channels;
  sound_buffersize = fragsize;

  framesperbuf = sound_buffersize / (sizeof(float) * sound_channels);
  samplesperbuf = framesperbuf * sound_channels;
  if (verbose) {
    printf("%ld frames (%ld samples) per buffer.\n",
	   framesperbuf, samplesperbuf);
    printf("%ld frames per second.\n",
	   rate);
  }

  emptying = 0;
  filling = 0;

  bailing = FALSE;

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    return FALSE;     
  }
  memset(valbuffer, 0, sizeof(long) * samplesperbuf);

  rawbuffer = (buffer_t *)malloc(sizeof(buffer_t) * bufcount);
  memset(rawbuffer, 0, sizeof(buffer_t) * bufcount);

  for (bx=0; bx<bufcount; bx++) {
    buffer_t *buffer = &rawbuffer[bx];

    buffer->full = FALSE;

    buffer->buf = (float *)malloc(sound_buffersize);
    if (!buffer->buf) {
      fprintf(stderr, "Unable to allocate sound buffer.\n");
      /* free stuff */
      return FALSE;    
    }
    memset(buffer->buf, 0, sound_buffersize);

    res = pthread_mutex_init(&buffer->mutex, NULL);
    if (res) {
      fprintf(stderr, "Unable to init mutex.\n");
      /* free stuff */
      return FALSE;
    }

    res = pthread_cond_init(&buffer->cond, NULL);
    if (res) {
      fprintf(stderr, "Unable to init cond.\n");
      /* free stuff */
      return FALSE;
    }

  }

  /* AudioDeviceAddIOProc is deprecated as of OSX 10.5. Use the
     osxaq driver instead. */
  status = AudioDeviceAddIOProc(audevice, PlaybackIOProc, (void *)1);
  if (status) {
    fprintf(stderr, "Could not add IOProc to device.\n");
    return FALSE;
  }

  started = FALSE;

  return TRUE;
}

void audev_close_device()
{
  OSStatus status;
  int bx;

  if (audevice == kAudioDeviceUnknown) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  bailing = TRUE;

  if (!started) {
    /* We never got to the point of starting playback. Do it now. */
    started = TRUE;
    status = AudioDeviceStart(audevice, PlaybackIOProc);
    if (status) {
      fprintf(stderr, "Could not late-start audio device.\n");
      return;
    }
  }

  /* Wait on each buffer to make sure they're all drained. */
  for (bx=0; bx<bufcount; bx++) {
    buffer_t *buffer = &rawbuffer[bx];

    pthread_mutex_lock(&buffer->mutex);
    
    while (buffer->full)
      pthread_cond_wait(&buffer->cond, &buffer->mutex);

    pthread_mutex_unlock(&buffer->mutex);
  }

  status = AudioDeviceStop(audevice, PlaybackIOProc);
  if (status) {
    fprintf(stderr, "Could not stop audio device; continuing.\n");
  }

  audevice = kAudioDeviceUnknown;

  for (bx=0; bx<bufcount; bx++) {
    buffer_t *buffer = &rawbuffer[bx];

    if (buffer->buf) {
      free(buffer->buf);
      buffer->buf = NULL;
    }

    pthread_mutex_destroy(&buffer->mutex);
    pthread_cond_destroy(&buffer->cond);
  }

  free(rawbuffer);

  if (valbuffer) {
    free(valbuffer);
    valbuffer = NULL;
  }
}

static OSStatus PlaybackIOProc(AudioDeviceID inDevice,
  const AudioTimeStamp *inNow,
  const AudioBufferList *inInputData,
  const AudioTimeStamp *inInputTime,
  AudioBufferList *outOutputData,
  const AudioTimeStamp *inOutputTime,
  void *inClientData)
{
  float *ptr = outOutputData->mBuffers[0].mData;
  int ix;
  buffer_t *buffer;

  buffer = &rawbuffer[emptying];

  pthread_mutex_lock(&buffer->mutex);

  if (!buffer->full) {

    pthread_mutex_unlock(&buffer->mutex);

    for (ix = 0; ix < samplesperbuf; ix++)
      ptr[ix] = 0.0;

  }
  else {

    for (ix = 0; ix < samplesperbuf; ix++)
      ptr[ix] = buffer->buf[ix];

    buffer->full = FALSE;

    emptying += 1;
    if (emptying >= bufcount)
      emptying = 0;

    pthread_mutex_unlock(&buffer->mutex);
    pthread_cond_signal(&buffer->cond);
  }

  return kAudioHardwareNoError;
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
  int ix, res;

  if (audevice == kAudioDeviceUnknown) {
    fprintf(stderr, "Sound device is not open.\n");
    return FALSE;
  }

  while (1) {
    float *destptr;
    long *srcptr;
    buffer_t *buffer;

    if (bailing) {
      return FALSE;
    }

    res = mixfunc(valbuffer, genfunc, rock);
    if (res) {
      bailing = TRUE;
      return TRUE;
    }

    buffer = &rawbuffer[filling];

    pthread_mutex_lock(&buffer->mutex);
    
    while (buffer->full) {
      pthread_cond_wait(&buffer->cond, &buffer->mutex);
    }

    srcptr = valbuffer;
    destptr = buffer->buf;
    
    for (ix=0; ix<samplesperbuf; ix++, srcptr++, destptr++) {
      long samp = *srcptr;
      if (samp > 0x7FFF)
	samp = 0x7FFF;
      else if (samp < -0x7FFF)
	samp = -0x7FFF;
      *destptr = ((float)samp) * (float)0.00003051757;
      /* that is, dest = (samp/32768) */
    }
    
    buffer->full = TRUE;
    
    filling += 1;
    if (filling >= bufcount) 
      filling = 0;
    
    pthread_mutex_unlock(&buffer->mutex);

    if (!started && filling == 0) {
      /* When all the buffers are filled for the first time, we can
         start the device playback. */
      OSStatus status;
      started = TRUE;
      status = AudioDeviceStart(audevice, PlaybackIOProc);
      if (status) {
        fprintf(stderr, "Could not start audio device.\n");
        return FALSE;
      }
    }
  }
}

