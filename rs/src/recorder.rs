use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::SampleFormat;
use std::sync::{Arc, Mutex};

pub struct Recorder {
    target_sample_rate: u32,
    buffer: Arc<Mutex<Vec<f32>>>,
    stream: Option<cpal::Stream>,
}

impl Recorder {
    pub fn new(target_sample_rate: u32) -> Self {
        Self {
            target_sample_rate,
            buffer: Arc::new(Mutex::new(Vec::new())),
            stream: None,
        }
    }

    pub fn start(&mut self) {
        self.buffer.lock().unwrap().clear();

        let host = cpal::default_host();
        let device = host.default_input_device().expect("No input device found");

        println!("[typeoff] Audio device: {:?}", device.name());

        let supported = device
            .default_input_config()
            .expect("No default input config");

        let sample_format = supported.sample_format();
        let device_sr = supported.sample_rate().0;
        let channels = supported.channels() as usize;
        let target_sr = self.target_sample_rate;

        println!(
            "[typeoff] Device: {}Hz, {}ch, {:?} → resampling to {}Hz",
            device_sr, channels, sample_format, target_sr
        );

        let config = cpal::StreamConfig {
            channels: supported.channels(),
            sample_rate: supported.sample_rate(),
            buffer_size: cpal::BufferSize::Default,
        };

        let buffer = Arc::clone(&self.buffer);
        let resample_ratio = target_sr as f64 / device_sr as f64;

        fn process_audio(
            samples: &[f32],
            channels: usize,
            device_sr: u32,
            target_sr: u32,
            resample_ratio: f64,
            buffer: &Arc<Mutex<Vec<f32>>>,
        ) {
            // Mix to mono (no gain — cpal delivers normalized f32 on all platforms)
            let mono: Vec<f32> = if channels > 1 {
                samples
                    .chunks(channels)
                    .map(|frame| frame.iter().sum::<f32>() / channels as f32)
                    .collect()
            } else {
                samples.to_vec()
            };

            // Resample if needed
            if device_sr != target_sr {
                let out_len = (mono.len() as f64 * resample_ratio) as usize;
                let mut resampled = Vec::with_capacity(out_len);
                for i in 0..out_len {
                    let src_idx = i as f64 / resample_ratio;
                    let idx = src_idx as usize;
                    let frac = (src_idx - idx as f64) as f32;
                    let s0 = mono.get(idx).copied().unwrap_or(0.0);
                    let s1 = mono.get(idx + 1).copied().unwrap_or(s0);
                    resampled.push(s0 + (s1 - s0) * frac);
                }
                buffer.lock().unwrap().extend_from_slice(&resampled);
            } else {
                buffer.lock().unwrap().extend_from_slice(&mono);
            }
        }

        // Build stream based on device's native sample format
        let stream = match sample_format {
            SampleFormat::I16 => {
                let buffer = Arc::clone(&buffer);
                device
                    .build_input_stream(
                        &config,
                        move |data: &[i16], _: &cpal::InputCallbackInfo| {
                            let float_data: Vec<f32> =
                                data.iter().map(|&s| s as f32 / i16::MAX as f32).collect();
                            process_audio(
                                &float_data,
                                channels,
                                device_sr,
                                target_sr,
                                resample_ratio,
                                &buffer,
                            );
                        },
                        |err| eprintln!("[typeoff] Audio error: {}", err),
                        None,
                    )
                    .expect("Failed to build i16 input stream")
            }
            SampleFormat::F32 => {
                let buffer = Arc::clone(&buffer);
                device
                    .build_input_stream(
                        &config,
                        move |data: &[f32], _: &cpal::InputCallbackInfo| {
                            process_audio(
                                data,
                                channels,
                                device_sr,
                                target_sr,
                                resample_ratio,
                                &buffer,
                            );
                        },
                        |err| eprintln!("[typeoff] Audio error: {}", err),
                        None,
                    )
                    .expect("Failed to build f32 input stream")
            }
            _ => {
                let buffer = Arc::clone(&buffer);
                device
                    .build_input_stream(
                        &config,
                        move |data: &[f32], _: &cpal::InputCallbackInfo| {
                            process_audio(
                                data,
                                channels,
                                device_sr,
                                target_sr,
                                resample_ratio,
                                &buffer,
                            );
                        },
                        |err| eprintln!("[typeoff] Audio error: {}", err),
                        None,
                    )
                    .expect("Failed to build input stream")
            }
        };

        stream.play().expect("Failed to start recording");
        self.stream = Some(stream);
    }

    pub fn stop(&mut self) -> Vec<f32> {
        self.stream = None;
        let audio = self.get_audio();
        self.buffer.lock().unwrap().clear();
        audio
    }

    pub fn get_audio(&self) -> Vec<f32> {
        self.buffer.lock().unwrap().clone()
    }

    pub fn get_duration(&self) -> f32 {
        self.buffer.lock().unwrap().len() as f32 / self.target_sample_rate as f32
    }
}
