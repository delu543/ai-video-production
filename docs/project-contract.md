# 主工程契约 v1

示例：[project.example.json](../skills/ai-video-production/assets/project.example.json)。它是字段示例，事实/来源/媒体未核实，不能直接生产。`init` 清空示例内容，保留参数结构。

| 字段 | 用途 |
|---|---|
| `schema_version` | 当前 1；不兼容更改需迁移与版本说明 |
| `profile` | 输出尺寸/FPS/编码/字体/两语字段/首尾淡化 |
| `facts` | 事实 ID、表述、事件时间、证据、核查状态 |
| `beats` | 叙事单元，旁白/原话/有意留白、事实引用、画面需求 |
| `assets` | ID→原文件元数据、来源、日期、许可、实际画质；音频也登记 |
| `shots` | 镜头顺序、绑定叙事单元、源入点、速度、时长、构图、边界逻辑 |
| `captions` | 最终全片时间的 start/end；top/bottom 是已校对两语文本，显式换行 |
| `audio_cues` | 已制作音频的排布、叙事角色、增益、包络与淡化 |
| `master_audio` | 最终混音相对工程目录的路径 |
| `music_plan` | 全片声音世界、各段情绪与触发点，不只是曲目名 |
| `budget` | 单项目货币、已授权额度与授权范围说明 |
| `reviews` | 实际审阅门；程序不默认通过主观检查 |

## 时间线

每个镜头 `duration` 包含自己参与交叉淡化的片段；右镜头的 `transition.duration` 是与左镜头重叠的时长。第一镜头无重叠，直接切重叠为零。

```text
镜头 A 5.0s + 镜头 B 5.0s，B 淡化重叠 0.6s
B 开始 = 5.0 − 0.6 = 4.4s
全片长 = 5.0 + 5.0 − 0.6 = 9.4s
```

字幕、叙事触发、音轨在这个最终全局轴定位。更改重叠时长会影响后续时间；锁定旁白后优先调整镜头时长保持全局边界。严禁另写一套独立音频计时器。以累计边界乘 FPS 取整计算帧数，桥段帧数来自相邻边界差，保持总帧精确。

相邻淡化不能吃掉整个短镜头。原视频要有源时段覆盖 `source_in + duration × speed`；变速必须写理由，不自动 loop/tpad。render 使用规范化 CFR 素材核心段和明确帧数 blend，保留全部已计划时长。复杂 J/L-cut 在音轨 start/source_in 上安排；复杂运动图形用外部工具后以实际媒体登记。

## 画面

`framing=cover` 按比例铺满裁切，`contain` 保留内容并使用柔化背景。`crop=[w,h,x,y]` 是原片像素，裁切后再缩放；`quality.effective_width/height` 必须反映裁切损失与真实细节，探测只能排除明显夸大。

`origin` 区分 real、archival、self_recorded、authored_graphic（准确自制图表）、authored_audio（自编配乐/音效，仅限音频且须写 rights_basis）、generated、synthetic_test。图表只在解释有必要时使用，并注明数据来源；不能将生成场景改标为图表规避真实素材要求。

照片 `zoom` 支持 cover 的 0..0.08 缓推（例如 0.03 为到 1.03x）；复杂或保内容照片运动使用专用工具。`transition` 当前支持 cut/dissolve；每个边界写 relation，cut 另有 cut_reason。不能因为渲染器支持 cut 就忽略逻辑。

## 音轨

`audio_cues` 的 `start` 是全片时间；`source_in` 是音频源入点；`duration` 为使用长度；`envelope=[[秒, dB], ...]` 的秒从该 cue 开始，节点递增线性插值，首尾维持端点。为空时使用 `gain_db`。包络存在时它是完整增益曲线，不再叠加 gain_db。`fade_in/out` 在音量包络之后叠加。

`role` 为 narration/original/music/ambience。同期原话与后期补入环境声/拟音在来源说明中区分，不增加新的role枚举。音乐cue必须写selection_reason，且全片有music_plan。可在music_plan的 `unscored_windows=[{start,end,reason}]` 记录无乐窗口（全片时间），并记录声音细节策略与实际听审状态；这些是设计记录，当前CLI不自动验证窗口是否无音乐或曲目是否合适。无乐用不安排music cue或明示包络实现，不能把整个混音静音。脚本不推断声音的情绪、不自动 duck；设计者将退让/恢复节点写到包络。`amix normalize=0` 保留设计相对平衡，随后整体二遍 loudnorm；总响度归一不能纠正被音乐盖住的人声。

## 检查阶段与边界

`design`：结构、已核查事实、来源、素材主观质量、有效尺寸、源时段、镜头作用/边界关系、复用、字幕、音轨与预算。`render` 增加文件/解码维度/实际时长探测。`publish` 增加许可与主观审阅门。

合成测试素材必须 origin=synthetic_test，并显式 `--allow-test-assets` 才能测试渲染；默认生产检查拒绝它们。测试夹具不进入真实成片。

字段只是声明。机器无法确认画面确实对应旁白、档案年份无误、许可依据足够、声线年轻自然，也无法测量所有字体字宽；这些由实际研究和审阅证据补足。
