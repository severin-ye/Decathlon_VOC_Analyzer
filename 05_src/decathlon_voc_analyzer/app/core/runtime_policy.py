import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from decathlon_voc_analyzer.app.core.config import Settings, get_settings


class RuntimeExecutionPolicy(BaseModel):
    allow_degradation: bool = True
    full_power: bool = False


class RuntimePolicyError(RuntimeError):
    def __init__(self, *, component: str, problem: str, action: str) -> None:
        self.component = component
        self.problem = problem
        self.action = action
        super().__init__(self.render())

    def render(self) -> str:
        return (
            "[Error] Runtime policy blocked automatic degradation\n"
            f"       component = {self.component}\n"
            f"       problem = {self.problem}\n"
            f"       action = {self.action}"
        )


@lru_cache(maxsize=8)
def _load_runtime_execution_policy(path_str: str) -> RuntimeExecutionPolicy:
    path = Path(path_str)
    if not path.exists():
        return RuntimeExecutionPolicy()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimePolicyError(
            component="runtime_policy",
            problem=f"Runtime policy config file is not a JSON object: {path}",
            action=f"Fix {path} to be a JSON object, e.g. {{\"allow_degradation\": true, \"full_power\": false}}.",
        )
    return RuntimeExecutionPolicy.model_validate(payload)


def get_runtime_execution_policy(settings: Settings | None = None) -> RuntimeExecutionPolicy:
    active_settings = settings or get_settings()
    return _load_runtime_execution_policy(str(active_settings.runtime_execution_policy_path.resolve()))


def should_forbid_degradation(policy: RuntimeExecutionPolicy) -> bool:
    return policy.full_power or not policy.allow_degradation


def _relax_guidance(settings: Settings) -> str:
    return (
        f"To allow degradation, modify {settings.runtime_execution_policy_path}, "
        "set full_power to false or set allow_degradation to true."
    )


def require_full_power_request(component: str, use_llm: bool, settings: Settings) -> RuntimeExecutionPolicy:
    policy = get_runtime_execution_policy(settings)
    if policy.full_power and not use_llm:
        raise RuntimePolicyError(
            component=component,
            problem="full_power=true, but current request disabled LLM chain.",
            action="Remove --no-llm or set use_llm to true in request.",
        )
    return policy


def resolve_llm_permission(component: str, use_llm: bool, settings: Settings) -> tuple[bool, str | None]:
    policy = require_full_power_request(component, use_llm, settings)
    if not use_llm:
        return False, None
    if settings.qwen_plus_api_key:
        return True, None

    problem = "LLM path requested but QWEN_PLUS_API_KEY / qwen-plus_api is missing, cannot call qwen-plus."
    action = (
        "Configure QWEN_PLUS_API_KEY / qwen-plus_api in workspace root .env or current environment variables and retry."
        f" {_relax_guidance(settings)}"
    )
    if should_forbid_degradation(policy):
        raise RuntimePolicyError(component=component, problem=problem, action=action)
    return False, f"{component}: {problem} degraded to heuristic."


def handle_llm_failure(component: str, exc: Exception, settings: Settings) -> str:
    policy = get_runtime_execution_policy(settings)
    problem = f"LLM call failed, silent degradation not allowed by current policy. Original error: {exc}"
    action = (
        "Check API Key, network connectivity, model service status or quota and retry."
        f" {_relax_guidance(settings)}"
    )
    if should_forbid_degradation(policy):
        raise RuntimePolicyError(component=component, problem=problem, action=action) from exc
    return f"{component}: LLM call failed, degraded to heuristic ({exc})"


def validate_full_power_prerequisites(*, use_llm: bool, retrieval_backend: str, settings: Settings) -> RuntimeExecutionPolicy:
    policy = require_full_power_request("workflow_preflight", use_llm, settings)
    if not policy.full_power:
        return policy

    issues: list[str] = []
    if retrieval_backend != "qdrant":
        issues.append("retrieval_backend is not qdrant")
    if settings.embedding_backend != "local_qwen3":
        issues.append(f"embedding_backend={settings.embedding_backend}, strict mode expects local_qwen3")
    if settings.reranker_backend != "local_qwen3":
        issues.append(f"reranker_backend={settings.reranker_backend}, strict mode expects local_qwen3")
    if settings.multimodal_reranker_backend != "local_qwen3_vl":
        issues.append(
            f"multimodal_reranker_backend={settings.multimodal_reranker_backend}, strict mode expects local_qwen3_vl"
        )

    if issues:
        raise RuntimePolicyError(
            component="workflow_preflight",
            problem="Full power prerequisites not met: " + "; ".join(issues),
            action=(
                "Fix the above dependencies and retry."
                f" Current policy file: {settings.runtime_execution_policy_path}."
            ),
        )
    return policy