/// LLM-based text correction — local Qwen model via llama.cpp.
///
/// Port of python/engine/corrector.py.
/// Uses Qwen2.5-0.5B-Instruct in GGUF Q4 format for homophone correction.

use llama_cpp_2::context::params::LlamaContextParams;
use llama_cpp_2::llama_backend::LlamaBackend;
use llama_cpp_2::llama_batch::LlamaBatch;
use llama_cpp_2::model::params::LlamaModelParams;
use llama_cpp_2::model::{AddBos, LlamaChatMessage, LlamaModel};
use llama_cpp_2::sampling::LlamaSampler;

const SYSTEM_PROMPT: &str = "\
你是语音转录纠错助手。规则：\
1. 只纠正明显的同音字、谐音错误。\
2. 不要改变原文的意思、语序、风格和标点。\
3. 原文是什么语言就输出什么语言，不要翻译。\
4. 如果没有错误，原样输出。\
5. 只输出纠正后的文字，不要解释。";

pub struct Corrector {
    backend: Option<LlamaBackend>,
    model: Option<LlamaModel>,
    enabled: bool,
    model_path: String,
}

impl Corrector {
    pub fn new(correction_mode: &str, model_path: Option<String>) -> Self {
        let enabled = correction_mode == "local";
        Self {
            backend: None,
            model: None,
            enabled,
            model_path: model_path.unwrap_or_default(),
        }
    }

    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    /// Lazy-load the model on first correction request.
    fn ensure_loaded(&mut self) -> bool {
        if self.model.is_some() {
            return true;
        }
        if !self.enabled || self.model_path.is_empty() {
            return false;
        }
        if !std::path::Path::new(&self.model_path).exists() {
            eprintln!("[corrector] Model not found: {}", self.model_path);
            self.enabled = false;
            return false;
        }

        println!("[corrector] Loading model: {}", self.model_path);

        // llama.cpp logging goes through tracing — no separate suppress needed

        let backend = match LlamaBackend::init() {
            Ok(b) => b,
            Err(e) => {
                eprintln!("[corrector] Failed to init backend: {:?}", e);
                self.enabled = false;
                return false;
            }
        };

        let params = LlamaModelParams::default();

        // Disable GPU on non-Apple-Silicon Macs (AMD Radeon produces garbage)
        #[cfg(target_os = "macos")]
        {
            let is_apple_silicon = std::process::Command::new("sysctl")
                .args(["-n", "machdep.cpu.brand_string"])
                .output()
                .map(|o| String::from_utf8_lossy(&o.stdout).contains("Apple"))
                .unwrap_or(false);

            if !is_apple_silicon {
                println!("[corrector] Non-Apple-Silicon Mac, using CPU.");
                params = params.with_n_gpu_layers(0);
            }
        }
        let model = match LlamaModel::load_from_file(&backend, &self.model_path, &params) {
            Ok(m) => m,
            Err(e) => {
                eprintln!("[corrector] Failed to load model: {:?}", e);
                self.enabled = false;
                return false;
            }
        };

        println!("[corrector] Model loaded.");
        self.backend = Some(backend);
        self.model = Some(model);
        true
    }

    /// Correct transcription errors using local LLM.
    pub fn correct(&mut self, text: &str) -> String {
        if !self.enabled || text.is_empty() || text.trim().is_empty() {
            return text.to_string();
        }
        if !self.ensure_loaded() {
            return text.to_string();
        }

        let model = self.model.as_ref().unwrap();
        let backend = self.backend.as_ref().unwrap();

        // Build prompt using the model's chat template
        let messages = match (
            LlamaChatMessage::new("system".into(), SYSTEM_PROMPT.into()),
            LlamaChatMessage::new("user".into(), text.into()),
        ) {
            (Ok(sys), Ok(usr)) => vec![sys, usr],
            _ => return text.to_string(),
        };

        let prompt = match model.chat_template(None) {
            Ok(tmpl) => match model.apply_chat_template(&tmpl, &messages, true) {
                Ok(p) => p,
                Err(e) => {
                    eprintln!("[corrector] Chat template error: {:?}", e);
                    return text.to_string();
                }
            },
            Err(_) => {
                // Fallback: manual ChatML format for Qwen
                format!(
                    "<|im_start|>system\n{}<|im_end|>\n<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n",
                    SYSTEM_PROMPT, text
                )
            }
        };

        // Create context
        let ctx_params = LlamaContextParams::default()
            .with_n_ctx(std::num::NonZeroU32::new(512));
        let mut ctx = match model.new_context(backend, ctx_params) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[corrector] Context error: {:?}", e);
                return text.to_string();
            }
        };

        // Tokenize prompt — no extra BOS, chat template handles it
        let tokens = match model.str_to_token(&prompt, AddBos::Never) {
            Ok(t) => t,
            Err(e) => {
                eprintln!("[corrector] Tokenize error: {:?}", e);
                return text.to_string();
            }
        };

        // Feed prompt into context
        let mut batch = LlamaBatch::new(512, 1);
        for (i, &token) in tokens.iter().enumerate() {
            let is_last = i == tokens.len() - 1;
            if batch.add(token, i as i32, &[0], is_last).is_err() {
                return text.to_string();
            }
        }
        if ctx.decode(&mut batch).is_err() {
            return text.to_string();
        }

        // Generate with greedy sampling (matching Python do_sample=False)
        let mut sampler = LlamaSampler::chain_simple([LlamaSampler::greedy()]);

        let max_new_tokens = text.len() + 50;
        let mut result_tokens = Vec::new();
        let mut n_cur = tokens.len() as i32;

        for _ in 0..max_new_tokens {
            let token = sampler.sample(&ctx, batch.n_tokens() - 1);
            sampler.accept(token);

            if model.is_eog_token(token) {
                break;
            }

            result_tokens.push(token);

            batch.clear();
            if batch.add(token, n_cur, &[0], true).is_err() {
                break;
            }
            n_cur += 1;

            if ctx.decode(&mut batch).is_err() {
                break;
            }
        }

        // Detokenize — token by token using token_to_piece_bytes
        let mut result_bytes: Vec<u8> = Vec::new();
        for &tok in &result_tokens {
            match model.token_to_piece_bytes(tok, 32, false, None) {
                Ok(bytes) => result_bytes.extend_from_slice(&bytes),
                Err(_) => {}
            }
        }
        let result = String::from_utf8_lossy(&result_bytes).trim().to_string();

        if result.is_empty() {
            return text.to_string();
        }

        // Safety guard: reject if length deviates >50% (matching Python lines 98-100)
        let len_ratio = result.chars().count() as f32 / text.chars().count() as f32;
        if len_ratio > 1.5 || len_ratio < 0.5 {
            eprintln!("[corrector] Rejected (length {:.0}%): \"{}\" → \"{}\"", len_ratio * 100.0, text, result);
            return text.to_string();
        }

        if result != text {
            println!("[corrector] \"{}\" → \"{}\"", text, result);
        }

        result
    }
}
