#include "medview_core.h"

#include <array>
#include <cassert>
#include <cmath>

int main() {
  std::array<unsigned char, 24> mask{};
  mask[1 * 3 * 2 + 2 * 2 + 1] = 1;
  mask[0] = 1;
  MaskMetrics result{};
  assert(medview_mask_metrics(mask.data(), 4, 3, 2, 0.5, 0.5, 2.0, &result) == 0);
  assert(result.voxel_count == 2);
  assert(std::abs(result.volume_mm3 - 1.0) < 1e-9);
  assert(result.min_x == 0 && result.max_x == 1);
  assert(result.min_y == 0 && result.max_y == 2);
  assert(result.min_z == 0 && result.max_z == 1);

  std::array<float, 4> values{-1.0F, 0.5F, 2.0F, 0.49F};
  std::array<unsigned char, 4> thresholded{};
  assert(medview_threshold_mask(values.data(), thresholded.data(), 4, 0.5F) == 2);
  assert(thresholded[1] == 1 && thresholded[2] == 1 && thresholded[3] == 0);
  assert(medview_mask_metrics(nullptr, 1, 1, 1, 1, 1, 1, &result) == 1);
  return 0;
}

