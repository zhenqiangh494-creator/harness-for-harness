# Harness Engineering Agent

这个工程提供一个闭环 harness engineering agent：输入任务说明和评价指标，调用大模型 API 生成 harness 工程代码，运行评测命令，把失败输出和指标反馈喂回模型，然后自动调整文件结构、测试和实现。

核心目标不是一次性生成代码，而是让 agent 在 `generate -> test -> reflect -> redesign -> patch` 的循环里持续优化，直到指标达标或达到迭代上限。

## 快速开始

先准备任务和指标：

```powershell
python -m harness_agent run --task examples/task.md --metrics examples/metrics.json --out .harness_runs/demo --mock
```

`--mock` 不调用 API，用于验证本地闭环流程。真实调用大模型时设置环境变量：

```powershell
$env:HARNESS_LLM_API_KEY="你的 API key"
$env:HARNESS_LLM_MODEL="你的模型名"
python -m harness_agent run --task examples/task.md --metrics examples/metrics.json --out .harness_runs/real
```

默认接口是 OpenAI-compatible Chat Completions：

```text
HARNESS_LLM_BASE_URL=https://api.openai.com/v1
HARNESS_LLM_API_KEY=...
HARNESS_LLM_MODEL=...
```

如果你使用兼容 OpenAI 协议的国内或私有模型服务，只需要改 `HARNESS_LLM_BASE_URL`、`HARNESS_LLM_API_KEY` 和 `HARNESS_LLM_MODEL`。

## 输入格式

任务可以是文件路径，也可以是短文本：

```powershell
python -m harness_agent run --task "为客服问答构建离线评测 harness" --metrics examples/metrics.json --out .harness_runs/support_eval
```

指标文件是 JSON：

```json
{
  "max_iterations": 5,
  "target_score": 1.0,
  "commands": [
    {
      "name": "unit",
      "command": "python -m unittest discover -s tests",
      "timeout_seconds": 120
    }
  ]
}
```

每条 command 在生成的 harness 工程目录中执行。默认用退出码判断是否通过，也可以用正则提取分数：

```json
{
  "name": "score",
  "command": "python evaluate.py",
  "score_regex": "score=([0-9.]+)",
  "timeout_seconds": 120
}
```

## 输出结构

`--out` 指向 agent 生成的 harness 工程目录。目录中会包含模型生成的源码、测试、文档，以及隐藏的 `.harness_agent/iterations` 记录每轮 proposal、评测结果和反馈。

## 设计约束

- 所有生成文件都限制在 `--out` 目录内。
- 模型必须返回严格 JSON proposal，agent 会解析并应用完整文件内容。
- 评测命令是闭环的真实反馈来源，模型不能只靠自述判断成功。
- API key 只从环境变量读取，不写入生成代码或日志。
- 默认不依赖第三方 Python 包，方便在空环境运行。

## 常用命令

```powershell
python -m unittest discover -s tests
python -m harness_agent run --task examples/task.md --metrics examples/metrics.json --out .harness_runs/demo --mock
```
