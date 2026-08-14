# AI-Work-Watcher

**把每次 AI 编程请求，变成更清楚的 Prompt、可验证的流程和可复用的改进。**

[English](README.md)

> **Alpha · 0.2.0a1。** 面向使用 Codex CLI 或 Claude Code 的个人开发者；稳定版之前，接口与本地数据格式仍可能变化。

AI-Work-Watcher 是一个本地优先的 AI 工作流教练与 Prompt 管理系统。任务开始前，Agent Skill 会结合你的原始请求与工程上下文，生成待批准的任务简报和改良 Prompt；任务结束后，只记录结果、验证、返工以及结果约束下的效率证据；长期使用时，再提议把有效 Prompt、流程和工程上下文沉淀为版本化资产。它不保存完整对话，也不会静默修改仓库。

```text
准备                 执行                  收尾                 改进
请求 + 工程上下文 → 批准任务简报 → Codex/Claude 工作 → 证据 → 可复用资产
```

## 为什么需要它

AI 编程低效，往往不是因为单次 token 多，而是目标模糊、验收标准缺失、工程指令过期、验证不完整，或者同一种 Prompt 返工反复出现。AI-Work-Watcher 让这些流程问题变得可见、可验证、可逐步改善。成本只是可选的效率信号，而且必须先满足任务结果与质量要求。

## 当前 Alpha 已实现

- Prepare 生成可批准的任务简报：目标、上下文、约束、验收标准、未知项、推荐流程与改良 Prompt。
- Finish 记录结构化证据，但不保存完整回复、transcript、源码、diff、patch 或终端输出。
- 独立跟踪任务定义、上下文结构、Prompt 有效性、执行与验证、结果约束效率五个维度；每项引用证据，不计算总分。
- 扫描关键工程路径、类型和哈希，识别上下文漂移，同时排除常见 secrets、依赖目录和生成树。
- 将成功 Prompt 与流程晋升为 `.ai-work-watcher/` 下不可覆盖的递增版本。
- 同一项目至少完成三个任务，并由用户在当前会话确认后，才允许生成趋势。
- 为 Codex CLI 与 Claude Code 安装同一套 Skill 和低置信度 SessionEnd 兜底。
- 归档 v0 旧数据，但不把旧评分转换到新模型。

## 安装

要求：macOS、Python 3.9–3.13，以及 Codex CLI 或 Claude Code 至少一个。

```bash
git clone https://github.com/Jinchengawu/AI-Work-Watcher.git
cd AI-Work-Watcher
python3 -m pip install -e .
ai-work-watcher install
ai-work-watcher doctor
```

`install` 会添加用户级 Skill 链接、引导指令和 SessionEnd Hook；不会安装周调度器，也不会在后台调用模型。`doctor` 会分别报告 Codex 与 Claude Code 状态，未安装的宿主显示为跳过。

## 第一次使用

项目必须显式登记；父目录或无关仓库不会自动进入观察范围。

```bash
cd /path/to/your-project
ai-work-watcher project add . --name my-project
```

随后在这个项目里启动 Codex CLI 或 Claude Code，并输入：

```text
使用 $ai-work-watcher 准备这个任务：
增加 CSV 导出，同时保持现有 JSON 格式不变。
```

Skill 会检查工程指令和测试入口，指出缺失的验收标准，并展示任务简报与改良 Prompt。你批准之前，既不会记录任务，也不会修改项目文件。执行结束后，让 Skill 完成 Finish；确定性 CLI 会把精简记录保存在私人目录。

## 五维教练模型

每个 Finish 诊断都包含 `score: 1–5 | null`、对应状态、置信度、证据 ID、诊断和下一步。

| 维度 | 要回答的问题 |
| --- | --- |
| `task_definition` | 目标、约束和验收标准是否清楚？ |
| `context_structure` | Prompt 是否与工程结构、指令和现状一致？ |
| `prompt_effectiveness` | Prompt 是否减少歧义并推动有效执行？ |
| `execution_verification` | 流程选择、执行顺序和验证是否完整？ |
| `result_adjusted_efficiency` | 结果和质量达标后，返工、时间、轮次、token 与费用是否合理？ |

1–5 分依次映射为 `needs_attention`、`unstable`、`developing`、`healthy`、`repeatable`；证据不足时为 `unknown`。失败或质量下降的任务，不能仅凭 token 少或费用低获得更好的效率评价。

## 命令

```text
ai-work-watcher install | uninstall | doctor
ai-work-watcher project add | remove | list | inspect
ai-work-watcher task prepare | finish --stdin
ai-work-watcher prompt list | show | promote | archive
ai-work-watcher trends generate --stdin
ai-work-watcher proposal accept | reject | verify
ai-work-watcher migrate legacy-v0
ai-work-watcher prune
```

Prepare、Finish 和趋势判断应通过 Agent Skill 使用。CLI 负责校验和保存已经批准的结构化输入，不是后台分析器。

## 数据与批准边界

私人数据保存在 `~/.ai-work-watcher/`：配置、已批准的任务简报与 Prompt、精简结果、结构快照、观察、提案、趋势报告和迁移归档。可共享且已批准的资产保存在项目内：

```text
.ai-work-watcher/
├── project.md
├── prompts/
│   ├── index.json
│   └── <name>-r<N>.md
└── workflows/
    ├── index.json
    └── <name>-r<N>.md
```

当前 Alpha 不保存完整模型回复、transcript、源码、diff、patch、终端输出或 secrets。任何项目级改动都需要具体提案和明确批准。源码目录重组不属于同一次教练流程；AI-Work-Watcher 只会为它另行生成实施计划。

更多细节见[协议](docs/protocol.md)、[评估范围](docs/evaluation.md)与[安全政策](SECURITY.md)。

## 当前限制

- 仅面向个人开发者；不提供团队权限、员工评价或管理看板。
- 仅支持 Codex CLI 与 Claude Code，尚未支持其他 Agent 宿主。
- 没有 Web UI、托管服务、发布自动化或默认后台分析。
- 趋势质量依赖至少三个已完成任务及真实的结构化证据。
- Alpha 迁移会保留旧数据归档，但不会转换旧评分。

## 开发

```bash
python3 -m unittest discover -s tests -v
python3 .agents/skills/ai-work-watcher/scripts/validate_skill.py .agents/skills/ai-work-watcher
git diff --check
```

欢迎贡献，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。项目采用 [MIT License](LICENSE)。
