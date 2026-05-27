---
name: jenkins-log
description: Jenkins build log viewer — fetch and display build console output
triggers:
  - jenkins-log
  - jenkins log
  - 构建日志
  - console output
---

# /jenkins-log — Build Log Viewer

Quick log viewing for Jenkins builds. Auto-resolves latest build number and supports full or tail log output.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/build-log oa-service` | 自动获取 oa-service 最新构建号，展示最后 100 行日志 |
| `/build-log oa-service 123` | 展示 build #123 的最后 100 行日志 |
| `/build-log oa-service full` | 自动获取最新构建号，展示完整日志 |
| `/build-log oa-service 123 full` | 展示 build #123 的完整日志 |
| `/build-log oa-service 123 full tail=50` | 展示 build #123 的最后 50 行日志 |

## 工作流

### 场景 1: 只有 job_name — 自动获取最新构建号

1. 解析用户输入:
   - `job_name`: 用户提供的 job 名称
   - 检查是否包含 "full" 关键字

2. 调用 `mcp__jenkins__jenkins_list_builds`，参数:
   - `job_name`: 用户指定的 job
   - 不指定数量，只需获取最近 1 次

3. 从返回结果中提取最新构建号 (lastBuild.number 或 builds[0].number)

4. 根据是否有 "full" 标志决定日志范围:
   - 有 "full": `tail` 参数设为 0 (获取完整日志)
   - 无 "full": `tail` 参数设为 100 (默认最后 100 行)

5. 调用 `mcp__jenkins__jenkins_get_build_log`，参数:
   - `job_name`: 同上
   - `build_number`: 步骤 3 获取的最新构建号
   - `tail`: 步骤 4 决定的值

6. 展示日志:
   ```
   ====== oa-service Build #123 日志 ======
   (最后 100 行 | 完整日志)

   [2024-01-15 14:30:00] Starting build...
   [2024-01-15 14:30:05] Fetching code...
   ...
   [2024-01-15 14:32:30] BUILD SUCCESS
   ```

### 场景 2: 有 job_name + build_number — 直接获取日志

1. 解析用户输入:
   - `job_name`: 用户提供的 job 名称
   - `build_number`: 用户提供的构建号
   - 检查是否包含 "full" 关键字
   - 检查是否有 `tail=N` 参数

2. 确定 tail 值:
   - "full" 关键字 → tail = 0 (完整日志)
   - "tail=N" 参数 → tail = N
   - 都没有 → tail = 100 (默认最后 100 行)

3. 调用 `mcp__jenkins__jenkins_get_build_log`，参数:
   - `job_name`: 同上
   - `build_number`: 用户指定的构建号
   - `tail`: 步骤 2 决定的值

4. 展示日志 (格式同场景 1)

### 场景 3: 日志过长时的处理

1. 如果返回的日志超过 200 行:
   - 展示前 50 行和最后 50 行
   - 中间显示 "... (省略 N 行) ..."

2. 提示用户:
   ```
   日志共 X 行，当前展示首尾各 50 行。
   使用 /build-log {job_name} {build_number} full 查看完整日志
   使用 /build-log {job_name} {build_number} tail=200 查看更多
   ```

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 默认只获取最后 100 行日志，避免返回过多内容
- "full" 关键字表示获取完整日志 (tail=0)
- 自动解析最新构建号，用户不需要手动查找
- 日志过长时自动截断展示，并提示用户如何获取更多
- 如果 job 不存在或构建号无效，展示友好的错误提示
