# jenkins-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-green.svg)](https://modelcontextprotocol.io/)
[![Jenkins](https://img.shields.io/badge/Jenkins-CI%2FCD-red.svg)](https://www.jenkins.io/)

A **Model Context Protocol (MCP)** server for Jenkins CI/CD. Interact with your Jenkins instance directly from AI agents like Claude Code -- list jobs, trigger builds, check status, view logs, and more.

## Why jenkins-mcp?

Instead of switching to your browser to check build status or trigger deploys, ask your AI assistant. Jenkins-mcp bridges Jenkins and MCP-compatible AI tools, giving your agent full visibility into your CI/CD pipeline.

**Use it to:**

- Check build status across all jobs at a glance
- Trigger deployments with parameter selection
- Debug failed builds by pulling console logs
- Compare build parameters between runs
- Monitor the build queue

## Features

- **11 MCP tools** -- read-only, write, and advanced operations
- **7 Claude Code skills** -- `/jenkins-deploy`, `/jenkins-status`, `/jenkins-log`, `/jenkins-queue`, `/jenkins-cancel`, `/jenkins-compare`, `/jenkins-test` for interactive workflows
- **Password masking** -- sensitive parameters are automatically redacted
- **Folder support** -- works with folder-based Jenkins organizations via `JENKINS_FOLDER`
- **Build & watch** -- trigger a build and poll until completion
- **Build comparison** -- diff parameters between two builds side-by-side
- **Test reports** -- pull JUnit test results from any build

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp
./install.sh

# 2. Set environment variables
export JENKINS_URL="https://your-jenkins.example.com"
export JENKINS_USER="your-username"
export JENKINS_TOKEN="your-api-token"

# 3. Run
jenkins-mcp
```

See [Configuration](#configuration) for Claude Code integration.

## Installation

### Automated (recommended)

```bash
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp
chmod +x install.sh
./install.sh
```

The install script will:
1. Create a Python virtual environment (`.venv/`)
2. Install dependencies (`mcp`, `pydantic`, `httpx`)
3. Print instructions for configuring your MCP client

### Manual

```bash
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install mcp pydantic httpx
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JENKINS_URL` | Yes | -- | Jenkins base URL (e.g. `https://jenkins.example.com`) |
| `JENKINS_USER` | Yes | -- | Jenkins username |
| `JENKINS_TOKEN` | Yes | -- | Jenkins API token (generate at `/user/<you>/configure`) |
| `JENKINS_FOLDER` | No | -- | Folder path for folder-based Jenkins (e.g. `oa`) |

Generate your API token at: `https://<your-jenkins>/user/<username>/configure`

### Claude Code

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "jenkins": {
      "command": "/path/to/jenkins-mcp/.venv/bin/python",
      "args": ["/path/to/jenkins-mcp/jenkins_mcp.py"],
      "env": {
        "JENKINS_URL": "https://your-jenkins.example.com",
        "JENKINS_USER": "your-username",
        "JENKINS_TOKEN": "your-api-token",
        "JENKINS_FOLDER": ""
      }
    }
  }
}
```

Or use the `update-config` skill after installing.

## MCP Tools Reference

### Read-only

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `jenkins_list_jobs` | List all jobs with status (color, last build, URL) | -- |
| `jenkins_get_job` | Job details + parameter definitions | `job_name` |
| `jenkins_list_builds` | Build history for a job | `job_name`, `limit` (default 10) |
| `jenkins_get_build` | Build details: params, cause, duration, status | `job_name`, `build_number` |
| `jenkins_get_build_log` | Console output (tail mode) | `job_name`, `build_number`, `tail` (1-5000, default 200) |
| `jenkins_get_queue` | Current build queue with wait time and reasons | -- |

### Write

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `jenkins_build` | Trigger a build (with optional parameters) | `job_name`, `parameters` |
| `jenkins_build_and_watch` | Trigger build + poll until completion | `job_name`, `parameters`, `poll_interval` (3-60s), `timeout_seconds` (30-1800s) |
| `jenkins_cancel_build` | Cancel a running build | `job_name`, `build_number` |

### Advanced

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `jenkins_compare_builds` | Side-by-side diff of build parameters | `job_name`, `build_number_a`, `build_number_b` |
| `jenkins_get_test_report` | JUnit test results summary | `job_name`, `build_number` |

## Claude Code Skills

Seven slash-command skills are included for interactive workflows:

| Skill | Trigger | Description |
|-------|---------|-------------|
| `/jenkins-deploy` | `jenkins-deploy`, `/jenkins-deploy <job>` | Interactive build trigger -- lists jobs, presents parameter choices, triggers build, and watches for result |
| `/jenkins-status` | `jenkins-status`, `/jenkins-status <job>` | Quick status overview -- shows all jobs grouped by status, auto-fetches failure logs |
| `/jenkins-log` | `jenkins-log`, `/jenkins-log <job>` | Quick log viewer -- auto-resolves latest build, supports tail/full modes |
| `/jenkins-queue` | `jenkins-queue` | View build queue -- shows pending and queued builds |
| `/jenkins-cancel` | `jenkins-cancel <job>` | Cancel a running or queued build |
| `/jenkins-compare` | `jenkins-compare <job>` | Compare two builds -- parameters, duration, status |
| `/jenkins-test` | `jenkins-test <job>` | View test report -- test results, failures, statistics |

Install skills by copying the `skills/` directory into `~/.claude/skills/`.

## Usage Examples

### List all jobs

```
> List all Jenkins jobs

jenkins_list_jobs()

# Returns:
# | Job              | Status  | Last Build | URL                                    |
# |------------------|---------|------------|----------------------------------------|
# | oa-service       | blue    | #123       | https://jenkins.example.com/job/oa...  |
# | oa-gateway       | red     | #789       | https://jenkins.example.com/job/oa...  |
# | oa-platform-php  | blue    | #456       | https://jenkins.example.com/job/oa...  |
```

### Trigger a build with parameters

```
> Deploy oa-service to kn with branch feat/new-auth

jenkins_build(job_name="oa-service", parameters={
    "test_version": "kn",
    "oa_branch": "feat/new-auth"
})

# Returns:
# Build triggered successfully!
# Job: oa-service
# Queue URL: https://jenkins.example.com/queue/item/456/
```

### Trigger and wait for completion

```
> Build oa-service and wait for it

jenkins_build_and_watch(job_name="oa-service", parameters={
    "test_version": "kn",
    "oa_branch": "feat/new-auth"
}, poll_interval=10, timeout_seconds=600)

# Returns:
# Build #124 completed: SUCCESS
# Duration: 2m 30s
# URL: https://jenkins.example.com/job/oa-service/124/
```

### Check build log for failures

```
> Show me the log for oa-service build 123

jenkins_get_build_log(job_name="oa-service", build_number=123, tail=50)

# Returns the last 50 lines of console output
```

### Compare two builds

```
> Compare parameters of build 120 and 124 for oa-service

jenkins_compare_builds(
    job_name="oa-service",
    build_number_a=120,
    build_number_b=124
)

# Returns:
# | Parameter     | Build #120          | Build #124          |
# |---------------|---------------------|---------------------|
# | test_version  | kn                  | stage               |
# | oa_branch     | feat/old-feature    | feat/new-auth       |
```

### Get test results

```
> Show test results for oa-service build 124

jenkins_get_test_report(job_name="oa-service", build_number=124)

# Returns:
# Test Report for oa-service #124
# Total: 156 | Passed: 152 | Failed: 3 | Skipped: 1
# Duration: 45.2s
```

## Development

### Prerequisites

- Python 3.10+
- A Jenkins instance for testing

### Setup

```bash
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Project Structure

```
jenkins-mcp/
  jenkins_mcp.py     # Single-file MCP server (all 11 tools)
  skills/
    jenkins-deploy/   # /jenkins-deploy skill
    jenkins-status/   # /jenkins-status skill
    jenkins-log/      # /jenkins-log skill
    jenkins-queue/    # /jenkins-queue skill
    jenkins-cancel/   # /jenkins-cancel skill
    jenkins-compare/  # /jenkins-compare skill
    jenkins-test/     # /jenkins-test skill
  pyproject.toml      # Package metadata and dependencies
  LICENSE             # MIT
  .gitignore
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit with conventional commits (`feat:`, `fix:`, etc.)
6. Open a pull request

## License

[MIT](LICENSE) -- Copyright (c) 2025-2026 ElioJin

---

## 中文说明

### 项目简介

jenkins-mcp 是一个基于 Model Context Protocol (MCP) 的 Jenkins 服务器。它让你可以直接在 AI 助手（如 Claude Code）中操作 Jenkins -- 查看任务、触发构建、检查状态、获取日志，无需切换到浏览器。

### 安装

**一键安装：**

```bash
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp
chmod +x install.sh
./install.sh
```

**手动安装：**

```bash
git clone https://github.com/ElioJin/jenkins-mcp.git
cd jenkins-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install mcp pydantic httpx
```

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `JENKINS_URL` | 是 | Jenkins 地址 |
| `JENKINS_USER` | 是 | 用户名 |
| `JENKINS_TOKEN` | 是 | API Token（在 `/user/<用户名>/configure` 页面生成） |
| `JENKINS_FOLDER` | 否 | 文件夹路径（适用于按文件夹组织的 Jenkins） |

### 工具列表

| 工具 | 类型 | 说明 |
|------|------|------|
| `jenkins_list_jobs` | 只读 | 列出所有 Job 及状态 |
| `jenkins_get_job` | 只读 | 获取 Job 详情和参数定义 |
| `jenkins_list_builds` | 只读 | 获取构建历史 |
| `jenkins_get_build` | 只读 | 获取构建详情（参数、耗时、原因） |
| `jenkins_get_build_log` | 只读 | 获取控制台输出 |
| `jenkins_get_queue` | 只读 | 查看构建队列 |
| `jenkins_build` | 写入 | 触发构建 |
| `jenkins_build_and_watch` | 写入 | 触发构建并等待结果 |
| `jenkins_cancel_build` | 写入 | 取消正在运行的构建 |
| `jenkins_compare_builds` | 高级 | 对比两次构建的参数差异 |
| `jenkins_get_test_report` | 高级 | 获取测试报告 |

### Claude Code Skills

| 命令 | 说明 |
|------|------|
| `/jenkins-deploy` | 交互式部署 -- 选择 Job、填写参数、触发构建并等待结果 |
| `/jenkins-status` | 快速状态查看 -- 展示所有 Job 状态，自动拉取失败日志 |
| `/jenkins-log` | 快速日志查看 -- 自动解析最新构建号，支持 tail/full 模式 |
| `/jenkins-queue` | 查看构建队列 -- 展示排队中的构建 |
| `/jenkins-cancel` | 取消构建 -- 取消运行中或排队的构建 |
| `/jenkins-compare` | 对比构建 -- 对比两次构建的参数、耗时、状态 |
| `/jenkins-test` | 测试报告 -- 查看构建的测试结果和失败详情 |

### 使用示例

**触发部署：**
```
> 部署 oa-service 到 kn 环境，分支 feat/new-auth
```

**查看构建状态：**
```
> 查看 oa-service 最近的构建状态
```

**查看失败日志：**
```
> 显示 oa-service 第 123 次构建的日志
```

**对比构建参数：**
```
> 对比 oa-service 的 120 和 124 次构建参数
```
