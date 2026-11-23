---
id: FOR-TOPIC-0002
title: 证据：从反应、来源到事件经过
topic: 痕迹与物证
subject: FOR
volume: 造物卷
page: 522
links: []
source: 格物识微_全书增绘_20261121.pdf
---

```{=typst}
#block(breakable: false, width: 100%)[
#grid(columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr), column-gutter: 2mm, align: horizon,
block(width: 100%, inset: 5pt, radius: 2pt, fill: rgb("#e9f2f0"))[#align(center)[#text("观察和初筛")#linebreak()#text("发现线索")]],
[→],
block(width: 100%, inset: 5pt, radius: 2pt, fill: rgb("#e9f2f0"))[#align(center)[#text("进一步检验")#linebreak()#text("确认是什么")]],
[→],
block(width: 100%, inset: 5pt, radius: 2pt, fill: rgb("#e9f2f0"))[#align(center)[#text("来源判断")#linebreak()#text("来自谁或何处")]],
[→],
block(width: 100%, inset: 5pt, radius: 2pt, fill: rgb("#e9f2f0"))[#align(center)[#text("活动与经过")#linebreak()#text("结合其他信息解释")]])
]
```

图：证据问题的层级示意。图中不是所有案件统一的操作流程；后一层不能由前一层自动推出。

#### 血液初筛阳性，能证明是人血吗？

初筛反应提示“值得进一步检查”，并不自动确认是血，更不能直接确定是人血或某个人的血。一些常用筛查会受其他物质干扰；如果两种初筛对相似干扰都敏感，也不能简单看成两次完全独立的证明。专业实验室需要根据检材选择适当的后续检验；即便确认有血，来源、形成时间与活动过程仍是不同问题。单次阴性也受检材及检验条件影响，不能自动证明事件没发生。[美国司法部 NIJ：血液筛查](https://nij.ojp.gov/nij-hosted-online-training-courses/laboratory-orientation-and-testing-body-fluids-and-tissues/testing-body-fluids-tissues/blood/screening-tests)；[论坛提问](https://www.reddit.com/r/forensics/comments/1bkcz47/luminol_and_phenolphthalein/)。

#### 一张血迹照片，能数出击打次数吗？

液滴的形成与运动、接触表面的材料和角度、吸收与后续扰动都会影响最终图样。相似图样可能有不同成因，同一类事件也可能留下不同图样。应先描述照片实际显示什么，再分析哪些机制与之相容，并与伤情、现场记录等信息对照；不能把“看起来像某种图样”直接等同于已确定的击打次数、凶器、先后顺序或身份。NIJ 资助的研究也发现，分析人员对部分图样的解释存在分歧；研究中的具体比例不能直接当成某个案件的错误概率。[NIJ 研究报告](https://www.ojp.gov/pdffiles1/nij/grants/304645.pdf)；[论坛提问](https://www.reddit.com/r/forensics/comments/1h7bnck/what_kind_of_spatter_is_this_not_real_crime_scene/)。

#### 有接触 DNA，就证明本人到场吗？

DNA 的来源与它怎样到达物体，是两个不同层次的问题。直接接触是一种可能，间接转移也是一种可能：例如甲的遗留物经乙的手转到门把。现场原有背景、采样污染、时间经过及样本混合都会影响解释；提出二次转移的可能，也不等于证明本案已经发生二次转移。检验中的统计比较须看具体假设，不能直接翻译成“此人实施行为或有罪的概率”。[NIST：DNA 混合物](https://www.nist.gov/feature-stories/dna-mixtures-forensic-science-explainer)；[论坛提问](https://www.reddit.com/r/forensics/comments/16z0ojv/is_touch_dna_real_or_reliable/)。

#### 模糊监控能无限放大增强吗？

目标在画面里只有少量像素时，普通放大主要是放大已有的画面信息；曝光、运动模糊、压缩、角度及其他画面是否可用都会影响辨认。适当处理可能突出已有信息，但不能保证恢复未记录的细节。生成式工具给出的清晰字形可能是模型推测，不能直接视为摄像头实际拍到的字符。依法保留有权取得的原始导出文件、来源和时间信息，必要时由持证专业人员评估处理过程及其他独立画面。[NIST：法庭虹膜图像与缺失细节](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=931557)；[NIST／OSAC 数字视频检验工作流程](https://www.nist.gov/system/files/documents/2026/07/10/OSAC%202022-S-0031,%20Standard%20Guide%20for%20Forensic%20Digital%20Video%20Examination%20Workflow%20Version%202.0.pdf)；[论坛提问](https://www.reddit.com/r/forensics/comments/hekaim/cctvs_and_license_plates/)。

#### 发现有关手机，必须一直开机吗？

没有适合所有设备与情境的“永远开机”或“永远关机”规则：关机可能改变设备当前状态，影响能够获取的信息；持续运行也可能发生同步或其他变化。普通人先确保安全，不擅自解锁、重置、查阅或改变陌生设备状态；记录发现位置和可直接观察到的状态，尽快交有权限的人员按设备型号和程序判断。[SWGDE：移动设备证据保全](https://www.swgde.org/documents/published-complete-listing/18-f-003-swgde-best-practices-for-mobile-device-evidence-collection-and-preservation-handling-and-acquisition/)；[论坛提问](https://www.reddit.com/r/digitalforensics/comments/1pq4dmz/after_extraction/)。

#### 创建时间晚于修改时间，就证明文件伪造吗？

文件的创建时间、修改时间和访问时间是不同的记录字段；复制、文件系统、软件行为、设备时钟和时区都可能影响所显示的信息。某些复制方式可以产生“新位置的创建时间晚于内容修改时间”，这本身既不证明伪造，也不能排除伪造。例如同一时刻以 UTC 显示为 10:00、以 UTC+8 显示为 18:00，差异可能只是时区；但不能因此假定两台设备时钟都准确。文件哈希是由文件内容计算出的摘要，可与可信的原始记录比较，以检查内容是否一致；哈希相同本身不能证明谁在何时写成文件。应结合有权保存的原始材料、取得路径、系统信息和独立时间线。[Microsoft：文件时间](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times)；[NIST 数字调查技术](https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8354.pdf)；[论坛提问](https://www.reddit.com/r/DataHoarder/comments/1i0uytc/how_do_i_preserve_created_and_modified_times/)。
