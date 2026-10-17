#!/usr/bin/env python3
"""Run the built workspace locally with a backend-only, in-memory API key."""
from __future__ import annotations

import argparse
from dataclasses import replace
import getpass
import hashlib
import os
from pathlib import Path
import socket
import sys
import threading
import warnings
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.staticfiles import StaticFiles  # noqa: E402
import uvicorn  # noqa: E402
from backend.app.api import create_app  # noqa: E402
from backend.app.providers.config import ProviderSettings  # noqa: E402
from backend.app.providers.transport import STRUCTURED_VISION_MODELS, TIMESTAMP_MODELS  # noqa: E402
from backend.app.service import WorkflowService  # noqa: E402


def read_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        print("请粘贴 OpenAI API Key 后按回车（输入不会显示，也不会保存到文件）。", flush=True)
        # Never fall back to echoed stdin when no secure terminal is available.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                key = getpass.getpass("API Key: ").strip()
            except (getpass.GetPassWarning, EOFError) as exc:
                raise ValueError("请在本机 Terminal / PowerShell 中运行启动程序，再输入密钥。") from exc
    if not key or any(character.isspace() for character in key) or not key.isascii():
        raise ValueError("API Key 为空或包含无效字符，请重新复制完整密钥。")
    return key


def local_settings(data_dir: Path, api_key: str) -> ProviderSettings:
    settings = replace(
        ProviderSettings.from_env(), api_key=api_key, cache_dir=data_dir / "provider-cache",
        timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        # A failed first experiment must not silently start another paid attempt.
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
        analysis_language=os.getenv("ANALYSIS_OUTPUT_LANGUAGE", "Chinese"),
    )
    if not settings.api_key:
        raise ValueError("Live mode requires a backend API key.")
    text_models = (settings.vision_model, settings.creative_model, settings.m2_model)
    if any(model not in STRUCTURED_VISION_MODELS for model in text_models):
        raise ValueError("当前适配器尚不支持所配置的文本/视觉模型，请检查 LOCAL_API.md。")
    if settings.transcription_model not in TIMESTAMP_MODELS:
        raise ValueError("当前时间戳转写适配器要求 whisper-1，请检查 LOCAL_API.md。")
    return settings


def prepare_reference(service: WorkflowService, source: Path) -> str:
    """Import supplied real media once; never analyze, apply, or approve it."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    for state in service.store.list():
        # A tombstone also counts: reopening must respect an explicit deletion.
        if any(video.content_sha256 == digest for video in state.videos):
            return state.task.task_id
    state = service.create("掼蛋视频 · 真实识别实验")
    with source.open("rb") as stream:
        state = service.upload(state.task.task_id, state.task.version, source.name, stream)
    return state.task.task_id


def local_app(data_dir: Path, settings: ProviderSettings, reference: Path | None = None):
    service = WorkflowService(data_dir, provider_settings=settings)
    if reference is not None:
        prepare_reference(service, reference)
    app = create_app(service=service)
    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="workspace")
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data" / "live")
    parser.add_argument("--reference", type=Path, help="Prepare a real video without analyzing it")
    parser.add_argument("--no-open", action="store_true", help="Do not open this machine's browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        parser.error("Built frontend missing. Use scripts/start-local.sh or scripts/start-local.ps1.")
    reference = args.reference
    bundled_reference = ROOT / "samples" / "guandan-reference.mp4"
    if reference is None and bundled_reference.is_file():
        reference = bundled_reference
    if reference is not None and not reference.is_file():
        parser.error("Reference file not found.")
    # Reserve the loopback socket before accepting credentials or importing data.
    # Do not open a browser pointing at an unrelated process occupying this port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", args.port))
        except OSError:
            parser.error(f"端口 {args.port} 已被占用。关闭旧服务，或启动时加 --port {args.port + 1}。")
        try:
            settings = local_settings(args.data_dir, read_api_key())
        except ValueError as exc:
            parser.error(str(exc))
        app = local_app(args.data_dir, settings, reference)
        address = f"http://127.0.0.1:{args.port}"
        print(f"\nVideo Anatomy: {address}\n任务保存在: {args.data_dir.resolve()}", flush=True)
        print("密钥已在后端内存中配置；尚未验证 API 权限或余额。", flush=True)
        print(f"视觉 / 创意 / Brief: {settings.vision_model} / {settings.creative_model} / {settings.m2_model}")
        print(f"语音: {settings.transcription_model}；自动重试: {settings.max_retries}")
        print("启动和上传不调用模型；点击分析或 AI 生成后会使用 API 余额。", flush=True)
        print("停止服务：Ctrl+C。下次启动可重新输入密钥；已保存任务会保留。", flush=True)
        if not args.no_open:
            @app.on_event("startup")
            async def open_browser():
                timer = threading.Timer(1, webbrowser.open, args=(address,))
                timer.daemon = True
                timer.start()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port))
        server.run(sockets=[listener])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
