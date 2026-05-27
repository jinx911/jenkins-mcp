---
name: jenkins-cancel
description: Cancel a running or queued Jenkins build
triggers:
  - jenkins-cancel
  - jenkins cancel
  - 取消构建
  - abort build
  - kill build
---

# /jenkins-cancel — Cancel Jenkins Build

Cancel a running or queued Jenkins build. Supports auto-resolving the latest build number.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/jenkins-cancel oa-service` | 自动获取 oa-service 最新构建，如果正在运行则提示取消 |
| `/jenkins-cancel oa-service 123` | 直接取消 build #123 |
| `/jenkins-cancel` | 列出所有正在运行/排队的构建，让用户选择取消 |

## 工作流

### 场景 1: 无参数 — 列出可取消的构建

1. 调用 `mcp__jenkins__jenkins_list_jobs` 获取所有 job
2. 对每个 job，调用 `mcp__jenkins__jenkins_list_builds` 获取最近 1 次，筛选状态为 BUILDING 或 queued 的
3. 使用 AskUserQuestion 展示正在运行/排队的构建:
   ```
   当前运行中的构建:
   - oa-service #123 (BUILDING, 已运行 2m)
   - oa-gateway #456 (BUILDING, 已运行 30s)

   请选择要取消的构建:
   ```
4. 用户选择后，进入场景 3

### 场景 2: 有 job_name — 取消最新运行中的构建

1. 调用 `mcp__jenkins__jenkins_list_builds`，参数:
   - `job_name`: 用户指定的 job
   - `limit`: 1

2. 检查最新构建状态:
   - 如果正在运行 (BUILDING):
     使用 AskUserQuestion 确认:
     ```
     确认取消 oa-service #123?
     该构建正在运行中，取消后不可恢复。
     ```
   - 如果已完成:
     ```
     oa-service 最新构建 #122 已完成 (SUCCESS)，无需取消。
     是否要取消特定构建号？请输入 build_number:
     ```

3. 用户确认后，进入场景 3

### 场景 3: 有 job_name + build_number — 执行取消

1. 调用 `mcp__jenkins__jenkins_cancel_build`，参数:
   - `job_name`: job 名称
   - `build_number`: 构建号

2. 展示结果:
   ```
   已取消 oa-service #123
   状态: ABORTED
   ```

3. 如果取消失败，展示错误信息并建议用户检查构建状态

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 取消操作必须先确认，不能直接执行
- 明确告知用户取消后不可恢复
- 如果构建已完成，提示用户无需取消
