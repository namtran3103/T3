#!/bin/bash
cd dp || exit
cd LightGBM || exit
cmake -DBUILD_STATIC_LIB=ON -B bin -S .
cmake --build bin -j 8
