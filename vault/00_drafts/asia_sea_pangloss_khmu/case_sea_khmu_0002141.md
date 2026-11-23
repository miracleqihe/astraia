---
id: case_sea_khmu_0002141
title: Khmu 录音目录 · Chants des Khamous Yuan 2
aliases:
- Chants des Khamous Yuan 2
- Khmu Yuan songs 2
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
- type: COMPARED_WITH
  target: case_sea_khmu_0002140
  weight: 1.0
  note: 目录题名显示 1 和 2，日期相同但讲述者未知；是否连续及具体角色须回查。
  status: null
sources:
- citation: CNRS-LACITO，Pangloss Khmu 馆藏目录，保留目录网页快照。
  type: pangloss_khmu_catalogue
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: Khmu / DOI 0002141
  local_path: .local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html
  content_sha256: 392ee320fd8fce58fd67d4fa65eb085d2d90a0b23b0bf26c63feb2e2188065ee
- citation: CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。
  type: pangloss_khmu_detail
  url: https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-90346b9c-bc13-34ae-b8e7-96c104c05388&corpus=Khmu
  doi: 10.24397/pangloss-0002141
  locator: 录音 0002141
  local_path: .local/import-sources/pangloss-khmu-detail-2026-11-22-v1/records/0002141/page.html
  content_sha256: b8cd154d0121a9bed7953b28b95d228ad6a488f2020dc282286b5bcc793a13fd
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
  locator: Khmu Yuan 歌唱：两段候选
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
  "馆方目录题名": "Chants des Khamous Yuan 2",
  "馆方目录研究者": "Ferlus, Michel — Raw, Kam",
  "馆方目录讲述者": "unknown",
  "馆方目录录音日期": "1976-11",
  "馆方时长": "00:30:54",
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
        "title": "Khmu Yuan songs 2"
      }
    ],
    "researchers": "Ferlus, Michel; Raw, Kam",
    "speakers": "unknown",
    "recorded": "11/1976",
    "recording_location": "Northern Laos",
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
  "id": "yuan_song_parts",
  "label": "Khmu Yuan 歌唱：两段候选",
  "note": "目录题名显示 1 和 2，日期相同但讲述者未知；是否连续及具体角色须回查。",
  "members": [
    {
      "id": "0002140",
      "title": "Chants des Khamous Yuan 1",
      "speakers": "unknown",
      "recorded": "1976-11",
      "doi": "https://doi.org/10.24397/pangloss-0002140",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-4e18927b-2247-35d4-bc2d-d64c21d28647&corpus=Khmu",
      "node_id": "case_sea_khmu_0002140"
    },
    {
      "id": "0002141",
      "title": "Chants des Khamous Yuan 2",
      "speakers": "unknown",
      "recorded": "1976-11",
      "doi": "https://doi.org/10.24397/pangloss-0002141",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-90346b9c-bc13-34ae-b8e7-96c104c05388&corpus=Khmu",
      "node_id": "case_sea_khmu_0002141"
    }
  ]
}
```

## 原音、转写与复核

本卡只索引一条馆藏录音，不自动判定为一篇故事；一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；具体许可和相关社区要求须逐项核查。
