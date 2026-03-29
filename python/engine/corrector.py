"""LLM-based text correction — local model or API."""

SYSTEM_PROMPT = (
    "你是语音转录纠错助手。规则："
    "1. 只纠正明显的同音字、谐音错误。"
    "2. 不要改变原文的意思、语序、风格和标点。"
    "3. 原文是什么语言就输出什么语言，不要翻译。"
    "4. 如果没有错误，原样输出。"
    "5. 只输出纠正后的文字，不要解释。"
)


class Corrector:
    """Text correction via LLM. Supports local model and API (future).

    Config:
        correction_mode: "off" | "local" | "api"
        correction_model: model ID for local (default: Qwen/Qwen2.5-0.5B-Instruct)
        correction_api_url: API endpoint (future)
        correction_api_key: API key (future)
    """

    def __init__(self, config):
        self._config = config
        self._mode = config.get("correction_mode", "off")
        self._model = None
        self._tokenizer = None
        self._device = None

    @property
    def enabled(self):
        return self._mode != "off"

    def load(self):
        """Load model (lazy, only when first correction is requested)."""
        if self._model is not None:
            return

        if self._mode == "local":
            self._load_local()
        # "api" mode doesn't need preloading

    def _load_local(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = self._config.get("correction_model", "Qwen/Qwen2.5-0.5B-Instruct")
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"[typeoff] Loading correction model ({model_id}) on {self._device}...")
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
            device_map=self._device,
            trust_remote_code=True,
        )
        self._model.eval()
        print(f"[typeoff] Correction model loaded.")

    def correct(self, text):
        """Correct transcription errors. Returns corrected text."""
        if not text or not text.strip() or not self.enabled:
            return text

        if self._mode == "local":
            return self._correct_local(text)
        elif self._mode == "api":
            return self._correct_api(text)
        return text

    def _correct_local(self, text):
        self.load()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

        input_text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(input_text, return_tensors="pt").to(self._device)

        import torch
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=len(text) + 50,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[1]:]
        result = self._tokenizer.decode(generated, skip_special_tokens=True).strip()

        # Safety: if result length deviates too much, keep original
        if len(result) > len(text) * 1.5 or len(result) < len(text) * 0.5:
            print(f"[corrector] rejected (length): \"{text}\" → \"{result}\"")
            return text

        if result != text:
            print(f"[corrector] \"{text}\" → \"{result}\"")

        return result

    def _correct_api(self, text):
        """API-based correction (future). Placeholder."""
        # TODO: implement API call to OpenAI/Anthropic/custom endpoint
        # url = self._config.get("correction_api_url")
        # key = self._config.get("correction_api_key")
        return text

    def unload(self):
        """Release model memory."""
        self._model = None
        self._tokenizer = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
