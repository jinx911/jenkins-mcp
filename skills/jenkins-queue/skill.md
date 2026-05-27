---
name: jenkins-queue
description: View Jenkins build queue — check pending and running builds, manage queue
triggers:
  - jenkins-queue
  - jenkins queue
  - build queue
  - 构建队列
  - 排队
---

# /jenkins-queue — Jenkins Build Queue Viewer

View and manage the Jenkins build queue. Shows pending builds waiting for executor slots.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/jenkins-queue` | 显示当前构建队列中的所有等待任务 |

## 工作流

### 场景 1: 查看构建队列

1. 调用 `mcp__jenkins__jenkins_get_queue` 获取当前队列

2. 展示队列信息:

   ```
   ====== Jenkins 构建队列 ======

   当前排队任务: 3

   1. oa-service (等待中, 已等 30s)
      参数: test_version=kn, oa_branch=feat/xxx
      原因: 等待执行器

   2. oa-gateway (等待中, 已等 15s)
      参数: test_version=kn, oa_branch=master

   3. oa-platform-php (阻塞中)
      参数: test_version=stage, platform_branch=master
      原因: 等待 oa-platform-php #456 完成
   ```

3. 如果队列为空:
   ```
   ====== Jenkins 构建队列 ======
   当前无排队任务
   ```

4. 如果有排队任务，使用 AskUserQuestion 询问:
   ```
   排队中有 N 个任务，是否需要操作？
   - 输入 job_name + build_number 取消排队 (使用 /jenkins-cancel)
   - 输入 'n' 退出
   ```

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 队列为空时给出明确提示
- 有排队任务时引导用户使用 /jenkins-cancel 取消不需要的任务
