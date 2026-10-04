# 上手与调用

## 在 Codex 中制作

安装 `ai-video-production` 后，使用 `$ai-video-production` 加需求。Agent 读取 Skill、建立仓库外独立工程，完成研究、文案、素材、剪辑设计、配音、配乐、字幕、渲染与验收。新预算若未授权，先完成免费步骤，再就具体收费对象请求决策；不要先付费再补授权。

明确试音方向时可以写“先给 3 个约 10 秒英文样本”；明确接受画面后可写“只换人声和重新编排音乐，画面尽量保留”。要求“完整视频”时不能只给脚本。

## 环境

- macOS/Linux，Python 3.9+；工具无第三方 Python 运行依赖。
- FFmpeg 6+ 与可用 FFprobe；FFmpeg 包含 libx264、libass、blend、gblur、loudnorm、amix。`doctor` 报告实际版本/滤镜，发现缺项先解决受影响能力。
- 支持目标语言且许可适用的字体，例如 Noto Sans CJK；本仓库不捆绑字体。字体不存在时 libass 可能回退，必须检查实际字形。
- 网页检索/操作、ASR/对齐由当前 Agent 工具提供。TTS 可用内置的 `voice` 命令（MiniMax），它只读取 `MINIMAX_API_KEY` 或 `~/.config/minimax/api_key`，并在账本授权内付费；其余命令不注册服务、不付费、不下载第三方素材。

如果二进制不在 PATH，可设置 `FFMPEG_BIN`、`FFPROBE_BIN` 到实际绝对路径。它们是本机环境配置，不提交 Git。不要把他人电脑路径写进脚本。

## 手动执行本地工具

以下为命令契约，素材与时间线必须先真实制作；初始化本身不可渲染。

```bash
python3 skills/ai-video-production/scripts/video.py doctor
python3 skills/ai-video-production/scripts/video.py init ../video-project
# Agent 完成 ../video-project/brief.json 与 project.json，准备素材/声音
python3 skills/ai-video-production/scripts/video.py check ../video-project/project.json --stage design
python3 skills/ai-video-production/scripts/video.py check ../video-project/project.json --stage render
python3 skills/ai-video-production/scripts/video.py captions ../video-project/project.json ../video-project/deliverables
python3 skills/ai-video-production/scripts/video.py mix ../video-project/project.json ../video-project/audio/master.wav
python3 skills/ai-video-production/scripts/video.py render ../video-project/project.json ../video-project/deliverables/film-v1.mp4
python3 skills/ai-video-production/scripts/video.py qa ../video-project/project.json ../video-project/deliverables/qa-v1.json ../video-project/deliverables/film-v1.mp4
python3 skills/ai-video-production/scripts/video.py review-frames ../video-project/project.json ../video-project/work/review-v1 ../video-project/deliverables/film-v1.mp4
```

渲染和混音拒绝覆盖已有交付物，修改时选新版本路径并更新 `master_audio`。机器报告中的视听字段是 `not_reviewed`，必须真实播放之后填写。公开发布前还要 `check --stage publish`，核对每个媒体使用依据和人工审阅门。

## 安装与更新

`scripts/install_skill.py` 将完整 Skill 包复制到 Agent 的 Skill 目录并写安装清单：默认 `--target codex`（`~/.codex/skills/`），也可用 `--target claude`（`~/.claude/skills/`）或 `--target agents`（`~/.agents/skills/`），`--destination` 可指定任意路径。重复安装同一内容不重写；已存在来源不明/被本地改动的 Skill 会拒绝覆盖。`--update` 仅更新具有匹配安装清单的版本，旧版本保留到隐藏备份目录，不删除。仓库规范为唯一真源，不直接改安装副本。

可以用 `--destination` 安装到测试目录。工具本地结构校验通过，不代表客户端已在新会话自动识别；首次调用需观察它实际读取此 Skill。现有窗口可以明确指定 `$ai-video-production` 或直接指向 SKILL.md。
