from __future__ import annotations
import os, time
from typing import Optional, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError

def _get_conf(key: str, default=None):
    try:
        import frappe
        conf = getattr(frappe, "conf", {}) or {}
        val = conf.get(key)
        if val not in (None, ""):
            return val
    except Exception:
        pass
    return os.getenv(key, default)

class LLMConfig:
    def __init__(self):
        # 'local' only — no fallback unless you later switch to 'auto' or 'cloud'
        self.provider: str      = _get_conf("LLM_PROVIDER", "local")
        self.base_url: str      = _get_conf("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        self.api_key: str       = _get_conf("LLM_API_KEY", "ollama")
        self.model: str         = _get_conf("LLM_MODEL", "mistral:instruct")
        self.temperature: float = float(_get_conf("LLM_TEMPERATURE", "0.1"))
        self.max_tokens: int    = int(_get_conf("LLM_MAX_TOKENS", "1536"))
        self.cloud_base_url: str = _get_conf("CLOUD_BASE_URL", "https://api.openai.com/v1")
        self.cloud_api_key: str  = _get_conf("CLOUD_API_KEY", "")
        self.cloud_model: str    = _get_conf("CLOUD_MODEL", "gpt-4o-mini")

STOP_SEQUENCES = ["\n\n# DONE", "<|stop|>"]

class CircuitBreaker(Exception): ...
class LLMClient:
    def __init__(self, cfg: Optional[LLMConfig] = None):
        self.cfg = cfg or LLMConfig()
        self.local = OpenAI(base_url=self.cfg.base_url, api_key=self.cfg.api_key)
        self._fail_window: List[float] = []

    def _check_circuit(self):
        now = time.time()
        self._fail_window = [t for t in self._fail_window if now - t < 90]
        if len(self._fail_window) >= 3 and now - self._fail_window[-1] < 30:
            raise CircuitBreaker("LLM circuit open; try later")

    def _record_fail(self):
        self._fail_window.append(time.time())

    def _call(self, client: OpenAI, model: str, messages: list, streaming: bool) -> Any:
        if streaming:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=self.cfg.temperature,
                max_tokens=self.cfg.max_tokens, stop=STOP_SEQUENCES, stream=True
            )
            def gen():
                for evt in resp:
                    yield evt.choices[0].delta.content or ""
            return gen()
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens, stop=STOP_SEQUENCES
        )
        return resp.choices[0].message.content

    @retry(
        reraise=True,
        retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
    )
    def complete(self, system: str, user: str, streaming: bool=False) -> Any:
        self._check_circuit()
        msgs = [{"role":"system","content":system},{"role":"user","content":user}]
        try:
            return self._call(self.local, self.cfg.model, msgs, streaming)
        except APIConnectionError:
            self._record_fail()
            raise
        except (APIStatusError, RateLimitError):
            self._record_fail()
            raise

PLANNER_SYSTEM = (
    "You are an ERPNext/Frappe agent planner.\n"
    "ONLY return machine-executable tool calls; DO NOT describe UI navigation.\n"
    "Available tools: create_doctype, update_doctype, create_workflow, create_query_report, "
    "create_script_report, run_sql, run_report, get_sales_stats, get_purchase_stats, "
    "get_inventory_snapshot, create_task, enqueue_background_job.\n"
    "Return STRICT JSON: {\"intent\": <one of: analytics|structural_change|reporting|tasking>, "
    "\"steps\": [{\"tool\": <tool_name>, \"args\": {...}}], "
    "\"risks\": [\"...\"], \"confirm_required\": <true|false>}.\n"
    "Limit steps<=8. Use safe defaults. No prose, no UI steps."
)
