cmake_minimum_required(VERSION 3.21)

# Ixion host: one process that loads both game modules and switches between them. Standalone
# project; it links only SDL3 and never sees game headers. Windows only for v0.
project(ixion LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "The Ixion host is Windows-only for v0 (it uses the Win32 fiber API).")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(SDL3 CONFIG REQUIRED)

set(IXION_API_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../include")

# The host is a plain Win32 program; keep <windows.h> lean and expose the Vista+ fiber APIs.
set(IXION_HOST_DEFINITIONS UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX _WIN32_WINNT=0x0A00)

add_executable(ixion
    main.cpp
    host.cpp
    host.hpp
)
target_include_directories(ixion PRIVATE "${IXION_API_DIR}")
target_compile_definitions(ixion PRIVATE ${IXION_HOST_DEFINITIONS})
target_link_libraries(ixion PRIVATE SDL3::SDL3)

add_executable(ixion_fiber_smoke
    fiber_smoke.cpp
)
target_compile_definitions(ixion_fiber_smoke PRIVATE ${IXION_HOST_DEFINITIONS})
