use bytemuck::{Pod, Zeroable};
use serde::Serialize;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::time::Instant;

const VERSION: &str = "1.2.7-native.1";
#[cfg(target_os = "windows")]
const BACKENDS: wgpu::Backends = wgpu::Backends::PRIMARY;
#[cfg(not(target_os = "windows"))]
const BACKENDS: wgpu::Backends = wgpu::Backends::PRIMARY;

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
struct Params {
    count: u32,
    groups_x: u32,
    _pad1: u32,
    _pad2: u32,
}

#[derive(Serialize, Clone)]
struct LumaStats {
    brightness: f64,
    highlight_ratio: f64,
    clipped_highlights: f64,
    shadow_ratio: f64,
    crushed_shadows: f64,
    dyn_range: f64,
    p50: f64,
    p95: f64,
    p99: f64,
    p999: f64,
}

#[derive(Serialize)]
struct Response<T: Serialize> {
    ok: bool,
    version: &'static str,
    backend: String,
    hardware_detected: bool,
    hardware_name: String,
    driver_version: String,
    acceleration_available: bool,
    accelerated: bool,
    elapsed_ms: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    fallback_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    stats: Option<T>,
    #[serde(skip_serializing_if = "Option::is_none")]
    timings: Option<Timings>,
}

#[derive(Serialize, Clone, Default)]
struct Timings {
    read_input_ms: f64,
    gpu_compute_ms: f64,
    total_native_ms: f64,
}

fn main() {
    let started = Instant::now();
    let args: Vec<String> = env::args().collect();
    let result = match args.get(1).map(String::as_str) {
        Some("capabilities") => capabilities(started),
        Some("self-test") => self_test(started),
        Some("luma-stats") => luma_stats_command(&args, started),
        Some("serve") => serve(),
        _ => Err("usage: shapeyourphoto_gpu_core <capabilities|self-test|luma-stats>".to_string()),
    };
    match result {
        Ok(json) => println!("{json}"),
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(2);
        }
    }
}

fn capabilities(started: Instant) -> Result<String, String> {
    let info = pollster::block_on(adapter_info());
    let response: Response<()> = match info {
        Some(info) => Response {
            ok: true,
            version: VERSION,
            backend: format!("Native GPU backend / wgpu {:?}", info.backend),
            hardware_detected: true,
            hardware_name: info.name,
            driver_version: info.driver_info,
            acceleration_available: true,
            accelerated: false,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: None,
            stats: None,
            timings: None,
        },
        None => Response {
            ok: false,
            version: VERSION,
            backend: "CPU fallback".to_string(),
            hardware_detected: false,
            hardware_name: "No compatible native GPU adapter".to_string(),
            driver_version: String::new(),
            acceleration_available: false,
            accelerated: false,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: Some("No compatible native GPU adapter was returned by wgpu.".to_string()),
            stats: None,
            timings: None,
        },
    };
    serde_json::to_string(&response).map_err(|err| err.to_string())
}

fn self_test(started: Instant) -> Result<String, String> {
    let width = 256u32;
    let height = 256u32;
    let mut pixels = Vec::with_capacity((width * height) as usize);
    for y in 0..height {
        for x in 0..width {
            let r = x as u32;
            let g = y as u32;
            let b = ((x + y) / 2) as u32;
            pixels.push((r << 16) | (g << 8) | b);
        }
    }
    let result = pollster::block_on(run_gpu_luma_stats(&pixels));
    let response = match result {
        Ok((stats, backend, hardware, driver)) => Response {
            ok: true,
            version: VERSION,
            backend,
            hardware_detected: true,
            hardware_name: hardware,
            driver_version: driver,
            acceleration_available: true,
            accelerated: true,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: None,
            stats: Some(stats),
            timings: None,
        },
        Err(reason) => Response {
            ok: false,
            version: VERSION,
            backend: "CPU fallback".to_string(),
            hardware_detected: false,
            hardware_name: "No compatible native GPU adapter".to_string(),
            driver_version: String::new(),
            acceleration_available: false,
            accelerated: false,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: Some(reason),
            stats: None,
            timings: None,
        },
    };
    serde_json::to_string(&response).map_err(|err| err.to_string())
}

fn luma_stats_command(args: &[String], started: Instant) -> Result<String, String> {
    let input = value_after(args, "--input").ok_or("--input is required")?;
    let width: u32 = value_after(args, "--width").ok_or("--width is required")?.parse().map_err(|_| "invalid --width")?;
    let height: u32 = value_after(args, "--height").ok_or("--height is required")?.parse().map_err(|_| "invalid --height")?;
    let bytes = fs::read(input).map_err(|err| err.to_string())?;
    let expected = width as usize * height as usize * 3;
    if bytes.len() != expected {
        return Err(format!("input size mismatch: got {}, expected {}", bytes.len(), expected));
    }
    let mut pixels = Vec::with_capacity(width as usize * height as usize);
    for rgb in bytes.chunks_exact(3) {
        pixels.push(((rgb[0] as u32) << 16) | ((rgb[1] as u32) << 8) | rgb[2] as u32);
    }
    let result = pollster::block_on(run_gpu_luma_stats(&pixels));
    let response = match result {
        Ok((stats, backend, hardware, driver)) => Response {
            ok: true,
            version: VERSION,
            backend,
            hardware_detected: true,
            hardware_name: hardware,
            driver_version: driver,
            acceleration_available: true,
            accelerated: true,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: None,
            stats: Some(stats),
            timings: None,
        },
        Err(reason) => Response {
            ok: false,
            version: VERSION,
            backend: "CPU fallback".to_string(),
            hardware_detected: false,
            hardware_name: "No compatible native GPU adapter".to_string(),
            driver_version: String::new(),
            acceleration_available: false,
            accelerated: false,
            elapsed_ms: elapsed_ms(started),
            fallback_reason: Some(reason),
            stats: None,
            timings: None,
        },
    };
    serde_json::to_string(&response).map_err(|err| err.to_string())
}

fn serve() -> Result<String, String> {
    let context = pollster::block_on(GpuContext::new())?;
    let stdin = io::stdin();
    let mut stdout = io::stdout();
    for line in stdin.lock().lines() {
        let started = Instant::now();
        let line = line.map_err(|err| err.to_string())?;
        if line.trim().is_empty() {
            continue;
        }
        let value: serde_json::Value = match serde_json::from_str(&line) {
            Ok(value) => value,
            Err(err) => {
                writeln!(stdout, "{{\"ok\":false,\"fallback_reason\":\"invalid JSON: {err}\"}}").ok();
                stdout.flush().ok();
                continue;
            }
        };
        if value.get("cmd").and_then(|item| item.as_str()) == Some("shutdown") {
            break;
        }
        let input = value.get("input").and_then(|item| item.as_str()).unwrap_or("");
        let width = value.get("width").and_then(|item| item.as_u64()).unwrap_or(0) as u32;
        let height = value.get("height").and_then(|item| item.as_u64()).unwrap_or(0) as u32;
        let read_started = Instant::now();
        let response = match read_rgb_pixels(input, width, height) {
            Ok(pixels) => {
                let read_input_ms = elapsed_ms(read_started);
                let compute_started = Instant::now();
                match context.compute_luma_stats(&pixels) {
                    Ok(stats) => Response {
                    ok: true,
                    version: VERSION,
                    backend: context.backend.clone(),
                    hardware_detected: true,
                    hardware_name: context.hardware_name.clone(),
                    driver_version: context.driver_version.clone(),
                    acceleration_available: true,
                    accelerated: true,
                    elapsed_ms: elapsed_ms(started),
                    fallback_reason: None,
                    stats: Some(stats),
                    timings: Some(Timings {
                        read_input_ms,
                        gpu_compute_ms: elapsed_ms(compute_started),
                        total_native_ms: elapsed_ms(started),
                    }),
                    },
                    Err(reason) => Response {
                    ok: false,
                    version: VERSION,
                    backend: "CPU fallback".to_string(),
                    hardware_detected: true,
                    hardware_name: context.hardware_name.clone(),
                    driver_version: context.driver_version.clone(),
                    acceleration_available: false,
                    accelerated: false,
                    elapsed_ms: elapsed_ms(started),
                    fallback_reason: Some(reason),
                    stats: None,
                    timings: Some(Timings {
                        read_input_ms,
                        gpu_compute_ms: elapsed_ms(compute_started),
                        total_native_ms: elapsed_ms(started),
                    }),
                    },
                }
            }
            Err(reason) => Response {
                ok: false,
                version: VERSION,
                backend: "CPU fallback".to_string(),
                hardware_detected: true,
                hardware_name: context.hardware_name.clone(),
                driver_version: context.driver_version.clone(),
                acceleration_available: false,
                accelerated: false,
                elapsed_ms: elapsed_ms(started),
                fallback_reason: Some(reason),
                stats: None,
                timings: Some(Timings {
                    read_input_ms: elapsed_ms(read_started),
                    gpu_compute_ms: 0.0,
                    total_native_ms: elapsed_ms(started),
                }),
            },
        };
        writeln!(
            stdout,
            "{}",
            serde_json::to_string(&response).map_err(|err| err.to_string())?
        )
        .map_err(|err| err.to_string())?;
        stdout.flush().map_err(|err| err.to_string())?;
    }
    Ok("{\"ok\":true,\"version\":\"1.2.6-native.1\",\"backend\":\"server stopped\"}".to_string())
}

fn read_rgb_pixels(input: &str, width: u32, height: u32) -> Result<Vec<u32>, String> {
    if input.is_empty() || width == 0 || height == 0 {
        return Err("input, width and height are required".to_string());
    }
    let bytes = fs::read(input).map_err(|err| err.to_string())?;
    let expected = width as usize * height as usize * 3;
    if bytes.len() != expected {
        return Err(format!("input size mismatch: got {}, expected {}", bytes.len(), expected));
    }
    let mut pixels = Vec::with_capacity(width as usize * height as usize);
    for rgb in bytes.chunks_exact(3) {
        pixels.push(((rgb[0] as u32) << 16) | ((rgb[1] as u32) << 8) | rgb[2] as u32);
    }
    Ok(pixels)
}

async fn adapter_info() -> Option<wgpu::AdapterInfo> {
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
        backends: BACKENDS,
        dx12_shader_compiler: Default::default(),
        flags: wgpu::InstanceFlags::empty(),
        gles_minor_version: wgpu::Gles3MinorVersion::Automatic,
    });
    let adapter = instance
        .request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: None,
            force_fallback_adapter: false,
        })
        .await?;
    Some(adapter.get_info())
}

struct GpuContext {
    device: wgpu::Device,
    queue: wgpu::Queue,
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline: wgpu::ComputePipeline,
    backend: String,
    hardware_name: String,
    driver_version: String,
}

impl GpuContext {
    async fn new() -> Result<Self, String> {
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor {
            backends: BACKENDS,
            dx12_shader_compiler: Default::default(),
            flags: wgpu::InstanceFlags::empty(),
            gles_minor_version: wgpu::Gles3MinorVersion::Automatic,
        });
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                compatible_surface: None,
                force_fallback_adapter: false,
            })
            .await
            .ok_or_else(|| "No compatible native GPU adapter was returned by wgpu.".to_string())?;
        let info = adapter.get_info();
        let (device, queue) = adapter
            .request_device(
                &wgpu::DeviceDescriptor {
                    label: Some("ShapeYourPhoto GPU device"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::downlevel_defaults(),
                },
                None,
            )
            .await
            .map_err(|err| err.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("luma histogram shader"),
            source: wgpu::ShaderSource::Wgsl(SHADER.into()),
        });
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("luma bind group layout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::COMPUTE,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Storage { read_only: true },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::COMPUTE,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Storage { read_only: false },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::COMPUTE,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("luma pipeline layout"),
            bind_group_layouts: &[&bind_group_layout],
            push_constant_ranges: &[],
        });
        let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("luma histogram pipeline"),
            layout: Some(&pipeline_layout),
            module: &shader,
            entry_point: "main",
        });
        Ok(Self {
            device,
            queue,
            bind_group_layout,
            pipeline,
            backend: format!("Native GPU backend / wgpu {:?}", info.backend),
            hardware_name: info.name,
            driver_version: info.driver_info,
        })
    }

    fn compute_luma_stats(&self, pixels: &[u32]) -> Result<LumaStats, String> {
        if pixels.is_empty() {
            return Err("empty image".to_string());
        }
        let pixel_buffer = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("pixels"),
            contents: bytemuck::cast_slice(pixels),
            usage: wgpu::BufferUsages::STORAGE,
        });
        let zero_hist = vec![0u32; 260];
        let hist_buffer = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("histogram"),
            contents: bytemuck::cast_slice(&zero_hist),
            usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC,
        });
        let total_groups = ((pixels.len() as u32) + 255) / 256;
        let groups_x = total_groups.min(65535).max(1);
        let groups_y = ((total_groups + groups_x - 1) / groups_x).max(1);
        let params = Params {
            count: pixels.len() as u32,
            groups_x,
            _pad1: 0,
            _pad2: 0,
        };
        let params_buffer = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("params"),
            contents: bytemuck::bytes_of(&params),
            usage: wgpu::BufferUsages::UNIFORM,
        });
        let readback = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("histogram readback"),
            size: (zero_hist.len() * std::mem::size_of::<u32>()) as u64,
            usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("luma bind group"),
            layout: &self.bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: pixel_buffer.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: hist_buffer.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: params_buffer.as_entire_binding(),
                },
            ],
        });
        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("luma command encoder"),
        });
        {
            let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("luma compute pass"),
                timestamp_writes: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.dispatch_workgroups(groups_x, groups_y, 1);
        }
        encoder.copy_buffer_to_buffer(&hist_buffer, 0, &readback, 0, readback.size());
        self.queue.submit(Some(encoder.finish()));

        let slice = readback.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |value| {
            let _ = tx.send(value);
        });
        self.device.poll(wgpu::Maintain::Wait);
        rx.recv().map_err(|err| err.to_string())?.map_err(|err| err.to_string())?;
        let data = slice.get_mapped_range();
        let hist: Vec<u32> = bytemuck::cast_slice(&data).to_vec();
        drop(data);
        readback.unmap();
        Ok(stats_from_histogram(&hist, pixels.len() as f64))
    }
}

async fn run_gpu_luma_stats(pixels: &[u32]) -> Result<(LumaStats, String, String, String), String> {
    let context = GpuContext::new().await?;
    let stats = context.compute_luma_stats(pixels)?;
    Ok((
        stats,
        context.backend,
        context.hardware_name,
        context.driver_version,
    ))
}

fn stats_from_histogram(hist: &[u32], total: f64) -> LumaStats {
    let mut weighted = 0f64;
    for (bin, count) in hist.iter().take(256).enumerate() {
        weighted += bin as f64 * *count as f64;
    }
    let percentile = |pct: f64| -> f64 {
        let target = (total * pct).ceil().max(1.0);
        let mut seen = 0f64;
        for (bin, count) in hist.iter().take(256).enumerate() {
            seen += *count as f64;
            if seen >= target {
                return bin as f64 / 255.0;
            }
        }
        1.0
    };
    LumaStats {
        brightness: weighted / total / 255.0,
        highlight_ratio: hist.get(256).copied().unwrap_or(0) as f64 / total,
        clipped_highlights: hist.get(257).copied().unwrap_or(0) as f64 / total,
        shadow_ratio: hist.get(258).copied().unwrap_or(0) as f64 / total,
        crushed_shadows: hist.get(259).copied().unwrap_or(0) as f64 / total,
        dyn_range: percentile(0.95) - percentile(0.05),
        p50: percentile(0.50),
        p95: percentile(0.95),
        p99: percentile(0.99),
        p999: percentile(0.999),
    }
}

fn value_after<'a>(args: &'a [String], key: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|window| window[0] == key)
        .map(|window| window[1].as_str())
}

fn elapsed_ms(started: Instant) -> f64 {
    started.elapsed().as_secs_f64() * 1000.0
}

const SHADER: &str = r#"
struct Params {
    count: u32,
    groups_x: u32,
    _pad1: u32,
    _pad2: u32,
}

@group(0) @binding(0) var<storage, read> pixels: array<u32>;
@group(0) @binding(1) var<storage, read_write> histogram: array<atomic<u32>>;
@group(0) @binding(2) var<uniform> params: Params;
var<workgroup> local_histogram: array<atomic<u32>, 260>;

@compute @workgroup_size(256)
fn main(
    @builtin(global_invocation_id) global_id: vec3<u32>,
    @builtin(local_invocation_id) local_id: vec3<u32>
) {
    let local_index = local_id.x;
    atomicStore(&local_histogram[local_index], 0u);
    if (local_index < 4u) {
        atomicStore(&local_histogram[256u + local_index], 0u);
    }
    workgroupBarrier();

    let i = global_id.x + global_id.y * params.groups_x * 256u;
    if (i < params.count) {
        let p = pixels[i];
        let r = (p >> 16u) & 255u;
        let g = (p >> 8u) & 255u;
        let b = p & 255u;
        let luma = (r * 77u + g * 150u + b * 29u) >> 8u;
        atomicAdd(&local_histogram[luma], 1u);
        if (luma >= 245u) {
            atomicAdd(&local_histogram[256], 1u);
        }
        if (luma >= 251u) {
            atomicAdd(&local_histogram[257], 1u);
        }
        if (luma <= 20u) {
            atomicAdd(&local_histogram[258], 1u);
        }
        if (luma <= 8u) {
            atomicAdd(&local_histogram[259], 1u);
        }
    }
    workgroupBarrier();

    let value = atomicLoad(&local_histogram[local_index]);
    if (value > 0u) {
        atomicAdd(&histogram[local_index], value);
    }
    if (local_index < 4u) {
        let extra_index = 256u + local_index;
        let extra_value = atomicLoad(&local_histogram[extra_index]);
        if (extra_value > 0u) {
            atomicAdd(&histogram[extra_index], extra_value);
        }
    }
}
"#;

mod util {
    pub use wgpu::util::DeviceExt;
}

use util::*;
