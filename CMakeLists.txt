cmake_minimum_required(VERSION 3.20)
project(MedViewCore VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(medview_core SHARED cpp/src/mask_metrics.cpp)
target_include_directories(medview_core PUBLIC cpp/include)
target_compile_options(medview_core PRIVATE $<$<CXX_COMPILER_ID:Clang,GNU>:-Wall;-Wextra;-Wpedantic;-Werror>)
set_target_properties(medview_core PROPERTIES OUTPUT_NAME "medview_core")

enable_testing()
add_executable(medview_core_tests cpp/tests/test_mask_metrics.cpp)
target_link_libraries(medview_core_tests PRIVATE medview_core)
add_test(NAME medview_core_tests COMMAND medview_core_tests)

