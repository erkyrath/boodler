all: makecboodle boodle/__init__.pyc

cboodle/cboodle.so: makecboodle

makecboodle:
	(cd cboodle; make cboodle.so)

boodle/cboodle.so: cboodle/cboodle.so
	cp cboodle/cboodle.so boodle/cboodle.so

boodle/__init__.pyc: boodle/cboodle.so
	python -c 'from boodle import *'
	touch boodle/__init__.pyc

configure:
	python configure.py

clean:
	(cd cboodle; make clean)
	(cd boodle; rm -f *.o *.so *.pyc *~)
	(cd effects; rm -f *.pyc *~)
	(cd doc; rm -f *~)
	rm -f *.pyc *.raw *~

