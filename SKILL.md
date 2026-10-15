---
name: douyin-video-analyzer
description: 短视频/图文内容采集与 PREP 结构拆解工具。输入抖音/小红书链接或文案，自动提取标题、完整逐字稿/正文，并按 PREP 模型拆解为可照讲的内容结构（观点/理由/展开/结尾），写入飞书多维表格或保存本地。支持抖音视频/图文、小红书视频/图文、X 推文等多平台。适用于研究对标账号、找选题灵感、筛选优质内容、建立个人内容素材库等场景。
---

# 短视频/图文内容采集与 PREP 拆解器

## 支持平台

| 平台 | 链接类型 | 自动提取 | 备注 |
|---|---|---|---|
| 抖音 | 视频链接 | ✅ web.fetch / iesdouyin 路线 | 优先 web.fetch，失败走 iesdouyin |
| 抖音 | 图文笔记 | ⚠️ 需用户提供元数据/图片直链 | 图文无音频，需 OCR 提取文字 |
| 小红书 | 视频链接 | ✅ fetch_xiaohongshu.py | 需配置 XHS_COOKIE 否则可能被风控 |
| 小红书 | 图文笔记 | ✅ fetch_xiaohongshu.py | 同上，图片自动下载 OCR |
| X / Twitter | 推文 | ⚠️ 需用户提供截图/文案 | OCR 或手动粘贴 |
| 其他 | — | ❌ | 需用户手动提供文案 |

## 执行目录

执行本 Skill 任何命令前，先将工作目录切换到本 Skill 根目录：

```bash
cd "<douyin-video-analyzer Skill 根目录绝对路径>"
```

例如：
```bash
cd "C:\Users\67594\AppData\Local\DoubaoWork\User Data\Default\.doubaowork\agent_mode\workspace\.user_skills\douyin-video-analyzer"
```

下文涉及 `scripts/` 下脚本的路径均相对于该目录。

## 工作流程总览

```
输入链接/文案 → ①平台识别 → ②提取内容 → ③PREP拆解 → ④输出(飞书/本地)
```

支持单条和批量（多条链接）处理。批量时逐条执行①②③，最后统一执行④。

---

## Step 1：平台识别与内容提取

根据用户输入的链接类型，选择对应的提取路径：

### 1.1 抖音视频

**优先路径：web.fetch 快速解析**

1. 直接调用 `web.fetch`，将抖音视频链接作为输入。
2. 从返回内容中提取视频文本/逐字稿。

**回退路径：iesdouyin 路线（无需 cookie/登录）**

当 web.fetch 失败时，使用本 Skill 自带的 `scripts/download_douyin_audio.py`：

```bash
python scripts/download_douyin_audio.py "<douyin_url>"
```

- 自动提取 video_id（支持短链和完整链接）
- 用 `iesdouyin.com/share/video/<id>` + iPhone UA 获取分享页
- 从 `window._ROUTER_DATA` 提取标题和视频直链
- 下载视频 → ffmpeg 提取音频
- 输出：音频文件路径 + 标题

**关键点**：必须用 `iesdouyin.com/share/video/` 而非 `douyin.com/video/`，且 UA 必须是 iPhone。

### 1.2 抖音图文笔记

抖音图文笔记无法通过 web.fetch 或 iesdouyin 路线自动提取内容（页面 JS 渲染且无音频）。

**处理方式**：
1. 请用户提供完整元数据（标题、图片直链等），或
2. 请用户直接粘贴图文里的文字内容，或
3. 请用户提供截图，Agent OCR 提取文字。

### 1.3 小红书笔记（视频/图文）

使用本 Skill 自带的 `scripts/fetch_xiaohongshu.py`：

```bash
# 配置 cookie（强烈建议，否则可能被风控）
export XHS_COOKIE="从浏览器复制的 cookie 字符串"

# 抓取笔记（支持 xhslink 短链和 explore 链接）
python scripts/fetch_xiaohongshu.py "<xiaohongshu_url>" --output ./output
```

**功能**：
- 自动提取标题、正文、标签、作者、互动数据
- 图文笔记：自动下载所有图片
- 视频笔记：自动下载视频 + 本地转录（需 funasr 依赖）
- 输出：带 frontmatter 的 Markdown 文件

**无 cookie 时**：可能被风控拦截，此时需用户手动提供文案。

### 1.4 X / Twitter 推文

X 推文无法自动解析。请用户：
1. 提供截图，Agent OCR 提取文字；或
2. 直接粘贴推文内容。

### 1.5 本地视频/音频文件

用户提供本地 mp4/mp3 文件时，直接走本地转写路径（见 Step 2.3）。

---

## Step 2：提取完整逐字稿/正文内容

### 2.1 抖音视频逐字稿

- **web.fetch 成功**：直接使用返回的文本作为逐字稿。
- **iesdouyin 路线成功**：得到音频文件后，走本地转写（见 2.3）。

### 2.2 小红书/图文内容

- **fetch_xiaohongshu.py 成功**：直接使用提取的正文/转录文本。
- **图片内容**：下载图片后用 Agent 的 Read 工具 OCR 提取文字。

### 2.3 转写（首选通义听悟，回退 faster-whisper）

当需要转写时（iesdouyin 下载的音频、用户提供的视频文件、小红书视频等），**优先使用通义听悟云端转写**（识别质量高，抗背景音乐干扰）：

**通义听悟转写（已配置时首选）**：

1. 音频提取（若输入是视频文件）：用本 Skill 自带的正确重采样脚本：
   ```bash
   python scripts/extract_audio.py "<视频文件.mp4>" "<音频.wav>"
   ```
   ⚠️ 必须用该脚本（AudioResampler 重采样到 16kHz 单声道）。**禁止**用 `frame.rate=16000` 直接改帧率——那不会真正重采样，会把音频变调损坏，导致任何转写引擎输出乱码。
2. 云端转写：调用本 Skill 自带脚本（两条实现，按环境自动选）：
   ```bash
   # 方式一：标准实现（需 aliyun SDK + oss2）
   python scripts/tingwu_transcribe.py "<音频路径.wav>" "<输出逐字稿.txt>" --source-lang cn
   # 方式二：纯标准库实现（无 SDK 依赖，macOS/无网环境也能跑，功能相同）
   python scripts/tingwu_std.py "<音频路径.wav>" "<输出逐字稿.txt>" --source-lang cn
   ```
3. 脚本自动完成：上传 OSS（自动复用同一 bucket）→ CreateTask 创建离线任务 → 轮询 → 下载转写结果 → 输出纯文本。
4. 凭证从 `scripts/chubby_common/config.py` 读取（TINGWU_ACCESS_KEY_ID / TINGWU_ACCESS_KEY_SECRET / TINGWU_APP_KEY，支持环境变量覆盖）。
5. 超长音频（>60 分钟）会触发通义单任务时长配额（`PRE.AudioDurationQuotaLimit`），需先用帧对齐方式切段（每段 ≤57 分钟）再逐段转写、最后拼接。
6. 转写失败时如实报告错误，不要自动回退到其他未授权服务。

**faster-whisper 本地转写（无 API 凭证时的回退方案）**：

**完整步骤**（读取 `references/local-transcription-guide.md` 查看详细说明）：

1. **下载/定位音频文件**：mp3 或 wav 格式
2. **本地转写**：用 faster-whisper 转写
   - 国内网络需设置镜像：`$env:HF_ENDPOINT = "https://hf-mirror.com"`
   - 推荐用 `base` 模型（中文识别效果可接受，加载快）
   - CPU int8 推理
   - 转写脚本示例见 `references/local-transcription-guide.md`
3. **后处理**：修正明显的语音识别错误（如同音字、断句），但【原文稿】字段保留转写原文

> 注意：faster-whisper 的 base/small 模型对带背景音乐/口音的视频识别效果差（可能输出乱码或极短文本），此时优先用通义听悟；两个都不可用时，请用户提供文案。
>
> 模型首次运行会自动下载（约 150MB-500MB），缓存到本地，后续转写无需重新下载。

### 逐字稿/正文处理

- 保留完整原文，不要删减、改写或概括。
- 去除时间戳标记（如 `[00:01]`），保留纯文本内容。
- 如果视频无口播（纯音乐/画面），逐字稿字段填"无口播内容"。

---

## Step 3：PREP 结构拆解

基于「内容标题 + 完整逐字稿/正文」，按 PREP 模型拆解内容，生成两项输出：

### 3.1 内容结构（PREP 完整结构）

**写入 Base 的"内容结构"字段**：直接可照讲的 PREP 完整结构，格式如下：

```
P 观点：<一句话核心观点，直接可讲>

R 为什么这么说：<支撑理由，直接给内容本身>
1. <理由1>
2. <理由2>
3. <理由3>

E 展开讲讲：<展开/案例/方法的实质内容，可照讲>

P 结尾总结：<结尾总结，可照讲>
```

### 3.2 PREP 四字段

**写入 Base 的"观点(Point)/理由(Reason)/例子(Example)/总结(Point)"四个字段**：每字段两段式——
- **【核心内容】**：原文精简版，尽量保留原话表达，只做必要删减，不要大改
- **【原文】**：摘自逐字稿的完整原话（可省略中间用"……"连接）

关键规范（读取 `references/content-structure-template.md` 查看完整说明）：
- **先判定结构变种**：拆解前先判断这条内容是 PREP 完整型 / PEP（无 R 型，观点罗列清单）/ PR（无 E 型，纯论证），避免分类错误。
- 内容结构字段里的所有内容**必须可以直接照着讲**，禁止写对博主行为的描述（如"他直接给出结论""她强调说""博主在叮嘱"）。
- R 里**只有理由确实是并列的多点时，才用 1、2、3 编号**；如果 R 是一两句连续的话（递进/转折/论证一段话），就直接写一段，不要强行拆编号。
- 【核心内容】贴近原文语言，是原文的精简版。
- **允许缺段，禁止凑数**：PREP 是拆解工具不是强制模板，某段（尤其 E 展开/R 理由）没有实质内容时，如实标注"（本内容为XX型，无独立展开/案例部分）"，绝不能为了填满 PREP 把其他段落内容重复搬进来。R 是"为什么这么说"的论据、E 是"展开讲讲"的案例/方法/数据，二者必须互不重复。

---

## Step 4：数据输出

### 输出方式选择

- 用户明确要求飞书多维表格，或提供了 Base 链接 → 写入飞书 Base
- 用户说"不需要飞书""保存到本地""导出文件" → 保存到本地
- 用户未指定 → 默认询问用户偏好，或同时提供两种方式

### 方式 A：写入飞书多维表格

#### 新建 Base（用户没有现成表时）

1. 读取 `references/base-field-schema.md` 获取标准字段定义和字段 JSON。
2. 使用 lark-base Skill 创建 Base：

```bash
lark-cli base +base-create --name "抖音视频素材库" --table-name "视频采集" --fields '<field-json-array>' --as user
```

3. 创建成功后记录 base_token 和 table_id，告知用户 Base 链接。

#### 写入已有 Base（用户提供了 Base 链接时）

1. 先用 `lark-cli base +url-resolve --url "<url>" --as user` 获取 base_token 和 table_id。
2. 用 `lark-cli base +field-list --base-token <token> --table-id <id> --as user` 确认字段结构。
3. 字段不匹配时，先创建缺失字段（参考 base-field-schema.md），再写入数据。
4. 使用 `+record-batch-create` 批量写入（单批最多 200 条）。

#### 字段映射

| Base 字段名 | 字段类型 | 数据来源 |
|---|---|---|
| 视频链接 | 超链接 | Step 1 |
| 视频标题 | 文本 | Step 1 |
| 内容结构 | 多行文本 | Step 3.1（PREP 完整结构） |
| 观点(Point) | 多行文本 | Step 3.2（核心内容+原文） |
| 理由(Reason) | 多行文本 | Step 3.2（核心内容+原文） |
| 例子(Example) | 多行文本 | Step 3.2（核心内容+原文） |
| 总结(Point) | 多行文本 | Step 3.2（核心内容+原文） |
| 原文稿 | 多行文本 | Step 2（完整逐字稿/正文） |

> 字段顺序固定为：视频链接 → 视频标题 → 内容结构 → 观点(Point) → 理由(Reason) → 例子(Example) → 总结(Point) → 原文稿。

### 方式 B：保存到本地

使用本 Skill 附带的导出脚本：

```bash
python "<本Skill目录>/scripts/export_to_local.py" --input "<json数据文件路径>" --format csv --output "<输出目录>"
```

或由 Agent 直接生成文件：
- **CSV 格式**：适合表格查看和后续导入
- **JSON 格式**：保留完整结构化数据，适合程序处理
- **Markdown 格式**：适合阅读，每条视频一个章节

本地文件默认保存到当前工作目录下的 `douyin_export/` 文件夹，文件名格式 `douyin_analysis_YYYYMMDD_HHmmss.csv`。

---

## 批量处理

当用户提供多个链接/文案时：

1. 将所有输入整理为列表，去重。
2. 逐条执行 Step 1 → Step 2 → Step 3，每条结果暂存。
3. 全部完成后统一执行 Step 4（批量写入 Base 或导出一个文件）。
4. 过程中某条失败时，记录失败原因，继续处理下一条，最后汇总报告成功/失败数量。

批量处理时建议每 5 条向用户报告一次进度。

---

## 反模式

- **不要**用网页标题、描述或评论代替视频逐字稿/正文内容。
- **不要**对逐字稿/正文进行删减、改写或"优化"，保留原文。
- **不要**在 PREP 拆解时脱离实际内容空谈，所有分析必须有文本依据。
- **不要**跳过字段结构确认直接写入飞书 Base，字段不匹配会导致写入失败。
- **不要**把飞书 Base 的 wiki token、完整 URL 当作 base_token 使用。
- **不要**使用应用模式（app mode）操作 Base，一律使用经典 Base shortcut。
- **不要**在用户未要求时创建飞书 Base，先确认输出方式。
- **不要**强行用抖音工具解析小红书/X 等非抖音平台链接，按 Step 1 的平台识别选择对应路径。
- **不要**为了填满 PREP 而重复其他段落内容，允许缺段并如实标注。

---

## 输出报告规范

完成采集后，向用户输出简明报告：

```
✅ 采集完成：成功 X 条，失败 Y 条

【输出位置】
- 飞书 Base：<链接>（如适用）
- 本地文件：<路径>（如适用）

【失败明细】（如有）
- <链接>：<失败原因>
```

每条视频的详细分析内容写入 Base 或本地文件，不在报告中重复展开。
