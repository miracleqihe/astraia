---
id: case_sea_khmu_0002068
title: Khmu 录音目录 · Histoire khamoue du clan de la cage à poulets
aliases:
- Histoire khamoue du clan de la cage à poulets
- Khmu chicken coop clan story
node_type: case
z_layer: 1
genre: unclassified
credibility_tier: B
is_fictional_quarantine: false
spatial:
  lat: null
  lng: null
  precision: culture_region
  location_name: Khmu 语馆藏（单条录音地点待核）
  culture_region: Khmu 语录音馆藏
temporal: null
standards:
  atu_types: []
  thompson_motifs: []
  berezkin_codes: []
  ocm_codes: []
  macro_phylogeny: null
mechanisms: []
relations:
- type: PART_OF_MACRO_TREND
  target: corpus_sea_khmu_pangloss
  weight: 1.0
  note: 同一馆藏目录的录音资源；不表示同一故事、采录地点或传播关系。
  status: null
sources:
- citation: CNRS-LACITO，Pangloss Khmu 馆藏目录，保留目录网页快照。
  type: pangloss_khmu_catalogue
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: Khmu / DOI 0002068
  local_path: .local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html
  content_sha256: 392ee320fd8fce58fd67d4fa65eb085d2d90a0b23b0bf26c63feb2e2188065ee
- citation: CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。
  type: pangloss_khmu_detail
  url: https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-19fdfca2-7ff9-3d8f-a324-8dda58c3a138&corpus=Khmu
  doi: 10.24397/pangloss-0002068
  locator: 录音 0002068
  local_path: .local/import-sources/pangloss-khmu-detail-2026-11-22-v1/records/0002068/page.html
  content_sha256: ac0b2089f46e3e7a4f97179aeaa6f6aa038dff3d0d8a41f7635f4990530a591b
- citation: Astraia 首轮详情选取索引；分组只表示选取方法。
  type: pangloss_khmu_selection
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 目录显示分段或完整版本的候选
  local_path: reference/khmu_first_detail_selection.json
  content_sha256: 0bab5d7331a8fc6d9dd1a6e79cb996238a984e8941cb98ba5596f409ad6c0592
- citation: Astraia 目录字段对照索引；关系仅供人工核查。
  type: pangloss_khmu_comparison
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 鸡笼氏族题名：完整版本候选
  local_path: reference/khmu_recording_comparisons.json
  content_sha256: 84ebd4f33a287c9bfbe97e84ca08b007c69538772b1ba06de2f6b0b162bfe270
audit:
  created_at: '2026-11-22'
  reviewed_by_human: false
  ai_confidence: null
  is_sample: false
  reviewer: null
  reviewed_at: null
  review_note: null
---

## 馆方录音目录字段

```
{
  "馆方目录题名": "Histoire khamoue du clan de la cage à poulets",
  "馆方目录研究者": "Ferlus, Michel",
  "馆方目录讲述者": "Ta' Pom",
  "馆方目录录音日期": "1970-02-15",
  "馆方时长": "00:11:48",
  "馆方媒介图标": [
    "audio"
  ],
  "馆方转写图标": false,
  "详情采集状态": "已保存并核验详情元数据",
  "详情选取依据": "目录显示分段或完整版本的候选",
  "馆方详情字段": {
    "alternate_titles": [
      {
        "language_as_displayed": "(en)",
        "title": "Khmu chicken coop clan story"
      }
    ],
    "researchers": "Ferlus, Michel",
    "speakers": "Ta' Pom",
    "recorded": "15/02/1970",
    "recording_location": "Muong Ngoi",
    "deposit_affiliation": "Centre de recherches linguistiques sur l'Asie orientale",
    "license": "http://spdx.org/licenses/CC-BY-NC-SA-2.5"
  },
  "目录与详情研究者字段是否对应": true,
  "目录与详情讲述者字段是否对应": true,
  "目录与详情录音日期是否一致": true
}
```

## 目录对照候选（待复核）

```
{
  "id": "chicken_cage_versions",
  "label": "鸡笼氏族题名：完整版本候选",
  "note": "同一目录讲述者、日期和相近题名；其中一条标为完整版本，是否来自同次演述须回听。",
  "members": [
    {
      "id": "0002068",
      "title": "Histoire khamoue du clan de la cage à poulets",
      "speakers": "Ta' Pom",
      "recorded": "1970-02-15",
      "doi": "https://doi.org/10.24397/pangloss-0002068",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-19fdfca2-7ff9-3d8f-a324-8dda58c3a138&corpus=Khmu",
      "node_id": "case_sea_khmu_0002068"
    },
    {
      "id": "0002072",
      "title": "Histoire khamoue du clan de la cage à poulets (version complète)",
      "speakers": "Ta' Pom",
      "recorded": "1970-02-15",
      "doi": "https://doi.org/10.24397/pangloss-0002072",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-b1c80f5c-c9b8-37e6-b5ff-781ee6a8ab8d&corpus=Khmu",
      "node_id": "case_sea_khmu_0002072"
    }
  ]
}
```

## 原音、转写与复核

本卡只索引一条馆藏录音，不自动判定为一篇故事；一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；具体许可和相关社区要求须逐项核查。
