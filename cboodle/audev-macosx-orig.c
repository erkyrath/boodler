/* Boodler: a programmable soundscape tool
   Copyright 2001 by Andrew Plotkin <erkyrath@eblong.com>
   <http://www.eblong.com/zarf/boodler/>
   This program is distributed under the LGPL.
   See the LGPL document, or the above URL, for details.
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

static AudioDeviceID audevice = kAudioDeviceUnknown;
static long sound_rate = 0; /* frames per second */
static int sound_channels = 0;
static long sound_buffersize = 0; /* bytes */

static long samplesperbuf = 0;
static long framesperbuf = 0;

static pthread_mutex_t audiomutex;
static pthread_cond_t audiocond;
static float *rawbuffer = NULL; /* samplesperbuf floats */
static long *valbuffer = NULL; /* samplesperbuf longs */
static long sampleswritten = 0; /* rawbuffer[0..sampleswritten) is full */

static OSStatus PlaybackIOProc(AudioDeviceID inDevice,
  const AudioTimeStamp *inNow,
  const AudioBufferList *inInputData,
  const AudioTimeStamp *inInputTime,
  AudioBufferList *outOutputData,
  const AudioTimeStamp *inOutputTime,
  void *inClientData);

int audev_init_device(char *dummydevname, long ratewanted, int verbose, extraopt_t *extra)
{
  int ix, res;
  OSStatus status;
  long lx;
  int channels;
  long rate;
  long fragsize;
  extraopt_t *opt;
  UInt32 propsize;
  UInt32 bytecount;
  struct AudioStreamBasicDescription streamdesc;
  struct AudioBufferList buflist;
#define LEN_DEVICE_NAME 128
  char devicename[LEN_DEVICE_NAME];

  if (verbose) {
    printf("Boodler: MACOSX sound driver.\n");
  }

  fragsize = 32768;

  for (opt=extra; opt->key; opt++) {
    if (!strcmp(opt->key, "buffer") && opt->val) {
      fragsize = atol(opt->val);
    }
  }


  if (audevice != kAudioDeviceUnknown) {
    fprintf(stderr, "Sound device is already open.\n");
    return FALSE;
  }

  propsize = sizeof(audevice);
  status = AudioHardwareGetProperty(kAudioHardwarePropertyDefaultOutputDevice,
    &propsize, &audevice);
  if (status) {
    fprintf(stderr, "Could not get audio default device.\n");
    return FALSE;
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

  propsize = sizeof(buflist);
  status = AudioDeviceGetProperty(audevice, 1, 0,
    kAudioDevicePropertyStreamConfiguration, &propsize, &buflist);
  if (status) {
    fprintf(stderr, "Could not get audio device configuration.\n");
    return FALSE;
  }

  if (verbose) {
    printf("%d buffers in queue.\n", (int)buflist.mNumberBuffers);    
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

  sampleswritten = 0;

  rawbuffer = (float *)malloc(sound_buffersize);
  if (!rawbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    return FALSE;    
  }
  memset(rawbuffer, 0, sound_buffersize);

  valbuffer = (long *)malloc(sizeof(long) * samplesperbuf);
  if (!valbuffer) {
    fprintf(stderr, "Unable to allocate sound buffer.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    return FALSE;     
  }
  memset(valbuffer, 0, sizeof(long) * samplesperbuf);

  res = pthread_mutex_init(&audiomutex, NULL);
  if (res) {
    fprintf(stderr, "Unable to init mutex.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    free(valbuffer);
    valbuffer = NULL;
    return FALSE;
  }

  res = pthread_cond_init(&audiocond, NULL);
  if (res) {
    fprintf(stderr, "Unable to init condition variable.\n");
    free(rawbuffer);
    rawbuffer = NULL;
    free(valbuffer);
    valbuffer = NULL;
    return FALSE;
  }

  status = AudioDeviceAddIOProc(audevice, PlaybackIOProc, (void *)1);
  if (status) {
    fprintf(stderr, "Could not add IOProc to device.\n");
    return FALSE;
  }

  status = AudioDeviceStart(audevice, PlaybackIOProc);
  if (status) {
    fprintf(stderr, "Could not start audio device.\n");
    return FALSE;
  }

  return TRUE;
}

void audev_close_device()
{
  OSStatus status;
  int res;

  if (audevice == kAudioDeviceUnknown) {
    fprintf(stderr, "Unable to close sound device which was never opened.\n");
    return;
  }

  status = AudioDeviceStop(audevice, PlaybackIOProc);
  if (status) {
    fprintf(stderr, "Could not stop audio device; continuing.\n");
  }

  audevice = kAudioDeviceUnknown;

  if (rawbuffer) {
    free(rawbuffer);
    rawbuffer = NULL;
  }
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

  pthread_mutex_lock(&audiomutex);

  for (ix = 0; ix < sampleswritten; ix++)
    ptr[ix] = rawbuffer[ix];
  for (; ix < samplesperbuf; ix++)
    ptr[ix] = 0.0;

  sampleswritten = 0;

  pthread_mutex_unlock(&audiomutex);
  pthread_cond_signal(&audiocond);

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
    long pos;
    long count, count2;

    res = mixfunc(valbuffer, genfunc, rock);
    if (res)
      return TRUE;

    pos = 0;

    while (pos < samplesperbuf) {
      pthread_mutex_lock(&audiomutex);

      while (sampleswritten == samplesperbuf)
	pthread_cond_wait(&audiocond, &audiomutex);

      count = (samplesperbuf - pos);
      count2 = (samplesperbuf - sampleswritten);
      if (count2 < count)
	count = count2;

      srcptr = valbuffer+pos;
      destptr = rawbuffer+sampleswritten;

      for (ix=0; ix<count; ix++, srcptr++, destptr++) {
	long samp = *srcptr;
	if (samp > 0x7FFF)
	  samp = 0x7FFF;
	else if (samp < -0x7FFF)
	  samp = -0x7FFF;
	*destptr = ((float)samp) * (float)0.00003051757;
	/* that is, dest = (samp/32768) */
      }

      pos += count;
      sampleswritten += count;

      pthread_mutex_unlock(&audiomutex);
    }
  }
}

