# skyborn-plot (`skybornplot`)

High-performance, NCL-style atmospheric & climate visualization toolkit for Matplotlib and Cartopy, powered by pure C99 native kernels.

Part of the [**Skyborn** (`skyborn-org`)](https://github.com/skyborn-org) ecosystem.

## Key Features

- **`curly_vector` & `curly_vector_key`**: Curved streamline-following vector fields with NCL-faithful thinning, closed-apex open/filled arrowheads, and L-shaped reference vector keys.
- **`arrow_contour` & `arrow_contour_clabel`**: Streamline-aligned directional contour arrows with automatic label avoidance.
- **`shadow_contourf`**: Shaded/hatched significance and terrain overlays.
- **`gradient_fill_between` / `GradientFillBetween`**: Smooth vertical/horizontal gradient fills and figure helpers (`createFigure`, `add_equal_axes`, `add_centered_axes`).

## Installation

```bash
pip install skyborn-plot
```

Optional geospatial & xarray support:

```bash
pip install "skyborn-plot[geo]"
```

Or install the full Skyborn suite:

```bash
pip install skyborn
```

## Quick Start

```python
import matplotlib.pyplot as plt
import skybornplot as splt

fig, ax = plt.subplots(figsize=(8, 4))
cv = splt.curly_vector(
    ax, lon, lat, u, v,
    density=1.2,
    arrowstyle="->",
    color=speed,
    cmap="viridis",
)
splt.curly_vector_key(ax, cv, U=10.0, label="10 m s⁻¹")
```

Note: `skyborn.plot` in the `skyborn` package seamlessly re-exports `skybornplot`.

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
