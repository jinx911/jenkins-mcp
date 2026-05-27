---
name: jenkins-test-report
description: View Jenkins test report — test results, failures, and statistics for a build
triggers:
  - jenkins-test-report
  - jenkins test
  - test report
  - 测试报告
  - 测试结果
---

# /jenkins-test-report — Jenkins Test Report Viewer

View test reports for Jenkins builds. Shows test statistics, failed tests, and error details.

## 使用场景

| 用户输入 | 行为 |
|---------|------|
| `/jenkins-test-report oa-service` | 自动获取 oa-service 最新构建的测试报告 |
| `/jenkins-test-report oa-service 123` | 查看 build #123 的测试报告 |

## 工作流

### 场景 1: 只有 job_name — 自动获取最新构建号

1. 调用 `mcp__jenkins__jenkins_list_builds`，参数:
   - `job_name`: 用户指定的 job
   - `limit`: 1

2. 从返回结果中提取最新构建号

3. 进入场景 3

### 场景 2: 有 job_name + build_number — 直接获取

1. 解析输入:
   - `job_name`: job 名称
   - `build_number`: 构建号

2. 进入场景 3

### 场景 3: 展示测试报告

1. 调用 `mcp__jenkins__jenkins_get_test_report`，参数:
   - `job_name`: job 名称
   - `build_number`: 构建号

2. 展示测试报告:

   ```
   ====== oa-service #123 测试报告 ======

   总计: 150 | 通过: 145 | 失败: 3 | 跳过: 2
   通过率: 96.7%

   失败的测试:
   ─────────────────────
   1. TestUserService.testCreateUser
      错误: Expected status 201 but got 500
      耗时: 2.3s
      包: com.oa.service.user

   2. TestAuthService.testTokenRefresh
      错误: NullPointerException at AuthService.java:45
      耗时: 0.1s
      包: com.oa.service.auth

   3. TestReportService.testGeneratePDF
      错误: Timeout waiting for PDF generation
      耗时: 30.0s
      包: com.oa.service.report

   跳过的测试:
   ─────────────────────
   1. TestIntegration.testEmailSend (条件不满足)
   2. TestIntegration.testSMSNotify (条件不满足)
   ```

3. 如果没有测试报告:
   ```
   oa-service #123 没有测试报告。
   可能该构建没有配置测试步骤。
   ```

4. 如果全部通过:
   ```
   ====== oa-service #123 测试报告 ======
   总计: 150 | 通过: 150 | 失败: 0 | 跳过: 0
   通过率: 100% ✅

   所有测试通过!
   ```

## 重要规则

- 所有 Jenkins 操作必须通过 MCP 工具 (`mcp__jenkins__jenkins_*`) 执行，禁止使用 curl/bash
- 失败的测试必须展示详细信息（错误信息、耗时、包名）
- 通过率需要计算并展示
- 没有测试报告时给出明确提示
- 自动解析最新构建号，用户不需要手动查找
