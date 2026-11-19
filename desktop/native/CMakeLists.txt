cmake_minimum_required(VERSION 3.16)
project(VerilinxAvoid LANGUAGES CXX)

file(GLOB AVOID_SOURCES "${ADAPTAGRAMS_COLA}/libavoid/*.cpp")
add_library(avoid SHARED ${AVOID_SOURCES})
target_include_directories(avoid PUBLIC "${ADAPTAGRAMS_COLA}")
target_compile_features(avoid PRIVATE cxx_std_17)

add_library(verilinx_avoid SHARED bridge.cpp)
target_compile_features(verilinx_avoid PRIVATE cxx_std_17)
target_link_libraries(verilinx_avoid PRIVATE avoid)
set_target_properties(verilinx_avoid PROPERTIES BUILD_RPATH_USE_ORIGIN TRUE)
