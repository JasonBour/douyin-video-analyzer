#!/usr/bin/env python3
"""通义听悟离线转写：本地音频文件 → 逐字稿文本。

流程：
1. 读取 chubby_common/config.py 中的三件套（AccessKey ID/Secret + AppKey）
2. 将本地音频上传到阿里云 OSS（自动创建 bucket，同一 AccessKey）
3. 调用通义听悟 CreateTask（type=offline）创建离线转写任务
4. 轮询 GetTaskInfo 直到任务完成
5. 下载转写结果 JSON，提取纯文本逐字稿，写入输出文件

用法：
    python tingwu_transcribe.py <audio_path> <output_txt> [--source-lang cn] [--max-wait 600]

依赖：aliyun-python-sdk-core, oss2, PyAV(可选)
"""

import sys
import os
import json
import time
import random
import string
import datetime
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "chubby_common"))
import config

REGION = config.TINGWU_REGION or "cn-beijing"
DOMAIN = f"tingwu.{REGION}.aliyuncs.com"
VERSION = "2023-09-30"

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential


def make_request(method, uri):
    req = CommonRequest()
    req.set_accept_format('json')
    req.set_domain(DOMAIN)
    req.set_version(VERSION)
    req.set_protocol_type('https')
    req.set_method(method)
    req.set_uri_pattern(uri)
    req.add_header('Content-Type', 'application/json')
    return req


def ensure_oss_bucket(bucket_name, region):
    """确保 OSS bucket 存在（不存在则创建）。"""
    import oss2
    auth = oss2.Auth(config.TINGWU_ACCESS_KEY_ID, config.TINGWU_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, f"https://oss-{region}.aliyuncs.com", bucket_name)
    try:
        bucket.get_bucket_info()
    except oss2.exceptions.NoSuchBucket:
        print(f"[OSS] 创建 bucket: {bucket_name}", file=sys.stderr)
        bucket.create_bucket(oss2.BUCKET_ACL_PRIVATE)
    except oss2.exceptions.ServerError as e:
        raise RuntimeError(f"OSS 访问失败: {e.code} {e.message}")
    return bucket


def upload_to_oss(local_path, region):
    """上传本地文件到 OSS，返回带签名的公网 URL。"""
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"音频文件不存在: {local_path}")

    # 固定 bucket 名（基于 AK ID 派生），复用而非每次新建
    ak_tail = (config.TINGWU_ACCESS_KEY_ID or "default")[-8:].lower()
    bucket_name = "tingwu-transcribe-" + ak_tail
    bucket = ensure_oss_bucket(bucket_name, region)

    key = "audio/" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + os.path.basename(local_path)
    print(f"[OSS] 上传 {local_path} -> {key} ({os.path.getsize(local_path)/1024/1024:.1f} MB)", file=sys.stderr)
    bucket.put_object_from_file(key, local_path)

    # 签名 URL，有效期 2 小时，覆盖转写与结果下载
    url = bucket.sign_url("GET", key, 7200)
    return url


def create_task(file_url, task_key, source_lang="cn"):
    """创建离线转写任务，返回 TaskId。"""
    credentials = AccessKeyCredential(config.TINGWU_ACCESS_KEY_ID, config.TINGWU_ACCESS_KEY_SECRET)
    client = AcsClient(region_id=REGION, credential=credentials)

    req = make_request('PUT', '/openapi/tingwu/v2/tasks')
    req.add_query_param('type', 'offline')
    body = {
        "AppKey": config.TINGWU_APP_KEY,
        "Input": {
            "FileUrl": file_url,
            "SourceLanguage": source_lang,
            "TaskKey": task_key,
        },
    }
    req.set_content(json.dumps(body).encode('utf-8'))
    resp = json.loads(client.do_action_with_exception(req))
    if resp.get("Code") != "0":
        raise RuntimeError(f"CreateTask 失败: {resp}")
    return resp["Data"]["TaskId"]


def get_task(task_id):
    """查询任务状态与结果。"""
    credentials = AccessKeyCredential(config.TINGWU_ACCESS_KEY_ID, config.TINGWU_ACCESS_KEY_SECRET)
    client = AcsClient(region_id=REGION, credential=credentials)
    req = make_request('GET', f'/openapi/tingwu/v2/tasks/{task_id}')
    resp = json.loads(client.do_action_with_exception(req))
    return resp


def extract_transcript_from_result(result_obj):
    """从转写结果中提取纯文本。兼容通义听悟多种返回结构。

    已确认的结构：{TaskId, Transcription: {AudioInfo, Paragraphs: [
        {ParagraphId, SpeakerId, Words: [{Id, SentenceId, Start, End, Text}]}
    ]}}
    """
    import re
    texts = []
    try:
        # 兼容两层结构：带 Transcription 包装 或 直接是结果对象
        obj = result_obj.get("Transcription", result_obj)
        paragraphs = obj.get("Paragraphs") or obj.get("paragraphs") or []
        for p in paragraphs:
            if not isinstance(p, dict):
                continue
            if p.get("Text"):
                texts.append(p["Text"])
                continue
            words = p.get("Words") or p.get("words") or []
            # 按 SentenceId 分组还原句子
            sentences = {}
            for w in words:
                if not isinstance(w, dict):
                    continue
                sid = w.get("SentenceId")
                t = w.get("Text") or w.get("text") or ""
                if not t:
                    continue
                sentences.setdefault(sid, []).append(t)
            for sid in sorted(sentences.keys(), key=lambda x: (x is None, x)):
                parts = sentences[sid]
                # 词间拼接：连续 ASCII 字母/数字之间补空格，其余直接连
                buf = ""
                for i, tok in enumerate(parts):
                    if i > 0 and re.fullmatch(r"[A-Za-z0-9]+", parts[i - 1]) and re.fullmatch(r"[A-Za-z0-9]+", tok):
                        buf += " " + tok
                    else:
                        buf += tok
                if buf.strip():
                    texts.append(buf)
        if not texts:
            # 兜底：顶层 Sentences / Words
            for key in ("Sentences", "sentences"):
                sents = obj.get(key) or []
                for s in sents:
                    if isinstance(s, dict) and s.get("Text"):
                        texts.append(s["Text"])
            if not texts:
                for key in ("Words", "words"):
                    words = obj.get(key) or []
                    buf = ""
                    for w in words:
                        if isinstance(w, dict):
                            buf += w.get("Text") or w.get("text") or ""
                    if buf.strip():
                        texts.append(buf)
    except Exception as e:
        print(f"[WARN] 转写结果解析异常: {e}", file=sys.stderr)
    return "\n".join(t for t in texts if t.strip())


def poll_and_fetch(task_id, output_txt, max_wait=600, poll_interval=10):
    """轮询任务直到完成，下载并解析转写结果。"""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = get_task(task_id)
        data = resp.get("Data", {})
        status = data.get("TaskStatus")
        print(f"[Tingwu] 任务状态: {status}", file=sys.stderr)
        if status == "COMPLETED":
            result = data.get("Result", {})
            transcription_url = result.get("Transcription")
            if not transcription_url:
                # 部分返回结构将结果放在 Result 对象内部
                transcription_url = data.get("Transcription")
            if not transcription_url:
                raise RuntimeError("任务完成但未找到转写结果 URL")
            print(f"[Tingwu] 下载转写结果...", file=sys.stderr)
            import urllib.request
            with urllib.request.urlopen(transcription_url, timeout=60) as r:
                result_obj = json.loads(r.read().decode("utf-8"))
            # 调试：保存原始 JSON，便于排查解析问题
            try:
                raw_path = output_txt.rsplit(".", 1)[0] + ".raw.json"
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(result_obj, f, ensure_ascii=False, indent=2)
                print(f"[Tingwu] 原始结果已保存: {raw_path}", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] 原始结果保存失败: {e}", file=sys.stderr)
            return extract_transcript_from_result(result_obj)
        if status == "FAILED":
            raise RuntimeError(f"转写任务失败: {json.dumps(data, ensure_ascii=False)}")
        time.sleep(poll_interval)
    raise TimeoutError(f"任务 {task_id} 在 {max_wait}s 内未完成")


def main():
    parser = argparse.ArgumentParser(description="通义听悟离线转写")
    parser.add_argument("audio_path", help="本地音频文件路径（wav/mp3/m4a 等）")
    parser.add_argument("output_txt", help="逐字稿输出 txt 路径")
    parser.add_argument("--source-lang", default="cn", help="源语言，默认 cn")
    parser.add_argument("--max-wait", type=int, default=600, help="最大等待秒数")
    args = parser.parse_args()

    if not config.tingwu_configured():
        print("ERROR: 通义听悟三件套未配置完整。请检查 chubby_common/config.py 中的 "
              "TINGWU_ACCESS_KEY_ID / TINGWU_ACCESS_KEY_SECRET / TINGWU_APP_KEY。",
              file=sys.stderr)
        sys.exit(1)

    task_key = "task" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "".join(random.choices(string.digits, k=4))

    try:
        url = upload_to_oss(args.audio_path, REGION)
        task_id = create_task(url, task_key, args.source_lang)
        print(f"[Tingwu] 任务已创建: {task_id}", file=sys.stderr)
        transcript = poll_and_fetch(task_id, args.output_txt, max_wait=args.max_wait)
        if not transcript.strip():
            print("WARN: 转写结果为空（可能音频无人声或纯音乐）", file=sys.stderr)
        with open(args.output_txt, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"SUCCESS: 逐字稿已保存到 {args.output_txt}（{len(transcript)} 字）", file=sys.stderr)
        print(transcript[:1000])
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
