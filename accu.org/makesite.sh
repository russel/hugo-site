#!/bin/sh

rm -rf public
hugo -b https://newsite.accu.org
tar -C content -c --exclude "*.html" journal/ | tar -C public -x
tar -C public -cvf ../newsite.tar.gz .
