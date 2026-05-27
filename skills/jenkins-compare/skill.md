---
name: jenkins-compare
description: Compare two Jenkins builds — parameters, duration, status differences
triggers:
  - jenkins-compare
  - jenkins compare
  - 对比构建
  - compare builds
  - build diff
---

# /jenkins-compare — Compare Jenkins Builds

Compare two builds of the same job to find differences in parameters, duration, and status.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/jenkins-compare oa-service` | 自动对比 oa-service 最近两次构建 |
| `/jenkins-compare oa-service 123 124` | 对比 build #123 和 #124 |
| `/jenkins-compare oa-service 123` | 对比 build #123 与前一个 build (#122) |

## 工作流

### 场景 1: 只有 job_name — 自动对比最近两次

1. 调用 `mcp__jenkins__jenkins_list_builds`，参数:
   - `job_name`: 用户指定的 job
   - `limit`: 2

2. 提取最近两次构建号，进入场景 3

### 场景 2: 有 job_name + 一个 build_number — 与前一次对比

1. 解析输入:
   - `job_name`: job 名称
   - `build_number`: 用户指定的构建号
   - 对比目标: build_number - 1

2. 进入场景 3

### 场景 3: 执行对比

1. 调用 `mcp__jenkins__jenkins_compare_builds`，参数:
   - `job_name`: job 名称
   - `build_number_1`: 较早的构建号
   - `build_number_2`: 较新的构建号

2. 展示对比结果:
   ```
   ====== 构建对比 ======
   Job: oa-service
   Build #122 vs #123

   状态:
     #122: SUCCESS → #123: FAILURE  ⚠️

   耗时:
     #122: 2m 15s → #123: 2m 30s (+15s)

   参数变化:
     test_version: kn → kn (无变化)
     oa_branch: master → feat/new-feature  ← 变更

   触发者:
     #122: admin → #123: admin (无变化)
   ```

3. 如果两次构建参数有变化，高亮显示变更项

4. 如果最近一次从成功变为失败，提示:
   ```
   构建从 SUCCESS 变为 FAILURE，参数变更可能是原因。
   使用 /jenkins-log {job_name} {build_number} 查看失败日志
   ```

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 参数变化必须高亮显示
- 状态从 SUCCESS 变为 FAILURE 时自动提示查看日志
- 耗时差异显示为 +/- 增量
