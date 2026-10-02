#pragma once

#include <cstddef>

#if defined(_WIN32)
#define MEDVIEW_API __declspec(dllexport)
#else
#define MEDVIEW_API
#endif

extern "C" {

struct MaskMetrics {
  std::size_t voxel_count;
  double volume_mm3;
  std::size_t min_x, min_y, min_z;
  std::size_t max_x, max_y, max_z;
  int is_empty;
};

MEDVIEW_API int medview_mask_metrics(const unsigned char* mask, std::size_t nx,
                                     std::size_t ny, std::size_t nz,
                                     double sx, double sy, double sz,
                                     MaskMetrics* result);

MEDVIEW_API std::size_t medview_threshold_mask(const float* volume,
                                               unsigned char* mask,
                                               std::size_t count,
                                               float threshold);
}

