# ShapeYourPhoto Native GPU Core

This is the bundled GPU backend for ShapeYourPhoto v1.2.6.

It is a Rust command line component built into release packages as
`gpu/shapeyourphoto_gpu_core.exe`. The Python app calls it through a small JSON
protocol. Users do not install Rust, CUDA Toolkit, torch, CuPy, or OpenCV CUDA.

Supported commands:

- `capabilities`
- `self-test`
- `luma-stats --input <rgb-raw> --width <w> --height <h>`

The current accelerated path computes the analysis luma histogram, percentiles,
and exposure counters on the selected native GPU adapter through `wgpu`
(D3D12/Vulkan on Windows, depending on driver support). Large images use a 2D
workgroup dispatch so the backend stays within WebGPU limits across NVIDIA,
AMD, and integrated GPUs. If the adapter or shader path fails, the Python app
logs the reason and automatically uses its existing CPU path.

The Python caller only routes large enough analysis images through this backend;
small repair/comparison thumbnails remain on CPU until a benchmark proves the
GPU path is faster.
