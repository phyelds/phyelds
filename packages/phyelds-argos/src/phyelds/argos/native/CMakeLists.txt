cmake_minimum_required(VERSION 3.18)
project(phyelds_argos CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ARGoSConfig.cmake looks for the modules installed beside it only under the system
# prefixes: an ARGoS found through CMAKE_PREFIX_PATH would not find its own modules.
find_path(ARGOS_CMAKE_DIR FindARGoSQTOpenGL.cmake
    PATHS ${CMAKE_PREFIX_PATH} ENV CMAKE_PREFIX_PATH
    PATH_SUFFIXES share/argos3/cmake NO_DEFAULT_PATH)
find_package(ARGoS REQUIRED)
# Find both together so an interpreter can never be paired with another Python's ABI.
set(Python3_USE_STATIC_LIBS FALSE)
find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter Development.Embed)
if(Python3_VERSION VERSION_GREATER_EQUAL "3.14")
    message(FATAL_ERROR "phyelds currently supports Python 3.12 and 3.13")
endif()
include_directories(${ARGOS_INCLUDE_DIRS})
link_directories(${ARGOS_LIBRARY_DIR})

add_library(phyelds_argos SHARED controller.cpp devices.cpp)
target_compile_definitions(phyelds_argos PRIVATE
    PHYELDS_PYTHON_EXECUTABLE="${Python3_EXECUTABLE}")
target_compile_options(phyelds_argos PRIVATE -Wall -Wextra)
target_link_libraries(phyelds_argos PRIVATE Python3::Python
    argos3core_simulator argos3plugin_simulator_footbot argos3plugin_simulator_epuck
    argos3plugin_simulator_eyebot argos3plugin_simulator_pipuck argos3plugin_simulator_builderbot
    argos3plugin_simulator_drone
    argos3plugin_simulator_genericrobot ${ARGOS_LDFLAGS})

option(PHYELDS_ARGOS_GUI "Build Qt/OpenGL halo and label renderer" ON)
if(PHYELDS_ARGOS_GUI)
    find_package(ARGoSQTOpenGL REQUIRED)
    add_library(phyelds_argos_qt SHARED gui.cpp)
    target_include_directories(phyelds_argos_qt PRIVATE ${ARGOS_QTOPENGL_INCLUDE_DIRS})
    target_link_libraries(phyelds_argos_qt PRIVATE phyelds_argos
        argos3plugin_simulator_qtopengl ${ARGOS_QTOPENGL_LIBRARIES})
endif()
