---
name: build-status
description: Quick Jenkins build status check — view job status, recent builds, and failure logs
triggers:
  - build-status
  - build status
  - 构建状态
  - jenkins status
  - 构建结果
---

# /build-status — Jenkins Build Status Check

Quick status check for Jenkins builds. Shows overview, recent builds, and auto-fetches failure logs when needed.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/build-status` | 列出所有 job 及最新状态，高亮失败和运行中的构建 |
| `/build-status oa-service` | 显示 oa-service 最近 5 次构建的状态 |
| `/build-status oa-service 123` | 显示 build #123 的详细信息 |
| `/build-status oa-service 123 --log` | 显示 build #123 的详细信息 + 失败日志 |

## 工作流

### 场景 1: 无参数 — 所有 Job 概览

1. 调用 `mcp__jenkins__jenkins_list_jobs` 获取所有 job 列表
2. 对每个 job，调用 `mcp__jenkins__jenkins_list_builds` 获取最近 1 次构建状态
3. 按状态分类展示:

   ```
   ====== Jenkins 构建概览 ======

   🔴 失败:
     oa-platform-php    #456  FAILURE  (10min ago)
     oa-integration     #289  FAILURE  (25min ago)

   🟡 运行中:
     oa-service         #123  BUILDING (2min ago)

   🟢 成功:
     oa-gateway         #789  SUCCESS  (5min ago)
     oa-frontend        #345  SUCCESS  (1h ago)
     oa-go              #112  SUCCESS  (3h ago)
     oa-web-app-v2      #567  SUCCESS  (5h ago)
   ```

4. 优先展示失败和运行中的构建
5. 使用 AskUserQuestion 询问用户:
   ```
   要查看哪个 Job 的详细信息？
   - 输入 job_name 查看最近构建
   - 输入 job_name + build_number 查看特定构建
   - 或输入 'n' 退出
   ```

### 场景 2: 有 job_name — 最近构建列表

1. 调用 `mcp__jenkins__jenkins_list_builds`，参数:
   - `job_name`: 用户指定的 job 名称
   - 不指定数量时默认展示最近 5 次

2. 展示构建列表:
   ```
   ====== oa-service 最近构建 ======

   #123  FAILURE   2024-01-15 14:30:00  耗时: 2m 30s
   #122  SUCCESS   2024-01-15 13:00:00  耗时: 2m 15s
   #121  SUCCESS   2024-01-15 11:00:00  耗时: 2m 20s
   #120  FAILURE   2024-01-14 16:00:00  耗时: 3m 10s
   #119  SUCCESS   2024-01-14 14:00:00  耗时: 2m 05s
   ```

3. 如果最近一次构建失败，自动调用 `mcp__jenkins__jenkins_get_build_log` 获取最后 30 行日志:
   - `job_name`: 同上
   - `build_number`: 最近失败的 build number
   - `tail`: 30

4. 展示失败日志摘要:
   ```
   ====== 最近失败日志 (#123, 最后 30 行) ======

   [ERROR] ...
   [ERROR] Failed to execute goal...
   ...
   ```

5. 使用 AskUserQuestion 询问:
   ```
   下一步操作:
   - 输入 build_number 查看特定构建详情
   - 输入 'full-log' 查看完整失败日志
   - 输入 'n' 退出
   ```

### 场景 3: 有 job_name + build_number — 构建详情

1. 调用 `mcp__jenkins__jenkins_get_build`，参数:
   - `job_name`: 用户指定的 job
   - `build_number`: 用户指定的构建号

2. 展示构建详情:
   ```
   ====== 构建详情 ======
   Job: oa-service
   Build: #123
   状态: FAILURE
   触发者: admin
   开始时间: 2024-01-15 14:30:00
   耗时: 2m 30s
   URL: {build_url}

   参数:
     test_version = kn
     oa_branch = feat/new-feature
   ```

3. 如果构建状态为 FAILURE:
   - 自动调用 `mcp__jenkins__jenkins_get_build_log` 获取最后 30 行
   - 展示失败日志

4. 如果用户加了 `--log` 标志或构建成功但想看日志:
   - 使用 AskUserQuestion 询问是否查看更多日志
   - 确认后调用 `mcp__jenkins__jenkins_get_build_log` 获取

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 失败构建必须自动获取日志 (最后 30 行)，不需要用户额外请求
- 概览页面必须优先展示失败和运行中的构建
- 使用 AskUserQuestion 引导用户查看更多详情，不要一次性展示所有信息
- 展示时间时使用相对时间 (如 "10min ago")，也保留绝对时间
