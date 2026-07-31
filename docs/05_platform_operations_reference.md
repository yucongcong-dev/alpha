# WorldQuant BRAIN 平台运营与顾问流程 Reference

> 目标：集中记录官网 FAQ 里和 Alpha 研究方法无直接关系、但使用平台时经常会遇到的运营信息。

这篇不是 Alpha 研究教程，也不是官网 FAQ 全文镜像。  
它只把顾问申请、Workday、银行账户、背景调查、Referral、账号支持等内容按场景整理，方便查入口和边界。

---

## 1. 这篇文档适合什么时候看

遇到下面这些问题时看这篇：

- 如何成为 BRAIN research consultant
- consultant onboarding 需要哪些步骤
- Workday 问卷、协议、背景调查卡住了怎么办
- conditional consultant 是什么状态
- 银行账户、付款、earnings 页面在哪里看
- referral program 怎么理解
- 账号、密码、登录、旧 VRC Alpha、平台技术问题怎么处理

如果问题是：

- Alpha 为什么不过 Sharpe / Fitness / Turnover
- 如何降低相关性、改善 PnL、处理 weight coverage
- 数据字段、模板、simulation settings 怎么研究

请回到：

- [02_research_and_data_guide.md](02_research_and_data_guide.md)
- [03_optimization_and_submission.md](03_optimization_and_submission.md)
- [04_platform_reference.md](04_platform_reference.md)

---

## 2. Research Consultant 机会

官网 FAQ 和 Starter Pack 对 consultant 的定位大致是：

- research consultant 是参与 WorldQuant 研究生态的一种机会
- 用户需要先在 BRAIN 平台积累研究表现或挑战积分
- 满足条件后，平台可能邀请或允许进入申请流程
- consultant 可能获得更多 region、dataset、功能和潜在 compensation 机会

需要注意：

- 达到某个积分或等级不等于自动成为 consultant
- 资格、地区、邀请、审批和合规要求都以平台当时展示为准
- 本仓库不应把 consultant 资格当成 Alpha 质量判断的一部分

相关 FAQ 主题包括：

- `What do I get as a research consultant?`
- `Can I become a BRAIN consultant? Who is eligible?`
- `Will I become a consultant when I achieve 10,000 points in the WorldQuant Challenge?`
- `Do consultants need programming experience?`
- `Can candidates under 18 years of age become research consultants?`

---

## 3. Consultant Onboarding 总流程

官网把成为 consultant 的流程拆成多个步骤。常见路径可以按下面理解：

1. 平台或邮件通知你进入申请 / onboarding 流程
2. 登录 Workday
3. 填写 background check questionnaire
4. 上传 National ID 或 Passport 等身份材料
5. 完成 Background Check Authorization
6. 签署 Consulting Agreement
7. 获得 conditional consultant 或后续 consultant 状态
8. 按要求补充银行账户信息
9. 等待背景调查、平台审核和付款信息更新

FAQ 里有分地区版本，例如 Mainland China 与其他地区的流程截图可能不同。实际操作时优先看平台发给你的地区版本。

这部分内容不要写入本仓库自动化逻辑，因为：

- 申请步骤可能变化
- 地区差异很大
- 涉及身份、合同、银行和合规信息

---

## 4. Workday 相关问题

Workday 是 onboarding 过程中常见的操作入口，FAQ 主要覆盖这些场景：

- signing into Workday
- background check questionnaire
- questionnaire sent back
- upload National ID or Passport
- background check authorization
- sign consulting agreement
- update bank account details

实操边界：

- Workday 密码、身份材料、银行信息都属于敏感信息
- 不要把这些信息保存进仓库、日志、运行目录或截图
- 如果流程卡住，优先通过官网 `Submit a request` 或对应 support 入口处理

常见问题：

- `Unable to sign into Workday. Workday is not accepting my password`
- `I submitted my documents on Workday but I have not received any confirmation`
- `Questionnaire Sent Back`
- `I cannot update my Bank account details on workday`

---

## 5. 背景调查

背景调查相关 FAQ 主要回答：

- 为什么需要 background check
- background check 会检查什么
- 需要提交哪些文件
- 文件格式、清晰度和上传要求
- 之前在 VRC 做过背景调查是否还需要再次做
- background check 卡住时联系谁
- 如何查看 background check 状态

文档边界：

- 这里只记录流程类别，不记录个人材料要求细节
- 具体文件、格式和有效期以 Workday / support 当前页面为准
- 不要把身份证件、护照、雇主信息或背景调查材料放入本仓库

---

## 6. Conditional Consultant

`conditional consultant` 可以理解为 onboarding 过程中的中间状态：

- 你已经进入 consultant 流程
- 但背景调查、合规审核、协议或银行信息等事项可能还未完全完成
- 某些权限、payment accrual 或功能开放可能受该状态影响

FAQ 中也有 IQC 场景下的 conditional consultant 问题，例如：

- 是否能开始 earning
- 是否能获得更多 regions、datasets、SuperAlphas 等访问
- IQC base payment 是否从某个状态之后开始计算

这些规则和赛季、地区、身份状态有关，不能写死进 Alpha 研究流程。

---

## 7. 银行账户、Earnings 和付款

官网 FAQ 覆盖的付款相关问题包括：

- 在哪里看 earnings
- 刚提交 Alpha 后什么时候能看到 payment 信息
- 页面上有 earnings 但银行账户未收到 payout 的原因
- 如何更新 bank account details
- 无法更新银行账户时怎么办
- IQC payment dates 或 consultant payment dates

需要特别注意：

- 银行账户信息是敏感数据
- 本仓库不保存、读取、自动填写或验证银行信息
- payment date、汇率、币种、税务和地区规则都可能变化

对本仓库来说，最多只保留一个原则：

- Alpha 是否通过 submission check 和是否产生平台 compensation 是两个不同层面的事情。

---

## 8. Referral Program

Referral FAQ 主要覆盖：

- 谁有资格 referral
- 如何 refer
- 什么算 successful referral
- 被推荐人忘记填写 referrer 怎么办
- 被推荐人申请被拒是否仍有 referral fee
- referral amount 如何 redeem
- 推荐到 IQC 或 BRAIN 是否有不同规则

这部分属于平台运营，不属于 Alpha 研究质量。

本仓库不根据 referral 信息调整：

- 字段优先级
- 模板优先级
- submission 决策
- 研究结果评分

---

## 9. Account 和登录支持

General FAQ 里的账号类问题包括：

- 如何重置密码
- 为什么需要每 4 小时重新登录
- profile 在哪里
- 如何修改密码
- 如何删除或停用账号
- account locked 后怎么办
- 旧 VRC Alpha 为什么缺失
- 能否在金融机构工作时使用 BRAIN

实操边界：

- 登录凭证由本仓库的 credentials 模块加密保存，只用于 API 访问
- 不要把密码、session、cookie、Authorization header 写入 docs、runs、feedback 或截图
- 浏览器阅读平台文档时，不检查 cookie、localStorage、密码或会话存储

---

## 10. 技术支持和 Report an Error

FAQ 里的技术支持常见主题包括：

- simulations 长时间运行怎么办
- concurrent simulations limit
- 平台页面加载慢
- BRAIN platform experiencing difficulties
- 如何生成 HAR file
- common error messages
- operator access 变化

本仓库处理方式：

- simulation 长时间 pending：运行器应保存状态并支持续跑
- concurrent limit：不要盲目增大发起并发，应等待或降低并行量
- API / 页面异常：区分平台异常、网络异常、认证异常和本地代码异常
- HAR file：只在 support 明确要求时由用户手动生成，避免自动收集敏感请求

---

## 11. 不进入本仓库研究逻辑的内容

以下信息可以在本篇作为平台操作参考，但不应进入 alpha 生成、筛选或提交策略：

- Workday 步骤细节
- 身份证件、护照、背景调查材料
- 银行账户、税务、币种、付款日期
- Referral 奖励
- IQC 组队、证书、赛季日期、付款日期
- 账号删除、密码重置、平台登录频率

这些内容的共同特点是：

- 动态变化
- 强地区差异
- 涉及个人敏感信息
- 不直接影响 Alpha 的研究质量

---

## 12. 官方入口

- [FAQ 首页](https://support.worldquantbrain.com/hc/en-us)
- [General FAQs](https://support.worldquantbrain.com/hc/en-us/categories/4413011872791-General-FAQs)
- [Getting Started for Users](https://support.worldquantbrain.com/hc/en-us/categories/11773945689495-Getting-Started-for-Users)
- [Process to become a BRAIN consultant](https://support.worldquantbrain.com/hc/en-us/categories/4412989948823-Process-to-become-a-BRAIN-consultant)
- [Submit a request](https://support.worldquantbrain.com/hc/en-us/requests/new)
- [IQC 2026](https://support.worldquantbrain.com/hc/en-us/categories/12713090684951-IQC-2026)
