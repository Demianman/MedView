#include "medview_core.h"

#include <algorithm>
#include <limits>

int medview_mask_metrics(const unsigned char* mask, const std::size_t nx,
                         const std::size_t ny, const std::size_t nz,
                         const double sx, const double sy, const double sz,
                         MaskMetrics* result) {
  if (mask == nullptr || result == nullptr || nx == 0 || ny == 0 || nz == 0 ||
      sx <= 0 || sy <= 0 || sz <= 0) {
    return 1;
  }
  MaskMetrics out{};
  out.min_x = out.min_y = out.min_z = std::numeric_limits<std::size_t>::max();
  for (std::size_t z = 0; z < nz; ++z) {
    for (std::size_t y = 0; y < ny; ++y) {
      for (std::size_t x = 0; x < nx; ++x) {
        const auto index = x * ny * nz + y * nz + z;
        if (mask[index] == 0) continue;
        ++out.voxel_count;
        out.min_x = std::min(out.min_x, x); out.max_x = std::max(out.max_x, x);
        out.min_y = std::min(out.min_y, y); out.max_y = std::max(out.max_y, y);
        out.min_z = std::min(out.min_z, z); out.max_z = std::max(out.max_z, z);
      }
    }
  }
  out.is_empty = out.voxel_count == 0 ? 1 : 0;
  if (out.is_empty) out.min_x = out.min_y = out.min_z = 0;
  out.volume_mm3 = static_cast<double>(out.voxel_count) * sx * sy * sz;
  *result = out;
  return 0;
}

std::size_t medview_threshold_mask(const float* volume, unsigned char* mask,
                                   const std::size_t count, const float threshold) {
  if (volume == nullptr || mask == nullptr) return 0;
  std::size_t selected = 0;
  for (std::size_t i = 0; i < count; ++i) {
    mask[i] = volume[i] >= threshold ? 1 : 0;
    selected += mask[i];
  }
  return selected;
}

