# douyin-video-analyzer

短视频/图文内容采集与 PREP 结构拆解工具。输入抖音/小红书链接或文案，自动提取标题、完整逐字稿/正文，并按 PREP 模型拆解为可照讲的内容结构。

## ✨ 功能特性

- **多平台支持**：抖音/小红书/B站/快手/微博/YouTube/TikTok等主流短视频平台
- **双转写引擎**：
  - **通义听悟云端转写**（推荐）：抗背景音乐干扰，识别准确率高，支持长音频
  - **本地faster-whisper转写**：无需API密钥，离线可用，CPU int8推理
- **PREP 自动拆解**：按观点/理由/展开/结尾四段式结构化输出，允许缺段不硬凑
- **飞书多维表格同步**：一键写入飞书 Base 建立内容素材库
- **本地导出**：支持 CSV / JSON / Markdown 格式导出

## 🌐 支持平台

| 平台 | 自动下载 | 自动转写 | 备注 |
|---|---|---|---|
| 抖音 | ✅ | ✅ | 支持短口令和完整链接，无需登录 |
| 小红书 | ✅ | ✅ | 需配置Cookie避免风控，支持视频/图文 |
| B站 | ✅ | ✅ | 自动获取标题、UP主、互动数据 |
| 快手 | ✅ | ✅ | |
| 微博视频 | ✅ | ✅ | |
| YouTube | ✅ | ✅ | |
| TikTok | ✅ | ✅ | |
| Instagram/Facebook | ✅ | ✅ | |
| X/Twitter | ✅ | ✅ | |
| AcFun/芒果TV/梨视频 | ✅ | ✅ | |

## 📦 项目结构

```
douyin-video-analyzer/
├── SKILL.md                 # Skill 定义文件（Agent 加载用）
├── README.md                # 本文件
├── scripts/
│   ├── download_douyin_audio.py   # 抖音视频下载+音频提取
│   ├── fetch_xiaohongshu.py       # 小红书笔记抓取
│   ├── extract_audio.py           # 视频重采样提取16k单声道音频
│   ├── tingwu_std.py              # 通义听悟纯标准库转写（无SDK依赖）
│   ├── tingwu_transcribe.py       # 通义听悟标准实现（需阿里云SDK）
│   ├── export_to_local.py         # 本地导出工具
│   └── chubby_common/
│       ├── config.py              # 配置文件（密钥走环境变量，无硬编码）
│       ├── deps.py                # 依赖检查
│       └── ...
├── references/
│   ├── base-field-schema.md       # 飞书Base字段定义
│   ├── content-structure-template.md  # PREP拆解模板
│   └── local-transcription-guide.md   # 本地whisper转写指南
└── output/                  # 输出目录
```

## 🚀 快速开始

### 1. 环境依赖

- Python 3.8+
- ffmpeg（用于音频提取）
- 二选一：
  - 通义听悟 API 凭证（推荐，识别效果好）
  - faster-whisper 本地环境（无需API，离线可用）

### 2. 配置环境变量

```bash
# ===== 方式一：通义听悟云端转写（推荐）=====
export ALIBABA_CLOUD_ACCESS_KEY_ID="你的AccessKey ID"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="你的AccessKey Secret"
export TINGWU_APP_KEY="你的通义听悟AppKey"

# ===== 方式二：本地faster-whisper（无需API）=====
# 国内网络需设置HF镜像
export HF_ENDPOINT="https://hf-mirror.com"
# 安装依赖：pip install faster-whisper

# 小红书 Cookie（可选，配置后避免被风控）
export XHS_COOKIE="从浏览器复制的小红书Cookie"
```

把上面的配置写到 `~/.zshrc` 或 `~/.bash_profile` 里，永久生效。

### 3. 基本使用

#### 抖音视频提取+转写

```bash
# 1. 下载抖音视频并提取音频
python scripts/download_douyin_audio.py "https://v.douyin.com/xxxxxx/"

# 2. 转写逐字稿
python scripts/tingwu_std.py "audio.wav" "output.txt" --source-lang cn
```

#### 小红书笔记抓取

```bash
# 抓取小红书笔记（自动下载视频/图片）
python scripts/fetch_xiaohongshu.py "https://www.xiaohongshu.com/explore/xxxxxx" --output ./output
```

#### 本地视频转写

```bash
# 1. 提取16k单声道音频（必须用这个脚本，不要直接ffmpeg改采样率）
python scripts/extract_audio.py "video.mp4" "audio.wav"

# 2. 通义听悟转写
python scripts/tingwu_std.py "audio.wav" "output.txt" --source-lang cn
```

## 📝 PREP 拆解模型

PREP 是经典的结构化表达框架：

| 段落 | 含义 | 说明 |
|---|---|---|
| **P**oint | 观点 | 一句话核心主张 |
| **R**eason | 理由 | 为什么这么说，背后的逻辑 |
| **E**xample | 展开 | 具体案例、方法、数据、细节 |
| **P**oint | 总结 | 结尾总结/行动号召 |

**重要原则**：允许缺段，禁止凑数。短平快视频没有E展开部分就如实标注，不要为了填满PREP硬凑。

## 🔧 常见问题

### Q: 转写结果有乱码怎么办？
A: 确保用 `scripts/extract_audio.py` 提取音频（真正重采样到16kHz），不要直接用ffmpeg改采样率，那样会把音频变调损坏。

### Q: 小红书抓取被风控了怎么办？
A: 配置 `XHS_COOKIE` 环境变量，从浏览器登录小红书后复制完整Cookie字符串。

### Q: 通义听悟API调用失败？
A: 检查环境变量是否正确配置，确认阿里云账号有通义听悟服务权限和余额。

### Q: 两种转写方式怎么选？
A:
- **通义听悟（云端）**：识别准确率高，抗背景音乐/口音干扰，适合带BGM的口播视频，按使用量付费
- **faster-whisper（本地）**：完全免费离线，CPU就能跑，但对带背景音乐/口音的视频识别效果较差，适合清晰口播内容
- 建议优先用通义听悟，无API时回退到本地whisper

### Q: 本地whisper效果不好怎么办？
A: 检查是否用`scripts/extract_audio.py`正确提取了16k单声道音频，不要直接用ffmpeg改采样率；或者改用通义听悟云端转写。

## 📄 License

MIT
