---
id: case_sea_khmu_0002001
title: Khmu 录音目录 · Histoire du Clan de la Civette
aliases:
- Histoire du Clan de la Civette
- History of the Chive Clan
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
  locator: Khmu / DOI 0002001
  local_path: .local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html
  content_sha256: 392ee320fd8fce58fd67d4fa65eb085d2d90a0b23b0bf26c63feb2e2188065ee
- citation: CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。
  type: pangloss_khmu_detail
  url: https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-1fe3527f-8a08-3a60-97d3-44f5e0dd12dd&corpus=Khmu
  doi: 10.24397/pangloss-0002001
  locator: 录音 0002001
  local_path: .local/import-sources/pangloss-khmu-detail-2026-11-22-v1/records/0002001/page.html
  content_sha256: ee26ccb7084a8add9f370d77c41f5727f587f1c0992042a564062b2f500fd44a
- citation: Astraia 首轮详情选取索引；分组只表示选取方法。
  type: pangloss_khmu_selection
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 目录题名含麝猫氏族的录音
  local_path: reference/khmu_first_detail_selection.json
  content_sha256: 0bab5d7331a8fc6d9dd1a6e79cb996238a984e8941cb98ba5596f409ad6c0592
- citation: Astraia 目录字段对照索引；关系仅供人工核查。
  type: pangloss_khmu_comparison
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 麝猫氏族题名：跨录音对照候选
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
  "馆方目录题名": "Histoire du Clan de la Civette",
  "馆方目录研究者": "Ferlus, Michel",
  "馆方目录讲述者": "Aay Phuy",
  "馆方目录录音日期": "1965-06-01",
  "馆方时长": "00:09:15",
  "馆方媒介图标": [
    "audio"
  ],
  "馆方转写图标": true,
  "详情采集状态": "已保存并核验详情元数据",
  "详情选取依据": "目录题名含麝猫氏族的录音",
  "馆方详情字段": {
    "alternate_titles": [
      {
        "language_as_displayed": "(en)",
        "title": "History of the Chive Clan"
      }
    ],
    "researchers": "Ferlus, Michel",
    "speakers": "Aay Phuy",
    "recorded": "01/06/1965",
    "recording_location": "Ban Hia, Luang Phrabang",
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
  "id": "civet_clan_title",
  "label": "麝猫氏族题名：跨录音对照候选",
  "note": "目录题名均涉及麝猫氏族；一条还涉及鸟氏族，录音边界和版本须分别核对。",
  "members": [
    {
      "id": "0002001",
      "title": "Histoire du Clan de la Civette",
      "speakers": "Aay Phuy",
      "recorded": "1965-06-01",
      "doi": "https://doi.org/10.24397/pangloss-0002001",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-1fe3527f-8a08-3a60-97d3-44f5e0dd12dd&corpus=Khmu",
      "node_id": "case_sea_khmu_0002001"
    },
    {
      "id": "0002036",
      "title": "Légende du Clan de la Civette",
      "speakers": "Pho Bun Can",
      "recorded": "1968-11-05",
      "doi": "https://doi.org/10.24397/pangloss-0002036",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-21a59cab-dac6-3990-ab34-63e3349c6c0b&corpus=Khmu",
      "node_id": "case_sea_khmu_0002036"
    },
    {
      "id": "0002046",
      "title": "Légende du Clan de la Civette",
      "speakers": "Sao May (from Xieng Khouang)",
      "recorded": "1968-11",
      "doi": "https://doi.org/10.24397/pangloss-0002046",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-23dacfa8-cf82-389e-84e0-5f7ca9675aa1&corpus=Khmu",
      "node_id": "case_sea_khmu_0002046"
    },
    {
      "id": "0002075",
      "title": "Histoire khamoue du clan de la civette",
      "speakers": "Thao Mi",
      "recorded": "1970-06-06",
      "doi": "https://doi.org/10.24397/pangloss-0002075",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-81ec32ca-8122-3934-9340-4be91b95f27c&corpus=Khmu",
      "node_id": "case_sea_khmu_0002075"
    },
    {
      "id": "0002116",
      "title": "Histoires khamoues des clan de la civette et de l'oiseau",
      "speakers": "Ta' Séén",
      "recorded": "1970-07-28",
      "doi": "https://doi.org/10.24397/pangloss-0002116",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-003fd903-e089-37c7-bf5a-5772e4e63126&corpus=Khmu",
      "node_id": "case_sea_khmu_0002116"
    },
    {
      "id": "0002159",
      "title": "Histoire khamoue du clan de la civette 2",
      "speakers": "Boua Phan Heuang Praseuth",
      "recorded": "1978-09-02",
      "doi": "https://doi.org/10.24397/pangloss-0002159",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-12165135-4c9b-3d1b-8507-7bb69a38732a&corpus=Khmu",
      "node_id": "case_sea_khmu_0002159"
    }
  ]
}
```

## 原音、转写与复核

本卡只索引一条馆藏录音，不自动判定为一篇故事；一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；具体许可和相关社区要求须逐项核查。
