# Astraia 界面统一与命名验证（2026-11-25）

Antigravity 会话报告独立预览分支 `ui-unification-preview`，提交短号 `bc11d8a`。该分支未推送：本次通过其文件查看器导出 19 个修改文件，在以 `41d9bb58` 为基线的本机独立工作树中构建；未核对云端完整提交哈希。按用户确认，将入口与馆藏导览中的模块名称恢复为「朔望叠影」，小屏短标签为「叠影」，对读内容本身的描述予以保留。

- `VITE_PUBLIC_DEMO=1 npm run build -- --base=/astraia/` 通过，包含 TypeScript 检查；Vite 有大体积代码块提示。`npm run test:portal` 的 12 项测试通过。
- 数据一致性脚本验证 11,216 个图谱节点、39,736 条关系、2,266 个知识条目及 73 条精选星桥；快照为 `af7e6767a0285f6fe11196d0d489344eca42c966026fee68a4b66448524388dd`。发布准备时核对九个数据文件及 129 个正文分片与线上现有版本一致。
- Edge 1440 × 900 和 390 × 844 检查了新名称及其无障碍标签、经典／朔望切换、展卷并读、古拓羊皮、F 级筛选、原典第 7 页图和移动端布局；未发现脚本错误、站内资源失败或水平溢出。经典与朔望视图往返、浏览器前进后退和筛选保持通过。
- 字体覆盖检查涵盖图谱、知识正文和界面使用的 6,247 个汉字，400、600 字重缺字均为 0；桌面与手机浏览器实际截图中的中文可见。本次没有生成或改写 PDF，未重新运行 PDF 双引擎检查。
- 预览截图及浏览器检查记录保存在工作区 `.local/antigravity-release-desktop.png`、`.local/antigravity-release-mobile.png`、`.local/antigravity-name-qa.log` 和 `.local/antigravity-release-qa.log`。

## 线上复核

- 公开站点提交 `80d97e28fb95e374670f4faf25bcca4bb7ba2a0b` 的两条 GitHub Pages 部署流程均成功。两个入口页面及三个相关脚本返回 HTTP 200，SHA-256 与本地发布包一致。
- Edge 公网桌面及移动端复测：入口分别显示「朔望叠影」与短名称「叠影」，无障碍名称为「切换到朔望叠影视图」，馆藏导览使用「朔望叠影」；入口与返回切换、浏览器前进后退、筛选保持、展卷并读、主题、F 级筛选和原典第 7 页图均通过。朔望画布读取到 11,216 个图谱节点，知识目录显示 2,266 条目。
- 使用 SwiftShader 的 WebGL 测试朔望地球仪：标点悬停、点击打开对应卷宗、拖动、缩放及维度切换通过，未见页面脚本错误；记录为 `.local/antigravity-live-globe-qa.log`。
- 线上检查记录保存在 `.local/antigravity-name-live.log`、`.local/antigravity-live-qa.log` 和 `.local/antigravity-live-router.log`；名称截图保存在 `.local/antigravity-name-desktop.png`、`.local/antigravity-name-mobile.png`。名称截图的经典地图使用刻意关闭 GPU 和软件光栅化的测试浏览器，不作为地图画面验证。
