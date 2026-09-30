# AI 视频制作

**从一句视频需求，推进到可以播放的成片。**

这是一套面向 Codex 的真实素材视频制作 Skill 与工程工具。适用于历史、科技科普、纪录短片、品牌和产品宣传：用事实与具体影像讲清内容，用自然人声、合理的音乐与镜头衔接形成完整观看体验。

**当前版本：0.1.0。** 已沉淀制作规范，并提供可运行的本地工程、字幕、混音、剪辑和验收工具。研究、素材语义判断与艺术决策由 Agent 执行；需要可用的网页能力、经授权的配音服务及真实素材。它不会仅凭一个 CLI 自动替你完成事实研究，也不承诺主观“完美”。

## 快速使用

在已有安装的 Codex 窗口中：

```text
$ai-video-production 做一个关于航空发展史的视频，约 6 分钟，面向年轻人，
用英文旁白、中文在上英文在下的字幕，交付完整视频。
```

题材、长度、语言都可换。没有指定的部分，Agent 根据简报与已有偏好作合理选择；新费用、资料外传和发布必须在有效授权内。若只要试音或设计阶段，直接写明。

在另一台 macOS/Linux 上安装：

```bash
git clone https://github.com/delu543/ai-video-production.git
cd ai-video-production
python3 scripts/install_skill.py
python3 skills/ai-video-production/scripts/video.py doctor
```

私有仓库需要有权限的 GitHub 登录。Python ≥3.9；渲染需 FFmpeg/FFprobe 及 libass，字幕需适用的中英文字体。安装工具不安装依赖、不删除现有 Skill；安装后在支持的客户端刷新 Skill 列表/开始下一轮调用。详见 [上手指南](docs/getting-started.md)。

## 制作标准

| 维度 | 具体要求 | 细则 |
|---|---|---|
| 文案 | 具体年份、人物、机制、变化；事实与观点分开；技术说明与人文思考同时成立 | [文案规范](skills/ai-video-production/references/editorial.md) |
| 素材 | 真实影像优先，原文件与裁后清晰度通过；逐句匹配，多来源、低重复 | [素材质量](skills/ai-video-production/references/sourcing.md)、[检索入口](skills/ai-video-production/references/source-catalog.md) |
| 画面 | 全幅构图，无上下黑条、叠字、廉价效果；档案/照片保内容融入 | [画面与转场](skills/ai-video-production/references/picture.md) |
| 镜头 | 每个镜头说明作用，每个边界说明前后关系；切换方式服从逻辑 | [镜头与转场](skills/ai-video-production/references/picture.md) |
| 人声 | 自然青年讲解，清楚稳健；试音定方向，专名校对，原声有语境 | [配音与原声](skills/ai-video-production/references/voice.md) |
| BGM | 统一声音世界，乐句和情绪随叙事发展；原声窗口退让，人声可辨 | [音乐与混音](skills/ai-video-production/references/music.md) |
| 字幕 | 最终音轨对齐，中上英下可配置；换行/空间/字形实际检查 | [字幕规范](skills/ai-video-production/references/captions.md) |
| 成本/交付 | 先记账再调用，未知结果不重付；可播放成片、工程、来源与验收分开 | [服务与费用](skills/ai-video-production/references/cost-and-providers.md)、[交付门](skills/ai-video-production/references/delivery.md) |

参考视频只用于学习问题推进、节奏和表现原则。不要抄画面设计、台词或镜头序列。不同项目使用自己的故事和视觉语言。

## 仓库导航

```text
skills/ai-video-production/    # 可独立安装的 Skill；制作规则的唯一真源
  SKILL.md                    # Agent 入口与阶段门
  agents/openai.yaml          # 调用与显示信息
  references/                 # 按文案、素材、画面、声音、交付分类的规范
  assets/                     # 通用简报与主时间线格式示例，不含第三方素材
  scripts/                    # Python 标准库 + FFmpeg 工程工具
docs/                         # 人用的上手、工程契约、验证与迭代说明
scripts/                      # 安装、仓库审计与测试入口
tests/                        # 单元与真实编码集成测试；只生成合成测试夹具
.github/workflows/            # 无收费、无私人数据的 CI
```

- [端到端流程](skills/ai-video-production/references/workflow.md)
- [工程数据契约与命令](docs/project-contract.md)
- [架构与来源边界](docs/architecture.md)
- [验证范围与案例](docs/validation.md)
- [迭代计划](docs/roadmap.md) / [变更记录](CHANGELOG.md) / [贡献方式](CONTRIBUTING.md)

## 边界

默认真实素材，禁用 AI 动态镜头；旁白允许 AI。配音/音乐供应商不固定，价格与许可使用前核查。默认本地交付，不自动发布。第三方媒体与秘密留在仓库外，免费访问不等于免费再利用。

本仓库暂为私有，尚未授予公开开源许可；工作流规范与代码由仓库所有者管理。FFmpeg、下载工具、字体与媒体各自按其许可证使用，仓库说明不重新授予这些权利。见 [LICENSE](LICENSE) 与 [安全边界](SECURITY.md)。
