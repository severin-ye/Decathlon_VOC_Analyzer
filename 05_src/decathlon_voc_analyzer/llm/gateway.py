import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from decathlon_voc_analyzer.app.core.config import get_settings

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional until env is upgraded
    ChatOpenAI = None


class QwenChatGateway:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: OpenAI | None = None
        self._chat_model: Any | None = None

    def invoke_json(
        self,
        prompt_template: Any,
        variables: dict[str, object],
        *,
        schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        messages = prompt_template.format_messages(**variables)
        if ChatOpenAI is not None:
            return self._invoke_with_langchain(messages, schema=schema, temperature=temperature, max_tokens=max_tokens)
        return self._invoke_with_openai(messages, schema=schema, temperature=temperature, max_tokens=max_tokens)

    def _invoke_with_langchain(
        self,
        messages: list[Any],
        *,
        schema: type[BaseModel] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        model = self._get_chat_model(temperature=temperature, max_tokens=max_tokens)
        if schema is not None:
            structured_model = model.with_structured_output(schema)
            response = structured_model.invoke(messages)
            if isinstance(response, BaseModel):
                return response.model_dump(mode="json")
            if isinstance(response, dict):
                return response
        response = model.invoke(messages)
        content = self._extract_content(response.content)
        return json.loads(content or "{}")

    def _invoke_with_openai(
        self,
        messages: list[Any],
        *,
        schema: type[BaseModel] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        client = self._get_openai_client()
        response = client.chat.completions.create(
            model=self.settings.qwen_plus_model,
            temperature=self.settings.llm_temperature if temperature is None else temperature,
            max_tokens=self.settings.llm_max_tokens if max_tokens is None else max_tokens,
            response_format={"type": "json_object"},
            messages=[self._serialize_message(message) for message in messages],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        if schema is not None:
            return schema.model_validate(parsed).model_dump(mode="json")
        return parsed

    def _get_chat_model(self, *, temperature: float | None = None, max_tokens: int | None = None) -> Any:
        if self._chat_model is None or temperature is not None or max_tokens is not None:
            if ChatOpenAI is None:
                raise RuntimeError("langchain_openai is not installed")
            model = ChatOpenAI(
                api_key=self.settings.qwen_plus_api_key,
                base_url=self.settings.qwen_base_url,
                model=self.settings.qwen_plus_model,
                temperature=self.settings.llm_temperature if temperature is None else temperature,
                max_tokens=self.settings.llm_max_tokens if max_tokens is None else max_tokens,
            )
            if temperature is None and max_tokens is None:
                self._chat_model = model
            return model
        return self._chat_model

    def _get_openai_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.qwen_plus_api_key,
                base_url=self.settings.qwen_base_url,
            )
        return self._client

    def _serialize_message(self, message: Any) -> dict[str, str]:
        role = getattr(message, "type", "human")
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        elif role == "system":
            role = "system"
        else:
            role = "user"
        return {"role": role, "content": self._extract_content(message.content)}

    def _extract_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(parts)
        return str(content)