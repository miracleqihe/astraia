# Astraia · 全球灵异、神话与民俗地图

**[打开 Astraia 在线图谱](https://miracleqihe.github.io/astraia/)**

线上图谱可直接阅读带出处的故事梗概、事件经过、档案提要与《子不语》古籍转录。“现代异闻”汇集有公开来源的都市传说与异常事件报道。各条记录保留原有复核状态。

Astraia 将地方档案、神话文本和研究文献整理成本地图谱。`vault/` 保存可以直接在 Obsidian 中打开的 UTF-8 Markdown 卡片。编译器读取 YAML 属性和正文，生成供浏览与查询使用的图谱快照。

私有仓库包含草稿、复核导出和本次纳语对照所需的指定快照；其他 `.local/` 采集资料仍只保存在原电脑。迁移后可浏览已提交的复核导出，但重新采集或重建全部批次时，需要补齐相应的本地原始快照。公开网页不包含本地复核页面或本地原始快照。

## 启动本地前端

在项目根目录运行以下 PowerShell 命令。已有图谱快照时可以直接启动。首次安装后，前端从本机读取图谱、底图和字体。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.catalogue --output web/public/data/catalogue_data.json
Set-Location web
npm.cmd ci
npm.cmd run dev
```

打开 [本地前端](http://127.0.0.1:5173/)。顶部可在 **UMBRA · 坤舆异志** 地图、**SIDERA · 玄象星络** 四层星图和 **OMNIA · 万象星枢** 知识星图之间切换。右侧馆藏导览提供地域与内容分类；资料目录可以交叉筛选地域、类型和图谱层级，再逐页展开更多条目。地图和民俗星图共用选中节点及虚构过滤状态。点选标记、星图节点或目录项可阅读卷宗，带坐标的卷宗可用“在地图定位”放大相应地点。链接可用 `?story=节点ID` 直达卷宗。 [近现代种子对照索引](reference/modern_seed_crosswalk.md)

顶部的“资料复核”进入逐条清单，也可直接打开 [本地复核页面](http://127.0.0.1:5173/review/index.html)。清单覆盖全部待审批次，显示原始字段、出处、坐标依据、标准码及待核对项。筛选支持出处、坐标、标准码、体裁、优先事项和复核状态。

复核页可按中国及相关资料、东亚其他地区、东南亚和跨区域馆藏筛选，再选择具体批次。原作梗概及其对应出处写在 `reference/reading_notes.yaml`；编号按卡片的来源顺序，之后才是补充出处。公开版按固定修订附载《子不语》公有领域原作的维基文库转录，并保留署名和许可链接。其他转录、档案正文与录音继续沿各自载体查阅。

地图概览使用本地 Natural Earth 1∶5000 万边界和城市坐标，放大后通过 OpenFreeMap 加载 OpenStreetMap 街区、水系和地名。地点重叠时可展开该点的资料，“此处条目”可列出视野中的记录。离线时可查看概览及图谱已有标点。地图区分地标定位与城区或区域参考点。 [Natural Earth 底图数据](https://github.com/topojson/world-atlas#countries-50mjson) [OpenFreeMap](https://openfreemap.org/)

更新 `vault/` 或阅读稿后，在项目根目录重新运行上面的 `pipeline.catalogue` 命令，再刷新前端。本地前端优先读取 `catalogue_data.json`；如果这个文件存在，只更新 `graph_data.json` 不会替换它。公开站点从发布图谱生成精简索引和正文文件：地图与星点先加载，正文及出处随后载入，并校验二者的快照与内容哈希。`npm run dev` 和 `npm run build` 会根据本地数据重新生成索引；正式发布时则从实际发布的快照重新生成，避免混用版本。若需要运行生产构建，在 `web/` 中执行以下命令，浏览器打开终端给出的本地地址。

```powershell
npm.cmd run build
npm.cmd run preview
```

## OMNIA 万象星枢（Life and Knowledge）

顶部第三个视图收录《格物识微》增绘版的五卷、二十门及 2,266 个条目。可切换三维星系和二维星盘，按学科浏览或检索原书正文及图注，并打开对应 PDF 页面。长按节点可暂时聚拢原书已引用的关联节点；搜索结果可在图上点亮，个人观测列表和笔记保存在当前浏览器。原书中的图表和图注保留在 PDF 中，手册原文注明急救、化学暴露与法医学专题为尚未经持证专业人员逐项审签的教学草稿。

原始 QMD 保存在 `knowledge/handbook.qmd`，逐条文字稿在 `knowledge/entries/`，网页数据、正文图像与原版 PDF 在 `web/public/knowledge/`。更新手册源稿后可使用 Poppler 的 `pdftotext` 重新生成（输入 PDF 须对应同一版源稿）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.build_life_knowledge --source knowledge/handbook.qmd --pdf web/public/knowledge/handbook.pdf --pdftotext 'pdftotext'
```

## 朔望叠影与经典图谱

顶部“朔望叠影”进入另一套三维呈现，“经典图谱”返回原来的地图、四层星图或万象星枢，并保留所选条目的定位。朔望视图连接同一份完整民俗目录与《格物识微》：有真实坐标的资料显示在地球上，所有图谱节点均可在目录检索或在玄象星域中查看。没有坐标的记录只提供目录和星络入口，不指定虚构地点。隐藏 F 级虚构的开关在两套视图中均可使用。

“心物桥接”提供 12 条以现有资料为基础整理的精选对读。任意民俗条目还可以通过卷宗内的“穿界星门”检索原书词条，建立一条自选对读星桥；也可以先选择知识词条，再选择民俗条目。关键词建议与人工选择只表示对读，不自动构成已证实的因果关联。浏览器地址保留一对自选条目，可用于分享；该选择不修改 `vault/`。有硬件加速时使用 WebGL，没有时使用同一数据的轻量画布投影。

前端构建时会基于实际图谱快照和原书词条生成 `syzygy/matches.json`：题名、别名与本地双语词表支持主题候选，来源类型支持阅读指引。界面分别标注两者，并单独显示原图谱中个案与机制之间已有的证据状态；算法不创建新的“已证实”关系。选中原书条目时可反向浏览、筛选匹配到的民俗资料。上下文对读、信源等级与 F 级开关在经典和朔望视图间传递；更换所选条目后会清除不再对应的旧配对。

两套视图在同一页面内切换并保留各自的画布，浏览器前进、后退和现有深链接仍可使用。朔望卷宗按需读取经 SHA-256 校验的故事与原书正文分片；体裁筛选只采用资料中已有的标记，未分类的资料不会被自动猜测。原书条目提供同学科前后翻阅和原版 PDF 物理页的按需图文阅读。

本地如果需要生成原典页图，先安装 `pip install -e ".[pages]"` 并确保 Poppler 的 `pdftotext`、`pdffonts` 在 PATH 中，再从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe pipeline/build_handbook_pages.py --output web/public/knowledge/pages
```

该步骤保留原有 PDF，使用 Poppler 和 PDFium 核对每页中文与条目编号，并生成可单页加载的 WebP。公开发布时会从实际发布的图谱和原书重建分片、原典页图与单条目分享页。仅在本地预览分享页时，可运行 `node web/scripts/build-share-pages.mjs web/public/data/graph_data.json web/public https://miracleqihe.github.io/astraia/`。

数据一致性与中文覆盖检查可从项目根目录运行：

```powershell
node web/scripts/check-syzygy-data.mjs
.\.venv\Scripts\python.exe web/scripts/check-syzygy-cjk.py
Set-Location web
npm.cmd run test:portal
```

字体检查需要先在 `web/` 安装前端依赖，并安装 Python 的 `figures` 可选依赖。

## 编译样例库

在项目根目录运行以下 PowerShell 命令。首次安装依赖需要联网，之后编译在本机完成。项目需要 Python 3.11 或更高版本。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pipeline.build_graph --include-samples
.\.venv\Scripts\python.exe -m pipeline.build_graph --include-samples --format sqlite
```

样例包含 12 张卡片和 13 条边，覆盖四层结构。从塞勒姆案可以沿主题码找到苏格兰猎巫档案和清代叫魂案，也可以查阅麦角中毒假说的原始论文与反驳。样例卡保留出处与中英文检索名称，`audit.reviewed_by_human` 为 `false`。

| 路径 | 内容 |
| --- | --- |
| `vault/01_cases/`、`vault/02_myth_corpora/` | L1 个案、L2 神话文本与档案组 |
| `vault/03_motifs_standards/`、`vault/04_mechanisms_theories/` | L3 标准码枢纽、L4 机制与理论 |
| `vault/05_quarantine_fiction/` | F 级虚构卡片 |
| `schema/node_schema.json` | 从 `pipeline/node_model.py` 生成的 JSON Schema |
| `web/public/data/graph_data.json` | JSON 图谱，包含 `nodes` 和 `links` |
| `.local/graph_data.sqlite3` | SQLite 图谱，包含 `nodes`、`links` 和 `metadata` 表 |

## 添加与校验卡片

1. 在对应目录创建 `<id>.md`，使文件名与 `id` 一致。可复制同层样例使用的 Frontmatter 结构。新卡片的 `audit.reviewed_by_human` 填 `false`，`audit.is_sample` 仅用于项目样例。
2. 填写能够查证的时间、地点和标准码。地点只有区域名称时，可留空经纬度。年代未知时，可填写 `era_label` 与 `uncertainty_note`，年份用 `null`。OCM 等数字形式的编码在 YAML 中用引号包成字符串。
3. 运行以下命令核对字段、文件位置与关系目标。检查通过后人工复核卡片，再将 `audit.reviewed_by_human` 改为 `true`。常规编译收录已人工复核的卡片，`--include-samples` 额外收录显式标记的样例。

```powershell
.\.venv\Scripts\python.exe -m pipeline.build_graph --validate-only
.\.venv\Scripts\python.exe -m pipeline.build_graph
```

同一标准码由一个 L3 卡片登记。编译器按 ATU、汤普森、别列兹金和 OCM 各自的编码范围匹配，并把尚无已收录枢纽的标引列在 `stats.unmatched_standard_codes`。自动连边表示共同标引。文化传播路径需要由卡片单独记录并提供依据。

解释关系须注明 `confirmed`、`contested`、`unverified` 或 `refuted` 及相应证据。来源有据的文化分析区以 `ATTESTS_MOTIF` 连接 L2 区域资料和 L3 母题。图谱的入度、出度与介数中心性基于有向拓扑计算，L3 枢纽另外统计已标记文化区的个案分布熵。F 级节点和涉及它们的边均排除在这些指标之外。

## 从资料生成待审草稿

更新 Python 依赖后，在项目根目录运行 `pipeline.ingest_agent`。资料可以是本地 PDF、网页地址、保存的 HTML、纯文本文件或直接输入的文字。

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent draft '资料.pdf' --citation '档案馆与档号'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent draft 'https://hraf.yale.edu/ocm/terms/754'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent draft --text '田野摘录涉及巫术指控。' --title '田野笔记' --citation '访谈记录 W23'
```

草稿位于 `vault/00_drafts/`，可在 Obsidian 或复核页面中打开。出处保留来源标题、最终网页地址或本地文件路径、内容哈希与引用位置。网络资料和直接输入的文字会将原始内容按 SHA-256 保存在 `.local/intake-sources/`；本地文件保留原位置并登记其路径和哈希。PDF 采用文件内从 1 开始的页号，网页与纯文本分别记录段落和行号。扫描件需先在本地 OCR，再导入文字层或纯文本。遇到网站安全验证页面时，导入会停止，请先取得可访问的原始资料。

标引只匹配 `reference/standards.json` 登记的编号、标准名称或具体别名。每条命中会记录资料位置和码表出处，未命中的字段留空。原文中明确写出但本地码表找不到的编码会列在草稿的“未匹配的原文编码”和复核清单中，供人工核查，不会自动填入标准码字段。码表包含 ATU、汤普森和 OCM 的起始条目，以及从别列兹金目录核对的 2,457 个母题码。批量补入的编号只匹配明确写出的代码。时空字段和实证解释由复核者依据材料填写。

默认资料库成功创建草稿后会自动更新复核清单；如页面已打开，刷新页面即可看到新条目。复核页的“本地入库草稿”包含草稿根目录及其他批次目录中尚未归入专门数据集的卡片；`asia_` 开头的批次在“中国与东亚、东南亚”组中复核。各组均可下载 CSV。若自动更新失败，草稿仍会保留，终端会提示原因和重建命令。使用自定义资料库时，可手动指定库和输出位置：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

复核草稿后，用 `--check` 做签核预检。把下面命令中的 `草稿ID` 换成创建草稿时返回的文件名。`--genre` 可改为实际体裁，也可提前在 YAML 中填写。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent approve '草稿ID' --genre memorate --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent approve '草稿ID' --genre memorate
```

签核将卡片移入正式目录，并重建 `web/public/data/graph_data.json`。命令沿用现有快照的样例和 F 级筛选设置。刷新本地前端即可查看新节点。使用 `--vault` 处理其他库时，可用 `--output` 指定对应前端的快照路径。

## 批次导入与研究覆盖

待审批次和计数清单保存在 `vault/00_drafts/`。爱丁堡调查库使用官方数据表、表模式和地名资料。其他公开档案样本和研究报告的核对卡可在 `reference/regional_records.yaml` 与 `reference/research_records.yaml` 查看。覆盖范围、来源许可和待补材料见 [研究覆盖与来源](reference/research_coverage.md)。

云南彝文 EAP081 项目检索共 731 条混合目录，完整行均保留在复核页 CSV；其中 82 件根据题名或摘要词汇，以及 EAP081/22 的完整馆藏上下文筛出，另建 14 张父级馆藏卡和 1 张项目卡。7 条已有录音目录关联原卡，628 条未筛入的目录仍需人工回查。51 件候选与其他条目同题，但不自动合并；目录行、影像和手稿册均不是独立故事数。82 件单件及 14 个父级的馆方访问条件均写明仅供研究，馆方所列影像入口可点击，但本地未取得影像或转录，其他使用条件与社区要求另核。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_bl_yi_project --output '.local/source-snapshots/bl-yi-project-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_bl_yi_project_details --index '.local/source-snapshots/bl-yi-project-new' --output '.local/source-snapshots/bl-yi-details-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets bl-yi-project --index '.local/source-snapshots/bl-yi-project-new' --details '.local/source-snapshots/bl-yi-details-new' --vault '其他资料库路径'
```

云南洞经表演与口述访谈的馆方系列列有 27 件电子文件夹，现已逐件建待审卡及一张系列卡，复核页可下载完整清单。馆方将系列范围写为 62 个文件，而 27 条单件范围字段首项数字相加为 57；统计口径待核，不据此推定缺失内容。6 件题名年份不在单件起止字段范围内，其中第 20 件的日期范围字段也与起止字段不同；16 件未单独列出访问条件，不能推定不受限制。文件夹和文件不等于故事数，未下载音视频或转写，坐标、叙事年代和标准码留空。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_bl_dongjing --output '.local/source-snapshots/bl-dongjing-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets bl-dongjing --snapshots '.local/source-snapshots/bl-dongjing-new' --vault '其他资料库路径'
```

大英图书馆缅甸多语唱片目录的 35 件唱片和一张馆藏组卡已进入待审；复核页可下载逐件清单。芝加哥大学 DSAL 三个语言卷中，33 件有严格编号候选，另 2 件仅有 `1/2` 与 `HALF` 的较弱文字线索。候选不证明录音面或版本相同，35 件候选的说话人字段均为空，须回查馆方采集记录。唱片数不是故事数；未下载音频或转写，录音权利和社区要求须逐件核实。坐标、叙事年代和标准码均未自动填写。可在允许的访问条件下使用新的快照目录复现采集和导入：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_bl_burma --output '.local/source-snapshots/bl-burma-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_dsal_burma --output '.local/source-snapshots/dsal-burma-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets bl-burma --snapshots '.local/source-snapshots/bl-burma-new' --dsal '.local/source-snapshots/dsal-burma-new' --vault '其他资料库路径'
```

《子不语》维基文库在线转录的 24 卷及 745 个分卷标题已列入复核：新增 744 张篇目草稿，既有《李通判》已补入原文和固定修订链接，另有 24 张分卷卡及一张资料组卡。复核页提供总目录与分卷对照 CSV；四处同序题名不同、一处锚点不同，均保留两边原值。转录未对照古籍底本，文学记述不自动成为事实或地图坐标；转载须保留站点贡献者、修订与 CC BY-SA 4.0 条款。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_zibuyu --output '.local/source-snapshots/zibuyu-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_zibuyu_talk --output '.local/source-snapshots/zibuyu-talk-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets zibuyu-wikisource --snapshots '.local/source-snapshots/zibuyu-new' --talk '.local/source-snapshots/zibuyu-talk-new' --vault '其他资料库路径'
```

印尼 Palu’e 馆藏提供 353 项目录筛查表，其中 323 项依据显式 `Sound` 类型建立待审卡；它们不是经核实的故事数。复核页提供完整 CSV 和单条出处，录音、转写及权利和社区要求须逐件核对。可用以下命令将已有字段索引导入新的资料库，或在允许的访问条件下采集至新的快照目录；已有批次和快照不会覆盖。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_palue_inventory --output '.local/source-snapshots/palue-new'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets palue-inventory --snapshots '.local/source-snapshots/palue-new' --vault '其他资料库路径'
```

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[datasets]'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets scottish --tables .local/import-sources/scottish-witches-tables.zip --schema .local/import-sources/scottish-witches-schema.sql --maps .local/import-sources/scottish-witches-maps.zip
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets references
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets references --records reference/research_records.yaml --batch research_report
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets berezkin-codes --catalogue .local/import-sources/berezkin-english-catalogue.html --study .local/import-sources/liu-2022-supplement-3.zip
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets berezkin --study .local/import-sources/liu-2022-supplement-3.zip
```

已生成的批次可直接复核。用 `approve-batch` 核对整批关系、坐标和标准码。人工复核通过后，去掉 `--check` 即可发布该批。逐张发布仍可用 `approve`，有关联的卡片须先确认关联目标已经入库或与其同批签核。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent approve-batch scottish_witchcraft --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent approve-batch regional_sources berezkin_distribution --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.ingest_agent approve-batch research_report --check
```

别列兹金分布批次的两个母题引用区域批次中的档案卡。两批可合并预检和签核，也可先签核区域批次。打开大批次时，地图会聚合附近点位，星图优先展示选中节点及关联。选中有分布记录的母题后，地图展示研究编码中的各个文化分析区，弧线表示同一母题的地区共现。节点目录可通过名称、标准码、地点、年代和出处检索全部已发布卡片。

## 逐条复核与签核

复核页面提供搜索、条件筛选、原始字段、出处链接和逐条复核记录。苏格兰原始档案表中的史料名称、卷页和索引号已经补入相应草稿。页面中的复核结果保存在当前浏览器，可导出为 JSON。CSV 供检索和表格软件查看。草稿在复核后被修改时，页面会标记“草稿已变化”，需要重新确认。日文研馆藏初始体裁留待复核时选择。

爱丁堡原表有 13 条史料索引的案件编号在案件表中未找到。复核页面可查看这些原始行及其备注，文件位于 `web/public/review/unmatched_references.csv`。没有关联案件的被告、缺少卷页或只按地名匹配的坐标均有单独提示。苏格兰 OCM 754 是调查主题的批量标引，逐条复核其适用性。别列兹金的同号异题、无定义地区编号和重复地区编号也有提示。5 个地区的原参考坐标与名称或所举族群存在地理疑点：地区卡暂不提供地图坐标，原值、对照来源和相关母题保留在复核页面。不能仅凭现代国界或族群举例确定正确的文化区点位。

未关联史料索引的编号核查示例见 `reference/scottish_reference_review_notes.md`；相同数字尾号不能作为自动关联依据。

苏格兰被告的调查库档号另与 Wikidata 的 P4478 编号快照核对，再按实体编号查找爱丁堡地图导出的居住地点。对照中有 30 张卡片的原生成点与同档号地图点相距超过 10 公里，原坐标暂不落图；原值、候选值、计算距离和出处都保留在卡片。这个距离只是复核提示，不证明哪一位置正确。许多原来没有地图坐标的卡片也给出候选点；候选点不会自动落图。人工选用候选点时，应在草稿中写明地图来源、坐标范围和与原登记地名的关系，再重新复核。地图导出本身来自 Wikidata，不能把两者当作互相独立的证据。少数 Wikidata 实体与调查库档号不是一对一，须核对合并或重复情况。

复核页面的“下载复核清单 CSV”提供各组清单和单独的苏格兰坐标对照表。坐标表逐条列出原始格网、原生成坐标、当前草稿坐标、关联实体、候选点、距离和来源哈希；文件为 UTF-8 BOM 编码。

苏格兰调查表、地图文件和 P4478 查询结果的本地路径与哈希登记在相关待审卡中。签核预检和正式签核会核对卡片声明的本地快照；文件缺失或内容与所记哈希不一致时停止签核。只带网址而没有本地文件路径的来源不在这项本地哈希检查范围内，仍需人工核对。草稿因补充来源路径或身份线索而改变时，原有复核记录会保留并显示“草稿已变化”，须重新确认。

以下命令用于向新导入的苏格兰批次补充已保存的快照路径与编号对照。P4478 快照如需重新获取，应指定新文件名；脚本不会覆盖已有快照。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_scottish_wikidata --output '.local/import-sources/新的-p4478.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_scottish_snapshots --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_scottish_snapshots
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_scottish_identity --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_scottish_identity
```

后两条命令默认使用现有 `wikidata-scottish-p4478.json`；如使用新文件，须以 `--wikidata` 指定。快照及同名 `.manifest.json` 必须同时保留。补充过程不改写正式卡片，已有人工编辑过的坐标会保留。

地区对照记录位于 `reference/berezkin_region_review_notes.yaml`，只适用于文件中记录了 SHA-256 的研究附件。若从原附件重新创建待审批次，运行下面的补注命令可给相关母题及共享卡片添加疑点说明，并只对与研究原值完全相同的存疑地区坐标留空。人工修改过的坐标保留；已签核卡片不会被改写。补注改变过的草稿须重新人工确认。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_berezkin_coordinates
.\.venv\Scripts\python.exe -X utf8 -m pipeline.audit_berezkin_coordinates
```

第二条命令使用前端同一份 Natural Earth 国家边界底图重新计算五个原参考点与现代国界的粗略叠置，并将底图和研究附件的哈希、方法限制及结果写入 `.local/intake-qa/berezkin-coordinate-map-check.json`。

当页面的复核记录已导出，可在项目根目录用以下命令预检。把路径改为实际下载的 JSON。预检将列出尚需先复核的关联卡片。去掉 `--check` 会签核依赖齐全的“复核通过”卡片，写入复核人、时间与备注，更新前端图谱和本地复核清单。标为“需要修改”的卡片留在待审目录。

若该卡可以在公开网站展示，还需由复核人勾选公开许可确认并填写可追溯的许可依据；仅完成本地复核的卡片不会进入线上发布包。确认公开后，若卡片内容或出处发生变化，发布程序会要求重新复核。标准码仍只使用本地码表；没有可靠坐标的卡片不在地图上推定标点。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_approval '复核记录.json' --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_approval '复核记录.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

以下命令先检查公开范围，再构建并推送至现有 GitHub Pages 子目录。目录节点保留真实复核状态；只有复核人确认公开许可且内容未变化的卡片才附带其正文。发布不会复制复核界面或本地原始快照。如仅需发布已确认公开许可的卡片，可增加 `--reviewed-only`。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.publish_site
.\.venv\Scripts\python.exe -X utf8 -m pipeline.publish_site --publish
```

源文件仍按原来的方式提交、推送。正式发布会由网站仓库的 GitHub Actions 同步新增或修改的 PDF、图像和图谱资源到 R2，验证通过后部署至 GitHub Pages。R2 凭据由发布仓库的 Actions Secrets 管理。

最后一条命令可随时按照当前草稿重建清单。对从头重新导入的苏格兰批次，可先运行 `pipeline.enrich_scottish`，从本地调查库的 `WDB_Reference` 表补充史料索引。命令在输入文件、码表和已有草稿之间保留各自的出处与哈希。

日文研批次读取本地保存的官方馆藏卡 HTML，保留馆藏号、所引书目、引用页和地域。条目中的年份指引用资料的出版时间。明确对应地名的市镇参考坐标与出处存放在 `reference/nichibun_places.yaml`。馆藏页中的正文与摘要可通过原链接回查。若要向新知识库重建批次，可执行以下命令。

```powershell
$nichibunFiles = @(Get-ChildItem -Path '.local/import-sources/nichibun' -Filter '*.html' | Select-Object -ExpandProperty FullName)
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets nichibun --files $nichibunFiles
```

项目保留了北海道与东北地区河童称谓的搜索页快照。以下命令可重新获取其中链接的单张馆藏卡，并跳过已保存的快照。向已有知识库追加新卡时，给批次指定新的名称。已收录或待审的卡片会被跳过。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_nichibun --search-html .local/import-sources/nichibun-tohoku-search.html --output .local/import-sources/nichibun
$nichibunFiles = @(Get-ChildItem -Path '.local/import-sources/nichibun' -Filter '*.html' | Select-Object -ExpandProperty FullName)
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets nichibun --batch nichibun_tohoku_more --files $nichibunFiles
```

Dúchas 批次读取已保存的学校、故事和页面 XML。点位采用学校登记地点，故事没有单条日期时使用馆藏项目的 1937–1939 年范围。页面 XML 有转录时，卡片保留带页号的短摘录。来源使用 CC BY-NC 4.0，卡片保留署名及原始链接。

```powershell
$duchasStories = @(Get-ChildItem -Path '.local/import-sources/duchas' -Filter 'story-*.xml' | Select-Object -ExpandProperty FullName)
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets duchas --stories $duchasStories
```

已保存的故事可按新批次增量入库；相同故事即使在其他批次使用了不同卡片 ID，也会按馆藏故事网址跳过。原区域批次中的图拉罗恩故事同样显示在 Dúchas 复核组，并关联现有资料组和称谓索引。新增 14 条来自 `reference/duchas_fairyfort_candidates.yaml`，为多郡的可查样本，不代表完整分布。批次记录候选清单的哈希；故事体裁待人工确认，标准码未作推断。多页故事的每个已保存页面都登记单独出处，复核页面会提示未保存的页面。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_duchas --all-pages --candidates reference/duchas_fairyfort_candidates.yaml --report '.local/intake-qa/新的获取记录.json'
$duchasFetch = Get-Content -Encoding utf8 '.local/intake-qa/新的获取记录.json' | ConvertFrom-Json
$duchasStories = @($duchasFetch.results | Where-Object { $_.status -eq 'ready' } | ForEach-Object { $_.files.story.path })
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets duchas --batch duchas_fairyforts_next --selection reference/duchas_fairyfort_candidates.yaml --stories $duchasStories
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_duchas_pages --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_duchas_pages
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

`--batch` 须指定尚不存在的名称，且只能使用小写英文字母、数字和下划线。在现有库中重用同一候选清单时，已存在的故事会被跳过；没有新增故事时命令会提示。获取器遵守站点公布的爬取间隔，校验 XML 编号，不覆盖已有快照；遇到访问限制或无效数据会停止。馆藏已提示 XML 接口未来将停用，后续应以其正式 API 说明为准。

## 中国与东亚、东南亚资料

复核页新增“中国与东亚、东南亚”资料组。第一批包括 2006 年国家级非遗名录的 31 项民间文学登记，以及中国文献、朝鲜半岛英文译本、菲律宾英文改写本和马来半岛历史期刊的 13 张资料组及文本卡。国家级名录是查找线索，不提供单篇故事的采录原文；其项目号不是 ATU、汤普森、别列兹金或 OCM 标准码。申报地区、文献所涉范围及故事地名分别保留，均未自动赋坐标。英文译写和历史作者的时代视角在卡片中注明；具体原文版本、采录人及传承背景仍待核查。

2011 年第三批国家级非遗名录另有 41 项民间文学新增项目和 8 项扩展项目，已按文化和旅游部原表分别建立待审卡，可下载“2011 年国家级民间文学项目清单”。扩展项目使用既有项目编号，申报地区要与原项目分别核查；项目数不是故事数。原表中的行政名称按当时原文保留，未自动赋故事地点、年代或国际标准码。[文化和旅游部原始名录](https://zwgk.mct.gov.cn/zfxxgkml/fwzwhyc/202012/t20201206_916812.html)

2008 年第二批新增 53 项及扩展 5 项、2014 年第四批新增 30 项及扩展 7 项、2021 年第五批新增 12 项及扩展 9 项也已建立待审卡。连同 2006 年和 2011 年，五批共登记 167 个新增项目及 29 个扩展项目，都是项目线索，不是 196 篇故事。同一行政编号与序号的登记提供跨年对照，名称及申报地区分别保留；题名不同会提示，不能据此推断故事同一或传播路线。复核页可打开另一张待审卡、查看原表，并下载项目清单与跨年对照 CSV。[2008 年名录](https://www.ihchina.cn/zhengce_details/11664) · [2014 年名录](https://www.ln.gov.cn/web/zwgkx/lnsrmzfgb/2015n/qk/2015n_dyq/gwywj/831B66689DB14A69B972FFBD5EF5169E/index.shtml) · [2021 年国务院公报](https://www.gov.cn/gbgl/92e7fad3d97742f1b1b2beb1fda9c049/files/8525ced0638e4480a1368790d9433924.pdf)

2021 年记录引用公报 PDF 第 24、33 页（印刷第 23、32 页）及本地字段索引。两页逐字段经 PDFium 与 Poppler 文字提取对照，并分别渲染检查；来源 PDF 部分字体未嵌入或没有 Unicode 映射，已在每条记录标出，仍须人工查看原表。没有生成或交付新的 PDF。

泰国诗琳通人类学中心的开放数据另含 226 条泰语叙事及一张资料组卡，可按原题或馆藏类别搜索。正文由 `description` 字段的 HTML 提取成纯文本，原始标记保留在 JSON 快照中。6 条的 `description` 为空、101 条的 `creator` 为空，1 条的单条 `license` 字段为空，均在复核页标示。`creator` 的实际角色和 `spatial` 的地点性质须回查，不能直接视为讲述人及采录点。原记录网站在入库时的 robots.txt 限制了自动抓取；卡片附原网页链接，数据本身来自有哈希的公开 JSON 快照。数据目录标注 Creative Commons Attribution Non-Commercial，具体版本与单条权利仍须核对。

老挝数字手稿馆的 `Folk Tale` 分类另有 453 件手稿元数据及一张资料组卡。卡片显示馆藏地坐标候选、抄本日期原字段和署名许可；地图坐标留空。馆藏地不等于故事发生地或采录地，抄本日期也不等于叙事年代。40 个 PLMP 档号各对应两条不同馆藏记录，相关 80 张卡已列出同号对照；不能仅凭档号自动合并。复核页可下载“老挝手稿档号与馆藏地对照”CSV。手稿影像通过原馆藏链接查看，本批没有下载影像或生成正文转录。

山东地方志镜像新增 17 张故事题名卡和 4 张章节资料组卡，分别来自平阴、青州、鱼台和嘉祥。镜像由第三方自称保留原地情数据库内容，纸本与转录准确性尚未核验；本地只保存研究字段索引，不保存网页原响应或正文，索引哈希不是网页哈希。平阴一篇标有讲述者、整理者候选，另一篇署作者，不能互换角色；青州一篇注明收入时删改。有关平阴一篇，镜像称 2008 年出版，另有论文引用相近题名的 1988 年资料本，两者关系及该篇是否收录在其中均待核。方志区域不是单篇采录点，坐标、年代和标准码留空，正文再利用许可待核；复核页可下载“山东方志镜像逐篇清单”CSV。

印尼望加锡的 HMML `Private Collection of Go Lan Ing` 在 2026-11-22 的馆方开放数据中选出 601 条手稿馆藏元数据，均为尚未完成编目的记录，不能当作 601 则民间故事。其中 12 个档号与旧 DREAMSEA 目录搜索索引中《Ouw Pe Coa》的分卷线索对应，已形成 12 张待审手稿卡和一张资料组卡。旧目录当次无法直接访问，题名、作者、语言、文字和抄写日期都是搜索索引候选，所述中国传说改编关系也需回查，不据此绘制传播路线。馆方当前元数据与旧目录候选分别保留来源和哈希，后者的哈希只校验本地研究索引，不是原网页哈希。望加锡是馆藏地，抄写日期和数字化日期不是故事发生年代；坐标与标准码留空。馆方元数据按 CC BY 4.0 署名，手稿影像及内容的使用条件另核；本批未复制影像或正文。复核页提供“望加锡手稿 12 册候选复核”和 601 条“望加锡馆藏元数据筛查清单”CSV。[HMML 数据入口](https://www.vhmml.org/dataPortal/dataset) · [第一册旧目录线索](https://www.hmmlcloud.org/dreamsea/detail.php?msid=7158)

菲律宾 SIL 馆藏的两则 Ilianen Manobo 口述录音样本已分别生成待审卡，并保留一张资料组卡。馆方均注明讲述人为 Ampatuan Ampalid、录音日期为 1976-08-02，并分别指向 2004 年和 2008 年出版的转写本。馆方公开的是样本，完整录音须申请在马尼拉档案现场收听；转写本尚未查阅。本地仅保存馆方目录网页，不保存录音或转写正文；具体录音地点、音频及文本的再利用许可和社区要求仍须核对。研究者曾居住的北哥打巴托不能直接视为两次录音地点，录音日期不是故事发生年代，坐标和标准码留空。复核页可下载“菲律宾 Ilianen 录音样本清单”CSV。[SIL 馆方录音目录](https://philippines.sil.org/resources/audio_and_video/ilianen_manobo_oral_narrative_recordings)

大英图书馆 `Or 16131/1–11` 高棉文折本馆藏已按馆方目录建立 11 册待审卡和一张馆藏组卡。各册可能包含诗体小说、故事及训诫文字，册数不是故事数；本地保存馆方目录网页及哈希，未保存手稿图像或转写正文。馆方组目录日期为 1890–1925，第 5 册单件目录为 1859–1925，两处原值并列并标记优先复核；馆方来源地也含疑问。本次 11 册目录的数字化字段均未显示链接，不能据此断言影像不存在。馆方目录文字按 CC BY 4.0 署名，手稿影像和内容的访问与再利用条件另核；坐标、体裁和标准码留空。复核页可下载“柬埔寨高棉文折本逐册清单”CSV。[馆藏组目录](https://searcharchives.bl.uk/catalog/032-003779224) · [第 5 册目录](https://searcharchives.bl.uk/catalog/040-003779290)

美国马萨诸塞大学洛厄尔分校的东南亚社群故事项目馆藏列出 23 项资料，涉及缅甸、柬埔寨、老挝和越南社群；本批为其中 22 项书籍或文档及一张馆藏组建立待审卡，另将一张活动海报保留在筛查清单。文档可能包含多篇故事，不能把项目资料件数当作故事数。馆方覆盖范围是洛厄尔，不能自动转为单篇故事的原采录地或叙事地点；2018–2019 是项目时间，非故事发生年代。单件页标有 PDF 等格式，但本次指定文件区域未检出可见链接，具体访问状况须回查。馆方说明允许私人、教育和研究用途，所需其他权利许可由使用者核实；本地只保存目录字段索引，未保存故事正文、音视频、图像或网页原响应，因此原响应哈希不能仅凭索引离线重算。复核页提供“洛厄尔东南亚社群项目逐件清单”和“项目资料筛查清单”CSV。[馆方项目目录](https://umlseada.omeka.net/collections/show/19) · [高棉故事文档目录](https://umlseada.omeka.net/items/show/1256)

[Nitean 高棉文故事转录目录](https://seuksa.com/nitean/folktales/)的 8 卷、214 章已逐篇建立待审卡，另有 8 张卷册卡和一张资料组卡。每篇保留目录与页面题名、原文链接、可见卷页线索及脚注定位；全部题名和卷名与目录一致，有 2 篇未提取到印本页码线索、148 篇页面有脚注。目录还列出独立序言，不计入 214 篇。复核页可下载“高棉文故事逐篇清单”，并从详情打开原文及脚注；本地只保存字段和响应指纹，不复制正文或网页原响应，所以原响应哈希无法仅凭字段索引离线重算。与 [Wikisource 另一份目录](https://wikisource.org/wiki/%E1%9E%94%E1%9F%92%E1%9E%9A%E1%9E%87%E1%9E%BB%E1%9F%86%E1%9E%9A%E1%9E%BF%E1%9E%84%E1%9E%96%E1%9F%92%E1%9E%9A%E1%9F%81%E1%9E%84%E1%9E%81%E1%9F%92%E1%9E%98%E1%9F%82%E1%9E%9A)的卷数及第 2、3、5 卷条数不同，均标记待核；题名相似不自动合并。原印本、采录背景、权利与社区要求仍须逐篇核实，选集地区不能当作采录地；坐标、年代、体裁及标准码留空。高棉文字使用随项目附带的 OFL 许可 Noto Sans Khmer 字体。

法国 CNRS-LACITO 的 Pangloss 永宁纳语馆藏目录在本次快照中有 337 条资源，包含叙事、词汇调查和生活记录；首轮依据馆方题名目的性选取其中 47 条录音，另建一张馆藏组卡。湖泊形成、人与狗交换寿命、姐妹出嫁与葬仪等同题记录按单次录音分别保存；14 个研究分组与 `COMPARED_WITH` 关系仅供人工对照，不表示已证实同源、同一次演述或传播路线。每张卡分别保存馆方目录和单条详情的题名、研究者、讲述者、录音日期、录音地点原字段及许可。首轮 31 条在目录中显示转写图标，27 条详情提供中文题名；图标并不保证所有文本或翻译可用。本地原始详情网页快照可能含馆方简介，草稿只提取目录字段。关联资源接口用于提取分句结构，音视频、转写正文及接口原始响应不保存在本地，可通过单条来源页面查看馆方提供的内容。

对上述 47 条录音的接口查询返回 63 个关联音视频资源，其中 31 条录音有转写或其他关联附件。18 个 XML 转写资源共含 2,100 个可定位分句；另有 22 个类型为 EGG 的附件，不计作 XML 转写。XML 分句中 2,099 段带法文、948 段带中文、321 段带英文译文语言标记，同一段可有多种译文；这些数字表示馆方字段存在，不代表译文已被人工审核。复核详情可输入分句序号跳转馆方页面，另可下载“永宁纳语分句定位清单”CSV。索引保留资源对应关系、时间和语言标记，但未保存转写正文；原始响应的 SHA-256 无法仅凭结构索引离线重算。音视频的许可原字段与附件自身许可分别列出，附件单独许可及社区要求仍须核明。

47 条详情中 43 条列出 CC BY-NC-SA 2.5，4 条对不同资源分别列出 CC BY-NC-SA 4.0；使用前须逐条核对适用资源与相关社区要求。馆方部分录音地点原文写作 `Yongning County` 或 `comté de Yongning`，研究者其他著作使用宁蒗县永宁乡等称谓，具体行政范围、历史时点和村名对应须核实；录音日期不是叙事年代。坐标、体裁和标准码均不自动推定。复核页可下载“永宁纳语录音对照清单”CSV。[Pangloss 馆藏目录](https://pangloss.cnrs.fr/corpus/Yongning_Na) · [研究者的地点说明](https://shs.hal.science/halshs-00358610)

已有目录快照可继续用于生成本轮 31 条待审候选及 337 项完整筛查表。此批只有目录字段，未取得单条详情，题名和版本字样只是待核线索；其余未选入资源保留在筛查表，不称作已核实的故事。原始快照、此前两个选取索引与本轮选取索引均绑定哈希。

另依据 Michaud 的 2025 年《永宁纳语声调》第二版新增三条生产生活背景候选，并为 26 张既有待审卡补入 PDF 链接与 DOI 对照。复核页可下载“纳语专著 DOI 与分句对照清单”，同时保留编号重复、版本差异和登记许可名称与链接不一致等疑点；这些对照不代表音频或转写已经校核。四批共 122 张待审录音卡，另有 215 条目录资源尚未逐条筛查。方法、许可边界及待核事项见[专著对照说明](reference/na_tone_book_notes_2025.md)。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets pangloss-na-catalogue --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --first 'reference/pangloss_na_selection_v1.json' --context 'reference/pangloss_na_context_selection_v1.json' --selection 'reference/pangloss_na_catalogue_selection_v1.json' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

该命令不联网；完整筛查表区分已登记详情、本轮目录候选与尚未选入的资源。已存在的录音 ID 或变动的索引会使导入停止，不覆盖既有草稿。

彝语馆藏目录可在新资料库中重新取得并建卡：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_bl_yi --output '.local/import-sources/新的彝语馆藏快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets bl-yi --snapshots '.local/import-sources/bl-yi-eap081-2026-11-23' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

获取器核验馆藏档号、六个子组、研究访问条件及目录文字许可，不请求音频或转写；已有快照经哈希检查后复用。本批是 1 个馆藏组和 6 个录音子组，不是 7 篇故事；字段疑点和访问条件见 `reference/bl_yi_eap081_notes.md`。

另按目录题名选取 41 条仪式、地方观念和口述背景资料，其中 3 条为歌曲类背景；每条单独分组，不自动创建同源对照。首轮与补充共 88 张待审录音卡，仍不是完整目录或随机样本。补充录音的 39 条许可原字段为 CC BY-NC-SA 2.5（其中 1 条逐资源列示），另 2 条逐资源列示 CC BY-NC-SA 4.0；媒体和附件许可及社区要求仍须分别核对。[录音 0004837](https://doi.org/10.24397/pangloss-0004837)的详情地点原字段写在四川，目录与详情的研究者字段写法不同；两边原值分别保留，地点、身份和叙事时空均待核。

Pangloss 的四川嘉绒语 Japhug 目录快照有 549 条录音资源和一张馆藏组待审卡；录音包含叙事、生活、技艺或语言资料，不能计为 549 篇民间故事。馆方目录中 542 条的讲述者字段为 Tshendzin，另 7 条采用其他署名；姓名异写与具体身份须回查，不能把资源数当作讲述者人数或社区覆盖。首轮依其他署名及目录中的年份目的性核验 37 条详情，后续按目录顺序分三批补充 200、200 和 112 条，现已保存全部 549 条的详情快照。目录与详情的研究者、讲述者和录音日期字段均可对应；许可原字段分别为 370 条 CC BY-NC-ND 2.5、178 条 CC BY-NC-ND 3.0 和 1 条 CC BY-NC-SA 2.5。音视频、转写、附件的适用许可与社区要求仍须分别核查，本地未复制音视频和转写正文。馆方详情的地点原文不自动转成坐标或叙事地点，录音日期不自动变成故事年代。复核页可下载“四川嘉绒语录音逐条清单”CSV。[Pangloss 目录](https://pangloss.cnrs.fr/corpus/Japhug)

研究者 Guillaume Jacques 的《A grammar of Japhug》介绍，语料除现场叙事外也包含从中文故事书翻译后录音的材料，涉及《聊斋志异》《西游记》及其他作品；书中将一部分这类文本以 `-zh` 区分。此说明提示应逐条核对文本来源和版本，不证明任何单条录音都属于某一版本或本土传统。[研究者著作](https://langsci-press.org/index.php/LangSci-Press/catalog/book/549)

韩国公共数据门户的[韩国学中央研究院声音资料目录](https://www.data.go.kr/data/15070383/fileData.do)提供的 ZIP 中，口碑文学 CSV 有 22,836 行：馆方类别为叙事 `설화` 的 13,050 行，另含民谣、巫歌和其他资料。已按原目录行生成“韩国口碑目录筛查清单（尚未入库）”，可从复核页浏览、搜索、筛查并下载，保留原始韩文、讲述者、采录地与来源哈希。739 行未填讲述者，449 组目录字段完全相同的行均保留；馆方短编号不能直接转换为单条链接。另有民谣和方言目录，此处未合并或按独立故事计数。目录筛查清单不是待审卡片，表格中的标记不会自动签核或编译入图谱；单条音频和转写许可、采录背景及相关社区要求须分别核查。

韩国筛查页明确使用本机 Microsoft YaHei 和 Malgun Gothic 的常规与粗体组合，以覆盖汉字、兼容汉字和韩文；缺少任一所需字体，或清单内容与快照哈希不符时，页面会停止显示并提示核对。CSV 采用带 BOM 的 UTF-8 编码；不同表格软件自身的字体设置仍需使用覆盖这些字符的字体。

复核页另有“韩国道峰区来源候选”：开放目录中该区域的 172 行与馆方 202 条检索结果对照，114 行出现来源候选、58 行暂未找到，存在多重候选的行均保留。已为 113 个不同候选取得馆方单条元数据，生成含 174 行的详情对照，并建立 172 张待审卡和一张资料组卡；116 对候选的采录地点字段在规范化比较下均对应，仍须核验历史行政范围、具体版本和同一次演述。题名规范化及字符相似度只用于筛查，不能代替人工签核。检索与详情页只保留字段索引，未保存原网页或转写正文，原网页响应哈希无法单凭本地索引重算。

[北泰数字手稿馆](https://digital.crossasia.org/digital-library-of-northern-thai-manuscripts/?lang=en)的 Folk Tale 检索结果已建立 78 件手稿的待审卡和一张资料组卡。64 件保留馆方的馆藏地坐标原字段，未自动转成叙事坐标；手稿件数不能视为故事数，馆藏档号不能视为标准码。复核页可下载“北泰手稿逐件复核清单”；单件影像、语言、年代及许可须回查，本地未下载影像或转录。

如需重建韩国目录筛查清单，请保留下载的原 ZIP、凭据及人工候选索引，指定一个不存在的新输出文件名；命令不会覆盖已有清单。候选单条链接须先核对原行字段，不得将短编号视为标准码。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.korea_aks_inventory --archive '.local/import-sources/korea-aks-audio-index-2026-11-22.zip' --receipt '.local/import-sources/korea-aks-audio-index-2026-11-22.receipt.json' --candidates 'reference/korea_aks_manual_candidates.json' --output 'reference/新的韩国目录清单.csv'
```

Pangloss 的 Khmu 馆藏目录快照有 177 条录音资源，已分别建立待审卡和一张资料组卡。目录包含叙事、歌唱、祈祷、访谈和词汇等材料；有些录音含多个内容或一段续集，不能按录音数计算故事数，也不能认为每段都只用 Khmu 语。首轮根据目录题名及资料形式目的性核查 47 条详情，后续 130 条已按目录顺序补齐详情；53 条目录讲述者字段未具名或含 `unknown`，身份不能推定。仅 9 条在目录中显示转写图标，不据此断言其他转写不存在。177 条详情的许可原字段均为 CC BY-NC-SA 2.5，音视频、转写和附件的具体许可及相关社区要求仍须分别核查；本地没有复制音视频或转写正文。

目录题名、讲述者及日期支持建立 11 组待核对照，共涉及 40 条录音；其中 Sin Xay 和 Sithon 与 Manola 的目录显示续集，洪水和氏族题名则只是跨录音的主题对照。关系不证明同一次演述、同源或历史传播。177 条详情中 6 条的录音地字段写有法国；例如 Sin Xay 的讲述者字段提及 Xieng Khouang，录音地字段则写 Vientiane，二者须分开看待。11 条日期范围的两个端点一致但写法不同，另 9 条暂无法直接比较，双方原值保留。坐标、叙事年代和标准码均不从馆藏范围或题名自动推定。复核页可下载“东南亚 Khmu 录音逐条清单”并在对照卡之间跳转。[Pangloss Khmu 目录](https://pangloss.cnrs.fr/corpus/Khmu) · [与录音 0001986 相关的研究](https://doi.org/10.4000/clo.7019)

后续详情补充会保留首轮字段、人工备注及每条来源快照，记录补充前后的草稿哈希；此前对变更草稿保存的浏览器复核决定会显示“草稿已变化”，须重新确认。新批次可按以下方式先保存并校验馆方快照，再预检待审草稿：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_pangloss_supplement --kind khmu --corpus '.local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html' --initial 'reference/khmu_first_detail_selection.json' --output '.local/import-sources/新批次目录' --limit 200 --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_pangloss_supplement --kind khmu --corpus '.local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html' --initial 'reference/khmu_first_detail_selection.json' --supplement '.local/import-sources/新批次目录' --check
```

核对预检结果后，以相同参数去掉 `--check` 追加详情；已签核、已补充或选取后发生变化的草稿不会被覆盖。四川嘉绒语使用 `--kind japhug` 及对应的目录和首轮选取文件，同样按批次保存快照。详情补充不等于人工签核，待审资料须通过现有审核流程才能编译进入正式图谱。

本轮浏览器回查四个镜像章节，17 个题名均在网页原始视图中找到；平阴署名线索、青州版本注记及嘉祥分组也已对照。检查结果和当次响应指纹保存在 `.local/intake-qa/shandong-source-observation.json`；网页原响应没有保存，不能单凭报告离线重算指纹，也不能由此证明镜像与纸本完全一致。

Digitizing Việt Nam 的越南文《Truyện cổ dân gian Chăm》新增 58 张单篇目录卡及一张选集卡，保存目录原题、逐篇链接、详情标题、段落数和字段快照哈希。选集前言称其中 32 篇由馆藏及家庭材料整理翻译，26 篇从书刊选录；目前不能判断每一篇属于哪一类，也未确定讲述者、原始语言或具体采录地。站点书目 `Date Created` 为 2000，前言落款是 1997 年秋，两者分别保留，不当作故事发生年代。7 篇标题旁的数字经回查为脚注按钮，已与标题分开保留；脚注内容仍待核查。馆方开放教育和研究用途，禁止商业使用；具体转载许可与社区权益待核。本地仅保存书目、目录字段及原网页响应指纹，不复制完整网页或正文；点击单篇出处可查看原站全文。复核页可下载“越南占族故事逐篇清单”CSV。

浙江《玉环文史资料》第二十二辑（2008）的“传说故事篇”目录另生成 47 张条目卡和一张资料组卡，逐条保留印刷页、双页扫描的 PDF 页码及原页链接。47 张故事卡都附有从条目末尾影像摘录的讲述者、整理者或流传范围候选，仍需人工逐字复核；其中 35 张由独立旁注补充索引新增。补充索引记录 36 条原书所列的早期刊载线索，早期版本本身尚未核验。“下一世怎么报答”的原登记候选“支存祥”与本轮识读候选“支存样”并列保留、标记冲突；“石蜂山”与同册另见的“石峰山”是否同地也待核实。PDF 是无文字层的扫描件，正文未转录，出版物及扫描影像的再利用许可待核。`pypdf` 报告 630 条对象引用或结构警告；Poppler 和 PDFium 可渲染全部 41 个条目起始扫描页，仍应逐页核对完整性。玉环史志网的网页是单独版本，不自动视为同一次采录。复核页可下载“玉环传说故事逐篇清单”CSV。

中央研究院民族学研究所的阿美族、雅美族口语资料有 565 条目录索引和一张资料组卡，来自八个目录组的公开分页；现已整理这 565 条的单条详情字段，但不能据此推定涵盖馆方所有藏品。目录涵盖口传故事、生活经验、风俗和歌谣，并非全部都是神话。每条保留原题及单条详情链接；详情按原字段保留档号、采集日期、族别、報導人、記音者和翻譯者，缺项不推定。馆方概述称马太安资料 30 则，现有目录列出 31 条，计数口径待核。565 条中，184 条的“阿美族”目录组与详情页“雅美族”字段不一致；152 条記音或翻譯角色与项目概述不同，141 条采集日期超出概述的 1982–1985 年范围。140 条未填写記音者、257 条未填写翻譯者、5 条未填写報導人，均须回查。目录第 104 条写「雙手插秧的人」，详情写「雙手補秧的人」，双方原字保留待核。采集地和日期不等于叙事地点及发生年代，均未自动转成坐标和图谱年份。复核页可下载“台湾口语资料逐条清单”CSV。

详情采集地还可与原住民族委员会的部落 GIS 点位表对照：目前 456 条有单一社区地标候选，109 条地点信息不足或找不到对应登记。匹配要求县市、乡镇及部落名称分别对应；“马太安／马太鞍”别写需结合馆方资料复核，同名部落不能仅按名称匹配。GIS 的坐标指向学校、道路等登记地标，不是具体录音点或故事发生地，也不能用社区族别判断个人身份。候选仅显示在复核界面与 CSV，不写入图谱坐标；参考系、地点范围、历史时期及相关社区观点仍需确认。

本次补充时，第 645 条的馆方使用声明相较相邻页面多一个“的”，原有非营利教育学术浏览和未经同意不得摘取出版的限制仍在。已记录此具体字词差异和当次响应指纹；其他未核实的声明变化仍会使获取器停止。详情页的原始 HTTP 响应未保存，不能凭字段索引离线重算其指纹。

馆方声明网站供非营利教育和学术浏览，未经同意不得摘取内容出版。本批只在本地研究区保存目录标签和描述字段，不保存译文、录音或整页 HTML；可通过馆方链接浏览原文与原音（若该条提供）。再利用许可和相关社区权益须另行确认。每个字段快照保存原始 HTTP 响应哈希以及自身文件哈希；因未保存完整原始响应，其原始哈希不能仅凭本地字段快照重算。这个研究索引不意味着取得任何公开出版授权。

来源 HTML 快照及哈希保存在 `.local/import-sources/asia-pilot/`，已逐条登记在草稿出处中。可用下面的命令向新的资料库重建批次；现有同名批次不会被覆盖。批量导入后重建清单，再刷新复核页面。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets chinese-heritage --file '.local/import-sources/asia-pilot/china_ich_2006.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets chinese-heritage-2011 --file '.local/import-sources/asia-china-ich-2011-2026-11-22.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets chinese-heritage-batch --year 2008 --file '.local/import-sources/asia-china-ich-2008-2026-11-22.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets chinese-heritage-batch --year 2014 --file '.local/import-sources/asia-china-ich-2014-2026-11-22.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets chinese-heritage-2021 --pdf '.local/import-sources/asia-china-ich-2021-gov-gazette-2026-11-22.pdf' --index '.local/import-sources/asia-china-ich-2021-field-index-2026-11-22.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets references --batch asia_pilot_2026 --records 'reference/asia_pilot_records.yaml'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets thai-folktales --file '.local/import-sources/thai-sac/folktales.json' --catalogue '.local/import-sources/thai-sac/catalogue.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets lao-manuscripts --snapshots '.local/import-sources/lao-dllm'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets yuhuan-stories --pdf '.local/import-sources/china-yuhuan/yuhuan-oral-literature-2008.pdf' --index 'reference/yuhuan_2008_story_index.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets sinica-oral --snapshots '.local/import-sources/sinica-oral'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets vietnam-cham --snapshots '.local/import-sources/vietnam-cham-folktales-v2'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets shandong-mirrors --index 'reference/shandong_mirror_index_v1.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets hmml-makassar --snapshots '.local/import-sources/hmml-makassar-2026-11-22-v1' --legacy 'reference/hmml_makassar_legacy_candidates_v1.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets philippines-ilianen --file '.local/import-sources/philippines-ilianen-sil-2026-11-22/catalogue.html'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets pangloss-na --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --selection 'reference/pangloss_na_selection_v1.json' --snapshots '.local/import-sources/pangloss-yongning-na-2026-11-22/details'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets pangloss-na-context --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --previous 'reference/pangloss_na_selection_v1.json' --selection 'reference/pangloss_na_context_selection_v1.json' --snapshots '.local/import-sources/pangloss-yongning-context-2026-11-23-v1'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets bl-khmer --snapshots '.local/import-sources/bl-khmer-or16131-2026-11-22'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets lowell-sea --snapshots '.local/import-sources/lowell-sea-folktales-2026-11-22'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets khmer-nitean --snapshots '.local/import-sources/nitean-khmer-folktales-2026-11-22' --comparison '.local/import-sources/wikisource-khmer-folktales-2026-11-22/selection.json'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_yuhuan_credits --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_yuhuan_credits
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

若需重新取得 HMML 当期数据，先将 `pipeline.fetch_hmml_dataset --output '新的原始数据目录'` 输出到新目录，再运行 `pipeline.hmml_makassar --source '新的原始数据目录' --output '新的选取目录'`。获取器检查馆方 robots.txt、文件大小和 ZIP 结构，选取器核验原包及每条元数据哈希；两者均不覆盖已有快照。数据更新后，旧目录候选与当前馆藏的对应关系仍需重新核验，不保证记录总数相同。

获取 Pangloss 单条元数据可用 `pipeline.fetch_pangloss_na --corpus '已保存的目录.html' --selection '选取索引.json' --output '新的详情目录' --delay 2`；首次核验的详情可通过 `--seed` 指定带哈希的快照清单。程序检查馆方 robots.txt、录音 DOI 与题名，间隔至少两秒；遇到临时数据库错误会有限重试，且可在同一选取范围和目录下续跑。目录或选取清单变化时须另建批次。声调与音标字符使用项目内附的 SIL Charis 字体，按 OFL 许可附带字体许可文件。

Japhug 详情使用 `python -m pipeline.fetch_pangloss_japhug --corpus '目录.html' --selection 'reference/japhug_first_detail_selection.json' --output '新的详情目录' --delay 2`；核验后的批次使用 `python -m pipeline.import_datasets pangloss-japhug --corpus '目录.html' --selection 'reference/japhug_first_detail_selection.json' --snapshots '详情目录'`。详情目录和选取范围受哈希绑定；批次只进入待审区。

Khmu 详情使用 `python -m pipeline.fetch_pangloss_khmu --corpus '目录.html' --selection 'reference/khmu_first_detail_selection.json' --output '新的详情目录' --delay 2`；核验后的批次使用 `python -m pipeline.import_datasets pangloss-khmu --corpus '目录.html' --selection 'reference/khmu_first_detail_selection.json' --snapshots '详情目录' --comparisons 'reference/khmu_recording_comparisons.json'`。对照索引绑定目录哈希并逐项核对题名、署名、日期和链接；遇到馆方 HTTP 429 会停止请求。

若需重新取得这两组东南亚馆藏，可分别运行 `pipeline.bl_khmer --output '新的高棉目录' --delay 2` 与 `pipeline.lowell_folktales --output '新的项目索引目录' --delay 2`。两者检查 robots.txt、馆方目录结构及来源链接，使用至少两秒的请求间隔；中断后可在同一范围和目录续跑，已完成快照只校验、不覆盖。高棉目录保留原 HTML 快照；洛厄尔只保存目录字段和原响应指纹，不能离线重算原响应哈希。重新导入应使用新资料库或处理重复卡片，现有同名批次不会覆盖。

2021 年公报的字段索引可用 `pipeline.chinese_heritage_2021 --pdf '已保存的原公报.pdf' --output '新字段索引.json'` 重新生成；命令需要 `datasets` 可选依赖中的 PDFium 以及 PATH 中的 Poppler `pdftotext`。该命令检查 PDF 页数、表格边界、行政项目编号及两种提取结果；生成后仍应比对两种渲染器的原页，不能把原 PDF 的缺失字体映射当作已修复。2011 年待审扩展项目可先运行 `pipeline.enrich_chinese_heritage_links --check` 预检，再运行同一命令添加来源核验通过的对照关联；现有正文和备注保留，签核或不匹配的卡片跳过。草稿变更后旧浏览器复核决定会显示为“草稿已变化”。

重新取得 Nitean 目录可运行 `pipeline.khmer_nitean --output '新的字段索引目录' --delay 2`，以及 `pipeline.khmer_wikisource --output '新的对照索引.json' --delay 2`。前者逐页检查链接和结构，连接暂时失败会有限重试，中断后可在同一选取目录续跑；HTTP 限制会停止。两者均不保存原网页或正文，已有字段索引不会覆盖。新版本的目录与文本身份仍需重新复核。

为待审录音卡建立分句索引时，可先获取到新目录，再预检补充。获取过程按每个音视频资源分别关联附件，遇到异常会停止；已保存索引不会覆盖。补充时若草稿在选取后被修改、已签核，或已登记了不同的分句索引，会跳过该卡，保留人工修改与原有来源。内容变化后旧的浏览器复核决定会显示为“草稿已变化”。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_pangloss_annotations --vault 'vault' --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --chosen 'reference/pangloss_na_selection_v1.json' --details '.local/import-sources/pangloss-yongning-na-2026-11-22/details' --output '.local/import-sources/新的分句索引' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_pangloss_annotations --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --chosen 'reference/pangloss_na_selection_v1.json' --details '.local/import-sources/pangloss-yongning-na-2026-11-22/details' --supplement '.local/import-sources/新的分句索引' --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_pangloss_annotations --corpus '.local/import-sources/pangloss-yongning-na-2026-11-22/corpus.html' --chosen 'reference/pangloss_na_selection_v1.json' --details '.local/import-sources/pangloss-yongning-na-2026-11-22/details' --supplement '.local/import-sources/新的分句索引'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

若要获取新版本的老挝馆藏检索快照，可运行 `pipeline.fetch_lao_dllm --output '新的快照目录'`。获取器按馆藏公开检索接口请求，至少间隔 1 秒，检查分页、编号和哈希；遇到访问限制或结果变化时停止并保留已保存文件。已有完整清单的目录不会覆盖。

北泰馆藏可用独立目录重新获取并生成待审卡：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_lanna --output '.local/import-sources/新的北泰快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets lanna-folktales --snapshots '.local/import-sources/新的北泰快照'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

获取器检查 robots.txt、分页、类别、编号和每页哈希，遇到访问限制或快照与凭据不符会停止；完整批次不覆盖。导入不会重复写入已有卡片，也不会自动签核或发布。

若需为新的资料库重新取得中研院目录，可运行 `pipeline.fetch_sinica_oral --output '新的研究索引目录' --details-per-group 3`，再用 `sinica-oral --snapshots` 从新目录入库。获取器检查 `robots.txt`、馆方链接及页面结构，至少间隔 1 秒，遇到访问限制或使用声明变化即停止；完整批次不覆盖。原网站可能变动，研究索引的条数和详情样本应以新快照为准；对已有资料库再次导入同一组 ID 会拒绝重复写入。

现有库可用新的目录继续补充详情与社区地标：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_sinica_details --output '.local/import-sources/新的详情批次' --limit 120 --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_sinica_details --supplement '.local/import-sources/新的详情批次' --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_sinica_details --supplement '.local/import-sources/新的详情批次'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_sinica_gis --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_sinica_gis
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue
```

详情获取保留选取清单，失败后用同一目录续跑，至少间隔两秒；遇到访问限制或权利声明变化时停止。补充前核对基础目录、字段快照及选取时的草稿哈希；获取期间被修改的草稿会跳过，之前的人工备注保持不变。补充改变草稿哈希，浏览器里对旧版本作出的复核决定会显示为“草稿已变化”，需要重新核对。GIS 命令默认使用带哈希的本地点位快照；更新后的来源须另存新文件并通过 `--data` 指定。

新建资料库可通过 `pipeline.fetch_vietnam_cham --output '新的越南选集目录' --delay 2` 获取允许访问的目录及逐篇字段，再用 `vietnam-cham --snapshots` 入库。获取器遵守网站 `robots.txt`，只访问公开页面，不调用受限的 `/api/`；中断后使用同一目录续跑，完整批次不会覆盖。现有 `vietnam-cham-folktales-v2` 保留了原始批次清单的哈希，复用 51 条原快照并重新核查 7 个标题脚注；未保存原始 HTTP 页面，因此不能单凭字段快照离线重算原响应指纹。

东亚和东南亚的地区、语言及原生社群仍需持续扩充；候选资料和现有覆盖限制见 `reference/research_coverage.md`。

菲律宾 Cole（1916）扫描本的目录索引可以在另一份资料库中重新生成：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets philippines-cole --toc reference\philippine_cole_1916_toc.tsv --snapshots .local\source-snapshots\philippine_cole_1916 --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

本批 61 项按原书目录的印刷页码区分，另建资料组；目录项与独立原始口述记录并非一一对应，部分章节的内部边界尚待复核。OCR 和页边界索引按下载文件的 SHA-256 校验，再寻找标题及页脚对应的扫描序号。61 条草稿现附 227 个候选扫描页的未校对 OCR 和逐页原扫描链接；五页没有识别出文字。切片保留误字、页眉、脚注及换行，起止依据下一目录项候选页，最后一项截至发音表候选页，不能作为已核定的篇章边界。逐页链接按扫描序号构造，并非全部重新访问验证；目录原分类保留旧称，不自动指认当代族群。原书美国公有领域状态、其他地区、数字副本再利用及社区要求须分别核对。草稿不包含扫描影像，坐标、年代和标准码仍为空；每篇仍需人审后才能进入正式图谱。此次补充改变了 61 条子卡和资料组卡的哈希，浏览器保存的旧复核决定须重新核对。

如需在其他资料库复现逐页候选，可先从已登记的本地快照建立新的切片目录，再先预检、后补入尚未复核的 61 条草稿：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.cole_ocr_segments --output '.local/source-snapshots/新的 Cole OCR 切片' --snapshots '.local/source-snapshots/philippine_cole_1916'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_cole_ocr --vault '其他资料库路径' --segments '.local/source-snapshots/新的 Cole OCR 切片' --snapshots '.local/source-snapshots/philippine_cole_1916' --check
.\.venv\Scripts\python.exe -X utf8 -m pipeline.enrich_cole_ocr --vault '其他资料库路径' --segments '.local/source-snapshots/新的 Cole OCR 切片' --snapshots '.local/source-snapshots/philippine_cole_1916'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

切片清单和逐页文件均与原始快照重算核对；遇到已复核、示例、来源变化或已有不同补充时停止，不覆盖草稿。复核清单列出页范围、源文件哈希及坐标、标准码问题。

1905 与 1922 年版本对照使用本地目录、两册 OCR 和扫描清单，以及安徒生中心参考快照：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_early_asia_editions --output '.local/source-snapshots/新的两册扫描快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_andersen_centre --output '.local/source-snapshots/新的安徒生中心快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets early-asia-editions --toc 'reference/jade_1922_toc.tsv' --snapshots '.local/source-snapshots/early-asia-editions-20261123' --andersen '.local/source-snapshots/andersen-centre-20261123' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

两种获取器检查 robots.txt，至少间隔一秒并拒绝覆盖既有目录。导入器固定核对本次来源的文件哈希；新版网页或扫描若变化会停止，需重新核验。1922 年目录共 33 项，使用阅读顺序而非原书章节号；复用已有 Lumawig 卡，其余逐项标记来源、页码、分类、坐标与标准码疑点。1905 年与 1916 年同题为候选版本对照，不自动视为同一次口述。抽样检查和地区标签限制见 `reference/early_asia_editions_notes.md`。

## 四川木雅语目录筛查

四川木雅语馆藏可从新的本地快照生成待审清单：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_minyag_wolp --output '.local/source-snapshots/新的木雅语目录' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets minyag-wolp --snapshots '.local/source-snapshots/新的木雅语目录' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

获取器检查 robots.txt，仅访问项目目录及站点条款，保留原网页和其版权通知，不下载音频或转写；输出目录不可覆盖。若需对照第 19 项的现行剑桥单件网页，可先运行 `pipeline.fetch_minyag_current --output '新的单件快照目录' --delay 2`，导入时另加 `--current '新的单件快照目录'`；该单件标注 All Rights Reserved。筛查表保留 62 条编号与 34 条待审候选，77 个音频文件与条目的对应关系不明，不能当作故事计数。原站限制本地个人或内部非商业使用，单条详情、权利与社区要求须另核。所有候选均需人工复核，不自动填写坐标、叙事年代或国际标准码。

## 马来西亚 Temiar 目录筛查

马来西亚 Temiar 馆藏可使用本地目录和可选单件对照生成待审卡：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_temiar_wolp --output '.local/source-snapshots/新的Temiar目录' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_temiar_current --output '.local/source-snapshots/新的Temiar单件快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets temiar-wolp --snapshots '.local/source-snapshots/新的Temiar目录' --current '.local/source-snapshots/新的Temiar单件快照' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

获取器遵守 robots.txt、保存原目录及版权通知，不请求音频与附件；已存在的输出目录不会覆盖。50 项筛查表区别歌曲音轨、背景文书和照片；第 10、45 项共用旧档案链接。收藏者、作者、录音工程师及演述者角色须分开核实；历史评论不能自动代表社区观点。单件权利及社区要求须逐条确认，所有候选待人工复核，坐标、叙事年代和标准码留空。

## 云南普米语目录筛查

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_pumi_wolp --output '.local/source-snapshots/新的普米语目录' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.fetch_pumi_current --output '.local/source-snapshots/新的普米语单件快照' --delay 2
.\.venv\Scripts\python.exe -X utf8 -m pipeline.import_datasets pumi-wolp --snapshots '.local/source-snapshots/新的普米语目录' --current '.local/source-snapshots/新的普米语单件快照' --vault '其他资料库路径'
.\.venv\Scripts\python.exe -X utf8 -m pipeline.review_queue --vault '其他资料库路径' --output '复核页面数据目录'
```

45 条目录题名按歌曲、访谈、仪式、演说和故事标签列出，另建馆藏组卡；题名标签及音轨数量不代表已核实的故事数。原项目总述称 45 个音频文件，第 41 条现行目录的馆藏总述称 46 个，数量差异待核。只保存目录及版权通知，不请求音频或附件；单件许可和社区要求另核，采录者不自动等于演述者。坐标、叙事年代和标准码留空，须人工复核后才能进入正式图谱。

## 导出研究视图

使用 `--exclude-fiction` 导出移除 F 级节点及其边的快照。`--output` 可以指定导出文件，`--vault` 可以指定另一份知识库。

```powershell
.\.venv\Scripts\python.exe -m pipeline.build_graph --include-samples --exclude-fiction --output .local/research_preview.json
```

对同一份知识库使用相同筛选参数时，JSON 与 SQLite 中的 `snapshot_id` 一致。校验失败会报告涉及的卡片和字段。每份导出都在完整写入后替换目标文件，可以随时用 `vault/` 重建。

```powershell
.\.venv\Scripts\python.exe -m pipeline.export_schema --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

