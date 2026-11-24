# OMNIA 万象星枢：原书与图表

`handbook.qmd` 是《格物识微》手册原稿；`entries/` 保留拆分后的 UTF-8 条目。前端使用 `web/public/knowledge/data.json`，并可打开原版 `handbook.pdf`。五卷中的节点按学科分布在星系里，节点之间的关联来自原书交叉引用。

OMNIA 提供三维星系和同一坐标的二维正投影星盘。点击学科或条目聚焦；长按条目时，其原书引用的上下游节点临时聚拢，松手回到原位。搜索按标题、正文与图注匹配，显示原书摘录及页码，最多点亮前 30 项；搜索轨迹表示检索顺序，不表示原书断言了这些条目之间的因果关系。条目可加入观测列表并添加笔记，数据保存在当前浏览器的本地存储中，不随仓库或网站发布。

图谱采用预计算的节点坐标；不支持硬件加速时使用按需重绘的 Canvas 视图。当前手册并未为所有知识条目标注可核验的宇宙事件年代，因此不推测知识节点的历史时间，也不生成伪造的演化时间轴。

手册中的 750 个 Typst 区块包含 438 幅实际图表和 312 个排版标记。实际图表已生成自包含 SVG，文字与原图出处保存在 `inline-figures/manifest.json`；296 处原生插图引用另外指向 295 个原图文件。涉及中文的原生 SVG 和图表内嵌 SVG 使用 SIL OFL 许可字体的子集，许可文件分别随图表目录保存。字体子集、原文件及结果的哈希记录见 `figures/font-report.json`。

重新生成转绘图表需要原手册资源目录及其字体、`pdftotext`，并安装可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[figures]'
.\.venv\Scripts\python.exe -m pipeline.render_life_figures --assets-root '原手册资源目录'
.\.venv\Scripts\python.exe -m pipeline.build_life_knowledge --source knowledge/handbook.qmd --pdf web/public/knowledge/handbook.pdf --pdftotext 'pdftotext可执行文件'
.\.venv\Scripts\python.exe -m unittest tests.test_life_figures -v
```

原生 SVG 如需从未嵌字体的源图重新生成，可用 `pipeline.embed_handbook_svg_fonts` 输出到独立目录，核对每张图的哈希和字体许可后再复制到发布目录。脚本会拒绝缺字或重复嵌入，不静默依赖系统字体。
