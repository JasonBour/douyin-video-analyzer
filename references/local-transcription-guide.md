# 本地转写指南（faster-whisper）

本文件说明当飞书妙记不可用时，如何使用 faster-whisper 进行本地语音转写。

## 适用场景

- 飞书妙记上传失败（文件过大 `quota_exceeded`、授权问题等）
- 小红书等不支持自动解析的平台视频（有视频直链或本地文件即可）
- 用户明确要求本地转写，不依赖云端服务

## 前置依赖安装

首次使用需安装两个 Python 包：

```bash
# 1. PyAV：视频提取音频
pip install av

# 2. faster-whisper：本地语音转写（比原版 whisper 快 4 倍）
pip install faster-whisper
```

> 国内网络安装 faster-whisper 后，下载模型时需设置 HuggingFace 镜像，见下文。

## 完整流程

### Step 1：下载视频（如有直链）

```powershell
Invoke-WebRequest -Uri "<视频直链.mp4>" -OutFile "<本地路径>\video.mp4" -UseBasicParsing
```

如果已经是本地视频文件，跳过此步。

### Step 2：提取音频

在 doubao-video-extract Skill 根目录下执行：

```bash
cd "<doubao-video-extract Skill 根目录>"
python scripts/convert/convert_video_to_audio.py "<本地路径>\video.mp4" --format mp3 --output-dir "<输出目录>"
```

输出为 mp3 文件，体积通常只有原视频的 1-2%。

> 如果报 `PyAV backend is not available`，先执行 `pip install av`。

### Step 3：本地转写

```powershell
# 国内网络必须设置镜像（否则 HuggingFace 连接超时）
$env:HF_ENDPOINT = "https://hf-mirror.com"

python -c "
from faster_whisper import WhisperModel

# 加载模型（首次自动下载，约 500MB，后续缓存复用）
# small 模型：中文识别效果好，CPU 可跑
# 可选：base（更快但准确率稍低）、medium（更准但更慢）
model = WhisperModel('small', device='cpu', compute_type='int8')

# 转写（指定中文，启用 VAD 去除静音，beam_size=5 提高准确率）
segments, info = model.transcribe('<音频路径>.mp3', language='zh', beam_size=5, vad_filter=True)

print(f'语言: {info.language}, 时长: {info.duration:.1f}s')

full_text = []
for segment in segments:
    text = segment.text.strip()
    print(text)
    full_text.append(text)

# 保存逐字稿
with open('<输出路径>_transcript.txt', 'w', encoding='utf-8') as f:
    f.write(''.join(full_text))
"
```

### Step 4：后处理

faster-whisper 的转写结果可能有少量识别错误，处理原则：

- **【内容结构】和【核心内容】字段**：可以修正明显的同音字、断句错误，让内容通顺
- **【原文】和【原文稿】字段**：尽量保留转写原文，只修正明显的识别错误（如人名、专有名词）
- 不要大改写原意，不要添加原文没有的内容

## 模型选择

| 模型 | 体积 | 中文准确率 | CPU 转写速度 | 适用场景 |
|---|---|---|---|---|
| base | ~150MB | 一般 | 快 | 短音频、对准确率要求不高 |
| **small** | ~500MB | **较好** | **中等** | **推荐，大多数口播视频** |
| medium | ~1.5GB | 好 | 慢 | 长音频、专业术语多 |
| large | ~3GB | 最好 | 很慢 | 极高准确率要求 |

> 默认用 `small`，兼顾准确率和速度。CPU 推理用 `compute_type='int8'` 降低内存占用。

## 常见问题

### Q1：HuggingFace 连接超时
**A**：设置国内镜像 `$env:HF_ENDPOINT = "https://hf-mirror.com"` 后重试。

### Q2：模型下载慢
**A**：镜像源下载速度通常 1-2MB/s，small 模型约 500MB，需几分钟。下载一次后缓存复用，后续不再下载。

### Q3：转写结果有很多识别错误
**A**：
- 换更大的模型（small → medium）
- 确认音频质量（是否有背景噪音、是否清晰）
- 检查 `language='zh'` 是否正确指定
- 后处理时人工修正明显错误

### Q4：视频文件很大，提取音频后还是很大
**A**：mp3 格式已经是压缩音频，通常 1 分钟约 1MB。如果还是过大，可以降低比特率，或直接用原视频文件转写（faster-whisper 支持视频格式输入，但需先提取音轨）。

### Q5：Windows  symlink 警告
**A**：HuggingFace 缓存默认用 symlink，Windows 非管理员模式会警告但不影响使用。可设置 `$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"` 关闭警告。

## 已验证案例

- 小红书视频直链（mp4，83MB）→ 提取 mp3（1.54MB）→ faster-whisper small 模型转写 → 3分21秒音频，中文识别准确率良好，成功拆解入库。
