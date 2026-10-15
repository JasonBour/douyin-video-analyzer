#!/usr/bin/env python3
"""通义听悟离线转写（纯标准库版，无第三方 SDK 依赖）。

替代 aliyunsdkcore + oss2：
- OSS 上传：OSS V1 签名（HMAC-SHA1）
- CreateTask / GetTaskInfo：阿里云 ROA acs 签名

用法：
    python tingwu_std.py <audio_path> <output_txt> [--source-lang cn] [--max-wait 1800]
"""
import sys
import os
import json
import time
import hashlib
import base64
import hmac
import email.utils
import urllib.request
import urllib.parse
import datetime
import argparse

_CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "chubby_common"),
    "/Users/jason/Library/Application Support/DoubaoWork/Default/.doubaowork/agent_mode/workspace/.user_skills/douyin-video-analyzer/scripts/chubby_common",
]
for _p in _CANDIDATE_PATHS:
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
import config

REGION = config.TINGWU_REGION or "cn-beijing"
DOMAIN = f"tingwu.{REGION}.aliyuncs.com"
VERSION = "2023-09-30"

AK_ID = config.TINGWU_ACCESS_KEY_ID
AK_SECRET = config.TINGWU_ACCESS_KEY_SECRET
APP_KEY = config.TINGWU_APP_KEY


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _md5_b64(data: bytes) -> str:
    return _b64(hashlib.md5(data).digest())


def _hmac_sha1(key: str, msg: str) -> str:
    return _b64(hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha1).digest())


def _gmt() -> str:
    return email.utils.formatdate(usegmt=True)


def oss_upload(local_path, region=REGION):
    """上传到 OSS，返回 2 小时签名 URL。"""
    import random
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)

    ak_tail = (AK_ID or "default")[-8:].lower()
    bucket_name = "tingwu-transcribe-" + ak_tail
    key = "audio/" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "_" + os.path.basename(local_path)

    host = f"https://{bucket_name}.oss-{region}.aliyuncs.com"
    url = f"{host}/{key}"
    date = _gmt()
    content_type = "application/octet-stream"

    with open(local_path, "rb") as f:
        data = f.read()
    content_md5 = _md5_b64(data)

    string_to_sign = f"PUT\n{content_md5}\n{content_type}\n{date}\n/{bucket_name}/{key}"
    signature = _hmac_sha1(AK_SECRET, string_to_sign)

    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Date", date)
    req.add_header("Content-Type", content_type)
    req.add_header("Content-MD5", content_md5)
    req.add_header("Authorization", f"OSS {AK_ID}:{signature}")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OSS 上传失败 {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")

    # 签名 URL（GET，2 小时）
    expires = str(int(time.time()) + 7200)
    sig_url = _hmac_sha1(AK_SECRET, f"GET\n\n\n{expires}\n/{bucket_name}/{key}")
    signed = f"{host}/{key}?OSSAccessKeyId={urllib.parse.quote(AK_ID)}&Expires={expires}&Signature={urllib.parse.quote(sig_url)}"
    print(f"[OSS] 上传完成 {len(data)/1024/1024:.1f} MB -> {bucket_name}/{key}", file=sys.stderr)
    return signed


def roa_sign(method, uri_pattern, query=None, body=None, date=None):
    """构造阿里云 ROA 签名 header。返回 (headers, auth)。"""
    if date is None:
        date = _gmt()
    accept = "application/json"
    content_type = "application/json"
    content_md5 = _md5_b64(body) if body else ""
    if body is None:
        content_type = ""

    # CanonicalizedResource: path + 排序后的 query
    canon_resource = uri_pattern
    if query:
        items = sorted(query.items())
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in items)
        canon_resource = f"{uri_pattern}?{qs}"

    string_to_sign = f"{method}\n{accept}\n{content_md5}\n{content_type}\n{date}\n{canon_resource}"
    signature = _hmac_sha1(AK_SECRET, string_to_sign)
    auth = f"acs {AK_ID}:{signature}"

    headers = {"Accept": accept, "Date": date}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-MD5"] = content_md5
    return headers, auth


def create_task(file_url, source_lang="cn"):
    """创建离线转写任务，返回 TaskId。"""
    task_key = "task" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    uri = "/openapi/tingwu/v2/tasks"
    query = {"type": "offline"}
    body = json.dumps({
        "AppKey": APP_KEY,
        "Input": {
            "FileUrl": file_url,
            "SourceLanguage": source_lang,
            "TaskKey": task_key,
        },
    }).encode("utf-8")

    headers, auth = roa_sign("PUT", uri, query=query, body=body)
    url = f"https://{DOMAIN}{uri}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, data=body, method="PUT")
    for k, v in headers.items():
        req.add_header(k, v)
    req.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"CreateTask HTTP {e.code}: {e.read().decode('utf-8','ignore')[:400]}")

    if resp.get("Code") != "0":
        raise RuntimeError(f"CreateTask 失败: {json.dumps(resp, ensure_ascii=False)[:400]}")
    return resp["Data"]["TaskId"]


def get_task(task_id):
    uri = f"/openapi/tingwu/v2/tasks/{task_id}"
    headers, auth = roa_sign("GET", uri)
    url = f"https://{DOMAIN}{uri}"
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    req.add_header("Authorization", auth)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def extract_transcript(result_obj):
    """按 SentenceId 分组拼接 Words（通义真实返回结构）。"""
    sentences = {}
    try:
        paragraphs = result_obj.get("Paragraphs", [])
        for p in paragraphs:
            for w in p.get("Words", []):
                sid = w.get("SentenceId", 0)
                t = w.get("Text", "")
                sentences.setdefault(sid, []).append(t)
    except Exception as e:
        print(f"[WARN] 解析异常: {e}", file=sys.stderr)
    if not sentences:
        # 兜底：直接取段落/句子文本
        try:
            texts = [p.get("Text", "") for p in result_obj.get("Paragraphs", []) if p.get("Text")]
        except Exception:
            texts = []
        return "\n".join(t for t in texts if t.strip())
    sids = sorted(sentences.keys())
    return "\n".join("".join(sentences[sid]).strip() for sid in sids if "".join(sentences[sid]).strip())


def poll_and_fetch(task_id, max_wait=1800, poll_interval=15):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        resp = get_task(task_id)
        data = resp.get("Data", {})
        status = data.get("TaskStatus")
        print(f"[Tingwu] {status}", file=sys.stderr)
        if status == "COMPLETED":
            transcription_url = (data.get("Result") or {}).get("Transcription") or data.get("Transcription")
            if not transcription_url:
                raise RuntimeError("任务完成但未找到转写结果 URL")
            with urllib.request.urlopen(transcription_url, timeout=120) as r:
                result_obj = json.loads(r.read().decode("utf-8"))
            # 通义返回结构: {TaskId, Transcription: {Paragraphs: [...]}}
            inner = result_obj.get("Transcription", result_obj)
            return extract_transcript(inner)
        if status == "FAILED":
            raise RuntimeError(f"转写失败: {json.dumps(data, ensure_ascii=False)[:300]}")
        time.sleep(poll_interval)
    raise TimeoutError(f"任务 {task_id} 超时")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_path")
    parser.add_argument("output_txt")
    parser.add_argument("--source-lang", default="cn")
    parser.add_argument("--max-wait", type=int, default=1800)
    args = parser.parse_args()

    if not (AK_ID and AK_SECRET and APP_KEY):
        print("ERROR: 三件套未配置", file=sys.stderr)
        sys.exit(1)

    try:
        url = oss_upload(args.audio_path)
        task_id = create_task(url, args.source_lang)
        print(f"[Tingwu] 任务已创建 {task_id}", file=sys.stderr)
        transcript = poll_and_fetch(task_id, max_wait=args.max_wait)
        with open(args.output_txt, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"SUCCESS: {len(transcript)} 字 -> {args.output_txt}", file=sys.stderr)
        print(transcript[:800])
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
