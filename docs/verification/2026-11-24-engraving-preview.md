# 金石图腾界面本地预览验证（2026-11-24）

本次将所提供 UI 套件的第二、三、四模块接入实际界面：信源等级星印、朔望手卷与横梁、五卷纹样及深空金错／古拓羊皮主题。第一模块的三维榫卯轴未引入，既有地球与星图的几何、镜头和数据不变。

## 构建与数据

- 以 `VITE_PUBLIC_DEMO=1` 执行 `npm run build -- --base=/astraia/ --outDir ../.local/totem-preview/astraia --emptyOutDir`，其中 `tsc --noEmit` 与 Vite 均通过。Vite 提示有大体积代码块。
- `npm run test:portal`：12 项通过。`node web/scripts/check-syzygy-data.mjs`：11,216 个节点、39,736 条关系、2,266 条知识、73 条精选桥；快照为 `af7e6767a0285f6fe11196d0d489344eca42c966026fee68a4b66448524388dd`。
- 星印使用已有的信源等级，体裁与关系状态继续读取原有记录；横梁开关只控制星桥的显示。

## 中文显示与浏览器

- `python web/scripts/check-syzygy-cjk.py` 对图谱、书籍、界面代码及新增星印模块使用的 6,247 个汉字做字形覆盖检查；400 和 600 字重各检查 104 个字体文件，缺字均为 0。
- Edge 桌面 1440 × 900 和移动 390 × 844 预览中，中文标题与正文可见；正文可选择，脚本读取选区时得到中文。此轮没有生成或改写 PDF，也没有重跑 PDF 双引擎检查。
- 桌面测试了 S/A/B/C/F 五个星印、隐藏 F 开关、朔望横梁与顶栏星桥开关的联动、两种主题及刷新后保留、低动态偏好、五卷纹样、原典第 7 页图、经典图谱筛选；未见页面脚本错误或失败的资源请求。
- 移动端测试了抽屉切换、B 级筛选、古拓主题及水平溢出。经典与朔望视图往返、浏览器前进后退和筛选保持通过。

## 预览

- 本机服务：`http://127.0.0.1:4331/astraia/syzygy/`。
- 截图：`.local/totem-preview-dark.png`、`.local/totem-preview-parchment.png`、`.local/totem-preview-mobile-index.png` 和 `.local/totem-preview-mobile-codex.png`。
- 本机预览为静态构建；页图与分享资源由本机现有预览资源补齐。本次没有推送或部署。
