# 数据许可与处理边界

## 已授权的示例数据

delu543 将以下由本项目自行编写、无真实用户资料的示例 JSON 文件按 **CC0-1.0 Universal** 提供：

- [brief.example.json](skills/ai-video-production/assets/brief.example.json)
- [project.example.json](skills/ai-video-production/assets/project.example.json)

适用范围包括这两份文件的结构与示例值，仅限贡献者/维护者有权处置的权利。可复用、修改和分发，用于商业或非商业项目；它们只是格式示例，事实/来源占位不是已核查的研究数据。

全文见 [LICENSES/CC0-1.0.txt](LICENSES/CC0-1.0.txt)，官方依据为 [CC0 Legal Code](https://creativecommons.org/publicdomain/zero/1.0/legalcode)。逐文件范围见 [licensing.json](licensing.json)。其余项目自有代码、文档、测试程序、规则与验收模板按根目录 [MIT](LICENSE) 提供。

## 不属于开放数据的内容

本仓库不包含公开授权的真实素材库、客户项目数据集或训练数据集。具体项目中的文案、上传资料、来源摘录、采访、肖像/音色、音频、视频、照片、字幕、成片、账单和登录数据不会因为使用本工具而变成 MIT/CC0 数据。

用户原有权利仍按其原始授权与相关条件处理；第三方内容保留原有许可。数据可访问不等于可转载、商用或用于训练。版权、数据库权、隐私、肖像、商标、声音授权与平台条款各自核查，不能用 CC0 标签替代其他人的必要许可。

## 处理与交接

- 默认项目数据留在仓库外本地，CLI 不上传资料或自动训练模型。
- 调用 TTS/ASR/音乐等外部服务前确认当次有效授权、必要上传范围、目标服务和适用条款；服务的保留/训练政策以当时账户条款为准，不承诺所有服务都零保留。
- 媒体记录来源、作者、原始时间、许可链接、使用依据、用途、署名要求、核查状态；保留必要许可证明。未知状态不得标为已具备发布权。
- 工程/原文件交接与成片发布分别核对权限。可交付视频不意味着可以把其素材另行再分发。
- 不将真实项目资料、截图、私人对话、密钥、账单或原素材提交到公开仓库/Issue。保留与删除按用户明确要求处理，工具不自行清理项目。

详细操作规则见 [Skill 的许可规范](skills/ai-video-production/references/licensing.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。新增开放数据必须有来源/授权记录，明确许可证并更新清单；不能自动继承这两份示例文件的 CC0 范围。
