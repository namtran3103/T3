cmake_minimum_required(VERSION 3.24)
project(DP)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fopenmp")
# Include the path to LightGBM headers
include_directories(LightGBM/include)

# Add the LightGBM library
link_directories(LightGBM)

add_executable(dp_experiment DP.cpp)
# Link compiled lleaves model
# add_dependencies(LightGBMExample run)
target_link_libraries(dp_experiment ${CMAKE_SOURCE_DIR}/../lleaves.o)
# Link LightGBM
target_link_libraries(dp_experiment ${CMAKE_SOURCE_DIR}/LightGBM/lib_lightgbm.a)
