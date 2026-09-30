# 第三方组件、字体、服务与媒体声明

本仓库自有代码/文档的 MIT 和两份示例数据的 CC0-1.0，不重新授权任何第三方作品。当前仓库不捆绑第三方代码、可执行文件、字体或原媒体；主要通过本机命令行接口使用独立工具。

## 实际使用的组件

| 组件 | 使用方式/版本范围 | 许可依据与责任 |
|---|---|---|
| Python | 本机 Python 3.9+，CI 3.9/3.12；标准库运行，无第三方 Python 运行包 | [Python 许可](https://docs.python.org/3/license.html)，按实际发行包保留相关条件 |
| FFmpeg / FFprobe | 本机外部 CLI，渲染器要求 FFmpeg 6+；`doctor` 记录实际版本，CI 安装 Ubuntu 软件包 | [官方许可说明](https://ffmpeg.org/legal.html)：构建可能涉及 LGPL/GPL 与外部组件；不能将本工具的 MIT 扩展到二进制/编码器。再分发时按具体构建重新核对 |
| libx264 / libass 等 | FFmpeg 实际构建内的编码/字幕组件；仓库不分发 | 随实际构建核查许可和分发条件，不能只凭 FFmpeg 名称给全部组件一个许可证 |
| Noto CJK 字体 | CI 从系统软件包安装；本机字体由使用者提供 | [Noto Sans CJK 许可](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE)，SIL OFL 1.1；其他字体按具体文件核对 |
| actions/checkout | CI 固定 v7.0.1 对应 SHA，详见 workflow | [官方 LICENSE](https://github.com/actions/checkout/blob/v7.0.1/LICENSE)，MIT |
| actions/setup-python | CI 固定 v7.0.0 对应 SHA，详见 workflow | [官方 LICENSE](https://github.com/actions/setup-python/blob/v7.0.0/LICENSE)，MIT |

## 可选能力与素材入口

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：可选授权下载工具，不在运行脚本内捆绑；[源码许可](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE) 与各发行包/依赖条件分别核对。下载成功不授予媒体再利用权。
- HyperFrames、Remotion、HeyGen 及 TTS/ASR/音乐服务仅是候选能力，不自动安装/订阅，也不统一宣称 MIT 或免费。集成时记录采用的版本、许可证/条款、数据去向与费用。
- 素材站、机构档案、官方频道、电影/综艺/新闻与音乐，逐条保留原有使用条件。检索目录不是媒体资产包，也不保证其中每一条都是可免费商用素材。

## 再分发与贡献

若未来捆绑二进制、字体、依赖源码或媒体，提交前新增清单，记录上游、版本、修改范围、许可证全文/必要 notices、来源/提供源代码等实际义务。当前没有提供这些第三方文件，因此不得声称其权利已由 MIT/CC0 清除。

第三方名称仅用于标识能力/来源，不代表合作、认可或背书。成片仍需项目自己的逐项媒体/音乐许可与人物授权记录，见 [DATA_LICENSE.md](DATA_LICENSE.md)。
