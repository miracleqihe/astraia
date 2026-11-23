---
id: case_sea_khmu_0002079
title: Khmu 录音目录 · Histoire khamoue du clan du tigre 2
aliases:
- Histoire khamoue du clan du tigre 2
- Khmu tiger clan story 2
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
  target: case_sea_khmu_0001998
  weight: 1.0
  note: 目录题名均涉及虎氏族，录音日期、角色和具体叙事须分别核对；不证明同源或传播。
  status: null
sources:
- citation: CNRS-LACITO，Pangloss Khmu 馆藏目录，保留目录网页快照。
  type: pangloss_khmu_catalogue
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: Khmu / DOI 0002079
  local_path: .local/import-sources/asia-sea-pangloss-khmu-2026-11-22.html
  content_sha256: 392ee320fd8fce58fd67d4fa65eb085d2d90a0b23b0bf26c63feb2e2188065ee
- citation: CNRS-LACITO，Pangloss 单条录音元数据；具体许可见原字段。
  type: pangloss_khmu_detail
  url: https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-8424e522-9972-3715-add5-03e0a61697bc&corpus=Khmu
  doi: 10.24397/pangloss-0002079
  locator: 录音 0002079
  local_path: .local/import-sources/pangloss-khmu-detail-2026-11-22-v1/records/0002079/page.html
  content_sha256: 6064ec6eb5bcbfc435e391cf9e69ec6aef9f407ed13bd433d8fe996ee976d951
- citation: Astraia 首轮详情选取索引；分组只表示选取方法。
  type: pangloss_khmu_selection
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 目录题名含虎氏族的录音
  local_path: reference/khmu_first_detail_selection.json
  content_sha256: 0bab5d7331a8fc6d9dd1a6e79cb996238a984e8941cb98ba5596f409ad6c0592
- citation: Astraia 目录字段对照索引；关系仅供人工核查。
  type: pangloss_khmu_comparison
  url: https://pangloss.cnrs.fr/corpus/Khmu
  doi: null
  locator: 虎氏族题名：跨录音对照候选
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
  "馆方目录题名": "Histoire khamoue du clan du tigre 2",
  "馆方目录研究者": "Ferlus, Michel",
  "馆方目录讲述者": "Ma' Mouan",
  "馆方目录录音日期": "1970-06-06",
  "馆方时长": "00:05:19",
  "馆方媒介图标": [
    "audio"
  ],
  "馆方转写图标": false,
  "详情采集状态": "已保存并核验详情元数据",
  "详情选取依据": "目录题名含虎氏族的录音",
  "馆方详情字段": {
    "alternate_titles": [
      {
        "language_as_displayed": "(en)",
        "title": "Khmu tiger clan story 2"
      }
    ],
    "researchers": "Ferlus, Michel",
    "speakers": "Ma' Mouan",
    "recorded": "06/06/1970",
    "recording_location": "Houay Ong, refugee at Paskane",
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
  "id": "tiger_clan_title",
  "label": "虎氏族题名：跨录音对照候选",
  "note": "目录题名均涉及虎氏族，录音日期、角色和具体叙事须分别核对；不证明同源或传播。",
  "members": [
    {
      "id": "0001998",
      "title": "Histoire du Clan du Tigre",
      "speakers": "Sèn Boun",
      "recorded": "1965-06-01",
      "doi": "https://doi.org/10.24397/pangloss-0001998",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-3e746621-439c-3cc0-98e3-eaabf97f1aa7&corpus=Khmu",
      "node_id": "case_sea_khmu_0001998"
    },
    {
      "id": "0002045",
      "title": "Légende du Clan du Tigre",
      "speakers": "Nay Thong Di (from Xieng Khouang)",
      "recorded": "1968-11",
      "doi": "https://doi.org/10.24397/pangloss-0002045",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-0ea3e232-88a3-3407-b9f6-c6adb69daf62&corpus=Khmu",
      "node_id": "case_sea_khmu_0002045"
    },
    {
      "id": "0002078",
      "title": "Histoire khamoue du clan du tigre",
      "speakers": "Ma' Mouan",
      "recorded": "1970-06-06",
      "doi": "https://doi.org/10.24397/pangloss-0002078",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-3226cdb9-afaa-3b6d-89fe-7c48c060e126&corpus=Khmu",
      "node_id": "case_sea_khmu_0002078"
    },
    {
      "id": "0002079",
      "title": "Histoire khamoue du clan du tigre 2",
      "speakers": "Ma' Mouan",
      "recorded": "1970-06-06",
      "doi": "https://doi.org/10.24397/pangloss-0002079",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-8424e522-9972-3715-add5-03e0a61697bc&corpus=Khmu",
      "node_id": "case_sea_khmu_0002079"
    },
    {
      "id": "0002133",
      "title": "Histoire khamoue du clan du tigre 3",
      "speakers": "Ta' Seu",
      "recorded": "start=1971-08-14; end=1971-08-15",
      "doi": "https://doi.org/10.24397/pangloss-0002133",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-f4cb2e8f-09b7-3b40-b9ee-d58e4bb12d4e&corpus=Khmu",
      "node_id": "case_sea_khmu_0002133"
    },
    {
      "id": "0002156",
      "title": "Histoire khamoue du clan du tigre 4",
      "speakers": "Boua Phan Heuang Praseuth",
      "recorded": "1978-09-02",
      "doi": "https://doi.org/10.24397/pangloss-0002156",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-c6226418-8848-38ae-b5a5-ee080d1a7687&corpus=Khmu",
      "node_id": "case_sea_khmu_0002156"
    },
    {
      "id": "0002157",
      "title": "Histoire khamoue du clan du tigre 5",
      "speakers": "Boua Phan Heuang Praseuth",
      "recorded": "1978-09-02",
      "doi": "https://doi.org/10.24397/pangloss-0002157",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-d86a70a3-3279-30ce-89c6-6f515e1798c8&corpus=Khmu",
      "node_id": "case_sea_khmu_0002157"
    },
    {
      "id": "0002158",
      "title": "Histoire khamoue du clan du tigre 6",
      "speakers": "Boua Phan Heuang Praseuth",
      "recorded": "1978-09-02",
      "doi": "https://doi.org/10.24397/pangloss-0002158",
      "url": "https://pangloss.cnrs.fr/corpus/show?oai_primary=cocoon-3ddc8233-3097-3672-9885-3c3f3bfd56bf&corpus=Khmu",
      "node_id": "case_sea_khmu_0002158"
    }
  ]
}
```

## 原音、转写与复核

本卡只索引一条馆藏录音，不自动判定为一篇故事；一条录音可能包含多个故事、片段、歌唱、祈祷或访谈。相似题名与分段提示须回听，不证明同一演述、母题、传播或历史事件。讲述者籍贯与具体录音地点不是同一字段；录音日期不是叙事年代，馆藏名称不保证每段都只用 Khmu 语。音视频与转写正文未复制；具体许可和相关社区要求须逐项核查。
