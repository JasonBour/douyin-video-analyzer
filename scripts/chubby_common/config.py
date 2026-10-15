"""平台配置：把每个采集平台的差异收敛为数据，而非代码复制。

新增平台只需声明一份 PlatformConfig，yt-dlp 封装 / 转录 / 文件名等
公共行为全部由 chubby_common 提供。
"""

import os
from dataclasses import dataclass, field

# ============================================================================
# 通义听悟（Tingwu）API 配置
# ----------------------------------------------------------------------------
# 接入方式二选一：
#
# 【方式 A：单 API Key（新版百炼，推荐）】只需一个 Key，sk- 开头
#   1. 系统环境变量：DASHSCOPE_API_KEY（推荐，Key 不进文件）
#   2. 直接改下面 TINGWU_API_KEY 占位字符串（文件勿外传/勿提交公开仓库）
#
# 【方式 B：旧版 AccessKey + AppKey】需要三样：
#   1. 系统环境变量：
#      ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET / TINGWU_APP_KEY
#   2. 或直接改下方三个占位字符串
# ----------------------------------------------------------------------------
# 方式 A：单 Key（百炼 DashScope API Key，sk- 开头）
TINGWU_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "") or os.environ.get("TINGWU_API_KEY", "")

# 方式 B：旧版三件套
TINGWU_ACCESS_KEY_ID = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
TINGWU_ACCESS_KEY_SECRET = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
TINGWU_APP_KEY = os.environ.get("TINGWU_APP_KEY", "")
TINGWU_REGION = os.environ.get("TINGWU_REGION", "cn-beijing")

# 密钥配置：全部走环境变量，不要硬编码在这里（开源安全）
# 使用前在 ~/.zshrc 或 ~/.bash_profile 里配置：
# export ALIBABA_CLOUD_ACCESS_KEY_ID="你的AccessKey ID"
# export ALIBABA_CLOUD_ACCESS_KEY_SECRET="你的AccessKey Secret"
# export TINGWU_APP_KEY="你的通义听悟AppKey"


def tingwu_configured() -> bool:
    """通义听悟是否已配置完成（方式 A 或方式 B 任一满足即可）。"""
    if TINGWU_API_KEY:
        return True
    return bool(TINGWU_ACCESS_KEY_ID and TINGWU_ACCESS_KEY_SECRET and TINGWU_APP_KEY)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class PlatformConfig:
    """单个平台的转录相关配置。"""

    id: str                      # 机器可读平台 ID，如 tiktok / weibo / zhihu
    name: str                    # 展示名，如 TikTok / 微博 / 知乎
    tag: str                     # Markdown tags 使用的标签名
    default_title: str           # 标题抓取失败时的兜底标题
    language: str = "auto"       # 转录语言：auto 或 zh
    ua: str = DEFAULT_UA         # User-Agent
    referer: str = ""            # Referer，为空则不传
    extra_ydl_args: tuple = field(default_factory=tuple)  # 附加 yt-dlp 参数
    tmp_prefix: str = ""         # 临时目录前缀，默认用 id
    info_timeout: int = 30       # 获取标题超时（秒）
    subtitle_timeout: int = 120  # 抓字幕超时（秒）
    download_timeout: int = 300  # 下载音频超时（秒）
    max_retry: int = 3           # 下载重试次数

    def __post_init__(self):
        if not self.tmp_prefix:
            object.__setattr__(self, "tmp_prefix", self.id)
