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
            "[错误] 运行策略阻止了自动降级\n"
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
            problem=f"运行策略配置文件不是 JSON object: {path}",
            action=f"将 {path} 修正为 JSON 对象，例如 {{\"allow_degradation\": true, \"full_power\": false}}。",
        )
    return RuntimeExecutionPolicy.model_validate(payload)


def get_runtime_execution_policy(settings: Settings | None = None) -> RuntimeExecutionPolicy:
    active_settings = settings or get_settings()
    return _load_runtime_execution_policy(str(active_settings.runtime_execution_policy_path.resolve()))


def should_forbid_degradation(policy: RuntimeExecutionPolicy) -> bool:
    return policy.full_power or not policy.allow_degradation


def _relax_guidance(settings: Settings) -> str:
    return (
        f"如需允许降级，请修改 {settings.runtime_execution_policy_path}，"
        "将 full_power 设为 false 或将 allow_degradation 设为 true。"
    )


def require_full_power_request(component: str, use_llm: bool, settings: Settings) -> RuntimeExecutionPolicy:
    policy = get_runtime_execution_policy(settings)
    if policy.full_power and not use_llm:
        raise RuntimePolicyError(
            component=component,
            problem="full_power=true，但当前请求关闭了 LLM 链路。",
            action="移除 --no-llm 或将请求中的 use_llm 改为 true。",
        )
    return policy


def resolve_llm_permission(component: str, use_llm: bool, settings: Settings) -> tuple[bool, str | None]:
    policy = require_full_power_request(component, use_llm, settings)
    if not use_llm:
        return False, None
    if settings.qwen_plus_api_key:
        return True, None

    problem = "请求了 LLM 路径，但缺少 QWEN_PLUS_API_KEY / qwen-plus_api，无法调用 qwen-plus。"
    action = (
        "在工作区根目录 .env 或当前环境变量中配置 QWEN_PLUS_API_KEY / qwen-plus_api 后重试。"
        f" {_relax_guidance(settings)}"
    )
    if should_forbid_degradation(policy):
        raise RuntimePolicyError(component=component, problem=problem, action=action)
    return False, f"{component}: {problem} 已降级为 heuristic。"


def handle_llm_failure(component: str, exc: Exception, settings: Settings) -> str:
    policy = get_runtime_execution_policy(settings)
    problem = f"LLM 调用失败，当前策略不允许静默回退。原始错误: {exc}"
    action = (
        "检查 API Key、网络连通性、模型服务状态或配额后重试。"
        f" {_relax_guidance(settings)}"
    )
    if should_forbid_degradation(policy):
        raise RuntimePolicyError(component=component, problem=problem, action=action) from exc
    return f"{component}: LLM 调用失败，已降级为 heuristic ({exc})"


def validate_full_power_prerequisites(*, use_llm: bool, retrieval_backend: str, settings: Settings) -> RuntimeExecutionPolicy:
    policy = require_full_power_request("workflow_preflight", use_llm, settings)
    if not policy.full_power:
        return policy

    issues: list[str] = []
    if not settings.qwen_plus_api_key:
        issues.append("缺少 QWEN_PLUS_API_KEY / qwen-plus_api")
    if retrieval_backend != "qdrant":
        issues.append("retrieval_backend 不是 qdrant")
    if settings.embedding_backend != "api":
        issues.append(f"embedding_backend={settings.embedding_backend}，期望 api")
    if settings.reranker_backend != "api":
        issues.append(f"reranker_backend={settings.reranker_backend}，期望 api")
    if settings.multimodal_reranker_backend not in {"qwen_vl", "api"}:
        issues.append(
            f"multimodal_reranker_backend={settings.multimodal_reranker_backend}，期望 qwen_vl 或 api"
        )

    if issues:
        raise RuntimePolicyError(
            component="workflow_preflight",
            problem="满血版前置条件不满足: " + "; ".join(issues),
            action=(
                "补齐上述依赖后重新运行。"
                f" 当前策略文件: {settings.runtime_execution_policy_path}。"
            ),
        )
    return policy