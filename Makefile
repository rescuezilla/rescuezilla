install: build.sh chroot.steps.part.1.sh chroot.steps.part.2.sh
	./build.sh

clean: 
	rm -rf livecd/
