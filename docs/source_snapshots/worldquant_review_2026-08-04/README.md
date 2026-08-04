# WorldQuant BRAIN 官网增量复核

复核日期：`2026-08-04`

本目录记录通过已登录 WorldQuant BRAIN 官网完成的增量复核，不重复保存没有变化的正文。
完整 Documentation 正文基线仍位于
[`worldquant_official_2026-08-03`](../worldquant_official_2026-08-03)，Operators 基线仍位于
[`worldquant_operators_2026-08-03`](../worldquant_operators_2026-08-03/README.md)。

## 复核结果

- Documentation 当前可见 `24` 篇，逐页读取了全部正文、链接和图片引用。
- 与 `2026-08-03` 正文基线相比，没有发现实质正文变化。
- `Introduction to BRAIN Expression Language` 从 `Discover BRAIN` 移到
  `Create Alphas`，当前页面路径也随之改变。
- 当前 section 数量为：Discover BRAIN `6`、Create Alphas `5`、Examples `3`、
  Interpret Results `2`、Understanding Data `5`、Advanced Topics `3`。
- Operators 当前仍为 `7` 个分类、`66` 个账号可见 `base` 算子；与基线相比，
  算子签名和页面说明均未变化。

## 边界

- 本轮使用官网渲染后的文章正文做增量比对；官网页面没有展示 API 的
  `lastModified` 和 `duration` 元数据，因此这些字段继续以 `2026-08-03` API 基线为准。
- 账号等级、平台版本和时间都会影响可见算子与内容，`24` 和 `66` 不是永久常量。
- 本目录保存目录结构和差异结论；没有变化的官网正文不再复制一份，避免每日复核制造重复镜像。

完整目录和机器可读结论见 [manifest.json](manifest.json)。
