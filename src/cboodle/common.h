/* Boodler: a programmable soundscape tool
   Copyright 2001-9 by Andrew Plotkin <erkyrath@eblong.com>
   Boodler web site: <http://boodler.org/>
   The cboodle extensions are distributed under the LGPL and the
   GPL; you may use cboodle under the terms of either license.
   See the LGPL or GPL documents, or the above URL, for details.
*/


/* We define our own TRUE and FALSE and NULL, because ANSI
    is a strange world. */
#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif
#ifndef NULL
#define NULL 0
#endif

/* must be able to hold a value between -0x7FFF and 0x7FFF */
typedef signed short value_t; 

typedef struct stereo_struct stereo_t;
typedef struct sample_struct sample_t;
typedef struct note_struct note_t;

typedef int (*generate_func_t)(long curtime, void *rock);
typedef int (*mix_func_t)(long *buffer, generate_func_t genfunc, void *rock);

typedef struct extraopt_struct {
  char *key;
  char *val;
} extraopt_t;
